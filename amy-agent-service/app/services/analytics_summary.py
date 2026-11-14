"""Shared Amy Analytics lead-session summary for Task P4 and admin chat.

Counts come from the same ``analytics_db.list_leads()`` path Overview / Analytics
already use. This is lead sessions (hot/warm/cold), not GA-style pageviews.

P1 adds with-email emphasis, admin-safe hot samples, last-seen window language,
and Submit Idea / contact email-capture counts for richer admin Q&A.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.db import analytics_db
from app.services.recommendation_format import (
    Recommendation,
    append_recommendations_block,
    assess_confidence,
    recommendation_from_mapping,
    recommendation_to_dict,
)

logger = logging.getLogger(__name__)

_HOT_SAMPLE_LIMIT = 5
_DAY_SECONDS = 24 * 60 * 60


def format_last_seen_ago(ts: float, *, now: float | None = None) -> str:
    """Human last-seen window language (m/h/d ago), matching Analytics UI style."""
    current = time.time() if now is None else now
    try:
        seen = float(ts)
    except (TypeError, ValueError):
        return "unknown"
    diff = max(0.0, current - seen)
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < _DAY_SECONDS:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // _DAY_SECONDS)}d ago"


def _session_short(session_id: str | None) -> str:
    raw = str(session_id or "").replace("-", "")
    return raw[:8] if raw else "unknown"


def _build_hot_sample(
    leads: list[dict[str, Any]],
    *,
    include_emails: bool,
    limit: int,
    now: float,
) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for lead in leads:
        if str(lead.get("lead_status") or "") != "hot":
            continue
        sid = lead.get("id") or lead.get("session_id")
        email = (lead.get("lead_email") or "").strip() or None
        item: dict[str, Any] = {
            "session_id": sid,
            "session_id_short": _session_short(str(sid) if sid else None),
            "lead_status": "hot",
            "has_email": bool(email),
            "last_seen_at": float(lead.get("last_seen_at") or 0),
            "last_seen": format_last_seen_ago(
                float(lead.get("last_seen_at") or 0), now=now
            ),
            "ip_country": lead.get("ip_country"),
            "ip_city": lead.get("ip_city"),
        }
        if include_emails:
            item["lead_email"] = email
        sample.append(item)
        if len(sample) >= limit:
            break
    return sample


def _last_seen_windows(leads: list[dict[str, Any]], *, now: float) -> dict[str, Any]:
    last_24h = 0
    last_7d = 0
    most_recent_at: float | None = None
    for lead in leads:
        try:
            seen = float(lead.get("last_seen_at") or 0)
        except (TypeError, ValueError):
            continue
        if seen <= 0:
            continue
        age = now - seen
        if age <= _DAY_SECONDS:
            last_24h += 1
        if age <= 7 * _DAY_SECONDS:
            last_7d += 1
        if most_recent_at is None or seen > most_recent_at:
            most_recent_at = seen
    return {
        "last_24h": last_24h,
        "last_7d": last_7d,
        "most_recent_at": most_recent_at,
        "most_recent": (
            format_last_seen_ago(most_recent_at, now=now)
            if most_recent_at is not None
            else None
        ),
    }


def build_analytics_summary(
    *,
    include_sample: bool = False,
    include_emails_in_sample: bool = False,
    hot_sample_limit: int = _HOT_SAMPLE_LIMIT,
    now: float | None = None,
) -> dict[str, Any]:
    """Return live lead-session counts (and optional sample) from Analytics DB.

    On success: ``ok=True`` with ``total``, ``counts``, ``with_email``,
    ``email_captures``, ``last_seen``, ``summary``.
    On failure: ``ok=False`` with ``error`` and an honest unavailable ``summary``.
    Never invents numbers — empty DB is ``ok=True`` with ``total=0``.
    """
    current = time.time() if now is None else now
    try:
        leads = analytics_db.list_leads()
        email_captures_total = analytics_db.count_email_capture_sessions()
        email_captures_7d = analytics_db.count_email_capture_sessions(
            since=current - 7 * _DAY_SECONDS
        )
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
            "email_captures": {"total": 0, "last_7d": 0},
            "last_seen": {
                "last_24h": 0,
                "last_7d": 0,
                "most_recent_at": None,
                "most_recent": None,
            },
            "recommendations": [],
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
    last_seen = _last_seen_windows(leads, now=current)
    other_bit = f", other={counts['other']}" if counts["other"] else ""
    most_recent_bit = (
        f"; most_recent_last_seen={last_seen['most_recent']}"
        if last_seen.get("most_recent")
        else ""
    )
    summary = (
        f"Analytics summary: {total} lead sessions "
        f"(hot={counts['hot']}, warm={counts['warm']}, cold={counts['cold']}"
        f"{other_bit}; with_email={with_email}; "
        f"email_captures_7d={email_captures_7d}; "
        f"seen_24h={last_seen['last_24h']}, seen_7d={last_seen['last_7d']}"
        f"{most_recent_bit})."
    )

    recommendations = build_analytics_recommendations(
        total=total,
        counts=counts,
        with_email=with_email,
        last_seen=last_seen,
        leads=leads,
    )
    result: dict[str, Any] = {
        "ok": True,
        "total": total,
        "counts": counts,
        "with_email": with_email,
        "email_captures": {
            "total": email_captures_total,
            "last_7d": email_captures_7d,
        },
        "last_seen": last_seen,
        "empty": total == 0,
        "summary": summary,
        "recommendations": [recommendation_to_dict(r) for r in recommendations],
    }
    if include_sample:
        # Prefer hot-first sample for admin Q&A; fall back to overall top leads.
        hot_sample = _build_hot_sample(
            leads,
            include_emails=include_emails_in_sample,
            limit=hot_sample_limit,
            now=current,
        )
        if hot_sample:
            sample = hot_sample
        else:
            sample = []
            for lead in leads[:hot_sample_limit]:
                sid = lead.get("id") or lead.get("session_id")
                email = (lead.get("lead_email") or "").strip() or None
                item: dict[str, Any] = {
                    "session_id": sid,
                    "session_id_short": _session_short(str(sid) if sid else None),
                    "lead_status": lead.get("lead_status"),
                    "has_email": bool(email),
                    "last_seen_at": float(lead.get("last_seen_at") or 0),
                    "last_seen": format_last_seen_ago(
                        float(lead.get("last_seen_at") or 0), now=current
                    ),
                    "ip_country": lead.get("ip_country"),
                    "ip_city": lead.get("ip_city"),
                }
                if include_emails_in_sample:
                    item["lead_email"] = email
                sample.append(item)
        result["sample"] = sample
        result["sample_count"] = len(sample)
        result["hot_sample"] = hot_sample
        result["hot_sample_count"] = len(hot_sample)
    return result


def _visitor_noun(n: int) -> str:
    return "visitor" if n == 1 else "visitors"


def _hot_email_evidence(*, hot: int, hot_with_email: int) -> str:
    """Plain-English email-split evidence (never key=value)."""
    hot_noun = _visitor_noun(hot)
    if hot_with_email <= 0:
        if hot == 0:
            return "No hot visitors left an email."
        return f"None of the {hot} hot {hot_noun} left an email."
    if hot_with_email >= hot:
        if hot == 1:
            return "The 1 hot visitor left an email."
        return f"All {hot} hot visitors left an email."
    return (
        f"{hot_with_email} of the {hot} hot {_visitor_noun(hot)} "
        f"left an email."
    )


def build_analytics_recommendations(
    *,
    total: int,
    counts: dict[str, int],
    with_email: int,
    last_seen: dict[str, Any],
    leads: list[dict[str, Any]],
) -> list[Recommendation]:
    """Conclusions only — not raw count sentences.

    Emits a hot-lead attention recommendation when any sessions are scored hot
    (the same judgment ``lead_scoring`` already applies per session). Plain
    totals with no hot emphasis return an empty list.

    Finding states the conclusion (not a repeated hot count). Evidence is the
    with/without-email split in plain English — never ``key=value`` dumps.
    """
    hot = int(counts.get("hot") or 0)
    if hot <= 0:
        return []

    hot_with_email = 0
    for lead in leads:
        if str(lead.get("lead_status") or "") != "hot":
            continue
        if lead.get("lead_email"):
            hot_with_email += 1
    hot_without_email = hot - hot_with_email
    _ = with_email  # overall with_email is already in the body counts

    seen_7d = int(last_seen.get("last_7d") or 0)
    span_days = 7.0 if seen_7d > 0 else 0.0
    confidence = assess_confidence(data_points=total, span_days=span_days)
    limitations = "Hot = rule-based intent. An email ≠ marketing consent."
    evidence = _hot_email_evidence(hot=hot, hot_with_email=hot_with_email)

    if hot_with_email == 0:
        finding = (
            "None of the hot visitors have left an email yet, so you can't "
            "reach them directly."
        )
        action = (
            "Review the hot sessions in Amy → Analytics and watch for contact "
            "capture before outreach."
        )
    elif hot_without_email > 0:
        finding = (
            "Most hot visitors haven't left an email yet, so you can't reach "
            "them directly."
        )
        action = (
            f"Contact the {hot_with_email} hot "
            f"{'lead' if hot_with_email == 1 else 'leads'} with an email first, "
            f"then review the other {hot_without_email} in Analytics."
        )
    else:
        finding = (
            "Every hot visitor left an email, so you can follow up directly."
        )
        action = (
            "Review hot leads with email in Amy → Analytics (or Email Marketing) "
            "and follow up via Approve → Send if appropriate."
        )

    return [
        Recommendation(
            finding=finding,
            evidence=evidence,
            confidence=confidence,
            limitations=limitations,
            recommended_action=action,
        )
    ]


def analytics_summary_for_chat() -> dict[str, Any]:
    """Richer P1 snapshot for admin ``POST /v1/chat`` (counts + admin-safe hot sample)."""
    return build_analytics_summary(
        include_sample=True,
        include_emails_in_sample=True,
    )


def analytics_summary_public_contract() -> dict[str, Any]:
    """Thin contract for ``GET /v1/analytics/summary`` (no email PII in sample)."""
    return build_analytics_summary(include_sample=True, include_emails_in_sample=False)


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
            "cold=0, with_email=0, email_captures_7d=0).\n"
            "If asked about visitors, traffic, leads, or hot leads, say there are "
            "no visitor sessions captured yet — not that you lack access.\n"
            "These are Amy Analytics lead sessions, not Google Analytics pageviews. "
            "Do NOT invent numbers."
        )

    counts = snapshot.get("counts") or {}
    other = int(counts.get("other") or 0)
    other_line = f", other={other}" if other else ""
    last_seen = snapshot.get("last_seen") or {}
    captures = snapshot.get("email_captures") or {}
    most_recent = last_seen.get("most_recent") or "n/a"

    lines = [
        "Live Amy Analytics snapshot (lead sessions — not GA pageviews):",
        f"- total_sessions: {int(snapshot.get('total') or 0)}",
        f"- hot: {int(counts.get('hot') or 0)}, warm: {int(counts.get('warm') or 0)}, "
        f"cold: {int(counts.get('cold') or 0)}{other_line}",
        f"- with_email: {int(snapshot.get('with_email') or 0)} "
        "(sessions that have a stored lead email)",
        f"- email_captures: total={int(captures.get('total') or 0)}, "
        f"last_7d={int(captures.get('last_7d') or 0)} "
        "(Submit Idea / contact-form capture events)",
        f"- last_seen windows: last_24h={int(last_seen.get('last_24h') or 0)}, "
        f"last_7d={int(last_seen.get('last_7d') or 0)}, "
        f"most_recent={most_recent}",
    ]

    hot_sample = list(snapshot.get("hot_sample") or [])
    if not hot_sample:
        # Older fixtures may only populate ``sample``.
        hot_sample = [
            item
            for item in list(snapshot.get("sample") or [])
            if str(item.get("lead_status") or "") == "hot"
        ]
    if hot_sample:
        geo_keys: list[str] = []
        for item in hot_sample:
            geo_parts = [
                p for p in (item.get("ip_city"), item.get("ip_country")) if p
            ]
            geo_keys.append(
                ", ".join(str(p) for p in geo_parts) if geo_parts else ""
            )
        shared_geo = bool(geo_keys) and all(geo_keys) and len(set(geo_keys)) == 1
        lines.append(
            f"- hot lead sample (admin-safe, up to {len(hot_sample)}; "
            "emails OK to share with this teammate):"
        )
        if shared_geo:
            lines.append(
                f"- sample display hint: all listed hot visitors share location "
                f"📍 {geo_keys[0]} — put it once in the section title "
                f"(e.g. **Hot Leads — 📍 City, Country**) and omit location "
                "from each row; short rows: id — active … · email or no email."
            )
        else:
            lines.append(
                "- sample display hint: locations differ — keep 📍 on each row "
                "when known; keep rows short (id · active … · email/no email)."
            )
        for item in hot_sample:
            email = item.get("lead_email")
            if email:
                email_bit = str(email)
            elif item.get("has_email"):
                email_bit = "(email on file)"
            else:
                email_bit = "(no email)"
            geo_parts = [
                p for p in (item.get("ip_city"), item.get("ip_country")) if p
            ]
            geo = (
                ", ".join(str(p) for p in geo_parts)
                if geo_parts
                else "unknown location"
            )
            short = item.get("session_id_short") or _session_short(
                str(item.get("session_id") or "")
            )
            lines.append(
                f"  • Visitor {short}: {email_bit}; {geo}; "
                f"last_seen={item.get('last_seen') or 'n/a'}"
            )
    else:
        lines.append("- hot lead sample: (none)")

    lines.extend(
        [
            "When the teammate asks about visitors, site traffic, leads, hot/warm/cold "
            "leads, emails captured, Submit Idea emails, or how recently visitors were "
            "seen, cite these figures. Prefer 'visitor sessions' / lead-status / "
            "last-seen language; do not claim Google Analytics-style unique pageviews.",
            "Do NOT invent other numbers beyond this snapshot.",
            "Do NOT write a Recommendations / Finding / Evidence / Confidence heading "
            "yourself — the system appends the recommendation block.",
        ]
    )
    body = "\n".join(lines)
    recs = _recommendations_from_snapshot(snapshot)
    return append_recommendations_block(body, recs)


def _recommendations_from_snapshot(snapshot: dict[str, Any]) -> list[Recommendation]:
    raw = snapshot.get("recommendations") or []
    out: list[Recommendation] = []
    for item in raw:
        if isinstance(item, Recommendation):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        try:
            out.append(recommendation_from_mapping(item))
        except (TypeError, ValueError):
            continue
    return out


def format_analytics_slash_reply(snapshot: dict[str, Any]) -> str:
    """Deterministic Telegram / Dashboard slash reply from a fresh summary pull."""
    if not snapshot.get("ok"):
        return (
            "Analytics unavailable right now (service/connection). "
            "Check Amy → Settings → Connection / Overview."
        )
    if snapshot.get("empty") or int(snapshot.get("total") or 0) == 0:
        return (
            "Amy Analytics: no visitor sessions recorded yet "
            "(lead sessions, not GA pageviews)."
        )

    counts = snapshot.get("counts") or {}
    last_seen = snapshot.get("last_seen") or {}
    captures = snapshot.get("email_captures") or {}
    lines = [
        "Amy Analytics (lead sessions — not GA pageviews)",
        f"Sessions: {int(snapshot.get('total') or 0)} "
        f"(hot={int(counts.get('hot') or 0)}, "
        f"warm={int(counts.get('warm') or 0)}, "
        f"cold={int(counts.get('cold') or 0)})",
        f"With email: {int(snapshot.get('with_email') or 0)}",
        f"Email captures (Submit Idea / contact): "
        f"total={int(captures.get('total') or 0)}, "
        f"last_7d={int(captures.get('last_7d') or 0)}",
        f"Last seen: 24h={int(last_seen.get('last_24h') or 0)}, "
        f"7d={int(last_seen.get('last_7d') or 0)}, "
        f"most recent={last_seen.get('most_recent') or 'n/a'}",
    ]
    hot_sample = snapshot.get("hot_sample") or []
    if hot_sample:
        lines.append("Hot sample:")
        for item in hot_sample:
            email = item.get("lead_email")
            if email:
                email_bit = str(email)
            elif item.get("has_email"):
                email_bit = "(email on file)"
            else:
                email_bit = "(no email)"
            short = item.get("session_id_short") or _session_short(
                str(item.get("session_id") or "")
            )
            lines.append(
                f"• Visitor {short}: {email_bit}; "
                f"last_seen={item.get('last_seen') or 'n/a'}"
            )
    return "\n".join(lines)
