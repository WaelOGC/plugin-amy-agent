"""Persistent SQLite store for Task Service (no TTL — rows live until deleted)."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

AssigneeType = Literal["amy", "human"]
Priority = Literal["normal", "urgent"]
TaskStatus = Literal["todo", "in_progress", "waiting_extension", "done"]
EscalationStage = Literal[
    "none",
    "midpoint_sent",
    "final_warning_sent",
    "expired",
    "reassigned",
    "creator_notified_no_one_available",
]

VALID_ASSIGNEE_TYPES = frozenset({"amy", "human"})
VALID_PRIORITIES = frozenset({"normal", "urgent"})
VALID_STATUSES = frozenset({"todo", "in_progress", "waiting_extension", "done"})
VALID_ESCALATION_STAGES = frozenset(
    {
        "none",
        "midpoint_sent",
        "final_warning_sent",
        "expired",
        "reassigned",
        "creator_notified_no_one_available",
    }
)

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "tasks.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

_TASK_COLUMN_DEFAULTS: dict[str, str] = {
    "escalation_stage": "TEXT NOT NULL DEFAULT 'none'",
    "escalation_stage_updated_at": "REAL",
    "acknowledged_at": "REAL",
    "extension_total_seconds": "REAL NOT NULL DEFAULT 0",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            assignee_type TEXT NOT NULL,
            assignee_wp_user_id INTEGER,
            created_by_wp_user_id INTEGER NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            escalation_stage TEXT NOT NULL DEFAULT 'none',
            escalation_stage_updated_at REAL,
            acknowledged_at REAL,
            extension_total_seconds REAL NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_users (
            wp_user_id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL DEFAULT '',
            synced_at REAL NOT NULL
        )
        """
    )
    _migrate_tasks_columns(conn)
    return conn


def _migrate_tasks_columns(conn: sqlite3.Connection) -> None:
    """Add Task-2 columns safely against an existing Task-1 tasks.db."""
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    for name, decl in _TASK_COLUMN_DEFAULTS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "assignee_type": row["assignee_type"],
        "assignee_wp_user_id": row["assignee_wp_user_id"],
        "created_by_wp_user_id": row["created_by_wp_user_id"],
        "priority": row["priority"],
        "status": row["status"],
        "due_date": row["due_date"],
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "escalation_stage": row["escalation_stage"] if "escalation_stage" in keys else "none",
        "escalation_stage_updated_at": (
            float(row["escalation_stage_updated_at"])
            if "escalation_stage_updated_at" in keys and row["escalation_stage_updated_at"] is not None
            else None
        ),
        "acknowledged_at": (
            float(row["acknowledged_at"])
            if "acknowledged_at" in keys and row["acknowledged_at"] is not None
            else None
        ),
        "extension_total_seconds": float(
            row["extension_total_seconds"]
            if "extension_total_seconds" in keys and row["extension_total_seconds"] is not None
            else 0
        ),
    }


