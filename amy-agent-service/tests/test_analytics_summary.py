"""Unit tests for shared analytics summary helper (P0 admin chat + Task P4)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import analytics_db  # noqa: E402
from app.services.analytics_summary import (  # noqa: E402
    analytics_summary_for_chat,
    build_analytics_summary,
    format_analytics_chat_context,
)

get_settings.cache_clear()


@pytest.fixture
def analytics_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", path)
    return path


def test_build_summary_empty_db(analytics_tmp) -> None:
    snap = build_analytics_summary(include_sample=True)
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert snap["total"] == 0
    assert snap["with_email"] == 0
    assert snap["counts"] == {"hot": 0, "warm": 0, "cold": 0, "other": 0}
    assert snap["sample_count"] == 0
    ctx = format_analytics_chat_context(snap)
    assert "EMPTY" in ctx
    assert "No visitor sessions recorded yet" in ctx


def test_build_summary_counts_live_leads(analytics_tmp) -> None:
    analytics_db.create_session("s-hot")
    analytics_db.set_lead_status("s-hot", "hot")
    analytics_db.set_lead_email("s-hot", "a@example.com")
    analytics_db.create_session("s-warm")
    analytics_db.set_lead_status("s-warm", "warm")
    analytics_db.create_session("s-cold")

    snap = analytics_summary_for_chat()
    assert snap["ok"] is True
    assert snap["empty"] is False
    assert snap["total"] == 3
    assert snap["counts"]["hot"] == 1
    assert snap["counts"]["warm"] == 1
    assert snap["counts"]["cold"] == 1
    assert snap["with_email"] == 1
    ctx = format_analytics_chat_context(snap)
    assert "total_sessions: 3" in ctx
    assert "hot: 1" in ctx
    assert "with_email: 1" in ctx


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
