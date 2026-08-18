"""SEO Tasks endpoints: check, list, detail, approve, reject."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import seo_tasks_db  # noqa: E402
from app.main import app  # noqa: E402

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
