"""Email marketing FluentSMTP history, opt-out, propose, inbound webhook."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"
os.environ.setdefault("PUBLIC_BASE_URL", "https://amy-api.example.com")

from app.config import get_settings  # noqa: E402
from app.db import conversations_db, email_history_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    db_path = tmp_path / "conversations.db"
    monkeypatch.setattr(conversations_db, "_DB_PATH", db_path)
    monkeypatch.setattr(email_history_db, "_DB_PATH", db_path)
    return TestClient(app)


def test_record_outbound_and_list_threads(client: TestClient) -> None:
    res = client.post(
        "/v1/email-marketing/outbound",
        headers=AUTH,
        json={
            "subject": "Hello from OGC",
            "body": "Thanks for your idea.",
            "from_email": "hello@ogcnewfinity.com",
            "wp_user_id": 1,
            "recipients": [
                {"email": "Lead@Example.com", "ok": True, "error": None},
                {"email": "fail@example.com", "ok": False, "error": "smtp boom"},
            ],
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["recorded"] == 2

    listed = client.get("/v1/email-marketing/threads", headers=AUTH)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    emails = {t["participant_email"] for t in body["threads"]}
    assert emails == {"lead@example.com", "fail@example.com"}


def test_suppression_blocks_propose_and_marks_outbound(client: TestClient) -> None:
    add = client.post(
        "/v1/email-marketing/suppressions",
        headers=AUTH,
        json={"email": "optout@example.com", "reason": "unsubscribe link", "source": "opt_out"},
    )
    assert add.status_code == 200

    check = client.get(
        "/v1/email-marketing/suppressions/check",
        headers=AUTH,
        params={"email": "optout@example.com"},
    )
    assert check.status_code == 200
    assert check.json()["suppressed"] is True

    propose = client.post(
        "/v1/email-marketing/propose",
        headers=AUTH,
        json={
            "to_email": "optout@example.com",
            "subject": "Should not land",
            "body": "Nope",
        },
    )
    assert propose.status_code == 400

    outbound = client.post(
        "/v1/email-marketing/outbound",
        headers=AUTH,
        json={
            "subject": "Still logged",
            "body": "Body",
            "from_email": "hello@ogcnewfinity.com",
            "recipients": [{"email": "optout@example.com", "ok": True}],
        },
    )
    assert outbound.status_code == 200
    item = outbound.json()["items"][0]
    assert item["message"]["status"] == "suppressed"


def test_propose_requires_human_approve(client: TestClient) -> None:
    res = client.post(
        "/v1/email-marketing/propose",
        headers=AUTH,
        json={
            "to_email": "prospect@example.com",
            "subject": "Outreach",
            "body": "Draft from Amy",
            "from_email": "hello@ogcnewfinity.com",
            "proposed_by": "amy",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["requires_human_approve"] is True
    assert data["message"]["direction"] == "proposed"
    assert data["message"]["channel"] == "amy_propose"
    assert data["message"]["status"] == "proposed"


def test_manual_inbound_note_and_webhook(client: TestClient) -> None:
    client.post(
        "/v1/email-marketing/outbound",
        headers=AUTH,
        json={
            "subject": "Ping",
            "body": "Hello",
            "from_email": "hello@ogcnewfinity.com",
            "recipients": [{"email": "reply@example.com", "ok": True}],
        },
    )
    threads = client.get("/v1/email-marketing/threads", headers=AUTH).json()["threads"]
    thread_id = next(t["id"] for t in threads if t["participant_email"] == "reply@example.com")

    note = client.post(
        f"/v1/email-marketing/threads/{thread_id}/notes",
        headers=AUTH,
        json={"body": "They replied by phone", "wp_user_id": 2, "as_inbound": False},
    )
    assert note.status_code == 200
    assert note.json()["direction"] == "note"

    inbound = client.post(
        "/v1/email-marketing/inbound",
        headers=AUTH,
        json={
            "from": "reply@example.com",
            "to": "hello@ogcnewfinity.com",
            "subject": "Re: Ping",
            "text": "Thanks — interested.",
        },
    )
    assert inbound.status_code == 200, inbound.text
    assert inbound.json()["direction"] == "inbound"
    assert inbound.json()["status"] == "received"

    detail = client.get(f"/v1/email-marketing/threads/{thread_id}", headers=AUTH)
    assert detail.status_code == 200
    body = detail.json()
    assert "FluentSMTP is outbound-only" in body["inbound_limitation"]
    dirs = [m["direction"] for m in body["messages"]]
    assert "outbound" in dirs
    assert "note" in dirs
    assert "inbound" in dirs


def test_requires_secret(client: TestClient) -> None:
    res = client.get("/v1/email-marketing/threads")
    assert res.status_code == 401
