"""Task Service P3 — owner/backup expiry escalate + reassign actions."""

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
    handle_expiry_action,
)
from app.services.task_owner import resolve_expiry_escalatee  # noqa: E402

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


def _sync_pool(
    client: TestClient,
    users: list[dict],
    *,
    site_default: int | None = None,
) -> None:
    body: dict = {"users": users}
    if site_default is not None:
        body["site_default_owner_wp_user_id"] = site_default
    response = client.post("/v1/tasks/sync-dashboard-users", headers=AUTH, json=body)
    assert response.status_code == 200


def _human_task(client: TestClient, **extra: object) -> dict:
    body = {
        "title": "P3 window",
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


def _expire_now(task_id: str, *, now: float, amy_capable: bool = False) -> dict:
    tasks_db.update_task(
        task_id,
        {
            "due_date": format_due_timestamp(now - 10),
            "escalation_stage": "mid_report_asked",
            "amy_capable": amy_capable,
        },
    )
    task = tasks_db.get_task(task_id)
    assert task is not None
    task["created_at"] = now - 200_000
    return task


def test_create_defaults_owner_to_creator(client: TestClient) -> None:
    created = _human_task(client)
    assert created["owner_wp_user_id"] == 1
    assert created["backup_wp_user_id"] is None
    assert created["created_by_wp_user_id"] == 1


def test_expiry_notifies_reachable_owner(client: TestClient) -> None:
    _sync_pool(
        client,
        [
            {"wp_user_id": 1, "display_name": "Owner", "telegram_linked": True},
            {"wp_user_id": 4, "display_name": "Assignee", "telegram_linked": True},
            {"wp_user_id": 9, "display_name": "Abdulla", "telegram_linked": True},
        ],
        site_default=9,
    )
    created = _human_task(client)
    now = 2_000_000.0
    task = _expire_now(created["id"], now=now)

    notes = check_standard_task(task, now=now)
    assert len(notes) == 1
    assert notes[0]["type"] == "task_expired"
    assert notes[0]["wp_user_id"] == 1
    payload = notes[0]["action_payload"]
    assert payload["choices"] == [
        "reassign_same",
        "reassign_other",
        "acknowledge_manual",
    ]
    assert payload["amy_capable"] is False
    assert payload["amy_execution_enabled"] is False
    assert payload["escalatee_role"] == "owner"


def test_expiry_falls_back_to_site_default_when_owner_no_telegram(
    client: TestClient,
) -> None:
    _sync_pool(
        client,
        [
            {"wp_user_id": 1, "display_name": "Owner", "telegram_linked": False},
            {"wp_user_id": 4, "display_name": "Assignee", "telegram_linked": True},
            {"wp_user_id": 9, "display_name": "Abdulla", "telegram_linked": True},
        ],
        site_default=9,
    )
    created = _human_task(client)
    now = 2_100_000.0
    task = _expire_now(created["id"], now=now)

    notes = check_standard_task(task, now=now)
    assert notes[0]["wp_user_id"] == 9
    assert notes[0]["action_payload"]["escalatee_role"] == "site_default"
    assert notes[0]["action_payload"]["escalatee_reason"] == "owner_unreachable_site_default"


def test_expiry_falls_back_to_backup_when_no_site_default(client: TestClient) -> None:
    _sync_pool(
        client,
        [
            {
                "wp_user_id": 1,
                "display_name": "Owner",
                "telegram_linked": False,
                "backup_wp_user_id": 7,
            },
            {"wp_user_id": 4, "display_name": "Assignee", "telegram_linked": True},
            {"wp_user_id": 7, "display_name": "Backup", "telegram_linked": True},
        ],
        site_default=0,
    )
    created = _human_task(client, backup_wp_user_id=7)
    assert created["backup_wp_user_id"] == 7
    resolved = resolve_expiry_escalatee(tasks_db.get_task(created["id"]))  # type: ignore[arg-type]
    assert resolved["role"] == "backup"
    assert resolved["wp_user_id"] == 7

    now = 2_200_000.0
    task = _expire_now(created["id"], now=now)
    notes = check_standard_task(task, now=now)
    assert notes[0]["wp_user_id"] == 7
    assert notes[0]["action_payload"]["escalatee_role"] == "backup"


def test_expiry_owner_gone_uses_site_default(client: TestClient) -> None:
    # Creator 1 is not in the dashboard pool → "gone".
    _sync_pool(
        client,
        [
            {"wp_user_id": 4, "display_name": "Assignee", "telegram_linked": True},
            {"wp_user_id": 9, "display_name": "Abdulla", "telegram_linked": False},
        ],
        site_default=9,
    )
    created = _human_task(client)
    now = 2_300_000.0
    task = _expire_now(created["id"], now=now)
    notes = check_standard_task(task, now=now)
    assert notes[0]["wp_user_id"] == 9


def test_amy_capable_expiry_includes_amy_take_choice_but_does_not_complete(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _sync_pool(
        client,
        [{"wp_user_id": 1, "display_name": "Owner", "telegram_linked": True}],
        site_default=1,
    )
    created = _human_task(client, amy_capable=True)
    now = 2_400_000.0
    task = _expire_now(created["id"], now=now, amy_capable=True)

    with caplog.at_level(logging.INFO, logger="app.services.task_escalation"):
        notes = check_standard_task(task, now=now)

    assert "amy_take" in notes[0]["action_payload"]["choices"]
    assert notes[0]["action_payload"]["amy_execution_enabled"] is False
    refreshed = tasks_db.get_task(created["id"])
    assert refreshed is not None
    assert refreshed["status"] == "todo"
    assert refreshed["escalation_stage"] == "expired"
    assert any("amy_capable=True" in r.message for r in caplog.records)


def test_reassign_other_resets_stage_and_notifies(client: TestClient) -> None:
    _sync_pool(
        client,
        [
            {"wp_user_id": 1, "display_name": "Owner", "telegram_linked": True},
            {"wp_user_id": 4, "display_name": "Old", "telegram_linked": True},
            {"wp_user_id": 5, "display_name": "New", "telegram_linked": True},
        ],
        site_default=1,
    )
    created = _human_task(client)
    now = 2_500_000.0
    task = _expire_now(created["id"], now=now)
    check_standard_task(task, now=now)

    result = handle_expiry_action(
        created["id"],
        actor_wp_user_id=1,
        action="reassign_other",
        assignee_wp_user_id=5,
    )
    assert result["outcome"] == "reassign_other"
    updated = result["task"]
    assert updated["assignee_wp_user_id"] == 5
    assert updated["escalation_stage"] == "none"
    # Past-due bump so scheduler does not immediately re-expire.
    assert updated["due_date"] is not None

    notes = notifications_db.list_notifications(wp_user_id=5, unread_only=False)
    assert any(n["type"] == "task_assigned" and n["task_id"] == created["id"] for n in notes)


def test_expiry_action_api_rejects_amy_take_while_p4_off(client: TestClient) -> None:
    created = _human_task(client, amy_capable=True)
    response = client.post(
        f"/v1/tasks/{created['id']}/expiry-action",
        headers=AUTH,
        json={
            "actor_wp_user_id": 1,
            "action": "amy_take",
        },
    )
    assert response.status_code == 400
    assert "not enabled" in response.json()["message"].lower()


def test_acknowledge_manual_via_api(client: TestClient) -> None:
    created = _human_task(client)
    response = client.post(
        f"/v1/tasks/{created['id']}/expiry-action",
        headers=AUTH,
        json={
            "actor_wp_user_id": 1,
            "action": "acknowledge_manual",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "acknowledged_manual"
    assert body["task"]["status"] == "in_progress"
    assert body["amy_execution_enabled"] is False
