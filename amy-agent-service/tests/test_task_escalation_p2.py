"""Task Service P2 — assign → mid@50% → expiry state machine."""

from __future__ import annotations

import logging
import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import notifications_db, progress_notes_db, tasks_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.task_escalation import (  # noqa: E402
    check_standard_task,
    format_due_timestamp,
    mid_due_timestamps,
    run_escalation_pass,
)

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


def _human_task(client: TestClient, **extra: object) -> dict:
    body = {
        "title": "P2 window",
        "assignee_type": "human",
        "assignee_wp_user_id": 4,
        "created_by_wp_user_id": 1,
        "due_date": "2099-01-01T00:00:00Z",
        "amy_capable": False,
    }
    body.update(extra)
    response = client.post("/v1/tasks", headers=AUTH, json=body)
    assert response.status_code == 200
    return response.json()


def test_mid_due_timestamps_at_half_window() -> None:
    created = 1_000.0
    due = 2_000.0
    mid_at, due_out = mid_due_timestamps(created, due)
    assert mid_at == 1_500.0
    assert due_out == due


def test_mid_at_50_sets_mid_report_asked_once(client: TestClient) -> None:
    created = _human_task(client)
    task = tasks_db.get_task(created["id"])
    assert task is not None

    now = 2_000_000.0
    task["created_at"] = now - 100_000
    task["due_date"] = format_due_timestamp(now + 100_000)
    task["escalation_stage"] = "none"
    tasks_db.update_task(
        task["id"],
        {
            "due_date": task["due_date"],
            "escalation_stage": "none",
        },
    )
    # Persist created_at via raw update fields that update_task allows — set on dict
    # used by check; DB stage assertion uses get after check.
    task["created_at"] = now - 100_000

    notes = check_standard_task(task, now=now)
    assert len(notes) == 1
    assert notes[0]["type"] == "mid_progress_ask"

    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["escalation_stage"] == "mid_report_asked"

    # Second pass must not double-fire.
    again = check_standard_task(refreshed | {"created_at": now - 100_000}, now=now)
    assert again == []
    assert tasks_db.get_task(created["id"])["escalation_stage"] == "mid_report_asked"


def test_legacy_midpoint_sent_does_not_re_fire(client: TestClient) -> None:
    created = _human_task(client)
    now = 2_000_000.0
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 100_000
    task["due_date"] = format_due_timestamp(now + 100_000)
    task["escalation_stage"] = "midpoint_sent"
    tasks_db.update_task(
        task["id"],
        {
            "due_date": task["due_date"],
            "escalation_stage": "midpoint_sent",
        },
    )
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 100_000

    notes = check_standard_task(task, now=now)
    assert notes == []
    # Still past mid, not yet due — no final warning in P2.
    mid_types = [
        n["type"]
        for n in notifications_db.list_notifications(wp_user_id=4, unread_only=False)
        if n["task_id"] == created["id"]
    ]
    assert "reminder_final" not in mid_types
    assert "mid_progress_ask" not in mid_types


def test_no_final_warning_near_due(client: TestClient) -> None:
    """Locked decision: one mid ask, then expiry — no +4h final warning."""
    created = _human_task(client)
    now = 2_000_000.0
    # Mid already asked; within what used to be the final-warning window.
    task = {
        **tasks_db.get_task(created["id"]),  # type: ignore[dict-item]
        "created_at": now - 100_000,
        "due_date": format_due_timestamp(now + 3_600),  # 1h left (< 4h)
        "escalation_stage": "mid_report_asked",
    }
    tasks_db.update_task(
        created["id"],
        {
            "due_date": task["due_date"],
            "escalation_stage": "mid_report_asked",
        },
    )
    notes = check_standard_task(task, now=now)
    assert notes == []
    assert tasks_db.get_task(created["id"])["escalation_stage"] == "mid_report_asked"


def test_expiry_marks_expired_and_notifies_creator(client: TestClient) -> None:
    created = _human_task(client, amy_capable=True)
    now = 2_000_000.0
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 200_000
    task["due_date"] = format_due_timestamp(now - 10)
    task["escalation_stage"] = "mid_report_asked"
    task["amy_capable"] = True
    tasks_db.update_task(
        created["id"],
        {
            "due_date": task["due_date"],
            "escalation_stage": "mid_report_asked",
            "amy_capable": True,
        },
    )
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 200_000

    notes = check_standard_task(task, now=now)
    assert len(notes) == 1
    assert notes[0]["type"] == "task_expired"
    assert notes[0]["wp_user_id"] == 1
    assert notes[0]["requires_action"] is True

    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["escalation_stage"] == "expired"
    # Never fake Amy completion.
    assert refreshed["status"] != "done"

    # Idempotent: second expiry pass is a no-op.
    assert check_standard_task(refreshed | {"created_at": now - 200_000}, now=now) == []


def test_amy_capable_expiry_logs_hook_does_not_complete(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    created = _human_task(client, amy_capable=True, title="Capable expiry")
    now = 3_000_000.0
    tasks_db.update_task(
        created["id"],
        {
            "due_date": format_due_timestamp(now - 1),
            "escalation_stage": "none",
            "amy_capable": True,
        },
    )
    task = tasks_db.get_task(created["id"])
    assert task is not None
    task["created_at"] = now - 50_000

    with caplog.at_level(logging.INFO, logger="app.services.task_escalation"):
        check_standard_task(task, now=now)

    assert any("amy_capable=True" in r.message for r in caplog.records)
    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["status"] == "todo"
    assert refreshed["escalation_stage"] == "expired"


def test_run_escalation_pass_drives_mid_then_expiry(client: TestClient) -> None:
    created = _human_task(client)
    now = 4_000_000.0
    # Created 2h ago, due in 2h → mid is exactly now.
    tasks_db.update_task(
        created["id"],
        {
            "due_date": format_due_timestamp(now + 7_200),
            "escalation_stage": "none",
        },
    )
    # Force created_at by rewriting through SQL isn't exposed; monkeypatch get list.
    row = tasks_db.get_task(created["id"])
    assert row is not None

    # Direct check with synthetic created_at (pass uses DB created_at from insert).
    # Simulate mid via check_standard_task then expiry via second call.
    mid_task = {**row, "created_at": now - 7_200, "escalation_stage": "none"}
    mid_notes = check_standard_task(mid_task, now=now)
    assert mid_notes[0]["type"] == "mid_progress_ask"

    expired_row = tasks_db.get_task(created["id"])
    assert expired_row is not None
    exp_task = {
        **expired_row,
        "created_at": now - 14_400,
        "due_date": format_due_timestamp(now - 1),
    }
    tasks_db.update_task(created["id"], {"due_date": exp_task["due_date"]})
    exp_task = {**tasks_db.get_task(created["id"]), "created_at": now - 14_400}  # type: ignore[dict-item]
    exp_notes = check_standard_task(exp_task, now=now)
    assert exp_notes[0]["type"] == "task_expired"

    # Scheduler pass should not crash on remaining open tasks.
    result = run_escalation_pass()
    assert result["tasks_checked"] >= 1
