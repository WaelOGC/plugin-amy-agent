"""Tests for admin allowlisted tools, intent detection, and provider tool loop."""

from __future__ import annotations

import asyncio
from typing import Sequence
from unittest.mock import patch

import pytest

from app.providers.base import BaseProvider
from app.providers.tool_types import CompletionTurn, ToolCallRequest, ToolSpec
from app.schemas.messages import ChatMessage
from app.services.admin_chat_tools import (
    ADMIN_TOOL_NAMES,
    ADMIN_TOOL_SPECS,
    detect_admin_tool_intent,
    execute_admin_tool,
    run_admin_tool_loop,
)


_LIVE_ANALYTICS = {
    "ok": True,
    "total": 3,
    "counts": {"hot": 1, "warm": 1, "cold": 1, "other": 0},
    "with_email": 2,
    "email_captures": {"total": 2, "last_7d": 1},
    "last_seen": {
        "last_24h": 1,
        "last_7d": 2,
        "most_recent_at": 1.0,
        "most_recent": "1h ago",
    },
    "hot_sample": [],
    "hot_sample_count": 0,
    "empty": False,
    "summary": "Analytics summary: 3 lead sessions.",
}

_LIVE_SEO = {
    "ok": True,
    "total": 2,
    "verdicts": {"red": 1},
    "statuses": {"pending_approval": 1, "approved": 1},
    "open_count": 1,
    "fixed_count": 1,
    "rejected_count": 0,
    "empty": False,
    "summary": "SEO review summary: 2 stored checks.",
}

_LIVE_TASKS = {
    "ok": True,
    "open_tasks": 4,
    "urgent_tasks": 1,
    "in_progress": 2,
    "running": 0,
    "completed_this_week": 1,
    "team_completion_rate": 40,
    "empty": False,
    "summary": "Task Service summary: open=4, urgent=1.",
}


_LIVE_TRAFFIC = {
    "ok": True,
    "windows": {
        "all_time": {"pageviews": 12, "unique_sessions": 4},
        "last_24h": {"pageviews": 3, "unique_sessions": 2},
        "last_7d": {"pageviews": 8, "unique_sessions": 3},
        "last_30d": {"pageviews": 12, "unique_sessions": 4},
    },
    "top_paths_7d": [{"path": "/", "pageviews": 5, "unique_sessions": 3}],
    "top_paths_all": [{"path": "/", "pageviews": 5, "unique_sessions": 3}],
    "empty": False,
    "summary": "Traffic depth (page_view events): all_time pageviews=12.",
}

_LIVE_EMAIL_AUDIENCE = {
    "ok": True,
    "total": 2,
    "counts": {"hot": 1, "warm": 0, "cold": 1, "other": 0},
    "email_captures": {"total": 2, "last_7d": 1},
    "sample": [
        {
            "session_id": "abc",
            "session_id_short": "abc",
            "lead_status": "hot",
            "lead_email": "a@example.com",
        }
    ],
    "sample_count": 1,
    "empty": False,
    "summary": "Email audience (read-only): 2 leads with email.",
    "send_policy": "approve_then_send",
}


def test_allowlisted_tool_specs() -> None:
    assert ADMIN_TOOL_NAMES == {
        "analytics_summary",
        "analytics_leads_query",
        "seo_summary",
        "task_stats",
        "analytics_traffic",
        "email_audience_summary",
    }
    assert {t.name for t in ADMIN_TOOL_SPECS} == ADMIN_TOOL_NAMES


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", []),
        ("how many visitors?", ["analytics_summary"]),
        ("any urgent tasks?", ["task_stats"]),
        ("SEO open count?", ["seo_summary"]),
        (
            "visitors and urgent tasks and SEO open?",
            ["analytics_summary", "seo_summary", "task_stats"],
        ),
        ("show me hot leads with email", ["analytics_summary", "analytics_leads_query"]),
        ("/analytics please", ["analytics_summary"]),
        (
            "how many pageviews this week?",
            ["analytics_traffic"],
        ),
        (
            "how's traffic looking?",
            ["analytics_summary", "analytics_traffic"],
        ),
        (
            "email audience size?",
            ["email_audience_summary"],
        ),
        (
            "who can we email for marketing?",
            ["email_audience_summary"],
        ),
    ],
)
def test_detect_admin_tool_intent(text: str, expected: list[str]) -> None:
    assert detect_admin_tool_intent(text) == expected


