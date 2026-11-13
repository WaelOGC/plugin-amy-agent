"""Lead scoring: cold / warm / hot from a session's stored events."""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from app.db import analytics_db
from app.services.recommendation_format import Recommendation, assess_confidence

LeadStatus = Literal["cold", "warm", "hot"]

# Conservative blog-article matcher used until the theme permalink is confirmed
# against ogc-newfinity (out of scope for this task). Treats:
#   - /blog/... (common WP "blog" prefix)
#   - /YYYY/MM/... or /YYYY/MM/DD/... (WP default date permalinks)
# as article paths. Flagged in the Task 1 report for double-check.
_BLOG_PATH_RE = re.compile(
    r"(^/blog(?:/|$))|(^/\d{4}/\d{2}(?:/\d{2})?(?:/|$))",
    re.IGNORECASE,
)

_CONTACT_STEP_NAMES = frozenset({"contact", "contact_form", "contact-form"})

_DAY_SECONDS = 24 * 60 * 60


def is_blog_article_path(page_path: str | None) -> bool:
    if not page_path:
        return False
    path = page_path.strip()
    if not path:
        return False
    if not path.startswith("/"):
        path = "/" + path
    return _BLOG_PATH_RE.search(path) is not None


def _event_step(event: dict[str, Any], key: str) -> str:
    data = event.get("event_data") or {}
    if not isinstance(data, dict):
        return ""
    value = data.get(key)
    return str(value).strip().lower() if value is not None else ""


def _event_ts(event: dict[str, Any]) -> float:
    for key in ("created_at", "ts", "timestamp"):
        raw = event.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _classify_events(events: list[dict[str, Any]]) -> tuple[LeadStatus, str]:
    """Return (status, rule_reason). First matching rule wins."""
    types = {e["event_type"] for e in events}

    if "contact_form_abandoned" in types:
        return "hot", "contact_form_abandoned present"
    if "contact_form_submitted" in types:
        return "hot", "contact_form_submitted present"
    if "submit_idea_completed" in types:
        return "hot", "submit_idea_completed present"
    for event in events:
        if event["event_type"] != "submit_idea_abandoned":
            continue
        if _event_step(event, "last_step") in _CONTACT_STEP_NAMES:
            return "hot", "submit_idea_abandoned at contact step"

    if "widget_message_sent" in types:
        return "warm", "widget_message_sent present"

    page_views = [e for e in events if e["event_type"] == "page_view"]
    if len(page_views) >= 2 and any(
        is_blog_article_path(e.get("page_path")) for e in page_views
    ):
        return "warm", f"{len(page_views)} page_views including a blog article path"

    if "submit_idea_started" in types:
        abandoned = "submit_idea_abandoned" in types
        completed = "submit_idea_completed" in types
        if not abandoned and not completed:
            return "warm", "submit_idea_started without abandon/complete"

    return "cold", "no warm/hot engagement rules matched"


def compute_lead_status(session_id: str) -> LeadStatus:
    """Return cold/warm/hot for a session. First matching rule wins."""
    events = analytics_db.list_events(session_id)
    status, _reason = _classify_events(events)
    return status


