"""Task Service outbound notify — templates + dashboard + WP channel relay.

Email (FluentSMTP / wp_mail) and Telegram (Admin Bot #11) are sent by WordPress.
This module owns templates, dashboard bell rows, and calling WP when configured.
Owner/Amy execution remain P3/P4 — expiry audience here is creator (owner stand-in).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from app.config import get_settings
from app.db import notifications_db, progress_notes_db

logger = logging.getLogger(__name__)

NotifyEvent = Literal["assign", "mid_progress", "expiry"]

_EVENT_TO_NOTIF_TYPE: dict[NotifyEvent, str] = {
    "assign": "task_assigned",
    "mid_progress": "mid_progress_ask",
    "expiry": "task_expired",
}


def format_due(task: dict[str, Any]) -> str:
    due = (task.get("due_date") or "").strip()
    return due if due else "No due date set"


def render_assign(task: dict[str, Any]) -> dict[str, str]:
    title = (task.get("title") or "Task").strip() or "Task"
    description = (task.get("description") or "").strip()
    due = format_due(task)
    subject = f"New task assigned: {title}"
    body_lines = [
        f'You have been assigned: "{title}".',
        f"Due: {due}",
    ]
    if description:
        body_lines.extend(["", "Details:", description])
    body_lines.extend(
        [
            "",
            "Open Amy → Task Service (or My Profile) on the dashboard for actions.",
            "If Telegram is connected, you can also reply there when asked for a progress update.",
        ]
    )
    body = "\n".join(body_lines)
    telegram = (
        f"📋 New task assigned\n\n"
        f"<b>{_escape_html(title)}</b>\n"
        f"Due: {_escape_html(due)}\n"
    )
    if description:
        telegram += f"\n{_escape_html(description)}\n"
    telegram += "\nOpen the Amy dashboard for full details."
    return {"subject": subject, "body": body, "telegram": telegram, "message": body}


def render_mid_progress(task: dict[str, Any]) -> dict[str, str]:
    title = (task.get("title") or "Task").strip() or "Task"
    due = format_due(task)
    subject = f"Progress check: {title}"
    body = (
        f'Halfway to the deadline for "{title}" (due {due}).\n\n'
        "Please reply with a short progress update — what is done and what remains.\n"
        "You can reply on Telegram (free text) or update the task in the Amy dashboard."
    )
    telegram = (
        f"⏳ Progress check\n\n"
        f'How is <b>{_escape_html(title)}</b> going?\n'
        f"Due: {_escape_html(due)}\n\n"
        "Reply here with a short free-text progress update "
        "(what is done / what is left)."
    )
    return {"subject": subject, "body": body, "telegram": telegram, "message": body}


def render_expiry(task: dict[str, Any]) -> dict[str, str]:
    title = (task.get("title") or "Task").strip() or "Task"
    due = format_due(task)
    subject = f"Task past due: {title}"
    body = (
        f'"{title}" is past its due date ({due}) without completion.\n\n'
        "Choose how to proceed in the Amy dashboard notification: "
        "reassign to the same person, reassign to someone else, "
        "or acknowledge and handle it manually.\n"
        "(Owner/backup + Amy take-over land in later phases.)"
    )
    telegram = (
        f"⚠️ Task past due\n\n"
        f"<b>{_escape_html(title)}</b>\n"
        f"Due: {_escape_html(due)}\n\n"
        "Open the Amy dashboard to reassign or acknowledge."
    )
    return {"subject": subject, "body": body, "telegram": telegram, "message": body}


def render_event(event: NotifyEvent, task: dict[str, Any]) -> dict[str, str]:
    if event == "assign":
        return render_assign(task)
    if event == "mid_progress":
        return render_mid_progress(task)
    if event == "expiry":
        return render_expiry(task)
    raise ValueError(f"unknown notify event: {event}")


def _escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def recipient_for_event(event: NotifyEvent, task: dict[str, Any]) -> int | None:
    """Who should receive this event (P1; owner/backup refined in P3)."""
    if event in {"assign", "mid_progress"}:
        if task.get("assignee_type") != "human":
            return None
        uid = task.get("assignee_wp_user_id")
        return int(uid) if uid is not None else None
    # expiry → creator as owner stand-in until P3
    return int(task["created_by_wp_user_id"])


def dispatch_task_notify(
    event: NotifyEvent,
    task: dict[str, Any],
    *,
    wp_user_id: int | None = None,
    requires_action: bool | None = None,
    action_payload: dict[str, Any] | None = None,
    create_dashboard: bool = True,
    dashboard_message: str | None = None,
) -> dict[str, Any]:
    """Create dashboard notification (optional) and relay email/Telegram via WP.

    Always safe to call from create/reassign and escalation. Channel failures
    are logged; dashboard still lands when create_dashboard is true.
    """
    rendered = render_event(event, task)
    recipient = int(wp_user_id) if wp_user_id is not None else recipient_for_event(event, task)
    result: dict[str, Any] = {
        "event": event,
        "task_id": task.get("id"),
        "wp_user_id": recipient,
        "dashboard": None,
        "channels": {"email": "skipped", "telegram": "skipped"},
        "pending_progress": False,
    }
    if recipient is None:
        result["channels"] = {"email": "no_recipient", "telegram": "no_recipient"}
        return result

    notif_type = _EVENT_TO_NOTIF_TYPE[event]
    if requires_action is None:
        requires_action = event == "expiry"
    if action_payload is None and event == "expiry":
        action_payload = {
            "choices": [
                "reassign_same",
                "reassign_other",
                "acknowledge_manual",
            ],
            "task_id": task["id"],
        }

    if create_dashboard:
        result["dashboard"] = notifications_db.create_notification(
            task_id=task["id"],
            wp_user_id=recipient,
            type=notif_type,
            message=dashboard_message or rendered["message"],
            requires_action=bool(requires_action),
            action_payload=action_payload,
        )

    if event == "mid_progress":
        progress_notes_db.set_pending_progress_reply(
            wp_user_id=recipient, task_id=task["id"]
        )
        result["pending_progress"] = True

    channel = _relay_channels_to_wordpress(
        event=event,
        task=task,
        wp_user_id=recipient,
        subject=rendered["subject"],
        body=rendered["body"],
        telegram_html=rendered["telegram"],
    )
    result["channels"] = channel
    return result


def _relay_channels_to_wordpress(
    *,
    event: NotifyEvent,
    task: dict[str, Any],
    wp_user_id: int,
    subject: str,
    body: str,
    telegram_html: str,
) -> dict[str, str]:
    settings = get_settings()
    base = (settings.wordpress_base_url or "").strip().rstrip("/")
    if not base:
        logger.info(
            "Task notify %s for task %s: wordpress_base_url unset — dashboard only",
            event,
            task.get("id"),
        )
        return {"email": "no_wordpress_url", "telegram": "no_wordpress_url"}

    url = f"{base}/wp-json/amy-agent/v1/task-notify"
    payload = {
        "event": event,
        "wp_user_id": wp_user_id,
        "task": {
            "id": task.get("id"),
            "title": task.get("title"),
            "description": task.get("description"),
            "due_date": task.get("due_date"),
            "priority": task.get("priority"),
            "assignee_wp_user_id": task.get("assignee_wp_user_id"),
            "created_by_wp_user_id": task.get("created_by_wp_user_id"),
        },
        "subject": subject,
        "body": body,
        "telegram_html": telegram_html,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Amy-Secret": settings.amy_shared_secret,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
            response = client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "WP task-notify failed status=%s task=%s event=%s",
                response.status_code,
                task.get("id"),
                event,
            )
            return {"email": "wp_error", "telegram": "wp_error"}
        data = response.json() if response.content else {}
        channels = data.get("channels") if isinstance(data, dict) else None
        if isinstance(channels, dict):
            return {
                "email": str(channels.get("email", "unknown")),
                "telegram": str(channels.get("telegram", "unknown")),
            }
        return {"email": "ok", "telegram": "ok"}
    except Exception:
        logger.exception(
            "WP task-notify relay failed task=%s event=%s", task.get("id"), event
        )
        return {"email": "relay_error", "telegram": "relay_error"}
