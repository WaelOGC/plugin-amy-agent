"""Unit tests for shared analytics summary helper (P0/P1 admin chat + Task P4)."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import analytics_db  # noqa: E402
from app.services.analytics_summary import (  # noqa: E402
    analytics_summary_for_chat,
    build_analytics_summary,
    format_analytics_chat_context,
    format_analytics_slash_reply,
    format_last_seen_ago,
)

get_settings.cache_clear()


@pytest.fixture
def analytics_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", path)
    return path


def test_format_last_seen_ago_windows() -> None:
    now = 1_700_000_000.0
    assert format_last_seen_ago(now - 10, now=now) == "just now"
    assert format_last_seen_ago(now - 120, now=now) == "2m ago"
    assert format_last_seen_ago(now - 7200, now=now) == "2h ago"
    assert format_last_seen_ago(now - 3 * 86400, now=now) == "3d ago"


def test_build_summary_empty_db(analytics_tmp) -> None:
    snap = build_analytics_summary(include_sample=True)
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert snap["total"] == 0
    assert snap["with_email"] == 0
    assert snap["counts"] == {"hot": 0, "warm": 0, "cold": 0, "other": 0}
    assert snap["sample_count"] == 0
    assert snap["hot_sample_count"] == 0
    assert snap["email_captures"] == {"total": 0, "last_7d": 0}
    assert snap["last_seen"]["last_24h"] == 0
    ctx = format_analytics_chat_context(snap)
    assert "EMPTY" in ctx
    assert "No visitor sessions recorded yet" in ctx
    assert "no visitor sessions recorded yet" in format_analytics_slash_reply(snap).lower()


def test_build_summary_counts_live_leads(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("s-hot", now=now - 60)
    analytics_db.set_lead_status("s-hot", "hot")
    analytics_db.set_lead_email("s-hot", "a@example.com")
    analytics_db.insert_event(
        session_id="s-hot",
        event_type="submit_idea_contact_captured",
        event_data={"email": "a@example.com"},
        now=now - 60,
    )
    analytics_db.create_session("s-warm", now=now - 2 * 86400)
    analytics_db.set_lead_status("s-warm", "warm")
    analytics_db.create_session("s-cold", now=now - 10 * 86400)

    snap = analytics_summary_for_chat()
    assert snap["ok"] is True
    assert snap["empty"] is False
    assert snap["total"] == 3
    assert snap["counts"]["hot"] == 1
    assert snap["counts"]["warm"] == 1
    assert snap["counts"]["cold"] == 1
    assert snap["with_email"] == 1
    assert snap["email_captures"]["total"] >= 1
    assert snap["last_seen"]["last_24h"] >= 1
    assert snap["last_seen"]["most_recent"] is not None
    assert snap["hot_sample_count"] == 1
    assert snap["hot_sample"][0]["lead_email"] == "a@example.com"
    assert snap["hot_sample"][0]["has_email"] is True

    ctx = format_analytics_chat_context(snap)
    assert "total_sessions: 3" in ctx
    assert "hot: 1" in ctx
    assert "with_email: 1" in ctx
    assert "email_captures:" in ctx
    assert "last_seen windows:" in ctx
    assert "a@example.com" in ctx
    assert "hot lead sample" in ctx

    slash = format_analytics_slash_reply(snap)
    assert "With email: 1" in slash
    assert "a@example.com" in slash


def test_public_sample_hides_emails(analytics_tmp) -> None:
    analytics_db.create_session("s-hot")
    analytics_db.set_lead_status("s-hot", "hot")
    analytics_db.set_lead_email("s-hot", "secret@example.com")
    snap = build_analytics_summary(include_sample=True, include_emails_in_sample=False)
    assert snap["hot_sample_count"] == 1
    assert "lead_email" not in snap["hot_sample"][0]
    assert snap["hot_sample"][0]["has_email"] is True
    slash = format_analytics_slash_reply(snap)
    assert "secret@example.com" not in slash
    assert "(email on file)" in slash


def test_build_summary_db_error_honest(analytics_tmp) -> None:
    with patch(
        "app.services.analytics_summary.analytics_db.list_leads",
        side_effect=RuntimeError("db down"),
    ):
        snap = build_analytics_summary()
    assert snap["ok"] is False
    assert "unavailable" in snap["summary"].lower()
    ctx = format_analytics_chat_context(snap)
    assert "UNAVAILABLE" in ctx
    assert "could not reach Analytics" in ctx
    assert "unavailable" in format_analytics_slash_reply(snap).lower()
