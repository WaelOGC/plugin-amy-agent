"""SEO Tasks batch engine: manual/auto continuation and per-item isolation."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import seo_batches_db, seo_tasks_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}

GREEN_SNAPSHOT = {
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


def _item(item_id: int, snapshot=None, title=None) -> dict:
    return {
        "item_id": item_id,
        "title": title if title is not None else f"Post {item_id}",
        "snapshot": GREEN_SNAPSHOT if snapshot is None else snapshot,
    }


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    db_path = tmp_path / "seo_tasks.db"
    monkeypatch.setattr(seo_tasks_db, "_DB_PATH", db_path)
    monkeypatch.setattr(seo_batches_db, "_DB_PATH", db_path)
    return TestClient(app)


def test_batch_requires_secret(client: TestClient) -> None:
    response = client.post(
        "/v1/seo-tasks/batches",
        json={
            "content_type": "post",
            "mode": "manual",
            "items": [_item(1)],
        },
    )
    assert response.status_code == 401


def test_manual_processes_only_first_batch(client: TestClient) -> None:
    items = [_item(i) for i in range(1, 6)]
    response = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "manual",
            "batch_size": 2,
            "items": items,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "in_progress"
    assert data["processed_count"] == 2
    assert data["total_items"] == 5
    assert len(data["reports"]) == 1
    assert len(data["reports"][0]["results"]) == 2
    assert data["reports"][0]["batch_index"] == 0


def test_manual_continue_reaches_completed(client: TestClient) -> None:
    items = [_item(i) for i in range(1, 6)]
    started = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "manual",
            "batch_size": 2,
            "items": items,
        },
    ).json()
    run_id = started["batch_run_id"]

    second = client.post(f"/v1/seo-tasks/batches/{run_id}/continue", headers=AUTH)
    assert second.status_code == 200
    assert second.json()["status"] == "in_progress"
    assert second.json()["processed_count"] == 4
    assert len(second.json()["reports"]) == 2

    third = client.post(f"/v1/seo-tasks/batches/{run_id}/continue", headers=AUTH)
    assert third.status_code == 200
    done = third.json()
    assert done["status"] == "completed"
    assert done["processed_count"] == 5
    assert len(done["reports"]) == 3
    assert len(done["reports"][2]["results"]) == 1


def test_auto_returns_every_batch_in_one_call(client: TestClient) -> None:
    items = [_item(i) for i in range(1, 7)]
    response = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "auto",
            "batch_size": 2,
            "items": items,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "completed"
    assert data["processed_count"] == 6
    assert len(data["reports"]) == 3
    assert [len(r["results"]) for r in data["reports"]] == [2, 2, 2]


def test_stop_blocks_further_continue(client: TestClient) -> None:
    items = [_item(i) for i in range(1, 6)]
    started = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "manual",
            "batch_size": 2,
            "items": items,
        },
    ).json()
    run_id = started["batch_run_id"]

    stopped = client.post(f"/v1/seo-tasks/batches/{run_id}/stop", headers=AUTH)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    again = client.post(f"/v1/seo-tasks/batches/{run_id}/continue", headers=AUTH)
    assert again.status_code == 409

    stop_again = client.post(f"/v1/seo-tasks/batches/{run_id}/stop", headers=AUTH)
    assert stop_again.status_code == 409


def test_malformed_item_does_not_abort_batch(client: TestClient) -> None:
    items = [
        _item(1),
        {"item_id": 2, "title": "Broken", "snapshot": "not-an-object"},
        _item(3),
    ]
    response = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "auto",
            "batch_size": 5,
            "items": items,
        },
    )
    assert response.status_code == 200, response.text
    results = response.json()["reports"][0]["results"]
    assert results[0]["error"] is None
    assert results[0]["check_id"]
    assert results[1]["error"]
    assert results[1]["check_id"] is None
    assert results[1]["verdict"] is None
    assert results[2]["error"] is None
    assert results[2]["check_id"]
    assert response.json()["status"] == "completed"


def test_batch_size_is_clamped(client: TestClient) -> None:
    huge = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "auto",
            "batch_size": 100,
            "items": [_item(1), _item(2)],
        },
    )
    assert huge.status_code == 200
    assert huge.json()["batch_size"] == 20

    tiny = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "auto",
            "batch_size": 0,
            "items": [_item(3)],
        },
    )
    assert tiny.status_code == 200
    assert tiny.json()["batch_size"] == 1


def test_successful_item_creates_pending_check(client: TestClient) -> None:
    response = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "page",
            "mode": "auto",
            "batch_size": 5,
            "items": [_item(99, title="About")],
        },
    )
    assert response.status_code == 200, response.text
    check_id = response.json()["reports"][0]["results"][0]["check_id"]
    assert check_id
    stored = seo_tasks_db.get_check(check_id)
    assert stored is not None
    assert stored["status"] == "pending_approval"
    assert stored["content_type"] == "page"
    assert stored["batch_run_id"] == response.json()["batch_run_id"]
    assert stored["wp_post_id"] == 99


def test_empty_items_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={"content_type": "post", "mode": "manual", "items": []},
    )
    assert response.status_code == 422


def test_auto_continue_conflicts(client: TestClient) -> None:
    started = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "post",
            "mode": "auto",
            "items": [_item(1), _item(2)],
            "batch_size": 1,
        },
    ).json()
    assert started["status"] == "completed"
    cont = client.post(
        f"/v1/seo-tasks/batches/{started['batch_run_id']}/continue",
        headers=AUTH,
    )
    assert cont.status_code == 409


def test_list_and_get_batch(client: TestClient) -> None:
    created = client.post(
        "/v1/seo-tasks/batches",
        headers=AUTH,
        json={
            "content_type": "media",
            "mode": "auto",
            "items": [
                {
                    "item_id": 8,
                    "title": "Hero",
                    "snapshot": {
                        "alt_text": "Hero image",
                        "title": "Studio hero",
                        "caption": "Front of house",
                        "description": "Used on the homepage.",
                        "filename": "hero.jpg",
                    },
                }
            ],
        },
    ).json()
    listed = client.get("/v1/seo-tasks/batches", headers=AUTH, params={"content_type": "media"})
    assert listed.status_code == 200
    ids = {row["batch_run_id"] for row in listed.json()["runs"]}
    assert created["batch_run_id"] in ids
    assert "reports" not in listed.json()["runs"][0]
    assert "items" not in listed.json()["runs"][0]

    detail = client.get(f"/v1/seo-tasks/batches/{created['batch_run_id']}", headers=AUTH)
    assert detail.status_code == 200
    assert len(detail.json()["reports"]) == 1
