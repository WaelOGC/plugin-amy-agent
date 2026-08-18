"""Lead scoring: cold / warm / hot from a session's stored events."""

from __future__ import annotations

import re
from typing import Any, Literal

from app.db import analytics_db

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


def compute_lead_status(session_id: str) -> LeadStatus:
    """Return cold/warm/hot for a session. First matching rule wins."""
    events = analytics_db.list_events(session_id)
    types = {e["event_type"] for e in events}

    if "contact_form_abandoned" in types:
        return "hot"
    if "contact_form_submitted" in types:
        return "hot"
    if "submit_idea_completed" in types:
        return "hot"
    for event in events:
        if event["event_type"] != "submit_idea_abandoned":
            continue
        if _event_step(event, "last_step") in _CONTACT_STEP_NAMES:
            return "hot"

    if "widget_message_sent" in types:
        return "warm"

    page_views = [e for e in events if e["event_type"] == "page_view"]
    if len(page_views) >= 2 and any(is_blog_article_path(e.get("page_path")) for e in page_views):
        return "warm"

    if "submit_idea_started" in types:
        abandoned = "submit_idea_abandoned" in types
        completed = "submit_idea_completed" in types
        if not abandoned and not completed:
            return "warm"

    return "cold"


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
    if event_type == "widget_message_sent":
        return "Sent a chat message"
    if event_type == "widget_opened":
        return "Opened chat"
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
