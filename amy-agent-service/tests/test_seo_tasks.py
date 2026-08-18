"""SEO Tasks endpoints: check, list, detail, approve, reject, generate."""

from __future__ import annotations

import json
import os
from typing import Sequence
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import seo_tasks_db  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.base import BaseProvider  # noqa: E402
from app.providers.errors import ProviderError  # noqa: E402
from app.providers.gemini import GeminiImageResult  # noqa: E402
from app.schemas.messages import ChatMessage  # noqa: E402
from app.services.seo_generate import fields_from_findings, parse_response  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}

GREEN_SNAPSHOT = {
    "wp_post_id": 42,
    "post_type": "post",
    "title": "Brand strategy for agencies",
    "content_excerpt": "A practical guide.",
    "focus_keyphrase": "brand strategy",
    "seo_title": "Brand strategy for growing agencies",
    "meta_description": "A practical brand strategy guide for growing agencies.",
    "has_featured_image": True,
    "featured_image_alt": "Team reviewing a brand strategy board",
    "og_title": "Brand strategy",
    "og_description": "How agencies grow with brand strategy.",
    "og_image": "https://example.com/og.jpg",
    "twitter_title": "Brand strategy",
    "twitter_description": "How agencies grow with brand strategy.",
    "twitter_image": "https://example.com/tw.jpg",
    "category_count": 2,
}

RED_SNAPSHOT = {
    **GREEN_SNAPSHOT,
    "wp_post_id": 7,
    "focus_keyphrase": "",
    "seo_title": "",
    "meta_description": "",
}


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    db_path = tmp_path / "seo_tasks.db"
    monkeypatch.setattr(seo_tasks_db, "_DB_PATH", db_path)
    return TestClient(app)


def test_check_requires_secret(client: TestClient) -> None:
    response = client.post("/v1/seo-tasks/check", json=GREEN_SNAPSHOT)
    assert response.status_code == 401


def test_check_stores_pending_and_returns_green(client: TestClient) -> None:
    response = client.post("/v1/seo-tasks/check", headers=AUTH, json=GREEN_SNAPSHOT)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["verdict"] == "green"
    assert data["findings"] == []
    assert data["status"] == "pending_approval"
    assert data["wp_post_id"] == 42
    assert data["check_id"]


def test_check_red_core_missing(client: TestClient) -> None:
    response = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["verdict"] == "red"
    fields = {item["field"] for item in data["findings"]}
    assert "focus_keyphrase" in fields
    assert "seo_title" in fields
    assert "meta_description" in fields


def test_list_and_filter(client: TestClient) -> None:
    client.post("/v1/seo-tasks/check", headers=AUTH, json=GREEN_SNAPSHOT)
    client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT)

    all_checks = client.get("/v1/seo-tasks/checks", headers=AUTH)
    assert all_checks.status_code == 200
    assert len(all_checks.json()["checks"]) == 2

    red = client.get("/v1/seo-tasks/checks", headers=AUTH, params={"verdict": "red"})
    assert {item["wp_post_id"] for item in red.json()["checks"]} == {7}

    pending = client.get(
        "/v1/seo-tasks/checks", headers=AUTH, params={"status": "pending_approval"}
    )
    assert len(pending.json()["checks"]) == 2


