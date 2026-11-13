"""Allowlisted admin chat tools + intent auto-invoke + provider tool loop (P3).

Maps Dashboard/Telegram ``mode: admin`` questions onto the same Analytics / SEO /
Task Service read paths Overview and P0–P2 snapshots already use. Slash commands
remain a WP/Telegram shortcut outside this loop.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Sequence

from app.db import analytics_db
from app.providers.base import BaseProvider
from app.providers.tool_types import CompletionTurn, ToolCallRequest, ToolSpec
from app.schemas.messages import ChatMessage, ToolCallPart
from app.services.analytics_summary import (
    analytics_summary_for_chat,
    format_analytics_chat_context,
    format_last_seen_ago,
)
from app.services.email_audience_summary import (
    email_audience_summary_for_chat,
    format_email_audience_chat_context,
)
from app.services.seo_task_summary import (
    format_seo_chat_context,
    format_task_service_chat_context,
    seo_review_summary_for_chat,
    task_service_summary_for_chat,
)
from app.services.traffic_summary import (
    format_traffic_chat_context,
    traffic_summary_for_chat,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
_LEADS_QUERY_DEFAULT_LIMIT = 10
_LEADS_QUERY_MAX_LIMIT = 25

ADMIN_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="analytics_summary",
        description=(
            "Live Amy Analytics lead-session summary: total sessions, hot/warm/cold, "
            "with_email, Submit Idea / contact email captures, last-seen windows, "
            "and an admin-safe hot lead sample. Use for visitors / traffic / leads / "
            "hot leads / emails captured questions. Not Google Analytics pageviews."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="analytics_leads_query",
        description=(
            "Query Amy Analytics lead sessions with optional filters "
            "(status=hot|warm|cold, has_email, limit). Returns a compact admin-safe "
            "list (email OK on this staff channel). Use after analytics_summary when "
            "the teammate wants a filtered list or sample."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["hot", "warm", "cold"],
                    "description": "Optional lead_status filter.",
                },
                "has_email": {
                    "type": "boolean",
                    "description": "When true, only sessions with a stored lead email.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _LEADS_QUERY_MAX_LIMIT,
                    "description": f"Max rows (default {_LEADS_QUERY_DEFAULT_LIMIT}).",
                },
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="seo_summary",
        description=(
            "Live SEO Tasks summary: total stored checks, open (pending_approval), "
            "fixed (approved), rejected, verdict/status breakdowns. Report-only — "
            "cannot approve or write SEO from chat."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="task_stats",
        description=(
            "Live Task Service board stats: open_tasks, urgent_tasks, in_progress, "
            "running (Amy execution), completed_this_week, team_completion_rate. "
            "Report-only — cannot reassign or mark done from chat."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="analytics_traffic",
        description=(
            "Live Amy Analytics page_view traffic depth: pageviews and unique "
            "sessions for all-time / 24h / 7d / 30d, plus top page paths. Use for "
            "site traffic, pageviews, page views over time, or top/most-visited "
            "pages. Not Google Analytics. Lead hot/warm/cold stays on analytics_summary."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="email_audience_summary",
        description=(
            "Read-only Email Marketing audience: count of Analytics leads with "
            "email, hot/warm/cold breakdown, recent email captures, small admin "
            "sample. Report-only — cannot send; Approve → Send stays in Email "
            "Marketing (FluentSMTP). No AgentMail."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
]

ADMIN_TOOL_NAMES = frozenset(spec.name for spec in ADMIN_TOOL_SPECS)

_ANALYTICS_INTENT = re.compile(
    r"\b("
    r"analytics|/analytics|"
    r"visitor|visitors|traffic|lead|leads|"
    r"hot\s+lead|warm\s+lead|cold\s+lead|"
    r"with[_\s-]?email|emails?\s+captured|email\s+capture|"
    r"submit\s+idea|last[_\s-]?seen|sessions?"
    r")\b",
    re.IGNORECASE,
)
_LEADS_QUERY_INTENT = re.compile(
    r"\b("
    r"list\s+(hot\s+)?leads|show\s+(me\s+)?(hot\s+)?leads|"
    r"hot\s+sample|which\s+leads|lead\s+list|leads\s+with\s+email|"
    r"filter\s+leads|who\s+are\s+the\s+hot"
    r")\b",
    re.IGNORECASE,
)
_TRAFFIC_INTENT = re.compile(
    r"\b("
    r"pageviews?|page\s+views?|site\s+traffic|traffic\s+depth|traffic|"
    r"top\s+pages?|most[_\s-]?visited|visited\s+pages?|"
    r"page_view|views\s+over\s+time|how\s+many\s+page"
    r")\b",
    re.IGNORECASE,
)
_EMAIL_AUDIENCE_INTENT = re.compile(
    r"\b("
    r"email\s+audience|marketing\s+audience|email\s+list|"
    r"audience\s+size|who\s+can\s+we\s+email|emails?\s+on\s+file|"
    r"marketing\s+list|email\s+marketing\s+audience|"
    r"how\s+many\s+(have|with)\s+email"
    r")\b",
    re.IGNORECASE,
)
_SEO_INTENT = re.compile(
    r"\b("
    r"seo|/seo|"
    r"pending[_\s-]?approval|yoast|meta\s+title|meta\s+description|"
    r"open\s+(seo\s+)?(issues?|checks?)|seo\s+(open|issues?|checks?|tasks?)"
    r")\b",
    re.IGNORECASE,
)
_TASK_INTENT = re.compile(
    r"\b("
    r"task\s+service|/tasks?|"
    r"urgent\s+tasks?|open\s+tasks?|in[_\s-]?progress|"
    r"board\s+stats?|any\s+urgent|running\s+tasks?|amy\s+execution|"
    r"completed\s+this\s+week|team\s+completion"
    r")\b",
    re.IGNORECASE,
)


def detect_admin_tool_intent(user_text: str) -> list[str]:
    """Return allowlisted tool names to auto-invoke from free-text intent.

    Slash shortcuts stay in WP/Telegram; this covers Amy-the-Leader auto-invoke
    without requiring the model to request tools first.
    """
    text = (user_text or "").strip()
    if not text:
        return []
    names: list[str] = []
    if _ANALYTICS_INTENT.search(text):
        names.append("analytics_summary")
    if _LEADS_QUERY_INTENT.search(text):
        if "analytics_leads_query" not in names:
            names.append("analytics_leads_query")
        if "analytics_summary" not in names:
            names.insert(0, "analytics_summary")
    if _TRAFFIC_INTENT.search(text):
        if "analytics_traffic" not in names:
            names.append("analytics_traffic")
        # Plain "traffic" also matches analytics intent; keep both when pageviews asked.
        if "analytics_summary" not in names and re.search(
            r"\b(traffic|visitors?)\b", text, re.IGNORECASE
        ):
            names.insert(0, "analytics_summary")
    if _EMAIL_AUDIENCE_INTENT.search(text):
        names.append("email_audience_summary")
    if _SEO_INTENT.search(text):
        names.append("seo_summary")
    if _TASK_INTENT.search(text):
        names.append("task_stats")
    # Preserve order, drop unknowns / dupes.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name in ADMIN_TOOL_NAMES and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _session_short(session_id: str | None) -> str:
    raw = str(session_id or "").replace("-", "")
    return raw[:8] if raw else "unknown"


def _run_analytics_summary(_args: dict[str, Any]) -> dict[str, Any]:
    snap = analytics_summary_for_chat()
    return {
        "ok": bool(snap.get("ok")),
        "tool": "analytics_summary",
        "snapshot": snap,
        "chat_context": format_analytics_chat_context(snap),
        "summary": snap.get("summary"),
        "recommendations": snap.get("recommendations") or [],
        "error": snap.get("error"),
    }


def _run_analytics_leads_query(args: dict[str, Any]) -> dict[str, Any]:
    status = args.get("status")
    if status is not None:
        status = str(status).strip().lower() or None
    has_email = args.get("has_email")
    if has_email is not None and not isinstance(has_email, bool):
        has_email = str(has_email).strip().lower() in {"1", "true", "yes"}
    try:
        limit = int(args.get("limit") or _LEADS_QUERY_DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = _LEADS_QUERY_DEFAULT_LIMIT
    limit = max(1, min(limit, _LEADS_QUERY_MAX_LIMIT))

    try:
        rows = analytics_db.list_leads(
            status=status,  # type: ignore[arg-type]
            has_email=has_email,
        )
    except ValueError as exc:
        return {
            "ok": False,
            "tool": "analytics_leads_query",
            "error": str(exc),
            "leads": [],
            "count": 0,
            "chat_context": (
                "analytics_leads_query failed (invalid filter). "
                "Do NOT invent leads. Ask the teammate to clarify status/has_email."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("analytics_leads_query failed")
        return {
            "ok": False,
            "tool": "analytics_leads_query",
            "error": str(exc) or exc.__class__.__name__,
            "leads": [],
            "count": 0,
            "chat_context": (
                "analytics_leads_query UNAVAILABLE (service/connection). "
                "Say you could not reach Analytics just now — not that you lack access. "
                "Do NOT invent leads."
            ),
        }

    leads: list[dict[str, Any]] = []
    for row in rows[:limit]:
        email = (row.get("lead_email") or "").strip() or None
        leads.append(
            {
                "session_id": row.get("id"),
                "session_id_short": _session_short(row.get("id")),
                "lead_status": row.get("lead_status"),
                "has_email": bool(email),
                "lead_email": email,
                "last_seen_at": float(row.get("last_seen_at") or 0),
                "last_seen": format_last_seen_ago(float(row.get("last_seen_at") or 0)),
                "ip_country": row.get("ip_country"),
                "ip_city": row.get("ip_city"),
            }
        )

    lines = [
        f"analytics_leads_query result (limit={limit}, "
        f"status={status or 'any'}, has_email={has_email}):",
        f"- matched_returned: {len(leads)} (of {len(rows)} matching filter)",
    ]
    if not leads:
        lines.append("- (none) — say no matching visitor sessions, not that you lack access.")
    else:
        for item in leads:
            email_bit = item["lead_email"] or (
                "(email on file)" if item["has_email"] else "(no email)"
            )
            geo_parts = [p for p in (item.get("ip_city"), item.get("ip_country")) if p]
            geo = ", ".join(str(p) for p in geo_parts) if geo_parts else "unknown location"
            lines.append(
                f"  • Visitor {item['session_id_short']}: status={item['lead_status']}; "
                f"{email_bit}; {geo}; last_seen={item['last_seen']}"
            )
    lines.append("Emails OK to share with this admin teammate. Do NOT invent other leads.")

    return {
        "ok": True,
        "tool": "analytics_leads_query",
        "filters": {"status": status, "has_email": has_email, "limit": limit},
        "total_matching": len(rows),
        "count": len(leads),
        "leads": leads,
        "chat_context": "\n".join(lines),
    }


def _run_seo_summary(_args: dict[str, Any]) -> dict[str, Any]:
    snap = seo_review_summary_for_chat()
    return {
        "ok": bool(snap.get("ok")),
        "tool": "seo_summary",
        "snapshot": snap,
        "chat_context": format_seo_chat_context(snap),
        "summary": snap.get("summary"),
        "recommendations": snap.get("recommendations") or [],
        "error": snap.get("error"),
    }


def _run_task_stats(_args: dict[str, Any]) -> dict[str, Any]:
    snap = task_service_summary_for_chat()
    return {
        "ok": bool(snap.get("ok")),
        "tool": "task_stats",
        "snapshot": snap,
        "chat_context": format_task_service_chat_context(snap),
        "summary": snap.get("summary"),
        "error": snap.get("error"),
    }


def _run_analytics_traffic(_args: dict[str, Any]) -> dict[str, Any]:
    snap = traffic_summary_for_chat()
    return {
        "ok": bool(snap.get("ok")),
        "tool": "analytics_traffic",
        "snapshot": snap,
        "chat_context": format_traffic_chat_context(snap),
        "summary": snap.get("summary"),
        "recommendations": snap.get("recommendations") or [],
        "error": snap.get("error"),
    }


def _run_email_audience_summary(_args: dict[str, Any]) -> dict[str, Any]:
    snap = email_audience_summary_for_chat()
    return {
        "ok": bool(snap.get("ok")),
        "tool": "email_audience_summary",
        "snapshot": snap,
        "chat_context": format_email_audience_chat_context(snap),
        "summary": snap.get("summary"),
        "error": snap.get("error"),
        "send_policy": snap.get("send_policy"),
        "total": snap.get("total"),
        "counts": snap.get("counts"),
    }


_HANDLERS = {
    "analytics_summary": _run_analytics_summary,
    "analytics_leads_query": _run_analytics_leads_query,
    "seo_summary": _run_seo_summary,
    "task_stats": _run_task_stats,
    "analytics_traffic": _run_analytics_traffic,
    "email_audience_summary": _run_email_audience_summary,
}


def execute_admin_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one allowlisted admin tool. Unknown names return an honest error payload."""
    args = arguments if isinstance(arguments, dict) else {}
    handler = _HANDLERS.get(name)
    if handler is None:
        return {
            "ok": False,
            "tool": name,
            "error": "unknown_tool",
            "chat_context": (
                f"Tool '{name}' is not allowlisted for admin chat. "
                "Do NOT invent results."
            ),
        }
    return handler(args)


