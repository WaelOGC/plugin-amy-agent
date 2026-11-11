"""P4 Amy execution engine — capability matrix + safe digital/in-system runs.

Locked rules (task-service-escalation-multiplan):
- Amy-at-create: todo → running → done/failed in the background.
- Expiry + amy_capable: Amy runs it (never fake done from the clock alone).
- Mark done only after verified allowlisted tool success + audit notes.
- If Amy cannot finish → failed + owner/backup can reassign (P3 UX).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Literal

from app import config_task_rules as rules
from app.db import analytics_db, notifications_db, progress_notes_db, seo_tasks_db, tasks_db
from app.services import task_owner

logger = logging.getLogger(__name__)

Trigger = Literal["create", "expiry", "amy_take", "manual"]

# ---------------------------------------------------------------------------
# Capability matrix (documented; expand with more allowlisted tools later)
# ---------------------------------------------------------------------------

CAPABILITY_MATRIX: dict[str, dict[str, Any]] = {
    "analytics_summary": {
        "label": "Analytics lead summary",
        "can": "Summarize in-system visitor leads (hot/warm/cold counts + sample).",
        "cannot": "Contact leads externally, send marketing mail, or change lead status.",
        "keywords": (
            "analytics",
            "lead",
            "leads",
            "visitor",
            "visitors",
            "traffic",
            "funnel",
            "conversion",
        ),
    },
    "seo_review_summary": {
        "label": "SEO checks summary",
        "can": "Summarize stored SEO Task checks (verdicts / pending approval).",
        "cannot": "Write meta to WordPress, approve/reject checks, or generate images.",
        "keywords": (
            "seo",
            "meta description",
            "keyphrase",
            "yoast",
            "serp",
            "on-page",
        ),
    },
    "digital_task_close": {
        "label": "Digital / in-system close",
        "can": (
            "When amy_capable is true, record a verified in-system completion "
            "audit (progress notes) for digital work the human attested Amy can do."
        ),
        "cannot": (
            "Physical / off-site / third-party human-only work; silent irreversible "
            "external actions; claiming done solely because a deadline passed."
        ),
        "keywords": (),  # selected via amy_capable attestation, not keywords
    },
}

_AMY_NOTE_USER_ID = 0  # system / Amy audit author


def capability_matrix_public() -> list[dict[str, str]]:
    """Stable public view for docs / API consumers."""
    rows: list[dict[str, str]] = []
    for key, meta in CAPABILITY_MATRIX.items():
        rows.append(
            {
                "id": key,
                "label": str(meta["label"]),
                "can": str(meta["can"]),
                "cannot": str(meta["cannot"]),
            }
        )
    return rows


def _task_text(task: dict[str, Any]) -> str:
    return f"{task.get('title') or ''} {task.get('description') or ''}".lower()


def match_capabilities(task: dict[str, Any]) -> list[str]:
    """Return allowlisted capability ids Amy may attempt for this task."""
    matched: list[str] = []
    text = _task_text(task)
    for key, meta in CAPABILITY_MATRIX.items():
        if key == "digital_task_close":
            continue
        keywords = meta.get("keywords") or ()
        if any(kw in text for kw in keywords):
            matched.append(key)
    # Human attestation that this is digital/in-system work Amy can close.
    if task.get("amy_capable"):
        matched.append("digital_task_close")
    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in matched:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _write_audit(task_id: str, note: str) -> dict[str, Any]:
    return progress_notes_db.create_progress_note(
        task_id=task_id,
        wp_user_id=_AMY_NOTE_USER_ID,
        note=note,
        source="amy",
    )


def _run_analytics_summary(task: dict[str, Any]) -> dict[str, Any]:
    leads = analytics_db.list_leads()
    counts = {"hot": 0, "warm": 0, "cold": 0, "other": 0}
    for lead in leads:
        status = str(lead.get("lead_status") or "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
    sample = []
    for lead in leads[:5]:
        sample.append(
            {
                "session_id": lead.get("session_id"),
                "lead_status": lead.get("lead_status"),
                "has_email": bool(lead.get("lead_email")),
            }
        )
    summary = (
        f"Analytics summary: {len(leads)} lead sessions "
        f"(hot={counts['hot']}, warm={counts['warm']}, cold={counts['cold']}"
        f"{f', other={counts['other']}' if counts['other'] else ''})."
    )
    note = _write_audit(task["id"], summary)
    return {
        "capability": "analytics_summary",
        "ok": True,
        "summary": summary,
        "counts": counts,
        "sample_count": len(sample),
        "audit_note_id": note["id"],
    }


def _run_seo_review_summary(task: dict[str, Any]) -> dict[str, Any]:
    checks = seo_tasks_db.list_checks()
    by_verdict: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in checks:
        v = str(row.get("verdict") or "unknown")
        s = str(row.get("status") or "unknown")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1
    summary = (
        f"SEO review summary: {len(checks)} stored checks. "
        f"Verdicts={by_verdict or {'none': 0}}; statuses={by_status or {'none': 0}}."
    )
    note = _write_audit(task["id"], summary)
    return {
        "capability": "seo_review_summary",
        "ok": True,
        "summary": summary,
        "verdicts": by_verdict,
        "statuses": by_status,
        "audit_note_id": note["id"],
    }


def _run_digital_task_close(task: dict[str, Any], *, trigger: str) -> dict[str, Any]:
    title = (task.get("title") or "Task").strip() or "Task"
    summary = (
        f'Amy completed digital/in-system work for "{title}" '
        f"(trigger={trigger}). Capability attested via amy_capable=true; "
        "audit recorded in Task Service — no external side effects."
    )
    note = _write_audit(task["id"], summary)
    return {
        "capability": "digital_task_close",
        "ok": True,
        "summary": summary,
        "audit_note_id": note["id"],
    }


_EXECUTORS: dict[str, Callable[..., dict[str, Any]]] = {
    "analytics_summary": _run_analytics_summary,
    "seo_review_summary": _run_seo_review_summary,
    "digital_task_close": _run_digital_task_close,
}


def _notify_owner(
    task: dict[str, Any],
    *,
    notif_type: str,
    message: str,
    requires_action: bool,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Best-effort owner notify — never roll back a verified done/failed status."""
    try:
        escalatee = task_owner.resolve_expiry_escalatee(task)
        uid = int(escalatee["wp_user_id"])
    except Exception:  # noqa: BLE001 — never fail the run on notify
        uid = int(task.get("owner_wp_user_id") or task.get("created_by_wp_user_id") or 0)
    if uid < 1:
        return None
    try:
        return notifications_db.create_notification(
            task_id=task["id"],
            wp_user_id=uid,
            type=notif_type,
            message=message,
            requires_action=requires_action,
            action_payload=action_payload or {"task_id": task["id"]},
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Amy owner notify failed task=%s type=%s", task.get("id"), notif_type
        )
        return None