def test_list_rejects_invalid_filter(client: TestClient) -> None:
    response = client.get(
        "/v1/seo-tasks/checks", headers=AUTH, params={"status": "done"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_filter"


def test_get_check_detail(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=GREEN_SNAPSHOT).json()
    response = client.get(f"/v1/seo-tasks/checks/{created['check_id']}", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["check_id"] == created["check_id"]


def test_get_unknown_check_404(client: TestClient) -> None:
    response = client.get("/v1/seo-tasks/checks/not-a-real-id", headers=AUTH)
    assert response.status_code == 404


def test_approve_stores_fields(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    approved = {"focus_keyphrase": "brand strategy", "seo_title": "Brand strategy"}
    response = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/approve",
        headers=AUTH,
        json={"approved_fields": approved},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_fields"] == approved


def test_approve_twice_conflicts(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=GREEN_SNAPSHOT).json()
    first = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/approve",
        headers=AUTH,
        json={"approved_fields": {}},
    )
    assert first.status_code == 200
    second = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/approve",
        headers=AUTH,
        json={"approved_fields": {}},
    )
    assert second.status_code == 409


def test_reject_with_reason(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    response = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/reject",
        headers=AUTH,
        json={"reason": "Will fix in the editor instead."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["reject_reason"] == "Will fix in the editor instead."


def test_category_check_uses_term_rules(client: TestClient) -> None:
    payload = {
        "wp_post_id": 11,
        "post_type": "category",
        "content_type": "category",
        "title": "Brand strategy",
        "seo_title": "Brand strategy category",
        "meta_description": "Articles about brand strategy.",
        "term_description": "Everything we publish on brand strategy.",
    }
    response = client.post("/v1/seo-tasks/check", headers=AUTH, json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["content_type"] == "category"
    assert data["verdict"] == "green"
    assert data["findings"] == []


def test_media_check_and_content_type_filter(client: TestClient) -> None:
    payload = {
        "wp_post_id": 88,
        "post_type": "attachment",
        "content_type": "media",
            "title": "Studio hero",
        "alt_text": "Studio hero image",
        "caption": "Front of house",
        "description": "Homepage banner.",
        "filename": "hero.jpg",
    }
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["content_type"] == "media"
    assert created.json()["verdict"] == "green"

    filtered = client.get(
        "/v1/seo-tasks/checks", headers=AUTH, params={"content_type": "media"}
    )
    assert filtered.status_code == 200
    ids = {item["check_id"] for item in filtered.json()["checks"]}
    assert created.json()["check_id"] in ids

    posts = client.get(
        "/v1/seo-tasks/checks", headers=AUTH, params={"content_type": "post"}
    )
    assert created.json()["check_id"] not in {
        item["check_id"] for item in posts.json()["checks"]
    }


class _FakeProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self, reply: str = "{}") -> None:
        self._reply = reply

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        assert api_key
        assert messages
        return self._reply


class _FailingProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        raise ProviderError("auth failed", code="auth_error")


def _ai_body(**overrides):
    body = {"provider": "openai", "api_key": "sk-test", "model": None}
    body.update(overrides)
    return {"ai": body}


def test_generate_fields_success(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    reply = json.dumps(
        {
            "seo_title": "Brand strategy for agencies",
            "meta_description": "A practical brand strategy guide for growing agencies.",
            "focus_keyphrase": "brand strategy",
        }
    )
    with patch("app.routes.seo_tasks.get_provider", return_value=_FakeProvider(reply)):
        response = client.post(
            f"/v1/seo-tasks/checks/{created['check_id']}/generate",
            headers=AUTH,
            json=_ai_body(),
        )
    assert response.status_code == 200, response.text
    data = response.json()
    generated = data["generated_fields"]
    assert "seo_title" in generated
    assert "meta_description" in generated
    assert len(generated["seo_title"]) <= 60
    assert len(generated["meta_description"]) <= 155
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o-mini"


def test_generate_fields_non_json_is_502(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    with patch(
        "app.routes.seo_tasks.get_provider",
        return_value=_FakeProvider("Sorry, I cannot do that."),
    ):
        response = client.post(
            f"/v1/seo-tasks/checks/{created['check_id']}/generate",
            headers=AUTH,
            json=_ai_body(),
        )
    assert response.status_code == 502
    assert response.json()["error"] == "generation_parse_error"


def test_generate_fields_provider_error_is_502(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    with patch("app.routes.seo_tasks.get_provider", return_value=_FailingProvider()):
        response = client.post(
            f"/v1/seo-tasks/checks/{created['check_id']}/generate",
            headers=AUTH,
            json=_ai_body(),
        )
    assert response.status_code == 502
    assert response.json()["error"] == "auth_error"


def test_generate_fields_unknown_check_404(client: TestClient) -> None:
    response = client.post(
        "/v1/seo-tasks/checks/not-a-real-id/generate",
        headers=AUTH,
        json=_ai_body(),
    )
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_generate_fields_green_check_nothing_to_generate(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=GREEN_SNAPSHOT).json()
    response = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/generate",
        headers=AUTH,
        json=_ai_body(),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "nothing_to_generate"


def test_generate_image_rejects_non_gemini(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()
    response = client.post(
        f"/v1/seo-tasks/checks/{created['check_id']}/generate-image",
        headers=AUTH,
        json=_ai_body(provider="openai"),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_provider"


def test_generate_image_gemini_mocked(client: TestClient) -> None:
    created = client.post("/v1/seo-tasks/check", headers=AUTH, json=RED_SNAPSHOT).json()

    async def _fake_generate_image(self, prompt: str, api_key: str) -> GeminiImageResult:
        assert api_key
        assert "OGC NewFinity" in prompt
        return GeminiImageResult(data_base64="dGVzdA==", mime_type="image/png")

    async def _fake_complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        return "Studio photo of a brand strategy workshop"

    with (
        patch(
            "app.routes.seo_tasks.GeminiProvider.generate_image",
            _fake_generate_image,
        ),
        patch("app.routes.seo_tasks.GeminiProvider.complete", _fake_complete),
    ):
        response = client.post(
            f"/v1/seo-tasks/checks/{created['check_id']}/generate-image",
            headers=AUTH,
            json=_ai_body(provider="gemini"),
        )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["image_base64"] == "dGVzdA=="
    assert data["mime_type"] == "image/png"
    assert data["suggested_alt_text"]


def test_parse_response_valid_json() -> None:
    parsed = parse_response(
        '{"seo_title": "Brand strategy", "meta_description": "A guide."}',
        ["seo_title", "meta_description"],
    )
    assert parsed == {
        "seo_title": "Brand strategy",
        "meta_description": "A guide.",
    }


def test_parse_response_fenced_json() -> None:
    raw = "```json\n{\"seo_title\": \"Brand strategy\"}\n```"
    parsed = parse_response(raw, ["seo_title"])
    assert parsed["seo_title"] == "Brand strategy"


def test_parse_response_ignores_extra_keys() -> None:
    parsed = parse_response(
        '{"seo_title": "Brand strategy", "extra": "nope"}',
        ["seo_title"],
    )
    assert parsed == {"seo_title": "Brand strategy"}
    assert "extra" not in parsed


def test_parse_response_clamps_at_word_boundary() -> None:
    long_title = "Brand " * 20  # well over 60 chars
    parsed = parse_response(json.dumps({"seo_title": long_title}), ["seo_title"])
    assert "seo_title" in parsed
    assert len(parsed["seo_title"]) <= 60
    assert not parsed["seo_title"].endswith(" ")


def test_parse_response_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_response("not json at all", ["seo_title"])


def test_fields_from_findings_expands_og_social() -> None:
    fields = fields_from_findings(
        [{"field": "og_social", "severity": "missing", "message": "missing"}]
    )
    assert fields == ["og_title", "og_description"]


def test_fields_from_findings_skips_image_and_categories() -> None:
    fields = fields_from_findings(
        [
            {"field": "featured_image", "severity": "missing", "message": "no image"},
            {"field": "categories", "severity": "missing", "message": "no cats"},
        ]
    )
    assert fields == []


def test_fields_from_findings_empty() -> None:
    assert fields_from_findings([]) == []
