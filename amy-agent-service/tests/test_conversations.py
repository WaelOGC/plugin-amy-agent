"""Conversation memory store, ownership filtering, and retention."""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import conversations_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    db_path = tmp_path / "conversations.db"
    monkeypatch.setattr(conversations_db, "_DB_PATH", db_path)
    return TestClient(app)


def test_create_append_get_messages_ordering(client: TestClient) -> None:
    conv = conversations_db.create_conversation(wp_user_id=1, mode="admin")
    assert conv["status"] == "active"
    assert conv["title"] is None
    assert conv["id"]

    conversations_db.append_message(conv["id"], "user", "Hello Amy, please help me")
    conversations_db.append_message(conv["id"], "assistant", "Sure — what do you need?")
    conversations_db.append_message(conv["id"], "user", "Second turn")

    messages = conversations_db.get_messages(conv["id"])
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "Hello Amy, please help me"
    assert messages[0]["id"] < messages[1]["id"] < messages[2]["id"]

    refreshed = conversations_db.get_conversation(conv["id"])
    assert refreshed is not None
    assert refreshed["title"] == "Hello Amy, please help me"


def test_title_truncates_to_sixty_chars(client: TestClient) -> None:
    conv = conversations_db.create_conversation(wp_user_id=1, mode="admin")
    long_text = "A" * 80
    conversations_db.append_message(conv["id"], "user", long_text)
    refreshed = conversations_db.get_conversation(conv["id"])
    assert refreshed is not None
    assert refreshed["title"] == "A" * 60


def test_list_conversations_ownership_filtering(client: TestClient) -> None:
    mine = conversations_db.create_conversation(wp_user_id=10, mode="admin", title="Mine")
    theirs = conversations_db.create_conversation(
        wp_user_id=20, mode="admin", title="Theirs"
    )
    widget = conversations_db.create_conversation(
        wp_user_id=10, mode="general", title="Widget"
    )

    as_user = conversations_db.list_conversations(wp_user_id=10, is_full_admin=False)
    assert {c["id"] for c in as_user} == {mine["id"], widget["id"]}
    assert all(c["wp_user_id"] == 10 for c in as_user)
    assert theirs["id"] not in {c["id"] for c in as_user}

    as_admin = conversations_db.list_conversations(wp_user_id=10, is_full_admin=True)
    assert {c["id"] for c in as_admin} >= {mine["id"], theirs["id"], widget["id"]}

    admin_only = conversations_db.list_conversations(
        wp_user_id=10, is_full_admin=True, mode="admin"
    )
    assert all(c["mode"] == "admin" for c in admin_only)
    assert theirs["id"] in {c["id"] for c in admin_only}
    assert widget["id"] not in {c["id"] for c in admin_only}


def test_rename_and_delete_removes_messages(client: TestClient) -> None:
    conv = conversations_db.create_conversation(wp_user_id=1, mode="admin")
    conversations_db.append_message(conv["id"], "user", "to delete")
    assert conversations_db.rename_conversation(conv["id"], "Renamed") is True
    renamed = conversations_db.get_conversation(conv["id"])
    assert renamed is not None
    assert renamed["title"] == "Renamed"

    assert conversations_db.delete_conversation(conv["id"]) is True
    assert conversations_db.get_conversation(conv["id"]) is None
    assert conversations_db.get_messages(conv["id"]) == []
    assert conversations_db.delete_conversation(conv["id"]) is False
    assert conversations_db.rename_conversation("missing", "x") is False


def test_archive_stale_conversations_only_old_active(client: TestClient) -> None:
    now = time.time()
    old = conversations_db.create_conversation(wp_user_id=1, mode="admin", title="Old")
    fresh = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Fresh"
    )
    already = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Already archived"
    )

    conn = conversations_db._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ?, status = 'active' WHERE id = ?",
                (now - (100 * 24 * 60 * 60), old["id"]),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ?, status = 'active' WHERE id = ?",
                (now, fresh["id"]),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ?, status = 'archived' WHERE id = ?",
                (now - (100 * 24 * 60 * 60), already["id"]),
            )
    finally:
        conn.close()

    result = conversations_db.archive_stale_conversations(days=90)
    assert result["archived"] == 1
    assert conversations_db.get_conversation(old["id"])["status"] == "archived"
    assert conversations_db.get_conversation(fresh["id"])["status"] == "active"
    assert conversations_db.get_conversation(already["id"])["status"] == "archived"

    listed = conversations_db.list_conversations(wp_user_id=1, is_full_admin=False)
    assert old["id"] not in {c["id"] for c in listed}
    with_archived = conversations_db.list_conversations(
        wp_user_id=1, is_full_admin=False, include_archived=True
    )
    assert old["id"] in {c["id"] for c in with_archived}


