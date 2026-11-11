"""Minimal progress-note storage for Telegram (and later dashboard) mid replies."""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any

from app.db.tasks_db import _DB_PATH, _DATA_DIR

_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_progress_notes (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            wp_user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_progress_replies (
            wp_user_id INTEGER PRIMARY KEY,
            task_id TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    return conn


def _note_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "wp_user_id": int(row["wp_user_id"]),
        "source": row["source"],
        "note": row["note"],
        "created_at": float(row["created_at"]),
    }


def create_progress_note(
    *,
    task_id: str,
    wp_user_id: int,
    note: str,
    source: str = "telegram",
) -> dict[str, Any]:
    text = (note or "").strip()
    if not text:
        raise ValueError("note is required")
    if source not in {"telegram", "dashboard", "api"}:
        raise ValueError("invalid source")
    now = time.time()
    note_id = str(uuid.uuid4())
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO task_progress_notes (
                    id, task_id, wp_user_id, source, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (note_id, task_id, int(wp_user_id), source, text, now),
            )
        row = conn.execute(
            "SELECT * FROM task_progress_notes WHERE id = ?", (note_id,)
        ).fetchone()
        assert row is not None
        return _note_from_row(row)
    finally:
        conn.close()


def list_progress_notes(task_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM task_progress_notes
            WHERE task_id = ?
            ORDER BY created_at DESC
            """,
            (task_id,),
        ).fetchall()
        return [_note_from_row(r) for r in rows]
    finally:
        conn.close()


def set_pending_progress_reply(*, wp_user_id: int, task_id: str) -> None:
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO pending_progress_replies (wp_user_id, task_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(wp_user_id) DO UPDATE SET
                    task_id = excluded.task_id,
                    updated_at = excluded.updated_at
                """,
                (int(wp_user_id), task_id, now),
            )
    finally:
        conn.close()


def get_pending_progress_reply(wp_user_id: int) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pending_progress_replies WHERE wp_user_id = ?",
            (int(wp_user_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "wp_user_id": int(row["wp_user_id"]),
            "task_id": row["task_id"],
            "updated_at": float(row["updated_at"]),
        }
    finally:
        conn.close()


def clear_pending_progress_reply(wp_user_id: int) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "DELETE FROM pending_progress_replies WHERE wp_user_id = ?",
                (int(wp_user_id),),
            )
    finally:
        conn.close()


def consume_telegram_progress_reply(
    *, wp_user_id: int, note: str
) -> dict[str, Any] | None:
    """If a mid-progress ask is pending for this user, save the note and clear it."""
    pending = get_pending_progress_reply(wp_user_id)
    if pending is None:
        return None
    saved = create_progress_note(
        task_id=pending["task_id"],
        wp_user_id=wp_user_id,
        note=note,
        source="telegram",
    )
    clear_pending_progress_reply(wp_user_id)
    return saved
