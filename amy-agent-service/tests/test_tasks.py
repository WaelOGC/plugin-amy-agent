"""Task Service CRUD — amy_capable + assignee modes."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import notifications_db, progress_notes_db, tasks_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks_db, "_DB_PATH", db_path)
    monkeypatch.setattr(notifications_db, "_DB_PATH", db_path)
    monkeypatch.setattr(progress_notes_db, "_DB_PATH", db_path)
    monkeypatch.setenv("WORDPRESS_BASE_URL", "")
    get_settings.cache_clear()
    return TestClient(app)


def test_create_task_defaults_amy_capable_false(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Human task",
            "assignee_type": "human",
            "assignee_wp_user_id": 7,
            "created_by_wp_user_id": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assignee_type"] == "human"
    assert data["assignee_wp_user_id"] == 7
    assert data["amy_capable"] is False


def test_create_amy_assignee_and_amy_capable(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Amy task",
            "assignee_type": "amy",
            "created_by_wp_user_id": 1,
            "amy_capable": True,
            "status": "todo",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assignee_type"] == "amy"
    assert data["assignee_wp_user_id"] is None
    assert data["amy_capable"] is True
    assert data["status"] == "todo"

    listed = client.get("/v1/tasks", headers=AUTH)
    assert listed.status_code == 200
    tasks = listed.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["amy_capable"] is True

    got = client.get(f"/v1/tasks/{data['id']}", headers=AUTH)
    assert got.status_code == 200
    assert got.json()["amy_capable"] is True


def test_patch_amy_capable(client: TestClient) -> None:
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Toggle capable",
            "assignee_type": "human",
            "assignee_wp_user_id": 3,
            "created_by_wp_user_id": 1,
            "amy_capable": False,
        },
    ).json()

    updated = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=AUTH,
        json={"amy_capable": True},
    )
    assert updated.status_code == 200
    assert updated.json()["amy_capable"] is True

    cleared = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=AUTH,
        json={"amy_capable": False, "assignee_type": "amy"},
    )
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["amy_capable"] is False
    assert body["assignee_type"] == "amy"
    assert body["assignee_wp_user_id"] is None
