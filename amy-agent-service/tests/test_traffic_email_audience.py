"""P4 traffic depth (page_view) + email audience read-only summary."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import analytics_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.email_audience_summary import (  # noqa: E402
    build_email_audience_summary,
    format_email_audience_chat_context,
)
from app.services.traffic_summary import (  # noqa: E402
    build_traffic_summary,
    format_traffic_chat_context,
)

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def analytics_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", path)
    return path


@pytest.fixture
def client(analytics_tmp) -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)


def test_count_page_views_and_top_paths(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("s1", now=now - 100)
    analytics_db.create_session("s2", now=now - 50)
    analytics_db.insert_event(
        session_id="s1", event_type="page_view", page_path="/", now=now - 90
    )
    analytics_db.insert_event(
        session_id="s1", event_type="page_view", page_path="/about", now=now - 80
    )
    analytics_db.insert_event(
        session_id="s2", event_type="page_view", page_path="/", now=now - 40
    )
    analytics_db.insert_event(
        session_id="s2",
        event_type="widget_opened",
        page_path="/",
        now=now - 30,
    )

    all_time = analytics_db.count_page_views()
    assert all_time == {"pageviews": 3, "unique_sessions": 2}
    recent = analytics_db.count_page_views(since=now - 60)
    assert recent["pageviews"] == 1
    assert recent["unique_sessions"] == 1

    top = analytics_db.top_page_paths(limit=5)
    assert top[0]["path"] == "/"
    assert top[0]["pageviews"] == 2
    assert top[0]["unique_sessions"] == 2
    assert top[1]["path"] == "/about"
    assert top[1]["pageviews"] == 1


def test_build_traffic_summary_live(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("t1", now=now - 10)
    analytics_db.insert_event(
        session_id="t1", event_type="page_view", page_path="/pricing", now=now - 5
    )
    snap = build_traffic_summary(now=now)
    assert snap["ok"] is True
    assert snap["empty"] is False
    assert snap["windows"]["all_time"]["pageviews"] == 1
    assert snap["windows"]["last_24h"]["pageviews"] == 1
    assert any(p["path"] == "/pricing" for p in snap["top_paths_all"])
    ctx = format_traffic_chat_context(snap)
    assert "page_view" in ctx
    assert "all_time:" in ctx
    assert "/pricing" in ctx


def test_build_traffic_summary_empty_and_error(analytics_tmp) -> None:
    snap = build_traffic_summary()
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert "EMPTY" in format_traffic_chat_context(snap)

    with patch(
        "app.services.traffic_summary.analytics_db.count_page_views",
        side_effect=RuntimeError("db down"),
    ):
        bad = build_traffic_summary()
    assert bad["ok"] is False
    assert "UNAVAILABLE" in format_traffic_chat_context(bad)


def test_email_audience_summary_live(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("e-hot", now=now)
    analytics_db.set_lead_status("e-hot", "hot")
    analytics_db.set_lead_email("e-hot", "hot@example.com")
    analytics_db.insert_event(
        session_id="e-hot",
        event_type="submit_idea_contact_captured",
        event_data={"email": "hot@example.com"},
        now=now,
    )
    analytics_db.create_session("e-cold", now=now)
    analytics_db.set_lead_status("e-cold", "cold")
    analytics_db.set_lead_email("e-cold", "cold@example.com")
    analytics_db.create_session("no-mail", now=now)

    snap = build_email_audience_summary(now=now)
    assert snap["ok"] is True
    assert snap["total"] == 2
    assert snap["counts"]["hot"] == 1
    assert snap["counts"]["cold"] == 1
    assert snap["send_policy"] == "approve_then_send"
    assert snap["sample_count"] == 2
    ctx = format_email_audience_chat_context(snap)
    assert "audience_total: 2" in ctx
    assert "Approve → Send" in ctx
    assert "AgentMail" in ctx
    assert "hot@example.com" in ctx


def test_email_audience_empty_and_error(analytics_tmp) -> None:
    snap = build_email_audience_summary()
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert "EMPTY" in format_email_audience_chat_context(snap)

    with patch(
        "app.services.email_audience_summary.analytics_db.list_leads",
        side_effect=RuntimeError("db down"),
    ):
        bad = build_email_audience_summary()
    assert bad["ok"] is False
    assert "UNAVAILABLE" in format_email_audience_chat_context(bad)


def test_traffic_and_email_audience_endpoints(client: TestClient) -> None:
    now = time.time()
    analytics_db.create_session("api-s", now=now)
    analytics_db.insert_event(
        session_id="api-s", event_type="page_view", page_path="/blog", now=now
    )
    analytics_db.set_lead_email("api-s", "api@example.com")
    analytics_db.set_lead_status("api-s", "warm")

    traffic = client.get("/v1/analytics/traffic", headers=AUTH)
    assert traffic.status_code == 200, traffic.text
    body = traffic.json()
    assert body["ok"] is True
    assert body["windows"]["all_time"]["pageviews"] >= 1
    assert any(p["path"] == "/blog" for p in body["top_paths_all"])

    audience = client.get("/v1/analytics/email-audience", headers=AUTH)
    assert audience.status_code == 200, audience.text
    abody = audience.json()
    assert abody["ok"] is True
    assert abody["total"] == 1
    assert abody["send_policy"] == "approve_then_send"
    assert abody["sample"][0]["lead_email"] == "api@example.com"


def test_endpoints_require_secret(client: TestClient) -> None:
    assert client.get("/v1/analytics/traffic").status_code == 401
    assert client.get("/v1/analytics/email-audience").status_code == 401