def tool_result_message(call: ToolCallRequest, result: dict[str, Any]) -> ChatMessage:
    """Build a ``role=tool`` message for the provider loop."""
    # Prefer the human chat_context string; keep compact JSON for structured fields.
    payload = {
        "ok": result.get("ok"),
        "tool": result.get("tool") or call.name,
        "chat_context": result.get("chat_context"),
        "summary": result.get("summary"),
        "recommendations": result.get("recommendations"),
        "error": result.get("error"),
        "count": result.get("count"),
        "total": result.get("total"),
        "total_matching": result.get("total_matching"),
        "filters": result.get("filters"),
        "leads": result.get("leads"),
        "send_policy": result.get("send_policy"),
        "counts": result.get("counts"),
    }
    # Drop None keys for a tighter tool result.
    compact = {k: v for k, v in payload.items() if v is not None}
    return ChatMessage(
        role="tool",
        content=json.dumps(compact, ensure_ascii=False),
        tool_call_id=call.id,
        name=call.name,
    )


def intent_context_messages(tool_names: Sequence[str]) -> tuple[list[ChatMessage], list[str]]:
    """Auto-invoke tools from intent and return system context messages + names used."""
    messages: list[ChatMessage] = []
    used: list[str] = []
    for name in tool_names:
        if name not in ADMIN_TOOL_NAMES:
            continue
        result = execute_admin_tool(name, {})
        used.append(name)
        body = result.get("chat_context") or result.get("summary") or json.dumps(result)
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    f"Auto-invoked admin tool `{name}` result "
                    "(use these live figures; do not invent):\n"
                    f"{body}"
                ),
            )
        )
    return messages, used


