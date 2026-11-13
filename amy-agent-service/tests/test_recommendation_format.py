"""Evidence-based recommendation format + conclusion wiring (RI concept 4)."""

from __future__ import annotations

import os
import time

import pytest

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import analytics_db, seo_tasks_db  # noqa: E402
from app.services.admin_chat_tools import execute_admin_tool  # noqa: E402
from app.services.analytics_summary import (  # noqa: E402
    build_analytics_recommendations,
    build_analytics_summary,
    format_analytics_chat_context,
    format_analytics_slash_reply,
)
from app.services.lead_scoring import (  # noqa: E402
    build_lead_status_recommendation,
    compute_lead_status,
)
from app.services.recommendation_format import (  # noqa: E402
    Recommendation,
    assess_confidence,
    format_recommendation,
    format_recommendations,
)
from app.services.seo_task_summary import (  # noqa: E402
    build_seo_recommendations,
    build_seo_review_summary,
    format_seo_chat_context,
)
from app.services.traffic_summary import (  # noqa: E402
    build_traffic_recommendations,
    build_traffic_summary,
    format_traffic_chat_context,
)

get_settings.cache_clear()


@pytest.fixture
def analytics_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "analytics.db"
    monkeypatch.setattr(analytics_db, "_DB_PATH", path)
    return path


@pytest.fixture
def seo_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "seo_tasks.db"
    monkeypatch.setattr(seo_tasks_db, "_DB_PATH", path)
    return path


# --- confidence rule -------------------------------------------------------


def test_assess_confidence_high() -> None:
    assert assess_confidence(data_points=30, span_days=7.0) == "high"
    assert assess_confidence(data_points=100, span_days=14.0, missing_fraction=0.1) == "high"


def test_assess_confidence_medium() -> None:
    assert assess_confidence(data_points=15, span_days=7.0) == "medium"
    assert assess_confidence(data_points=40, span_days=3.0) == "medium"
    assert assess_confidence(data_points=40, span_days=10.0, missing_fraction=0.3) == "medium"


def test_assess_confidence_low() -> None:
    assert assess_confidence(data_points=9, span_days=30.0) == "low"
    assert assess_confidence(data_points=0, span_days=0.0) == "low"
    assert assess_confidence(data_points=50, span_days=30.0, missing_fraction=0.6) == "low"


# --- formatter --------------------------------------------------------------


def test_format_recommendation_structure() -> None:
    rec = Recommendation(
        finding="Hot leads need follow-up.",
        evidence="3 hot sessions in last 7d (n=40).",
        confidence="medium",
        limitations="Rule-based intent only.",
        recommended_action="Review Amy → Analytics hot sample.",
    )
    text = format_recommendation(rec)
    assert "📊 Finding: Hot leads need follow-up." in text
    assert "📈 Evidence: 3 hot sessions in last 7d (n=40)." in text
    assert "🎯 Confidence: medium" in text
    assert "⚠️ Limitations: Rule-based intent only." in text
    assert "✅ Suggested action: Review Amy → Analytics hot sample." in text


def test_format_recommendation_omits_action_when_none() -> None:
    rec = Recommendation(
        finding="Session is cold.",
        evidence="1 page_view only.",
        confidence="low",
        limitations="Sparse tracking.",
        recommended_action=None,
    )
    text = format_recommendation(rec)
    assert "Suggested action" not in text
    assert format_recommendations([rec]) == text


def test_recommendation_rejects_empty_finding() -> None:
    with pytest.raises(ValueError, match="finding"):
        Recommendation(
            finding="  ",
            evidence="n=1",
            confidence="low",
            limitations="n/a",
        )


# --- lead_scoring conclusion ------------------------------------------------