def test_execute_analytics_and_seo_and_tasks() -> None:
    with (
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=_LIVE_ANALYTICS,
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_LIVE_SEO,
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            return_value=_LIVE_TASKS,
        ),
        patch(
            "app.services.admin_chat_tools.traffic_summary_for_chat",
            return_value=_LIVE_TRAFFIC,
        ),
        patch(
            "app.services.admin_chat_tools.email_audience_summary_for_chat",
            return_value=_LIVE_EMAIL_AUDIENCE,
        ),
    ):
        a = execute_admin_tool("analytics_summary", {})
        s = execute_admin_tool("seo_summary", {})
        t = execute_admin_tool("task_stats", {})
        tr = execute_admin_tool("analytics_traffic", {})
        e = execute_admin_tool("email_audience_summary", {})
    assert a["ok"] is True
    assert "total_sessions: 3" in a["chat_context"]
    assert s["ok"] is True
    assert "open (pending_approval): 1" in s["chat_context"]
    assert t["ok"] is True
    assert "urgent_tasks: 1" in t["chat_context"]
    assert tr["ok"] is True
    assert "page_view" in tr["chat_context"]
    assert "all_time:" in tr["chat_context"]
    assert e["ok"] is True
    assert e["send_policy"] == "approve_then_send"
    assert "Approve → Send" in e["chat_context"]
    assert "AgentMail" in e["chat_context"]


def test_execute_unknown_tool() -> None:
    result = execute_admin_tool("not_a_real_tool", {})
    assert result["ok"] is False
    assert result["error"] == "unknown_tool"


def test_analytics_leads_query_filters(tmp_path, monkeypatch) -> None:
    from app.db import analytics_db

    monkeypatch.setattr(analytics_db, "_DB_PATH", tmp_path / "analytics.db")
    analytics_db.create_session("sess-hot", ip_country="NL", ip_city="Den Haag")
    analytics_db.set_lead_status("sess-hot", "hot")
    analytics_db.set_lead_email("sess-hot", "hot@example.com")
    analytics_db.create_session("sess-cold", ip_country="BE", ip_city="Brussels")
    analytics_db.set_lead_status("sess-cold", "cold")

    result = execute_admin_tool(
        "analytics_leads_query",
        {"status": "hot", "has_email": True, "limit": 5},
    )
    assert result["ok"] is True
    assert result["count"] == 1
    assert result["leads"][0]["lead_email"] == "hot@example.com"
    assert "Visitor" in result["chat_context"]


def test_run_admin_tool_loop_executes_model_tool_calls() -> None:
    class _ToolingProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            if self.calls == 1:
                assert tools is not None
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(id="1", name="analytics_summary", arguments={}),
                        ToolCallRequest(id="2", name="task_stats", arguments={}),
                    ],
                )
            # After tool results are appended, return final answer.
            assert any(m.role == "tool" for m in messages)
            return CompletionTurn(text="3 visitors, 1 urgent task.")

    async def _run() -> tuple[str, list[str]]:
        with (
            patch(
                "app.services.admin_chat_tools.analytics_summary_for_chat",
                return_value=_LIVE_ANALYTICS,
            ),
            patch(
                "app.services.admin_chat_tools.task_service_summary_for_chat",
                return_value=_LIVE_TASKS,
            ),
        ):
            return await run_admin_tool_loop(
                _ToolingProvider(),
                [ChatMessage(role="user", content="stats please")],
                api_key="sk-test",
                model=None,
            )

    text, used = asyncio.run(_run())
    assert text == "3 visitors, 1 urgent task."
    assert used == ["analytics_summary", "task_stats"]