def build_lead_status_recommendation(
    session_id: str,
    *,
    now: float | None = None,
) -> Recommendation:
    """Evidence-based explanation of the hot/warm/cold judgment for one session.

    Keeps ``compute_lead_status`` as the ingest API; this wraps the same rule
    match as a :class:`Recommendation` for admin chat / Telegram.
    """
    events = analytics_db.list_events(session_id)
    status, rule_reason = _classify_events(events)
    n = len(events)
    timestamps = [_event_ts(e) for e in events if _event_ts(e) > 0]
    if timestamps:
        span_days = max(0.0, (max(timestamps) - min(timestamps)) / _DAY_SECONDS)
        # Single-moment bursts still count as a sub-day window.
        if span_days == 0.0 and n > 0:
            span_days = 0.01
    else:
        span_days = 0.0

    confidence = assess_confidence(data_points=n, span_days=span_days)
    type_counts: dict[str, int] = {}
    for event in events:
        et = str(event.get("event_type") or "unknown")
        type_counts[et] = type_counts.get(et, 0) + 1
    type_bits = ", ".join(f"{k}×{v}" for k, v in sorted(type_counts.items())) or "none"
    span_bit = f"{span_days:.1f}d" if span_days >= 0.1 else "<0.1d"
    evidence = (
        f"session_id={session_id}; {n} stored events over {span_bit}; "
        f"rule={rule_reason}; event_types=[{type_bits}]"
    )

    finding = f"This visitor session is scored {status}."
    if status == "hot":
        limitations = (
            "Rule-based intent only — does not prove purchase intent, "
            "attribution, or that the visitor wants contact."
        )
        action = (
            "Review this session in Amy → Analytics and follow up if contact "
            "details were captured."
        )
    elif status == "warm":
        limitations = (
            "Engagement signal only — chat or content interest does not "
            "guarantee a lead conversion."
        )
        action = (
            "Watch for further engagement (contact form / Submit Idea) before "
            "prioritizing outreach."
        )
    else:
        limitations = (
            "Absence of warm/hot rules is not proof of low value — sparse "
            "tracking or a short visit can look cold."
        )
        action = None

    # ``now`` reserved for future last-seen caveats; keep signature stable.
    _ = now if now is not None else time.time()
    return Recommendation(
        finding=finding,
        evidence=evidence,
        confidence=confidence,
        limitations=limitations,
        recommended_action=action,
    )


def signal_for_events(events: list[dict[str, Any]]) -> str:
    """Human-readable summary of the most recent meaningful event."""
    if not events:
        return "No activity yet"

    meaningful = [e for e in events if e["event_type"] != "page_view"]
    chosen = meaningful[-1] if meaningful else events[-1]
    event_type = chosen["event_type"]
    data = chosen.get("event_data") if isinstance(chosen.get("event_data"), dict) else {}
    path = chosen.get("page_path") or ""

    if event_type == "contact_form_abandoned":
        return "Reached contact form, didn't submit"
    if event_type == "submit_idea_abandoned":
        last_step = str((data or {}).get("last_step") or "").strip()
        if last_step.lower() in _CONTACT_STEP_NAMES:
            return "Reached contact form, didn't submit"
        if last_step:
            return f"Abandoned Submit Idea at {last_step}"
        return "Abandoned Submit Idea"
    if event_type == "contact_form_submitted":
        return "Submitted contact form"
    if event_type == "submit_idea_completed":
        return "Completed Submit Idea"
    if event_type == "submit_idea_contact_captured":
        return "Shared email on Submit Idea"
    if event_type == "widget_message_sent":
        return "Sent a chat message"
    if event_type == "widget_opened":
        return "Opened chat"
    if event_type == "chat_closing_wish":
        return "Received a closing wish"
    if event_type == "submit_idea_started":
        return "Started Submit Idea"
    if event_type == "submit_idea_step_reached":
        step = str((data or {}).get("step") or "").strip()
        if step.lower() in _CONTACT_STEP_NAMES:
            return "Reached Submit Idea contact step"
        if step:
            return f"Reached Submit Idea step: {step}"
        return "Reached a Submit Idea step"
    if event_type == "contact_form_started":
        return "Started contact form"
    if event_type == "page_view":
        return f"Viewed {path}" if path else "Viewed a page"
    return event_type.replace("_", " ")


def extract_captured_email(event_type: str, event_data: dict[str, Any] | None) -> str | None:
    """Email is stored only when a form actually captured it — never inferred."""
    if event_type not in analytics_db.EMAIL_CAPTURE_EVENT_TYPES:
        return None
    if not isinstance(event_data, dict):
        return None
    raw = event_data.get("email")
    if not isinstance(raw, str):
        return None
    email = raw.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return None
    return email[:254]


def extract_captured_whatsapp(event_type: str, event_data: dict[str, Any] | None) -> str | None:
    """Phone is stored only from the same capture events as the email."""
    if event_type not in analytics_db.EMAIL_CAPTURE_EVENT_TYPES:
        return None
    if not isinstance(event_data, dict):
        return None
    raw = event_data.get("whatsapp")
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    digits = sum(ch.isdigit() for ch in value)
    if digits < 6 or digits > 20:
        return None
    if any(ch not in "+0123456789 -()." for ch in value):
        return None
    return value[:32]
