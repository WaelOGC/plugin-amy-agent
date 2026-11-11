"""Task Service P1 — templates, assign notify, progress notes."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import notifications_db, progress_notes_db, tasks_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import task_notify  # noqa: E402
from app.services.task_escalation import check_standard_task  # noqa: E402

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


def test_assign_templates_include_title_due_description() -> None:
    task = {
        "id": "t1",
        "title": "Ship P1",
        "description": "Wire FluentSMTP + Telegram",
        "due_date": "2026-11-12",
        "assignee_type": "human",
        "assignee_wp_user_id": 7,
        "created_by_wp_user_id": 1,
    }
    rendered = task_notify.render_assign(task)
    assert "Ship P1" in rendered["subject"]
    assert "Wire FluentSMTP" in rendered["body"]
    assert "2026-11-12" in rendered["body"]
    assert "Ship P1" in rendered["telegram"]

    mid = task_notify.render_mid_progress(task)
    assert "Progress" in mid["subject"] or "progress" in mid["body"].lower()
    assert "Ship P1" in mid["telegram"]

    expiry = task_notify.render_expiry(task)
    assert "past its due date" in expiry["body"].lower()
    assert "past due" in expiry["telegram"].lower()


def test_create_human_task_creates_assign_dashboard_notification(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Notify me",
            "description": "Please do the thing",
            "assignee_type": "human",
            "assignee_wp_user_id": 9,
            "created_by_wp_user_id": 1,
            "due_date": "2026-12-01",
        },
    )
    assert response.status_code == 200
    task = response.json()

    notes = notifications_db.list_notifications(wp_user_id=9, unread_only=False)
    assert len(notes) >= 1
    assert notes[0]["type"] == "task_assigned"
    assert notes[0]["task_id"] == task["id"]
    assert "Notify me" in notes[0]["message"]


def test_create_amy_task_skips_assign_notification(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Amy only",
            "assignee_type": "amy",
            "created_by_wp_user_id": 1,
        },
    )
    assert response.status_code == 200
    notes = notifications_db.list_notifications(wp_user_id=1, unread_only=False)
    assert all(n["type"] != "task_assigned" for n in notes)


def test_reassign_fires_assign_notify(client: TestClient) -> None:
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Move me",
            "assignee_type": "human",
            "assignee_wp_user_id": 2,
            "created_by_wp_user_id": 1,
        },
    ).json()

    patched = client.patch(
        f"/v1/tasks/{created['id']}",
        headers=AUTH,
        json={"assignee_wp_user_id": 5},
    )
    assert patched.status_code == 200
    notes = notifications_db.list_notifications(wp_user_id=5, unread_only=False)
    assert any(n["type"] == "task_assigned" and n["task_id"] == created["id"] for n in notes)


def test_mid_progress_sets_pending_and_telegram_reply_saves_note(
    client: TestClient,
) -> None:
    created = client.post(
        "/v1/tasks",
        headers=AUTH,
        json={
            "title": "Halfway",
            "assignee_type": "human",
            "assignee_wp_user_id": 4,
            "created_by_wp_user_id": 1,
            "due_date": "2099-01-01T00:00:00Z",
        },
    ).json()

    task = tasks_db.get_task(created["id"])
    assert task is not None
    from app.services.task_escalation import format_due_timestamp

    # Synthetic window: mid at 50% of created_at → due (P2 mid_report_asked).
    now = 2_000_000.0
    task["created_at"] = now - 100_000
    task["due_date"] = format_due_timestamp(now + 100_000)
    task["escalation_stage"] = "none"

    notes = check_standard_task(task, now=now)
    assert len(notes) == 1
    assert notes[0]["type"] == "mid_progress_ask"
    stored = tasks_db.get_task(created["id"])
    assert stored is not None
    assert stored["escalation_stage"] == "mid_report_asked"
    pending = progress_notes_db.get_pending_progress_reply(4)
    assert pending is not None
    assert pending["task_id"] == created["id"]

    reply = client.post(
        "/v1/tasks/progress-notes/from-telegram",
        headers=AUTH,
        json={"wp_user_id": 4, "note": "Done the wiring, finishing tests"},
    )
    assert reply.status_code == 200
    body = reply.json()
    assert body["saved"] is True
    assert body["note"]["note"].startswith("Done the wiring")
    assert progress_notes_db.get_pending_progress_reply(4) is None

    listed = client.get(
        f"/v1/tasks/{created['id']}/progress-notes",
        headers=AUTH,
    )
    assert listed.status_code == 200
    assert len(listed.json()["notes"]) == 1


def test_telegram_reply_without_pending_is_not_saved(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks/progress-notes/from-telegram",
        headers=AUTH,
        json={"wp_user_id": 99, "note": "orphan reply"},
    )
    assert response.status_code == 200
    assert response.json()["saved"] is False