def test_run_admin_tool_loop_normalizes_empty_tool_call_ids() -> None:
    """Assistant tool_calls and tool results must share the same non-empty id."""

    class _EmptyIdProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0
            self.seen_ids: list[tuple[str, str]] = []

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            if self.calls == 1:
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(id="", name="seo_summary", arguments={}),
                    ],
                )
            assistant = next(m for m in messages if m.role == "assistant" and m.tool_calls)
            tool_msg = next(m for m in messages if m.role == "tool")
            self.seen_ids.append((assistant.tool_calls[0].id, tool_msg.tool_call_id or ""))
            return CompletionTurn(text="1 open SEO check.")

    async def _run() -> tuple[str, list[str], list[tuple[str, str]]]:
        provider = _EmptyIdProvider()
        with patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_LIVE_SEO,
        ):
            text, used = await run_admin_tool_loop(
                provider,
                [ChatMessage(role="user", content="SEO open?")],
                api_key="sk-test",
                model=None,
            )
        return text, used, provider.seen_ids

    text, used, seen = asyncio.run(_run())
    assert text == "1 open SEO check."
    assert used == ["seo_summary"]
    assert len(seen) == 1
    assistant_id, tool_id = seen[0]
    assert assistant_id
    assert assistant_id == tool_id


_SAMPLE_REC = {
    "finding": "1 hot lead session is active.",
    "evidence": "Based on 3 lead sessions in Amy Analytics.",
    "confidence": "low",
    "limitations": "Lead status is a heuristic, not a purchase guarantee.",
    "recommended_action": "Review the hot sample and follow up.",
}

_SAMPLE_REC_BLOCK = (
    "📊 Finding: 1 hot lead session is active.\n"
    "📈 Evidence: Based on 3 lead sessions in Amy Analytics.\n"
    "🎯 Confidence: low\n"
    "⚠️ Limitations: Lead status is a heuristic, not a purchase guarantee.\n"
    "✅ Suggested action: Review the hot sample and follow up."
)


def test_run_admin_tool_loop_appends_recommendations_block() -> None:
    """Tool-returned recommendations are appended verbatim after model text."""

    analytics_with_rec = {
        **_LIVE_ANALYTICS,
        "recommendations": [_SAMPLE_REC],
    }

    class _RecProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            if self.calls == 1:
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(id="1", name="analytics_summary", arguments={}),
                    ],
                )
            return CompletionTurn(text="There are 3 visitor sessions, including 1 hot.")

    async def _run() -> tuple[str, list[str]]:
        with patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=analytics_with_rec,
        ):
            return await run_admin_tool_loop(
                _RecProvider(),
                [ChatMessage(role="user", content="any hot leads?")],
                api_key="sk-test",
                model=None,
            )

    text, used = asyncio.run(_run())
    assert used == ["analytics_summary"]
    assert text.startswith("There are 3 visitor sessions, including 1 hot.")
    assert text.endswith(_SAMPLE_REC_BLOCK)
    assert text.count("📊 Finding:") == 1


def test_run_admin_tool_loop_dedupes_identical_recommendations() -> None:
    """Same finding/evidence from two tool calls appears once in the block."""

    analytics_with_rec = {
        **_LIVE_ANALYTICS,
        "recommendations": [_SAMPLE_REC],
    }
    traffic_with_same_rec = {
        **_LIVE_TRAFFIC,
        "recommendations": [_SAMPLE_REC],
    }

    class _DupProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            if self.calls == 1:
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(id="1", name="analytics_summary", arguments={}),
                        ToolCallRequest(id="2", name="analytics_traffic", arguments={}),
                    ],
                )
            return CompletionTurn(text="3 sessions; 12 pageviews.")

    async def _run() -> tuple[str, list[str]]:
        with (
            patch(
                "app.services.admin_chat_tools.analytics_summary_for_chat",
                return_value=analytics_with_rec,
            ),
            patch(
                "app.services.admin_chat_tools.traffic_summary_for_chat",
                return_value=traffic_with_same_rec,
            ),
        ):
            return await run_admin_tool_loop(
                _DupProvider(),
                [ChatMessage(role="user", content="leads and traffic?")],
                api_key="sk-test",
                model=None,
            )

    text, used = asyncio.run(_run())
    assert used == ["analytics_summary", "analytics_traffic"]
    assert text.count("📊 Finding:") == 1
    assert text.endswith(_SAMPLE_REC_BLOCK)


