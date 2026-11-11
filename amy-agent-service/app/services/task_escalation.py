"""Task escalation / reminder / extension engine (one-task-at-a-time helpers).

P2 standard state machine (APScheduler every 5 min + SQLite stages):
  none → mid_report_asked (50% of created_at→due) → expired (past due)

Mid ask + expiry reuse P1 ``task_notify`` (dashboard + email/Telegram relay).
Owner/backup reassign UX = P3. Amy execution = P4 (hook only — never fake done).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app import config_task_rules as rules
from app.db import notifications_db, tasks_db
from app.services import task_notify

logger = logging.getLogger(__name__)


def parse_due_timestamp(due_date: str | None) -> float | None:
    """Parse due_date TEXT as unix timestamp.

    Accepts ISO date (`YYYY-MM-DD`, treated as end of that UTC day) or full
    ISO datetime so short test windows (minutes) work.
    """
    if not due_date:
        return None
    raw = due_date.strip()
    if not raw:
        return None
    try:
        if "T" in raw or " " in raw:
            normalized = raw.replace("Z", "+00:00").replace(" ", "T")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        dt = datetime.strptime(raw, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
        return dt.timestamp()
    except ValueError:
        return None


def format_due_timestamp(ts: float) -> str:
    """Store extended due dates as ISO datetime UTC."""
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def mid_due_timestamps(
    created_at: float, due_ts: float
) -> tuple[float, float]:
    """Return (mid_at, due_ts) for a created_at → due window.

    Mid fires at STANDARD_MIDPOINT_FRACTION of the window. Callers schedule
    implicitly: APScheduler polls open tasks; no per-task job registry.
    """
    window = due_ts - created_at
    if window <= 0:
        return due_ts, due_ts
    mid_at = created_at + (window * rules.STANDARD_MIDPOINT_FRACTION)
    return mid_at, due_ts


def _set_stage(task_id: str, stage: str) -> None:
    tasks_db.update_task(
        task_id,
        {
            "escalation_stage": stage,
            "escalation_stage_updated_at": datetime.now(tz=timezone.utc).timestamp(),
        },
    )


def _assignee_id(task: dict[str, Any]) -> int | None:
    if task.get("assignee_type") != "human":
        return None
    uid = task.get("assignee_wp_user_id")
    return int(uid) if uid is not None else None


def _normalize_standard_stage(stage: str) -> str:
    """Map legacy Task-2 / P1 stage names onto the P2 machine."""
    if stage in tasks_db.MID_REPORT_SENT_STAGES:
        return "mid_report_asked"
    return stage


def _amy_capable_expiry_hook(task: dict[str, Any]) -> None:
    """P4 handoff stub — log only; never mark done or invent Amy work.

    When ``amy_capable`` is true, P4 should queue real in-system execution.
    Until then we only escalate notify (creator / future owner-backup).
    """
    if not task.get("amy_capable"):
        return
    # TODO(P4 / amy-execution): hand off digital/in-system work to Amy here
    # (status in_progress → tool allowlist → done/failed with audit). Do not
    # auto-complete or invent success because the deadline passed.
    logger.info(
        "Task %s expired with amy_capable=True — Amy handoff deferred to P4 "
        "(notify-only; no fake completion)",
        task.get("id"),
    )


def check_standard_task(task: dict[str, Any], *, now: float | None = None) -> list[dict[str, Any]]:
    """P2: mid progress ask @ 50% then expiry for non-urgent open tasks."""
    now = time_now(now)
    if task.get("priority") == "urgent":
        return []
    if task.get("status") == "done":
        return []

    due_ts = parse_due_timestamp(task.get("due_date"))
    if due_ts is None:
        return []

    stage = _normalize_standard_stage(task.get("escalation_stage") or "none")
    created = float(task.get("created_at") or now)
    notifications: list[dict[str, Any]] = []
    assignee = _assignee_id(task)

    # Past due → expire (creator / P3 owner decides; do not auto-complete).
    if now >= due_ts and stage != "expired":
        # TODO(P3): route expiry to owner/backup instead of creator-only.
        _set_stage(task["id"], "expired")
        _amy_capable_expiry_hook(task)
        dispatched = task_notify.dispatch_task_notify("expiry", task)
        if dispatched.get("dashboard"):
            notifications.append(dispatched["dashboard"])
        return notifications

    if now >= due_ts:
        return []

    mid_at, _ = mid_due_timestamps(created, due_ts)
    if mid_at >= due_ts:
        # Zero/negative window already handled; nothing to mid-ask.
        return []

    # One mid progress ask (idempotent via mid_report_asked + legacy aliases).
    if now >= mid_at and stage == "none":
        if assignee:
            dispatched = task_notify.dispatch_task_notify("mid_progress", task)
            if dispatched.get("dashboard"):
                notifications.append(dispatched["dashboard"])
        # Mark sent even without assignee so we never double-fire after a later assign.
        _set_stage(task["id"], "mid_report_asked")
        return notifications

    # Optional final warning deferred (STANDARD_FINAL_WARNING_ENABLED=False).
    if (
        rules.STANDARD_FINAL_WARNING_ENABLED
        and stage == "mid_report_asked"
        and assignee
    ):
        final_at = due_ts - rules.STANDARD_FINAL_WARNING_SECONDS
        if now >= final_at:
            title = task.get("title") or "Task"
            notifications.append(
                notifications_db.create_notification(
                    task_id=task["id"],
                    wp_user_id=assignee,
                    type="reminder_final",
                    message=(
                        f'Final warning: "{title}" is due soon. '
                        "Please finish or request an extension."
                    ),
                    requires_action=False,
                )
            )
            _set_stage(task["id"], "final_warning_sent")
            return notifications

    return notifications


def check_urgent_task(task: dict[str, Any], *, now: float | None = None) -> list[dict[str, Any]]:
    """Check-ins, reassignment, and no-one-available for urgent tasks."""
    now = time_now(now)
    if task.get("priority") != "urgent":
        return []
    if task.get("status") == "done":
        return []
    if task.get("acknowledged_at") is not None:
        return []

    assignee = _assignee_id(task)
    if assignee is None:
        # Amy-assigned urgent tasks: no human ack window to escalate.
        return []

    stage = task.get("escalation_stage") or "none"
    if stage == "creator_notified_no_one_available":
        return []

    created = float(task.get("created_at") or now)
    stage_updated = task.get("escalation_stage_updated_at")
    title = task.get("title") or "Task"
    notifications: list[dict[str, Any]] = []

    # Anchor for the current ack window: last reassignment time, else creation.
    window_start = float(stage_updated) if stage == "reassigned" and stage_updated else created
    elapsed = now - window_start

    def _maybe_send_checkin() -> None:
        """Send check-ins on a fixed interval without moving the ack window."""
        due_count = int(elapsed // rules.URGENT_CHECKIN_INTERVAL_SECONDS)
        if due_count < 1:
            return
        already = notifications_db.count_notifications(
            task_id=task["id"],
            type="urgent_checkin",
            since=window_start,
        )
        missing = due_count - already
        if missing < 1:
            return
        # One per pass is enough; next scheduler tick catches up if needed.
        notifications.append(
            notifications_db.create_notification(
                task_id=task["id"],
                wp_user_id=assignee,
                type="urgent_checkin",
                message=f'Urgent check-in: please acknowledge "{title}" and start work.',
                requires_action=False,
            )
        )

    if stage == "reassigned":
        _maybe_send_checkin()

        if elapsed >= rules.URGENT_REASSIGN_ACK_WINDOW_SECONDS:
            # Second failure: notify creator + all dashboard admins (owner stand-in).
            # TODO(roles): replace "every manage_options user" with the real business
            # owner once docs/05-admin-roles-and-social-publishing-plan.md exists.
            # TODO(amy-execution): if Amy could complete this task herself, attempt
            # that before broadcasting no_one_available. Notify-only for now.
            _set_stage(task["id"], "creator_notified_no_one_available")
            recipients = set(tasks_db.list_dashboard_user_ids())
            recipients.add(int(task["created_by_wp_user_id"]))
            for uid in recipients:
                notifications.append(
                    notifications_db.create_notification(
                        task_id=task["id"],
                        wp_user_id=uid,
                        type="no_one_available",
                        message=(
                            f'No one acknowledged urgent task "{title}" after reassignment. '
                            "Please handle this personally — Amy cannot auto-complete it yet."
                        ),
                        requires_action=True,
                        action_payload={"task_id": task["id"]},
                    )
                )
        return notifications

    _maybe_send_checkin()

    # First reassignment attempt after ack window.
    if elapsed >= rules.URGENT_ACK_WINDOW_SECONDS and stage != "reassigned":
        # TODO(departments): narrow candidates to the same department/section once
        # docs/05-admin-roles-and-social-publishing-plan.md is implemented. For now
        # any other dashboard (manage_options) human user is eligible.
        candidates = tasks_db.list_dashboard_user_ids(exclude=assignee)
        if not candidates:
            _set_stage(task["id"], "creator_notified_no_one_available")
            recipients = set(tasks_db.list_dashboard_user_ids())
            recipients.add(int(task["created_by_wp_user_id"]))
            for uid in recipients:
                notifications.append(
                    notifications_db.create_notification(
                        task_id=task["id"],
                        wp_user_id=uid,
                        type="no_one_available",
                        message=(
                            f'No other team member is available for urgent task "{title}". '
                            "Please handle this personally — Amy cannot auto-complete it yet."
                        ),
                        requires_action=True,
                        action_payload={"task_id": task["id"]},
                    )
                )
            return notifications

        new_assignee = candidates[0]
        previous = assignee
        updated = tasks_db.update_task(
            task["id"],
            {
                "assignee_type": "human",
                "assignee_wp_user_id": new_assignee,
                "acknowledged_at": None,
                "escalation_stage": "reassigned",
                "escalation_stage_updated_at": now,
            },
        )
        # Dashboard action notice (legacy type) + assign template outbound.
        notifications.append(
            notifications_db.create_notification(
                task_id=task["id"],
                wp_user_id=new_assignee,
                type="reassigned_to_you",
                message=f'Urgent task "{title}" was reassigned to you. Please acknowledge and start work.',
                requires_action=True,
                action_payload={"task_id": task["id"]},
            )
        )
        if updated is not None:
            task_notify.dispatch_task_notify(
                "assign",
                updated,
                wp_user_id=new_assignee,
                create_dashboard=False,
            )
        for uid in {previous, int(task["created_by_wp_user_id"])}:
            if uid == new_assignee:
                continue
            notifications.append(
                notifications_db.create_notification(
                    task_id=task["id"],
                    wp_user_id=uid,
                    type="reassigned_notice",
                    message=f'Urgent task "{title}" was reassigned to another team member.',
                    requires_action=False,
                    action_payload={
                        "task_id": task["id"],
                        "new_assignee_wp_user_id": new_assignee,
                    },
                )
            )
        return notifications

    return notifications


def request_extension(
    task_id: str,
    requester_wp_user_id: int,
    requested_seconds: float,
) -> dict[str, Any]:
    """Create an extension request; auto-approve normal tasks under the 24h cap."""
    task = tasks_db.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.get("status") == "done":
        raise ValueError("Cannot extend a completed task")
    if requested_seconds <= 0:
        raise ValueError("requested_seconds must be positive")

    title = task.get("title") or "Task"
    due_ts = parse_due_timestamp(task.get("due_date"))
    if due_ts is None:
        # No due date yet — treat "now" as the base so an extension still lands.
        due_ts = time_now()

    is_urgent = task.get("priority") == "urgent"
    already = float(task.get("extension_total_seconds") or 0)
    creator = int(task["created_by_wp_user_id"])

    if is_urgent or (already + requested_seconds) > rules.EXTENSION_CAP_SECONDS:
        ext = notifications_db.create_extension_request(
            task_id=task_id,
            requested_by_wp_user_id=requester_wp_user_id,
            requested_seconds=requested_seconds,
            status="pending",
        )
        hours = requested_seconds / 3600.0
        reason = (
            "Urgent tasks never auto-extend — creator approval is required."
            if is_urgent
            else "This request exceeds the 24-hour automatic extension cap."
        )
        notifications_db.create_notification(
            task_id=task_id,
            wp_user_id=creator,
            type="extension_needs_approval",
            message=(
                f'Extension request for "{title}" ({hours:.1f}h). {reason}'
            ),
            requires_action=True,
            action_payload={
                "extension_request_id": ext["id"],
                "task_id": task_id,
                "requested_seconds": requested_seconds,
                "requested_by_wp_user_id": requester_wp_user_id,
            },
        )
        return {
            "extension_request": ext,
            "outcome": "pending_approval",
            "task": tasks_db.get_task(task_id),
        }

    # Auto-approve within cap.
    new_due = due_ts + requested_seconds
    updated = tasks_db.update_task(
        task_id,
        {
            "due_date": format_due_timestamp(new_due),
            "extension_total_seconds": already + requested_seconds,
        },
    )
    ext = notifications_db.create_extension_request(
        task_id=task_id,
        requested_by_wp_user_id=requester_wp_user_id,
        requested_seconds=requested_seconds,
        status="auto_approved",
    )
    hours = requested_seconds / 3600.0
    notifications_db.create_notification(
        task_id=task_id,
        wp_user_id=requester_wp_user_id,
        type="extension_auto_granted",
        message=f'Extension of {hours:.1f}h for "{title}" was granted automatically.',
        requires_action=False,
        action_payload={"extension_request_id": ext["id"], "task_id": task_id},
    )
    return {
        "extension_request": ext,
        "outcome": "auto_approved",
        "task": updated,
    }


def approve_extension(
    request_id: str, *, actor_wp_user_id: int
) -> dict[str, Any]:
    ext = notifications_db.get_extension_request(request_id)
    if ext is None:
        raise ValueError("Extension request not found")
    if ext["status"] != "pending":
        raise ValueError("Extension request is not pending")

    task = tasks_db.get_task(ext["task_id"])
    if task is None:
        raise ValueError("Task not found")
    if int(task["created_by_wp_user_id"]) != int(actor_wp_user_id):
        raise PermissionError("Only the task creator can approve extensions")

    due_ts = parse_due_timestamp(task.get("due_date")) or time_now()
    requested = float(ext["requested_seconds"])
    already = float(task.get("extension_total_seconds") or 0)
    updated = tasks_db.update_task(
        task["id"],
        {
            "due_date": format_due_timestamp(due_ts + requested),
            "extension_total_seconds": already + requested,
        },
    )
    resolved = notifications_db.update_extension_request(
        request_id, status="approved"
    )
    title = task.get("title") or "Task"
    hours = requested / 3600.0
    notifications_db.create_notification(
        task_id=task["id"],
        wp_user_id=int(ext["requested_by_wp_user_id"]),
        type="extension_approved",
        message=f'Your {hours:.1f}h extension for "{title}" was approved.',
        requires_action=False,
        action_payload={"extension_request_id": request_id, "task_id": task["id"]},
    )
    return {"extension_request": resolved, "task": updated}


def deny_extension(request_id: str, *, actor_wp_user_id: int) -> dict[str, Any]:
    ext = notifications_db.get_extension_request(request_id)
    if ext is None:
        raise ValueError("Extension request not found")
    if ext["status"] != "pending":
        raise ValueError("Extension request is not pending")

    task = tasks_db.get_task(ext["task_id"])
    if task is None:
        raise ValueError("Task not found")
    if int(task["created_by_wp_user_id"]) != int(actor_wp_user_id):
        raise PermissionError("Only the task creator can deny extensions")

    resolved = notifications_db.update_extension_request(request_id, status="denied")
    title = task.get("title") or "Task"
    hours = float(ext["requested_seconds"]) / 3600.0
    notifications_db.create_notification(
        task_id=task["id"],
        wp_user_id=int(ext["requested_by_wp_user_id"]),
        type="extension_denied",
        message=f'Your {hours:.1f}h extension for "{title}" was denied.',
        requires_action=False,
        action_payload={"extension_request_id": request_id, "task_id": task["id"]},
    )
    return {"extension_request": resolved, "task": task}


def run_escalation_pass() -> dict[str, int]:
    """Load open tasks and run the appropriate check for each."""
    tasks = tasks_db.list_tasks(exclude_done=True)
    checked = 0
    created = 0
    for task in tasks:
        checked += 1
        if task.get("priority") == "urgent":
            notes = check_urgent_task(task)
        else:
            notes = check_standard_task(task)
        created += len(notes)
    logger.info(
        "Task escalation pass: checked=%s notifications_created=%s",
        checked,
        created,
    )
    return {"tasks_checked": checked, "notifications_created": created}


def time_now(now: float | None = None) -> float:
    if now is not None:
        return float(now)
    return datetime.now(tz=timezone.utc).timestamp()
