"""Shared SEO + Task Service summaries for Task P4 execution and admin chat (P2).

Reuses the same SQLite sources Overview already reads:
- SEO: ``seo_tasks_db.list_checks()`` (open = pending_approval, fixed = approved)
- Tasks: ``tasks_db.get_stats()`` + in-progress / running board counts

Chat may **report** these summaries only — no approve / write / reassign from chat.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db import seo_tasks_db, tasks_db

logger = logging.getLogger(__name__)


def build_seo_review_summary() -> dict[str, Any]:
    """Return live SEO check counts from ``seo_tasks.db``.

    On success: ``ok=True`` with ``total``, ``verdicts``, ``statuses``,
    ``open_count`` (pending_approval), ``fixed_count`` (approved), ``summary``.
    Empty DB is ``ok=True`` with ``total=0``. On failure: ``ok=False`` with an
    honest unavailable ``summary`` — never invents numbers.
    """
    try:
        checks = seo_tasks_db.list_checks()
    except Exception as exc:  # noqa: BLE001 — chat/task must degrade honestly
        logger.exception("SEO review summary failed")
        return {
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "summary": (
                "SEO Tasks unavailable: could not read stored SEO checks "
                "(service/connection)."
            ),
            "total": 0,
            "verdicts": {},
            "statuses": {},
            "open_count": 0,
            "fixed_count": 0,
            "rejected_count": 0,
            "empty": True,
        }

    by_verdict: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in checks:
        v = str(row.get("verdict") or "unknown")
        s = str(row.get("status") or "unknown")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1

    total = len(checks)
    open_count = int(by_status.get("pending_approval") or 0)
    fixed_count = int(by_status.get("approved") or 0)
    rejected_count = int(by_status.get("rejected") or 0)
    summary = (
        f"SEO review summary: {total} stored checks "
        f"(open/pending_approval={open_count}, fixed/approved={fixed_count}, "
        f"rejected={rejected_count}; "
        f"verdicts={by_verdict or {'none': 0}}; "
        f"statuses={by_status or {'none': 0}})."
    )
    return {
        "ok": True,
        "total": total,
        "verdicts": by_verdict,
        "statuses": by_status,
        "open_count": open_count,
        "fixed_count": fixed_count,
        "rejected_count": rejected_count,
        "empty": total == 0,
        "summary": summary,
    }


def build_task_service_summary() -> dict[str, Any]:
    """Return live Task Service board stats from ``tasks.db``.

    Mirrors Overview cards: open / urgent / in-progress (+ running), plus
    completed_this_week and team_completion_rate from ``get_stats()``.
    """
    try:
        stats = tasks_db.get_stats()
        in_progress = len(tasks_db.list_tasks(status="in_progress"))
        running = len(tasks_db.list_tasks(status="running"))
    except Exception as exc:  # noqa: BLE001 — chat/task must degrade honestly
        logger.exception("Task Service summary failed")
        return {
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "summary": (
                "Task Service unavailable: could not read task board stats "
                "(service/connection)."
            ),
            "open_tasks": 0,
            "urgent_tasks": 0,
            "in_progress": 0,
            "running": 0,
            "completed_this_week": 0,
            "team_completion_rate": 0,
            "empty": True,
        }

    open_tasks = int(stats.get("open_tasks") or 0)
    urgent_tasks = int(stats.get("urgent_tasks") or 0)
    completed_this_week = int(stats.get("completed_this_week") or 0)
    team_completion_rate = int(stats.get("team_completion_rate") or 0)
    summary = (
        f"Task Service summary: open={open_tasks}, urgent={urgent_tasks}, "
        f"in_progress={in_progress}, running={running}, "
        f"completed_this_week={completed_this_week}, "
        f"team_completion_rate={team_completion_rate}%."
    )
    return {
        "ok": True,
        "open_tasks": open_tasks,
        "urgent_tasks": urgent_tasks,
        "in_progress": in_progress,
        "running": running,
        "completed_this_week": completed_this_week,
        "team_completion_rate": team_completion_rate,
        "empty": open_tasks == 0 and completed_this_week == 0,
        "summary": summary,
    }


def seo_review_summary_for_chat() -> dict[str, Any]:
    """Admin chat snapshot — same read path as Task P4 ``seo_review_summary``."""
    return build_seo_review_summary()


def task_service_summary_for_chat() -> dict[str, Any]:
    """Admin chat snapshot — same stats Overview / ``GET /v1/tasks/stats`` use."""
    return build_task_service_summary()


def format_seo_chat_context(snapshot: dict[str, Any]) -> str:
    """System-message body for SEO checks — report-only, honest empty/unavailable."""
    if not snapshot.get("ok"):
        return (
            "Live SEO Tasks snapshot: UNAVAILABLE.\n"
            "You could not reach SEO Tasks just now (service/connection error).\n"
            "If asked about SEO open issues, pending approvals, or verdicts, say "
            "plainly that you couldn't reach SEO Tasks right now and suggest "
            "Amy → SEO Tasks / Overview.\n"
            "Do NOT say SEO is permanently unavailable. Do NOT invent counts. "
            "Do NOT approve, reject, or write SEO meta from chat."
        )

    if snapshot.get("empty") or int(snapshot.get("total") or 0) == 0:
        return (
            "Live SEO Tasks snapshot: EMPTY.\n"
            "No SEO checks stored yet (total=0, open=0, fixed=0, rejected=0).\n"
            "If asked about SEO open count or pending approvals, say there are "
            "no SEO checks recorded yet — not that you lack access.\n"
            "Do NOT invent counts. Do NOT approve/reject/write SEO from chat."
        )

    verdicts = snapshot.get("verdicts") or {}
    statuses = snapshot.get("statuses") or {}
    verdict_bits = ", ".join(
        f"{k}={int(v)}" for k, v in sorted(verdicts.items())
    ) or "none"
    status_bits = ", ".join(
        f"{k}={int(v)}" for k, v in sorted(statuses.items())
    ) or "none"

    lines = [
        "Live SEO Tasks snapshot (stored checks — report only):",
        f"- total_checks: {int(snapshot.get('total') or 0)}",
        f"- open (pending_approval): {int(snapshot.get('open_count') or 0)}",
        f"- fixed (approved): {int(snapshot.get('fixed_count') or 0)}",
        f"- rejected: {int(snapshot.get('rejected_count') or 0)}",
        f"- verdicts: {verdict_bits}",
        f"- statuses: {status_bits}",
        "When the teammate asks about SEO open issues, pending approvals, "
        "verdicts, or fixed checks, cite these figures.",
        "You may REPORT summaries only. Do NOT approve, reject, write Yoast/"
        "meta to WordPress, generate images, or claim you applied SEO changes "
        "from this chat.",
        "Do NOT invent other numbers beyond this snapshot.",
    ]
    return "\n".join(lines)


def format_task_service_chat_context(snapshot: dict[str, Any]) -> str:
    """System-message body for Task Service board — report-only."""
    if not snapshot.get("ok"):
        return (
            "Live Task Service snapshot: UNAVAILABLE.\n"
            "You could not reach Task Service just now (service/connection error).\n"
            "If asked about open, urgent, or in-progress tasks, say plainly that "
            "you couldn't reach Task Service right now and suggest Amy → Task "
            "Service / Overview.\n"
            "Do NOT say Task Service is permanently unavailable. Do NOT invent "
            "counts. Do NOT reassign or mark tasks done from chat."
        )

    open_tasks = int(snapshot.get("open_tasks") or 0)
    urgent = int(snapshot.get("urgent_tasks") or 0)
    in_progress = int(snapshot.get("in_progress") or 0)
    running = int(snapshot.get("running") or 0)
    completed = int(snapshot.get("completed_this_week") or 0)
    rate = int(snapshot.get("team_completion_rate") or 0)

    if snapshot.get("empty") and open_tasks == 0 and completed == 0:
        return (
            "Live Task Service snapshot: EMPTY.\n"
            "No tasks on the board yet (open=0, urgent=0, in_progress=0, "
            "running=0, completed_this_week=0).\n"
            "If asked about urgent or in-progress tasks, say there are none "
            "recorded yet — not that you lack access.\n"
            "Do NOT invent counts. Do NOT reassign or change task status from chat."
        )

    lines = [
        "Live Task Service snapshot (board stats — report only):",
        f"- open_tasks: {open_tasks} (status != done)",
        f"- urgent_tasks: {urgent} (priority=urgent and not done)",
        f"- in_progress: {in_progress}",
        f"- running (Amy execution): {running}",
        f"- completed_this_week: {completed}",
        f"- team_completion_rate: {rate}% (done among created last 30d)",
        "When the teammate asks about urgent tasks, open tasks, in-progress "
        "work, or board stats, cite these figures.",
        "You may REPORT summaries only. Do NOT reassign owners, acknowledge "
        "escalations, mark done/failed, or change priority/status from this chat "
        "unless a separate explicit write tool already allows it (none here).",
        "Do NOT invent other numbers beyond this snapshot.",
    ]
    return "\n".join(lines)
