"""Read-only Email Marketing audience summary for admin chat (P4).

Audience = Analytics lead sessions with a stored ``lead_email`` (same source
Overview's Email audience card and Email Marketing UI use). Report-only —
Approve → Send stays in wp-admin; no AgentMail / silent send from chat.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.db import analytics_db

logger = logging.getLogger(__name__)

_DAY_SECONDS = 24 * 60 * 60
_SAMPLE_LIMIT = 5


def _session_short(session_id: str | None) -> str:
    raw = str(session_id or "").replace("-", "")
    return raw[:8] if raw else "unknown"


def build_email_audience_summary(
    *,
    sample_limit: int = _SAMPLE_LIMIT,
    now: float | None = None,
) -> dict[str, Any]:
    """Return consented-lead-capture audience counts (read-only).

    On success: ``ok=True`` with ``total``, status breakdown, recent captures,
    and a small admin-safe sample. Empty audience is ``ok=True`` with zeros.
    """
    current = time.time() if now is None else now
    try:
        leads = analytics_db.list_leads(has_email=True)
        captures_total = analytics_db.count_email_capture_sessions()
        captures_7d = analytics_db.count_email_capture_sessions(
            since=current - 7 * _DAY_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("email audience summary failed")
        return {
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "summary": (
                "Email audience unavailable: could not read Analytics lead emails "
                "(service/connection)."
            ),
            "total": 0,
            "counts": {"hot": 0, "warm": 0, "cold": 0, "other": 0},
            "email_captures": {"total": 0, "last_7d": 0},
            "sample": [],
            "sample_count": 0,
            "empty": True,
            "send_policy": "approve_then_send",
        }

    counts = {"hot": 0, "warm": 0, "cold": 0, "other": 0}
    for lead in leads:
        status = str(lead.get("lead_status") or "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1

    sample: list[dict[str, Any]] = []
    for lead in leads[: max(1, sample_limit)]:
        email = (lead.get("lead_email") or "").strip() or None
        sid = lead.get("id")
        sample.append(
            {
                "session_id": sid,
                "session_id_short": _session_short(str(sid) if sid else None),
                "lead_status": lead.get("lead_status"),
                "lead_email": email,
                "ip_country": lead.get("ip_country"),
                "ip_city": lead.get("ip_city"),
                "last_seen_at": float(lead.get("last_seen_at") or 0),
            }
        )

    total = len(leads)
    other_bit = f", other={counts['other']}" if counts["other"] else ""
    summary = (
        f"Email audience (read-only): {total} leads with email "
        f"(hot={counts['hot']}, warm={counts['warm']}, cold={counts['cold']}"
        f"{other_bit}; captures_7d={captures_7d}). "
        "Send stays Approve → Send in Email Marketing — not from chat."
    )
    return {
        "ok": True,
        "total": total,
        "counts": counts,
        "email_captures": {"total": captures_total, "last_7d": captures_7d},
        "sample": sample,
        "sample_count": len(sample),
        "empty": total == 0,
        "summary": summary,
        "send_policy": "approve_then_send",
        "notes": (
            "Lead-capture emails, not proven marketing opt-ins. "
            "No AgentMail. No silent send from chat."
        ),
    }


def email_audience_summary_for_chat() -> dict[str, Any]:
    """Admin chat / tool payload for Email Marketing audience questions."""
    return build_email_audience_summary()


def format_email_audience_chat_context(snapshot: dict[str, Any]) -> str:
    """System/tool body for marketing-audience questions — report-only."""
    if not snapshot.get("ok"):
        return (
            "Live Email Marketing audience: UNAVAILABLE.\n"
            "You could not reach Analytics lead emails just now (service/connection).\n"
            "If asked about email audience / who we can email, say you couldn't reach "
            "Analytics right now and suggest Amy → Email Marketing / Overview.\n"
            "Do NOT invent audience size. Do NOT offer to send email from chat."
        )

    if snapshot.get("empty") or int(snapshot.get("total") or 0) == 0:
        return (
            "Live Email Marketing audience: EMPTY.\n"
            "No lead sessions with a stored email yet (audience_total=0).\n"
            "If asked about email audience, say no emails are on the marketing list yet "
            "— not that you lack access.\n"
            "Sending stays Approve → Send in Amy → Email Marketing (FluentSMTP); "
            "never AgentMail; never silent send from chat. Do NOT invent addresses."
        )

    counts = snapshot.get("counts") or {}
    captures = snapshot.get("email_captures") or {}
    other = int(counts.get("other") or 0)
    other_line = f", other={other}" if other else ""
    lines = [
        "Live Email Marketing audience (read-only — lead captures with email):",
        f"- audience_total: {int(snapshot.get('total') or 0)}",
        f"- by status: hot={int(counts.get('hot') or 0)}, "
        f"warm={int(counts.get('warm') or 0)}, "
        f"cold={int(counts.get('cold') or 0)}{other_line}",
        f"- email_captures (Submit Idea / contact events): "
        f"total={int(captures.get('total') or 0)}, "
        f"last_7d={int(captures.get('last_7d') or 0)}",
        "- send_policy: Approve → Send only in Amy → Email Marketing "
        "(FluentSMTP / wp_mail). No AgentMail. Chat cannot send.",
    ]

    sample = list(snapshot.get("sample") or [])
    if sample:
        lines.append(
            f"- sample (admin-safe, up to {len(sample)}; emails OK on this staff channel):"
        )
        for item in sample:
            email = item.get("lead_email") or "(no email)"
            short = item.get("session_id_short") or _session_short(
                str(item.get("session_id") or "")
            )
            lines.append(
                f"  • {short}: {email}; status={item.get('lead_status') or 'n/a'}"
            )
    else:
        lines.append("- sample: (none)")

    lines.extend(
        [
            "When the teammate asks about email audience, marketing list size, "
            "or who has an email on file for campaigns, cite these figures.",
            "Remind them sends require Approve → Send in Email Marketing — "
            "you report audience only from chat.",
            "Do NOT invent addresses or claim you can send from Telegram/Dashboard Chat.",
        ]
    )
    return "\n".join(lines)
