"""Analytics ingestion, lead scoring, and retention."""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import analytics_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import geolocation, lead_scoring  # noqa: E402

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    db_path = tmp_path / "analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", db_path)
    monkeypatch.setattr(geolocation, "lookup_ip", lambda ip: ("Netherlands", "The Hague"))
    return TestClient(app)


def _ingest(client: TestClient, session_id: str, event_type: str, **extra) -> dict:
    body = {
        "session_id": session_id,
        "event_type": event_type,
        "ip": extra.pop("ip", "8.8.8.8"),
    }
    body.update(extra)
    response = client.post("/v1/analytics/event", headers=AUTH, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_event_requires_secret(client: TestClient) -> None:
    response = client.post(
        "/v1/analytics/event",
        json={"session_id": "abc", "event_type": "page_view"},
    )
    assert response.status_code == 401


def test_unknown_event_type_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/analytics/event",
        headers=AUTH,
        json={"session_id": "sess-1", "event_type": "newsletter_signup", "ip": "1.1.1.1"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_event_type"


def test_contact_form_events_are_accepted(client: TestClient) -> None:
    data = _ingest(client, "sess-contact", "contact_form_started", page_path="/contact")
    assert data["ok"] is True
    data = _ingest(client, "sess-contact", "contact_form_abandoned", page_path="/contact")
    assert data["lead_status"] == "hot"


def test_page_view_is_cold(client: TestClient) -> None:
    data = _ingest(client, "sess-cold", "page_view", page_path="/")
    assert data["lead_status"] == "cold"


def test_widget_message_is_warm(client: TestClient) -> None:
    _ingest(client, "sess-warm", "page_view", page_path="/")
    data = _ingest(client, "sess-warm", "widget_message_sent")
    assert data["lead_status"] == "warm"


def test_blog_page_views_are_warm(client: TestClient) -> None:
    _ingest(client, "sess-blog", "page_view", page_path="/")
    data = _ingest(client, "sess-blog", "page_view", page_path="/blog/some-article")
    assert data["lead_status"] == "warm"


def test_submit_idea_in_progress_is_warm(client: TestClient) -> None:
    data = _ingest(client, "sess-si", "submit_idea_started")
    assert data["lead_status"] == "warm"


def test_submit_idea_abandoned_at_contact_is_hot(client: TestClient) -> None:
    _ingest(client, "sess-hot", "submit_idea_started")
    data = _ingest(
        client,
        "sess-hot",
        "submit_idea_abandoned",
        event_data={"last_step": "contact"},
    )
    assert data["lead_status"] == "hot"


def test_submit_idea_completed_stores_email_and_is_hot(client: TestClient) -> None:
    _ingest(client, "sess-done", "submit_idea_started")
    data = _ingest(
        client,
        "sess-done",
        "submit_idea_completed",
        event_data={"email": "lead@example.com"},
    )
    assert data["lead_status"] == "hot"
    leads = client.get("/v1/analytics/leads", headers=AUTH).json()["leads"]
    match = next(item for item in leads if item["session_id"] == "sess-done")
    assert match["lead_email"] == "lead@example.com"
    assert match["signal"] == "Completed Submit Idea"
    assert match["ip_country"] == "Netherlands"


def test_submit_idea_contact_captured_stores_email_early(client: TestClient) -> None:
    """Email-first step: lead_email is set before Q&A / completion."""
    _ingest(client, "sess-early", "submit_idea_started")
    data = _ingest(
        client,
        "sess-early",
        "submit_idea_contact_captured",
        event_data={"email": "early@example.com", "whatsapp": "+31 6 11112222"},
    )
    assert data["ok"] is True
    leads = client.get("/v1/analytics/leads", headers=AUTH).json()["leads"]
    match = next(item for item in leads if item["session_id"] == "sess-early")
    assert match["lead_email"] == "early@example.com"
    assert match["lead_whatsapp"] == "+31 6 11112222"
    assert match["signal"] == "Shared email on Submit Idea"

    # Abandon after early contact still keeps the email for marketing.
    _ingest(
        client,
        "sess-early",
        "submit_idea_abandoned",
        event_data={"last_step": "questions"},
    )
    leads2 = client.get("/v1/analytics/leads", headers=AUTH).json()["leads"]
    match2 = next(item for item in leads2 if item["session_id"] == "sess-early")
    assert match2["lead_email"] == "early@example.com"


def test_leads_filter_and_timeline(client: TestClient) -> None:
    _ingest(client, "sess-a", "page_view", page_path="/")
    _ingest(client, "sess-b", "widget_message_sent")
    warm = client.get("/v1/analytics/leads", headers=AUTH, params={"status": "warm"}).json()
    ids = {item["session_id"] for item in warm["leads"]}
    assert ids == {"sess-b"}

    timeline = client.get("/v1/analytics/leads/sess-b/events", headers=AUTH)
    assert timeline.status_code == 200
    assert timeline.json()["events"][0]["event_type"] == "widget_message_sent"


def test_leads_has_email_filter(client: TestClient) -> None:
    _ingest(client, "sess-no-mail", "page_view", page_path="/")
    _ingest(client, "sess-mail", "submit_idea_started")
    _ingest(
        client,
        "sess-mail",
        "submit_idea_completed",
        event_data={"email": "audience@example.com"},
    )

    with_email = client.get(
        "/v1/analytics/leads",
        headers=AUTH,
        params={"has_email": "true"},
    ).json()["leads"]
    with_ids = {item["session_id"] for item in with_email}
    assert "sess-mail" in with_ids
    assert "sess-no-mail" not in with_ids
    assert all(item.get("lead_email") for item in with_email)

    without_email = client.get(
        "/v1/analytics/leads",
        headers=AUTH,
        params={"has_email": "false"},
    ).json()["leads"]
    without_ids = {item["session_id"] for item in without_email}
    assert "sess-no-mail" in without_ids
    assert "sess-mail" not in without_ids

    hot_with_email = client.get(
        "/v1/analytics/leads",
        headers=AUTH,
        params={"status": "hot", "has_email": "true"},
    ).json()["leads"]
    assert {item["session_id"] for item in hot_with_email} == {"sess-mail"}


def test_geolocation_null_does_not_drop_event(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(geolocation, "lookup_ip", lambda ip: (None, None))
    data = _ingest(client, "sess-geo", "page_view", page_path="/about")
    assert data["ok"] is True
    session = analytics_db.get_session("sess-geo")
    assert session is not None
    assert session["ip_country"] is None


def test_private_ip_skips_lookup() -> None:
    country, city = geolocation.lookup_ip("127.0.0.1")
    assert country is None
    assert city is None


def test_purge_removes_old_events_and_orphaned_sessions(client: TestClient) -> None:
    now = time.time()
    analytics_db.create_session("old-sess", now=now - (100 * 24 * 60 * 60))
    analytics_db.insert_event(
        session_id="old-sess",
        event_type="page_view",
        page_path="/",
        now=now - (100 * 24 * 60 * 60),
    )
    analytics_db.create_session("new-sess", now=now)
    analytics_db.insert_event(
        session_id="new-sess",
        event_type="page_view",
        page_path="/",
        now=now,
    )
    result = analytics_db.purge_old_events(days=90)
    assert result["events_deleted"] == 1
    assert result["sessions_deleted"] == 1
    assert analytics_db.get_session("old-sess") is None
    assert analytics_db.get_session("new-sess") is not None


def test_blog_path_matcher() -> None:
    assert lead_scoring.is_blog_article_path("/blog/hello")
    assert lead_scoring.is_blog_article_path("/2026/08/18/hello")
    assert not lead_scoring.is_blog_article_path("/")
    assert not lead_scoring.is_blog_article_path("/submit-idea")
    assert not lead_scoring.is_blog_article_path("/contact")


def test_submit_idea_completed_stores_whatsapp_and_email(client: TestClient) -> None:
    _ingest(client, "sess-wa", "submit_idea_started")
    _ingest(
        client,
        "sess-wa",
        "submit_idea_completed",
        event_data={"email": "a@b.com", "whatsapp": "+31 6 12345678"},
    )
    leads = client.get("/v1/analytics/leads", headers=AUTH).json()["leads"]
    match = next(item for item in leads if item["session_id"] == "sess-wa")
    assert match["lead_email"] == "a@b.com"
    assert match["lead_whatsapp"] == "+31 6 12345678"


def test_submit_idea_email_only_has_null_whatsapp(client: TestClient) -> None:
    _ingest(client, "sess-em", "submit_idea_started")
    _ingest(
        client,
        "sess-em",
        "submit_idea_completed",
        event_data={"email": "only@example.com"},
    )
    leads = client.get("/v1/analytics/leads", headers=AUTH).json()["leads"]
    match = next(item for item in leads if item["session_id"] == "sess-em")
    assert match["lead_email"] == "only@example.com"
    assert match["lead_whatsapp"] is None


def test_invalid_whatsapp_does_not_overwrite_stored(client: TestClient) -> None:
    _ingest(client, "sess-inv", "submit_idea_started")
    _ingest(
        client,
        "sess-inv",
        "submit_idea_completed",
        event_data={"email": "keep@test.com", "whatsapp": "+31 6 99998888"},
    )
    for bad in ("", "abc", "123"):
        _ingest(
            client,
            "sess-inv",
            "submit_idea_completed",
            event_data={"whatsapp": bad},
        )
    session = analytics_db.get_session("sess-inv")
    assert session is not None
    assert session["lead_whatsapp"] == "+31 6 99998888"


def test_extract_captured_whatsapp() -> None:
    assert lead_scoring.extract_captured_whatsapp("submit_idea_completed", {"whatsapp": "+31612345678"}) == "+31612345678"
    assert (
        lead_scoring.extract_captured_whatsapp("submit_idea_completed", {"whatsapp": "+31 6-1234-5678"})
        == "+31 6-1234-5678"
    )
    assert lead_scoring.extract_captured_whatsapp("submit_idea_completed", {"whatsapp": "123"}) is None
    assert lead_scoring.extract_captured_whatsapp("submit_idea_completed", {"whatsapp": "abc1234567"}) is None
    assert lead_scoring.extract_captured_whatsapp("page_view", {"whatsapp": "+31612345678"}) is None
    assert (
        lead_scoring.extract_captured_whatsapp(
            "submit_idea_contact_captured", {"whatsapp": "+31699998888"}
        )
        == "+31699998888"
    )
    assert (
        lead_scoring.extract_captured_email(
            "submit_idea_contact_captured", {"email": "cap@example.com"}
        )
        == "cap@example.com"
    )


def test_analytics_summary_endpoint(client: TestClient) -> None:
    _ingest(client, "sum-hot", "submit_idea_started")
    _ingest(
        client,
        "sum-hot",
        "submit_idea_completed",
        event_data={"email": "sum@example.com"},
    )
    _ingest(client, "sum-cold", "page_view", page_path="/")

    bare = client.get("/v1/analytics/summary", headers=AUTH)
    assert bare.status_code == 200, bare.text
    data = bare.json()
    assert data["ok"] is True
    assert data["total"] == 2
    assert data["with_email"] == 1
    assert data["counts"]["hot"] == 1
    assert data["counts"]["cold"] == 1
    assert "slash_reply" in data and data["slash_reply"]
    assert data["hot_sample_count"] >= 1
    assert data["hot_sample"][0].get("lead_email") in (None, "")
    assert data["hot_sample"][0]["has_email"] is True
    assert "sum@example.com" not in data["slash_reply"]

    rich = client.get(
        "/v1/analytics/summary",
        headers=AUTH,
        params={"include_emails": "true"},
    )
    assert rich.status_code == 200, rich.text
    rich_data = rich.json()
    assert rich_data["hot_sample"][0].get("lead_email") == "sum@example.com"
    assert "sum@example.com" in rich_data["slash_reply"]
    assert "last_seen" in rich_data
    assert "email_captures" in rich_data


def test_existing_db_gains_lead_whatsapp_column(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy_analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", db_path)
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE visitor_sessions (
            id TEXT PRIMARY KEY,
            ip_country TEXT,
            ip_city TEXT,
            first_seen_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            lead_status TEXT NOT NULL DEFAULT 'cold',
            lead_email TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    migrated = analytics_db._connect()
    migrated.close()
    check = sqlite3.connect(str(db_path))
    columns = {row[1] for row in check.execute("PRAGMA table_info(visitor_sessions)").fetchall()}
    check.close()
    assert "lead_whatsapp" in columns