def test_lead_status_recommendation_hot(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("rec-hot", now=now - 100)
    analytics_db.insert_event(
        session_id="rec-hot",
        event_type="contact_form_abandoned",
        now=now - 50,
    )
    assert compute_lead_status("rec-hot") == "hot"
    rec = build_lead_status_recommendation("rec-hot", now=now)
    assert isinstance(rec, Recommendation)
    assert "hot" in rec.finding.lower()
    assert "contact_form_abandoned" in rec.evidence
    assert rec.confidence in {"high", "medium", "low"}
    assert rec.limitations.strip()
    assert rec.recommended_action


def test_lead_status_recommendation_warm_and_cold(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("rec-warm", now=now - 100)
    analytics_db.insert_event(
        session_id="rec-warm",
        event_type="widget_message_sent",
        now=now - 40,
    )
    warm = build_lead_status_recommendation("rec-warm", now=now)
    assert "warm" in warm.finding.lower()
    assert warm.evidence.strip()
    assert warm.limitations.strip()

    analytics_db.create_session("rec-cold", now=now - 100)
    analytics_db.insert_event(
        session_id="rec-cold",
        event_type="page_view",
        page_path="/",
        now=now - 40,
    )
    cold = build_lead_status_recommendation("rec-cold", now=now)
    assert "cold" in cold.finding.lower()
    assert cold.evidence.strip()
    assert cold.recommended_action is None


# --- analytics_summary conclusion vs factual --------------------------------


def test_analytics_recommendation_when_hot(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("a-hot", now=now - 60)
    analytics_db.set_lead_status("a-hot", "hot")
    analytics_db.set_lead_email("a-hot", "hot@example.com")
    analytics_db.create_session("a-cold", now=now - 120)
    analytics_db.set_lead_status("a-cold", "cold")

    snap = build_analytics_summary(include_sample=True, include_emails_in_sample=True)
    assert snap["ok"] is True
    assert len(snap["recommendations"]) == 1
    rec = snap["recommendations"][0]
    assert rec["finding"]
    assert rec["evidence"]
    assert "hot" in rec["finding"].lower()
    assert rec["confidence"] in {"high", "medium", "low"}
    assert rec["limitations"]

    ctx = format_analytics_chat_context(snap)
    assert "📊 Finding:" in ctx
    assert "Recommendations:" in ctx

    # Factual slash reply stays count-based (no recommendation block).
    slash = format_analytics_slash_reply(snap)
    assert "Sessions:" in slash
    assert "📊 Finding:" not in slash


def test_analytics_no_recommendation_without_hot(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("only-cold", now=now)
    analytics_db.set_lead_status("only-cold", "cold")
    snap = build_analytics_summary()
    assert snap["recommendations"] == []
    assert "📊 Finding:" not in format_analytics_chat_context(snap)
    # Direct builder stays empty.
    assert (
        build_analytics_recommendations(
            total=1,
            counts={"hot": 0, "warm": 0, "cold": 1, "other": 0},
            with_email=0,
            last_seen={"last_7d": 1},
            leads=[{"lead_status": "cold"}],
        )
        == []
    )


def test_analytics_factual_empty_unchanged(analytics_tmp) -> None:
    snap = build_analytics_summary()
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert snap["recommendations"] == []
    ctx = format_analytics_chat_context(snap)
    assert "EMPTY" in ctx
    assert "📊 Finding:" not in ctx
    slash = format_analytics_slash_reply(snap)
    assert "no visitor sessions recorded yet" in slash.lower()


# --- seo_task_summary conclusion --------------------------------------------


def test_seo_recommendation_when_open(seo_tmp) -> None:
    seo_tasks_db.create_check(
        wp_post_id=1,
        post_type="post",
        title="A",
        verdict="red",
        findings=[{"field": "meta_description", "issue": "missing"}],
    )
    snap = build_seo_review_summary()
    assert snap["open_count"] == 1
    assert len(snap["recommendations"]) == 1
    rec = snap["recommendations"][0]
    assert "pending_approval" in rec["finding"] or "open" in rec["finding"].lower()
    assert rec["evidence"]
    assert rec["limitations"]
    assert rec["recommended_action"]
    ctx = format_seo_chat_context(snap)
    assert "📊 Finding:" in ctx


def test_seo_no_recommendation_when_no_open(seo_tmp) -> None:
    row = seo_tasks_db.create_check(
        wp_post_id=2,
        post_type="post",
        title="B",
        verdict="green",
        findings=[],
    )
    seo_tasks_db.approve_check(row["check_id"])
    snap = build_seo_review_summary()
    assert snap["open_count"] == 0
    assert snap["recommendations"] == []
    assert "📊 Finding:" not in format_seo_chat_context(snap)
    assert (
        build_seo_recommendations(
            total=1,
            open_count=0,
            fixed_count=1,
            rejected_count=0,
            verdicts={"green": 1},
        )
        == []
    )


# --- traffic_summary conclusion ---------------------------------------------


def test_traffic_trend_recommendation(analytics_tmp) -> None:
    # 7d total 70 pageviews → daily avg 10; 24h=30 → 3× spike.
    recs = build_traffic_recommendations(
        last_24h={"pageviews": 30, "unique_sessions": 10},
        last_7d={"pageviews": 70, "unique_sessions": 40},
        top_paths_7d=[{"path": "/a", "pageviews": 20, "unique_sessions": 10}],
    )
    findings = " ".join(r.finding.lower() for r in recs)
    assert "above" in findings
    for r in recs:
        assert r.finding.strip() and r.evidence.strip() and r.limitations.strip()


def test_traffic_dominance_recommendation(analytics_tmp) -> None:
    recs = build_traffic_recommendations(
        last_24h={"pageviews": 5, "unique_sessions": 2},
        last_7d={"pageviews": 40, "unique_sessions": 20},
        top_paths_7d=[
            {"path": "/pricing", "pageviews": 30, "unique_sessions": 15},
            {"path": "/about", "pageviews": 10, "unique_sessions": 5},
        ],
    )
    assert any("dominates" in r.finding.lower() for r in recs)
    assert any("/pricing" in r.evidence for r in recs)


def test_traffic_no_recommendation_on_quiet_balanced(analytics_tmp) -> None:
    # 24h near daily avg; top path < 50%.
    recs = build_traffic_recommendations(
        last_24h={"pageviews": 10, "unique_sessions": 5},
        last_7d={"pageviews": 70, "unique_sessions": 40},
        top_paths_7d=[
            {"path": "/a", "pageviews": 20, "unique_sessions": 10},
            {"path": "/b", "pageviews": 20, "unique_sessions": 10},
            {"path": "/c", "pageviews": 30, "unique_sessions": 15},
        ],
    )
    assert recs == []


def test_traffic_factual_summary_unchanged_without_judgment(analytics_tmp) -> None:
    now = time.time()
    analytics_db.create_session("t-fact", now=now - 10)
    analytics_db.insert_event(
        session_id="t-fact",
        event_type="page_view",
        page_path="/only",
        now=now - 5,
    )
    snap = build_traffic_summary(now=now)
    assert snap["ok"] is True
    assert "pageviews=" in snap["summary"]
    # Single pageview cannot meet trend (need 7d ≥10) but may dominate — that's a conclusion.
    # Ensure factual chat lines still present either way.
    ctx = format_traffic_chat_context(snap)
    assert "all_time:" in ctx
    assert "page_view" in ctx


# --- admin chat wiring ------------------------------------------------------


def test_admin_tool_surfaces_formatted_recommendations(analytics_tmp, seo_tmp) -> None:
    now = time.time()
    analytics_db.create_session("tool-hot", now=now)
    analytics_db.set_lead_status("tool-hot", "hot")
    result = execute_admin_tool("analytics_summary", {})
    assert result["ok"] is True
    assert result["recommendations"]
    assert "📊 Finding:" in result["chat_context"]

    seo_tasks_db.create_check(
        wp_post_id=9,
        post_type="post",
        title="Open",
        verdict="orange",
        findings=[{"field": "title", "issue": "weak"}],
    )
    seo = execute_admin_tool("seo_summary", {})
    assert seo["recommendations"]
    assert "📊 Finding:" in seo["chat_context"]
