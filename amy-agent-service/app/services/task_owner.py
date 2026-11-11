"""P3 owner / backup resolution for Task Service expiry escalate.

Locked decisions (2026-11-11):
- Owner = task creator (``owner_wp_user_id`` / ``created_by_wp_user_id``).
- If creator has no Telegram or is gone → site default owner.
- Backup is the next fallback when site default is unset.
- Reachable = present in synced dashboard pool AND Telegram chat linked.
"""

from __future__ import annotations

from typing import Any

from app.db import tasks_db


def task_owner_id(task: dict[str, Any]) -> int:
    raw = task.get("owner_wp_user_id")
    if raw is not None:
        return int(raw)
    return int(task["created_by_wp_user_id"])


def task_backup_id(task: dict[str, Any]) -> int | None:
    raw = task.get("backup_wp_user_id")
    if raw is not None:
        return int(raw)
    return tasks_db.get_dashboard_user_backup(task_owner_id(task))


def is_reachable(wp_user_id: int | None) -> bool:
    """Creator/owner is reachable when still a dashboard user with Telegram linked."""
    if wp_user_id is None:
        return False
    uid = int(wp_user_id)
    if uid < 1:
        return False
    if not tasks_db.is_dashboard_user(uid):
        return False
    return tasks_db.is_telegram_linked(uid)


def resolve_expiry_escalatee(task: dict[str, Any]) -> dict[str, Any]:
    """Who gets the expiry notify (owner → site default → backup → owner fallback)."""
    owner = task_owner_id(task)
    if is_reachable(owner):
        return {
            "wp_user_id": owner,
            "role": "owner",
            "reason": "owner_reachable",
        }

    site_default = tasks_db.get_site_default_owner()
    if site_default is not None and int(site_default) > 0:
        return {
            "wp_user_id": int(site_default),
            "role": "site_default",
            "reason": "owner_unreachable_site_default",
        }

    backup = task_backup_id(task)
    if backup is not None and int(backup) > 0:
        return {
            "wp_user_id": int(backup),
            "role": "backup",
            "reason": "owner_unreachable_backup",
        }

    return {
        "wp_user_id": owner,
        "role": "owner",
        "reason": "owner_fallback",
    }


def expiry_action_choices(task: dict[str, Any]) -> list[str]:
    """Dashboard action choices for an expired task."""
    choices = ["reassign_same", "reassign_other", "acknowledge_manual"]
    if task.get("amy_capable"):
        choices.append("amy_take")
    return choices
