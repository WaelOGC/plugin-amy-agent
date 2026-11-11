"""Shared Amy Analytics lead-session summary for Task P4 and admin chat.

Counts come from the same ``analytics_db.list_leads()`` path Overview / Analytics
already use. This is lead sessions (hot/warm/cold), not GA-style pageviews.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db import analytics_db

logger = logging.getLogger(__name__)


def build_analytics_summary(*, include_sample: bool = False) -> dict[str, Any]:
    """Return live lead-session counts (and optional sample) from Analytics DB.

    On success: ``ok=True`` with ``total``, ``counts``, ``with_email``, ``summary``.
    On failure: ``ok=False`` with ``error`` and an honest unavailable ``summary``.
    Never invents numbers — empty DB is ``ok=True`` with ``total=0``.
    """
    try:
        leads = analytics_db.list_leads()
    except Exception as exc:  # noqa: BLE001 — chat/task must degrade honestly
        logger.exception("analytics summary failed")
        return {
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "summary": (
                "Analytics unavailable: could not read visitor lead sessions "
                "(service/connection)."
            ),
            "total": 0,
            "counts": {"hot": 0, "warm": 0, "cold": 0, "other": 0},
            "with_email": 0,
            "empty": True,
        }

    counts = {"hot": 0, "warm": 0, "cold": 0, "other": 0}
    with_email = 0
    for lead in leads:
        status = str(lead.get("lead_status") or "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
        if lead.get("lead_email"):
            with_email += 1

    total = len(leads)
    other_bit = f", other={counts['other']}" if counts["other"] else ""
    summary = (
        f"Analytics summary: {total} lead sessions "
        f"(hot={counts['hot']}, warm={counts['warm']}, cold={counts['cold']}"
        f"{other_bit}; with_email={with_email})."
    )

    result: dict[str, Any] = {
        "ok": True,
        "total": total,
        "counts": counts,
        "with_email": with_email,
        "empty": total == 0,
        "summary": summary,
    }
    if include_sample:
        sample = []
        for lead in leads[:5]:
            sample.append(
                {
                    "session_id": lead.get("id") or lead.get("session_id"),
                    "lead_status": lead.get("lead_status"),
                    "has_email": bool(lead.get("lead_email")),
                }
            )
        result["sample"] = sample
        result["sample_count"] = len(sample)
    return result


def analytics_summary_for_chat() -> dict[str, Any]:
    """Compact snapshot for admin ``POST /v1/chat`` context inject (counts only)."""
    return build_analytics_summary(include_sample=False)


def format_analytics_chat_context(snapshot: dict[str, Any]) -> str:
    """System-message body: live figures, empty, or unavailable — never 'no access'."""
    if not snapshot.get("ok"):
        return (
            "Live Amy Analytics snapshot: UNAVAILABLE.\n"
            "You could not reach Analytics just now (service/connection error).\n"
            "If asked about visitors, traffic, leads, or emails captured, say plainly "
            "that you couldn't reach Analytics right now and suggest checking "
            "Amy → Settings → Connection / Overview.\n"
            "Do NOT say you have no analytics access in general. "
            "Do NOT invent numbers."
        )

    if snapshot.get("empty") or int(snapshot.get("total") or 0) == 0:
        return (
            "Live Amy Analytics snapshot: EMPTY.\n"
            "No visitor sessions recorded yet (total_sessions=0, hot=0, warm=0, "
            "cold=0, with_email=0).\n"
            "If asked about visitors, traffic, leads, or hot leads, say there are "
            "no visitor sessions captured yet — not that you lack access.\n"
            "These are Amy Analytics lead sessions, not Google Analytics pageviews. "
            "Do NOT invent numbers."
        )

    counts = snapshot.get("counts") or {}
    other = int(counts.get("other") or 0)
    other_line = f", other={other}" if other else ""
    return (
        "Live Amy Analytics snapshot (lead sessions — not GA pageviews):\n"
        f"- total_sessions: {int(snapshot.get('total') or 0)}\n"
        f"- hot: {int(counts.get('hot') or 0)}, warm: {int(counts.get('warm') or 0)}, "
        f"cold: {int(counts.get('cold') or 0)}{other_line}\n"
        f"- with_email: {int(snapshot.get('with_email') or 0)}\n"
        "When the teammate asks about visitors, site traffic, leads, hot/warm/cold "
        "leads, or emails captured, cite these figures. Prefer 'visitor sessions' / "
        "lead-status language; do not claim Google Analytics-style unique pageviews.\n"
        "Do NOT invent other numbers beyond this snapshot."
    )