def test_purge_exported_and_grace_window(client: TestClient) -> None:
    now = time.time()
    exported = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Exported"
    )
    within_grace = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Within grace"
    )
    past_grace = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Past grace"
    )
    active_old = conversations_db.create_conversation(
        wp_user_id=1, mode="admin", title="Still active"
    )

    conversations_db.append_message(exported["id"], "user", "bye")
    conversations_db.append_message(past_grace["id"], "user", "old")

    conn = conversations_db._connect()
    try:
        with conn:
            # Exported recently — eligible for immediate purge once archived.
            conn.execute(
                """
                UPDATE conversations
                SET status = 'archived', updated_at = ?, exported_at = ?
                WHERE id = ?
                """,
                (now - (5 * 24 * 60 * 60), now, exported["id"]),
            )
            # Archived 95 days ago, not exported — still inside 90+30 grace.
            conn.execute(
                """
                UPDATE conversations
                SET status = 'archived', updated_at = ?, exported_at = NULL
                WHERE id = ?
                """,
                (now - (95 * 24 * 60 * 60), within_grace["id"]),
            )
            # Archived 130 days ago — past 90+30 window.
            conn.execute(
                """
                UPDATE conversations
                SET status = 'archived', updated_at = ?, exported_at = NULL
                WHERE id = ?
                """,
                (now - (130 * 24 * 60 * 60), past_grace["id"]),
            )
            # Old but still active — must not be purged.
            conn.execute(
                """
                UPDATE conversations
                SET status = 'active', updated_at = ?, exported_at = NULL
                WHERE id = ?
                """,
                (now - (200 * 24 * 60 * 60), active_old["id"]),
            )
    finally:
        conn.close()

    result = conversations_db.purge_exported_or_expired_conversations(
        archived_grace_days=30
    )
    assert result["deleted"] == 2
    assert conversations_db.get_conversation(exported["id"]) is None
    assert conversations_db.get_messages(exported["id"]) == []
    assert conversations_db.get_conversation(past_grace["id"]) is None
    assert conversations_db.get_conversation(within_grace["id"]) is not None
    assert conversations_db.get_conversation(active_old["id"]) is not None


def test_api_create_list_get_rename_delete_export(client: TestClient) -> None:
    create = client.post(
        "/v1/conversations",
        headers=AUTH,
        json={"wp_user_id": 7, "mode": "admin", "title": "Kickoff"},
    )
    assert create.status_code == 201, create.text
    conv_id = create.json()["id"]

    conversations_db.append_message(conv_id, "user", "Hi")
    conversations_db.append_message(conv_id, "assistant", "Hello")

    listed = client.get(
        "/v1/conversations",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
    )
    assert listed.status_code == 200
    assert any(c["id"] == conv_id for c in listed.json()["conversations"])

    detail = client.get(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
    )
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2

    forbidden = client.get(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 99, "is_full_admin": False},
    )
    assert forbidden.status_code == 403

    admin_ok = client.get(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 99, "is_full_admin": True},
    )
    assert admin_ok.status_code == 200

    renamed = client.patch(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
        json={"title": "New title"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "New title"

    exported = client.get(
        f"/v1/conversations/{conv_id}/export",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
    )
    assert exported.status_code == 200
    assert "attachment" in exported.headers.get("content-disposition", "")
    assert f"conversation-{conv_id}.json" in exported.headers.get(
        "content-disposition", ""
    )
    payload = exported.json()
    assert payload["exported_at"] is not None
    assert len(payload["messages"]) == 2

    deleted = client.delete(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
    )
    assert deleted.status_code == 204
    missing = client.get(
        f"/v1/conversations/{conv_id}",
        headers=AUTH,
        params={"wp_user_id": 7, "is_full_admin": False},
    )
    assert missing.status_code == 404
