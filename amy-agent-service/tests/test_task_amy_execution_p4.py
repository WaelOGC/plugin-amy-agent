"""Task Service P4 — Amy execution capability matrix + safe handoff."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app import config_task_rules as rules  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import (  # noqa: E402
    analytics_db,
    notifications_db,
    progress_notes_db,
    seo_tasks_db,
    tasks_db,
)
from app.main import app  # noqa: E402
from app.services import task_amy_execution  # noqa: E402
from app.services.task_escalation import (  # noqa: E402
    check_standard_task,
    format_due_timestamp,
)

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "tasks.db"
    analytics_path = tmp_path / "analytics.db"
    seo_path = tmp_path / "seo_tasks.db"
    monkeypatch.setattr(tasks_db, "_DB_PATH", db_path)
    monkeypatch.setattr(notifications_db, "_DB_PATH", db_path)
    monkeypatch.setattr(progress_notes_db, "_DB_PATH", db_path)
    monkeypatch.setattr(analytics_db, "_DB_PATH", analytics_path)
    monkeypatch.setattr(seo_tasks_db, "_DB_PATH", seo_path)
    monkeypatch.setenv("WORDPRESS_BASE_URL", "")
    monkeypatch.setattr(rules, "AMY_EXECUTION_ENABLED", True)
    get_settings.cache_clear()
    return TestClient(app)


def _sync_owner(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks/sync-dashboard-users",
        headers=AUTH,
        json={
            "users": [
                {"wp_user_id": 1, "display_name": "Owner", "telegram_linked": True},
            ],
            "site_default_owner_wp_user_id": 1,
        },
    )
    assert response.status_code == 200


def test_capability_matrix_documented() -> None:
    rows = task_amy_execution.capability_matrix_public()
    ids = {r["id"] for r in rows}
    assert "analytics_summary" in ids
    assert "seo_review_summary" in ids
    assert "digital_task_close" in ids
    for row in rows:
        assert row["can"]
        assert row["cannot"]


def test_amy_at_create_runs_to_done_when_capable(client: TestClient) -> None:
    _sync_owner(client)
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Summarize analytics leads for the week",
            "description": "Digital in-system digest of visitor leads.",
            "assignee_type": "amy",
            "created_by_wp_user_id": 1,
            "amy_capable": True,
        },
    )
    assert response.status_code == 200
    created = response.json()
    # BackgroundTasks run before TestClient returns control after the request.
    refreshed = client.get(f"/v1/tasks/{created['id']}", headers=AUTH).json()
    assert refreshed["assignee_type"] == "amy"
    assert refreshed["status"] == "done"
    notes = client.get(
        f"/v1/tasks/{created['id']}/progress-notes", headers=AUTH
    ).json()["notes"]
    assert notes
    assert any(n["source"] == "amy" for n in notes)
    assert any("successfully" in n["note"].lower() or "summary" in n["note"].lower() for n in notes)


def test_amy_at_create_fails_without_capability_match(client: TestClient) -> None:
    _sync_owner(client)
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Pick up packages from the warehouse",
            "description": "Physical off-site errand.",
            "assignee_type": "amy",
            "created_by_wp_user_id": 1,
            "amy_capable": False,
        },
    )
    assert response.status_code == 200
    created = response.json()
    refreshed = client.get(f"/v1/tasks/{created['id']}", headers=AUTH).json()
    assert refreshed["status"] == "failed"
    assert refreshed["status"] != "done"


def test_expiry_amy_capable_runs_amy_to_done(client: TestClient) -> None:
    _sync_owner(client)
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Human task later for Amy",
            "assignee_type": "human",
            "assignee_wp_user_id": 4,
            "created_by_wp_user_id": 1,
            "due_date": "2099-01-01T00:00:00Z",
            "amy_capable": True,
        },
    ).json()
    # Avoid create-time Amy run: human assignee. Expire + run via scheduler path.
    now = 5_000_000.0
    tasks_db.update_task(
        created["id"],
        {
            "due_date": format_due_timestamp(now - 10),
            "escalation_stage": "mid_report_asked",
            "amy_capable": True,
            "status": "todo",
        },
    )
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 200_000

    notes = check_standard_task(task, now=now)
    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["status"] == "done"
    assert refreshed["assignee_type"] == "amy"
    assert refreshed["escalation_stage"] == "expired"
    # Success path does not create expiry reassign CTA.
    assert notes == []
    owner_notes = notifications_db.list_notifications(wp_user_id=1, unread_only=False)
    assert any(n["type"] == "amy_execution_done" for n in owner_notes)


def test_expiry_not_capable_still_notifies_owner_without_auto_done(
    client: TestClient,
) -> None:
    _sync_owner(client)
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Visit client office",
            "assignee_type": "human",
            "assignee_wp_user_id": 4,
            "created_by_wp_user_id": 1,
            "due_date": "2099-01-01T00:00:00Z",
            "amy_capable": False,
        },
    ).json()
    now = 5_100_000.0
    tasks_db.update_task(
        created["id"],
        {
            "due_date": format_due_timestamp(now - 10),
            "escalation_stage": "mid_report_asked",
            "amy_capable": False,
        },
    )
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 200_000
    notes = check_standard_task(task, now=now)
    assert len(notes) == 1
    assert notes[0]["type"] == "task_expired"
    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["status"] == "todo"
    assert "amy_take" not in notes[0]["action_payload"]["choices"]


def test_amy_take_cta_runs_execution(client: TestClient) -> None:
    _sync_owner(client)
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "SEO review summary for homepage",
            "assignee_type": "human",
            "assignee_wp_user_id": 4,
            "created_by_wp_user_id": 1,
            "amy_capable": True,
        },
    ).json()
    response = client.post(
        f"/v1/tasks/{created['id']}/expiry-action",
        headers=AUTH,
        json={"actor_wp_user_id": 1, "action": "amy_take"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amy_execution_enabled"] is True
    assert body["outcome"].startswith("amy_take_")
    assert body["task"]["assignee_type"] == "amy"
    assert body["task"]["status"] in {"done", "failed"}
    # Keyword + amy_capable → should succeed.
    assert body["task"]["status"] == "done"


def test_never_marks_done_when_execution_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rules, "AMY_EXECUTION_ENABLED", False)
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Analytics summary",
            "assignee_type": "amy",
            "created_by_wp_user_id": 1,
            "amy_capable": True,
        },
    ).json()
    refreshed = client.get(f"/v1/tasks/{created['id']}", headers=AUTH).json()
    assert refreshed["status"] == "todo"

    with pytest.raises(ValueError, match="not enabled"):
        task_amy_execution.run_amy_task(created["id"], trigger="manual")

    response = client.post(
        f"/v1/tasks/{created['id']}/expiry-action",
        headers=AUTH,
        json={"actor_wp_user_id": 1, "action": "amy_take"},
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["message"].lower()