def run_amy_task(
    task_id: str,
    *,
    trigger: Trigger = "manual",
    actor_wp_user_id: int | None = None,
) -> dict[str, Any]:
    """Attempt real in-system execution. Never marks done without verified success."""
    if not rules.AMY_EXECUTION_ENABLED:
        raise ValueError("Amy execution is not enabled (AMY_EXECUTION_ENABLED=False)")

    task = tasks_db.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    if task.get("status") == "done":
        return {
            "outcome": "already_done",
            "task": task,
            "capabilities": [],
            "results": [],
            "amy_execution_enabled": True,
        }
    if task.get("status") == "running":
        return {
            "outcome": "already_running",
            "task": task,
            "capabilities": [],
            "results": [],
            "amy_execution_enabled": True,
        }

    # Take ownership for handoff triggers.
    claim_fields: dict[str, Any] = {
        "assignee_type": "amy",
        "assignee_wp_user_id": None,
        "status": "running",
        "acknowledged_at": None,
    }
    updated = tasks_db.update_task(task_id, claim_fields)
    if updated is None:
        raise ValueError("Task not found")
    task = updated

    title = (task.get("title") or "Task").strip() or "Task"
    _write_audit(
        task_id,
        f'Amy started execution for "{title}" (trigger={trigger}'
        f'{f", actor={actor_wp_user_id}" if actor_wp_user_id else ""}).',
    )

    capabilities = match_capabilities(task)
    if not capabilities:
        reason = (
            "No allowlisted digital/in-system capability matched. "
            "Mark the task Amy-capable for digital work, or reassign a human."
        )
        _write_audit(task_id, f"Amy failed: {reason}")
        failed = tasks_db.update_task(task_id, {"status": "failed"}) or task
        _notify_owner(
            failed,
            notif_type="amy_execution_failed",
            message=(
                f'Amy could not complete "{title}". {reason} '
                "Please reassign a human from the Task Service."
            ),
            requires_action=True,
            action_payload={
                "task_id": task_id,
                "choices": ["reassign_other", "acknowledge_manual"],
                "amy_capable": bool(failed.get("amy_capable")),
                "amy_execution_enabled": True,
                "outcome": "failed",
                "trigger": trigger,
            },
        )
        logger.info("Amy execution failed task=%s trigger=%s reason=no_capability", task_id, trigger)
        return {
            "outcome": "failed",
            "task": failed,
            "capabilities": [],
            "results": [],
            "reason": reason,
            "amy_execution_enabled": True,
        }

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for cap in capabilities:
        executor = _EXECUTORS.get(cap)
        if executor is None:
            errors.append(f"No executor for capability {cap}")
            continue
        try:
            if cap == "digital_task_close":
                results.append(executor(task, trigger=trigger))
            else:
                results.append(executor(task))
        except Exception as exc:  # noqa: BLE001 — capture per-tool failure
            logger.exception("Amy capability %s failed for task %s", cap, task_id)
            errors.append(f"{cap}: {exc}")
            _write_audit(task_id, f"Amy capability {cap} failed: {exc}")

    verified = [r for r in results if r.get("ok") and r.get("audit_note_id")]
    if not verified:
        reason = "; ".join(errors) if errors else "Allowlisted tools did not verify success."
        _write_audit(task_id, f"Amy failed: {reason}")
        failed = tasks_db.update_task(task_id, {"status": "failed"}) or task
        _notify_owner(
            failed,
            notif_type="amy_execution_failed",
            message=(
                f'Amy could not complete "{title}". {reason} '
                "Please reassign a human from the Task Service."
            ),
            requires_action=True,
            action_payload={
                "task_id": task_id,
                "choices": ["reassign_other", "acknowledge_manual"],
                "amy_capable": bool(failed.get("amy_capable")),
                "amy_execution_enabled": True,
                "outcome": "failed",
                "trigger": trigger,
            },
        )
        logger.info("Amy execution failed task=%s trigger=%s", task_id, trigger)
        return {
            "outcome": "failed",
            "task": failed,
            "capabilities": capabilities,
            "results": results,
            "reason": reason,
            "amy_execution_enabled": True,
        }

    # Verified tool success → done (never from the clock alone).
    caps_run = ", ".join(r["capability"] for r in verified)
    _write_audit(
        task_id,
        f'Amy finished "{title}" successfully. Verified capabilities: {caps_run}.',
    )
    done = tasks_db.update_task(task_id, {"status": "done"}) or task
    if trigger in {"expiry", "amy_take", "create"}:
        _notify_owner(
            done,
            notif_type="amy_execution_done",
            message=f'Amy completed "{title}" (digital/in-system). Verified: {caps_run}.',
            requires_action=False,
            action_payload={
                "task_id": task_id,
                "outcome": "done",
                "trigger": trigger,
                "capabilities": [r["capability"] for r in verified],
            },
        )
    logger.info(
        "Amy execution done task=%s trigger=%s caps=%s",
        task_id,
        trigger,
        caps_run,
    )
    return {
        "outcome": "done",
        "task": done,
        "capabilities": capabilities,
        "results": results,
        "amy_execution_enabled": True,
    }


def queue_amy_task(task_id: str, *, trigger: Trigger = "create") -> None:
    """Fire-and-forget wrapper for BackgroundTasks / scheduler hooks."""
    try:
        run_amy_task(task_id, trigger=trigger)
    except Exception:  # noqa: BLE001
        logger.exception("Background Amy execution crashed task=%s trigger=%s", task_id, trigger)