def _assistant_tool_call_message(turn: CompletionTurn) -> ChatMessage:
    parts = [
        ToolCallPart(
            id=c.id,
            name=c.name,
            arguments=c.arguments,
            thought_signature=c.thought_signature,
        )
        for c in turn.tool_calls
    ]
    return ChatMessage(
        role="assistant",
        content=(turn.text or "").strip(),
        tool_calls=parts,
    )


def _normalize_tool_call(raw: ToolCallRequest) -> ToolCallRequest:
    """Ensure every tool call has a stable id for provider round-trips."""
    call_id = (raw.id or "").strip() or f"call_{uuid.uuid4().hex[:12]}"
    args = raw.arguments if isinstance(raw.arguments, dict) else {}
    return ToolCallRequest(
        id=call_id,
        name=raw.name,
        arguments=args,
        thought_signature=raw.thought_signature,
    )


async def run_admin_tool_loop(
    provider: BaseProvider,
    messages: list[ChatMessage],
    *,
    api_key: str,
    model: str | None,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> tuple[str, list[str]]:
    """Provider tool-calling loop for admin mode.

    Returns ``(assistant_text, tools_used)``. When the provider lacks tool support,
    falls back to a single ``complete()`` text turn (intent context should already
    be injected by the caller).
    """
    tools_used: list[str] = []
    working = list(messages)

    if not getattr(provider, "supports_tools", False):
        text = await provider.complete(working, api_key=api_key, model=model)
        return text, tools_used

    for _ in range(max(1, max_rounds)):
        turn = await provider.complete_turn(
            working,
            api_key=api_key,
            model=model,
            tools=ADMIN_TOOL_SPECS,
        )
        if not turn.has_tool_calls:
            text = (turn.text or "").strip()
            if not text:
                raise ValueError("empty_reply")
            return text, tools_used

        # Normalize IDs before recording the assistant tool_calls message so
        # tool_result tool_call_id values always match (OpenAI/Anthropic require it).
        normalized = [_normalize_tool_call(raw) for raw in turn.tool_calls]
        working.append(
            _assistant_tool_call_message(
                CompletionTurn(text=turn.text, tool_calls=normalized)
            )
        )
        for call in normalized:
            result = execute_admin_tool(call.name, call.arguments)
            if call.name in ADMIN_TOOL_NAMES and call.name not in tools_used:
                tools_used.append(call.name)
            working.append(tool_result_message(call, result))

    # Exhausted rounds — ask for a final text-only answer without tools.
    final = await provider.complete_turn(
        working,
        api_key=api_key,
        model=model,
        tools=None,
    )
    text = (final.text or "").strip()
    if not text:
        raise ValueError("empty_reply")
    return text, tools_used