def create_task(
    *,
    title: str,
    created_by_wp_user_id: int,
    assignee_type: AssigneeType = "human",
    assignee_wp_user_id: int | None = None,
    description: str | None = None,
    priority: Priority = "normal",
    status: TaskStatus = "todo",
    due_date: str | None = None,
) -> dict[str, Any]:
    """Insert a new task and return the full row dict."""
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    if assignee_type not in VALID_ASSIGNEE_TYPES:
        raise ValueError("invalid assignee_type")
    if priority not in VALID_PRIORITIES:
        raise ValueError("invalid priority")
    if status not in VALID_STATUSES:
        raise ValueError("invalid status")
    if assignee_type == "amy":
        assignee_wp_user_id = None
    elif assignee_wp_user_id is None:
        raise ValueError("assignee_wp_user_id is required when assignee_type is human")

    now = time.time()
    task_id = str(uuid.uuid4())
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, title, description, assignee_type, assignee_wp_user_id,
                    created_by_wp_user_id, priority, status, due_date,
                    created_at, updated_at,
                    escalation_stage, escalation_stage_updated_at,
                    acknowledged_at, extension_total_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'none', NULL, NULL, 0)
                """,
                (
                    task_id,
                    title,
                    description,
                    assignee_type,
                    assignee_wp_user_id,
                    int(created_by_wp_user_id),
                    priority,
                    status,
                    due_date,
                    now,
                    now,
                ),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def get_task(task_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_tasks(
    *,
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    assignee_wp_user_id: int | None = None,
    exclude_done: bool = False,
) -> list[dict[str, Any]]:
    """Return tasks matching optional filters, newest first."""
    clauses: list[str] = []
    params: list[Any] = []

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError("invalid status")
        clauses.append("status = ?")
        params.append(status)
    if exclude_done:
        clauses.append("status != 'done'")
    if priority is not None:
        if priority not in VALID_PRIORITIES:
            raise ValueError("invalid priority")
        clauses.append("priority = ?")
        params.append(priority)
    if assignee_wp_user_id is not None:
        clauses.append("assignee_wp_user_id = ?")
        params.append(int(assignee_wp_user_id))

    sql = "SELECT * FROM tasks"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def update_task(task_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """Partial update. Returns updated row, or None if the task does not exist."""
    allowed = {
        "title",
        "description",
        "assignee_type",
        "assignee_wp_user_id",
        "priority",
        "status",
        "due_date",
        "escalation_stage",
        "escalation_stage_updated_at",
        "acknowledged_at",
        "extension_total_seconds",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_task(task_id)

    if "title" in updates:
        title = (updates["title"] or "").strip() if updates["title"] is not None else ""
        if not title:
            raise ValueError("title cannot be empty")
        updates["title"] = title

    if "assignee_type" in updates and updates["assignee_type"] not in VALID_ASSIGNEE_TYPES:
        raise ValueError("invalid assignee_type")
    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        raise ValueError("invalid priority")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError("invalid status")
    if (
        "escalation_stage" in updates
        and updates["escalation_stage"] not in VALID_ESCALATION_STAGES
    ):
        raise ValueError("invalid escalation_stage")

    existing = get_task(task_id)
    if existing is None:
        return None

    assignee_type = updates.get("assignee_type", existing["assignee_type"])
    if assignee_type == "amy":
        updates["assignee_wp_user_id"] = None
    elif "assignee_type" in updates or "assignee_wp_user_id" in updates:
        assignee_wp_user_id = updates.get(
            "assignee_wp_user_id", existing["assignee_wp_user_id"]
        )
        if assignee_wp_user_id is None:
            raise ValueError("assignee_wp_user_id is required when assignee_type is human")
        updates["assignee_wp_user_id"] = int(assignee_wp_user_id)

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values()) + [task_id]

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                params,
            )
            if cur.rowcount == 0:
                return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    """Delete a task. Returns True if a row was removed."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def acknowledge_task(task_id: str) -> dict[str, Any] | None:
    """Set acknowledged_at if not already set. Returns the task row."""
    existing = get_task(task_id)
    if existing is None:
        return None
    if existing.get("acknowledged_at") is not None:
        return existing
    return update_task(task_id, {"acknowledged_at": time.time()})


def sync_dashboard_users(users: list[dict[str, Any]]) -> int:
    """Replace the cached WP dashboard-user pool used for reassignment.

    WordPress pushes manage_options users here because the Python service
    has no direct WP user directory.
    """
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM dashboard_users")
            for user in users:
                uid = int(user.get("wp_user_id") or 0)
                if uid < 1:
                    continue
                conn.execute(
                    """
                    INSERT INTO dashboard_users (wp_user_id, display_name, synced_at)
                    VALUES (?, ?, ?)
                    """,
                    (uid, str(user.get("display_name") or ""), now),
                )
        return conn.execute("SELECT COUNT(*) FROM dashboard_users").fetchone()[0]
    finally:
        conn.close()


def list_dashboard_user_ids(*, exclude: int | None = None) -> list[int]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT wp_user_id FROM dashboard_users ORDER BY wp_user_id ASC"
        ).fetchall()
        ids = [int(r[0]) for r in rows]
        if exclude is not None:
            ids = [i for i in ids if i != int(exclude)]
        return ids
    finally:
        conn.close()


def get_stats() -> dict[str, Any]:
    """Aggregate counts for the Task Service stat cards.

    Definitions:
    - open_tasks: status != done
    - urgent_tasks: priority == urgent AND status != done
    - completed_this_week: status == done AND updated_at within the last 7 days
    - team_completion_rate: among tasks created in the last 30 days,
      (done count / total count) * 100, rounded to nearest int. 0 when none.
    """
    now = time.time()
    week_ago = now - (7 * 24 * 60 * 60)
    month_ago = now - (30 * 24 * 60 * 60)

    conn = _connect()
    try:
        open_tasks = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status != 'done'"
        ).fetchone()[0]
        urgent_tasks = conn.execute(
            """
            SELECT COUNT(*) FROM tasks
            WHERE priority = 'urgent' AND status != 'done'
            """
        ).fetchone()[0]
        completed_this_week = conn.execute(
            """
            SELECT COUNT(*) FROM tasks
            WHERE status = 'done' AND updated_at >= ?
            """,
            (week_ago,),
        ).fetchone()[0]
        created_last_30 = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE created_at >= ?",
            (month_ago,),
        ).fetchone()[0]
        done_created_last_30 = conn.execute(
            """
            SELECT COUNT(*) FROM tasks
            WHERE created_at >= ? AND status = 'done'
            """,
            (month_ago,),
        ).fetchone()[0]
    finally:
        conn.close()

    if created_last_30 == 0:
        rate = 0
    else:
        rate = int(round((done_created_last_30 / created_last_30) * 100))

    return {
        "open_tasks": int(open_tasks),
        "urgent_tasks": int(urgent_tasks),
        "completed_this_week": int(completed_this_week),
        "team_completion_rate": rate,
    }