def test_run_admin_tool_loop_skips_empty_recommendations() -> None:
    """Empty recommendations list leaves model text unchanged."""

    analytics_empty_rec = {
        **_LIVE_ANALYTICS,
        "recommendations": [],
    }

    class _EmptyRecProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            if self.calls == 1:
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(id="1", name="analytics_summary", arguments={}),
                    ],
                )
            return CompletionTurn(text="3 visitor sessions on file.")

    async def _run() -> tuple[str, list[str]]:
        with patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=analytics_empty_rec,
        ):
            return await run_admin_tool_loop(
                _EmptyRecProvider(),
                [ChatMessage(role="user", content="visitor count?")],
                api_key="sk-test",
                model=None,
            )

    text, used = asyncio.run(_run())
    assert used == ["analytics_summary"]
    assert text == "3 visitor sessions on file."
    assert "📊" not in text


def test_run_admin_tool_loop_appends_on_exhausted_rounds() -> None:
    """Exhausted-rounds fallback also appends the structured block."""

    analytics_with_rec = {
        **_LIVE_ANALYTICS,
        "recommendations": [_SAMPLE_REC],
    }

    class _ExhaustProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            self.calls += 1
            # Always request tools while tools are offered (loop rounds).
            if tools is not None:
                return CompletionTurn(
                    text=None,
                    tool_calls=[
                        ToolCallRequest(
                            id=f"c{self.calls}",
                            name="analytics_summary",
                            arguments={},
                        ),
                    ],
                )
            # Final text-only turn after MAX_TOOL_ROUNDS exhausted.
            return CompletionTurn(text="Still 3 sessions after several looks.")

    async def _run() -> tuple[str, list[str]]:
        with patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=analytics_with_rec,
        ):
            return await run_admin_tool_loop(
                _ExhaustProvider(),
                [ChatMessage(role="user", content="hot leads?")],
                api_key="sk-test",
                model=None,
                max_rounds=2,
            )

    text, used = asyncio.run(_run())
    assert used == ["analytics_summary"]
    assert text.startswith("Still 3 sessions after several looks.")
    assert text.endswith(_SAMPLE_REC_BLOCK)
    assert text.count("📊 Finding:") == 1


def test_run_admin_tool_loop_seed_recommendations_without_tool_calls() -> None:
    """Intent-seeded recommendations append even when the model calls no tools."""

    class _NoToolProvider(BaseProvider):
        provider_id = "openai"
        default_model = "gpt-4o-mini"
        supports_tools = True

        async def complete(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
        ) -> str:
            return "fallback"

        async def complete_turn(
            self,
            messages: Sequence[ChatMessage],
            api_key: str,
            model: str | None = None,
            tools: Sequence[ToolSpec] | None = None,
        ) -> CompletionTurn:
            return CompletionTurn(text="1 hot lead among 3 sessions.")

    async def _run() -> tuple[str, list[str]]:
        return await run_admin_tool_loop(
            _NoToolProvider(),
            [ChatMessage(role="user", content="hot leads?")],
            api_key="sk-test",
            model=None,
            seed_recommendations=[_SAMPLE_REC],
        )

    text, used = asyncio.run(_run())
    assert used == []
    assert text.endswith(_SAMPLE_REC_BLOCK)
