"""SQLite store for Task Service notifications and extension requests."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from app.db.tasks_db import _DB_PATH, _DATA_DIR

_DATA_DIR.mkdir(parents=True, exist_ok=True)

VALID_NOTIFICATION_TYPES = frozenset(
    {
        "reminder_midpoint",
        "reminder_final",
        "urgent_checkin",
        "task_expired",
        "reassigned_to_you",
        "reassigned_notice",
        "extension_auto_granted",
        "extension_needs_approval",
        "extension_approved",
        "extension_denied",
        "no_one_available",
    }
)

VALID_EXTENSION_STATUSES = frozenset(
    {"pending", "auto_approved", "approved", "denied"}
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            wp_user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            requires_action INTEGER NOT NULL DEFAULT 0,
            action_payload TEXT,
            created_at REAL NOT NULL,
            read_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS extension_requests (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            requested_by_wp_user_id INTEGER NOT NULL,
            requested_seconds REAL NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            resolved_at REAL
        )
        """
    )
    return conn


def _notification_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload_raw = row["action_payload"]
    payload = None
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = None
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "wp_user_id": int(row["wp_user_id"]),
        "type": row["type"],
        "message": row["message"],
        "requires_action": bool(row["requires_action"]),
        "action_payload": payload,
        "created_at": float(row["created_at"]),
        "read_at": float(row["read_at"]) if row["read_at"] is not None else None,
    }


def _extension_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "requested_by_wp_user_id": int(row["requested_by_wp_user_id"]),
        "requested_seconds": float(row["requested_seconds"]),
        "status": row["status"],
        "created_at": float(row["created_at"]),
        "resolved_at": float(row["resolved_at"]) if row["resolved_at"] is not None else None,
    }


def create_notification(
    *,
    task_id: str,
    wp_user_id: int,
    type: str,
    message: str,
    requires_action: bool = False,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if type not in VALID_NOTIFICATION_TYPES:
        raise ValueError("invalid notification type")
    now = time.time()
    notif_id = str(uuid.uuid4())
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO notifications (
                    id, task_id, wp_user_id, type, message,
                    requires_action, action_payload, created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    notif_id,
                    task_id,
                    int(wp_user_id),
                    type,
                    message,
                    1 if requires_action else 0,
                    json.dumps(action_payload) if action_payload is not None else None,
                    now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notif_id,)
        ).fetchone()
        assert row is not None
        return _notification_from_row(row)
    finally:
        conn.close()


def list_notifications(
    *,
    wp_user_id: int,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["wp_user_id = ?"]
    params: list[Any] = [int(wp_user_id)]
    if unread_only:
        clauses.append("read_at IS NULL")
    sql = (
        "SELECT * FROM notifications WHERE "
        + " AND ".join(clauses)
        + " ORDER BY created_at DESC"
    )
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_notification_from_row(r) for r in rows]
    finally:
        conn.close()


def count_notifications(
    *,
    task_id: str,
    type: str,
    since: float | None = None,
) -> int:
    clauses = ["task_id = ?", "type = ?"]
    params: list[Any] = [task_id, type]
    if since is not None:
        clauses.append("created_at >= ?")
        params.append(float(since))
    sql = "SELECT COUNT(*) FROM notifications WHERE " + " AND ".join(clauses)
    conn = _connect()
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


def get_notification(notif_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notif_id,)
        ).fetchone()
        return _notification_from_row(row) if row else None
    finally:
        conn.close()


def mark_notification_read(notif_id: str) -> dict[str, Any] | None:
    existing = get_notification(notif_id)
    if existing is None:
        return None
    if existing.get("read_at") is not None:
        return existing
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE notifications SET read_at = ? WHERE id = ?",
                (now, notif_id),
            )
        return get_notification(notif_id)
    finally:
        conn.close()


def create_extension_request(
    *,
    task_id: str,
    requested_by_wp_user_id: int,
    requested_seconds: float,
    status: str,
) -> dict[str, Any]:
    if status not in VALID_EXTENSION_STATUSES:
        raise ValueError("invalid extension status")
    if requested_seconds <= 0:
        raise ValueError("requested_seconds must be positive")
    now = time.time()
    req_id = str(uuid.uuid4())
    resolved_at = now if status in {"auto_approved", "approved", "denied"} else None
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO extension_requests (
                    id, task_id, requested_by_wp_user_id, requested_seconds,
                    status, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req_id,
                    task_id,
                    int(requested_by_wp_user_id),
                    float(requested_seconds),
                    status,
                    now,
                    resolved_at,
                ),
            )
        row = conn.execute(
            "SELECT * FROM extension_requests WHERE id = ?", (req_id,)
        ).fetchone()
        assert row is not None
        return _extension_from_row(row)
    finally:
        conn.close()


def get_extension_request(request_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM extension_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return _extension_from_row(row) if row else None
    finally:
        conn.close()


def update_extension_request(
    request_id: str, *, status: str, resolved_at: float | None = None
) -> dict[str, Any] | None:
    if status not in VALID_EXTENSION_STATUSES:
        raise ValueError("invalid extension status")
    existing = get_extension_request(request_id)
    if existing is None:
        return None
    now = time.time() if resolved_at is None else resolved_at
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE extension_requests
                SET status = ?, resolved_at = ?
                WHERE id = ?
                """,
                (status, now, request_id),
            )
        return get_extension_request(request_id)
    finally:
        conn.close()
