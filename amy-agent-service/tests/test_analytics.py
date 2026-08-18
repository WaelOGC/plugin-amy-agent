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


def test_leads_filter_and_timeline(client: TestClient) -> None:
    _ingest(client, "sess-a", "page_view", page_path="/")
    _ingest(client, "sess-b", "widget_message_sent")
    warm = client.get("/v1/analytics/leads", headers=AUTH, params={"status": "warm"}).json()
    ids = {item["session_id"] for item in warm["leads"]}
    assert ids == {"sess-b"}

    timeline = client.get("/v1/analytics/leads/sess-b/events", headers=AUTH)
    assert timeline.status_code == 200
    assert timeline.json()["events"][0]["event_type"] == "widget_message_sent"


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
