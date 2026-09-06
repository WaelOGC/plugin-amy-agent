"""Persistent SQLite store for conversation memory."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "conversations.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Guarded-ALTER registry — empty in v1; add column name → SQL type/default
# here when a future migration needs a new column on an existing conversations.db.
_CONVERSATION_COLUMN_DEFAULTS: dict[str, str] = {}
_MESSAGE_COLUMN_DEFAULTS: dict[str, str] = {
    "attachments": "TEXT",
}

_TITLE_MAX_LEN = 60
_ARCHIVE_AGE_DAYS = 90


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            wp_user_id INTEGER NOT NULL,
            mode TEXT NOT NULL DEFAULT 'admin',
            title TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            exported_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conv_messages_conv
        ON conversation_messages (conversation_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversations_owner
        ON conversations (wp_user_id, status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversations_status_updated
        ON conversations (status, updated_at)
        """
    )
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add new columns safely against an existing conversations.db (PRAGMA table_info)."""
    existing_conversations = {
        row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    for name, decl in _CONVERSATION_COLUMN_DEFAULTS.items():
        if name not in existing_conversations:
            conn.execute(f"ALTER TABLE conversations ADD COLUMN {name} {decl}")

    existing_messages = {
        row[1]
        for row in conn.execute("PRAGMA table_info(conversation_messages)").fetchall()
    }
    for name, decl in _MESSAGE_COLUMN_DEFAULTS.items():
        if name not in existing_messages:
            conn.execute(f"ALTER TABLE conversation_messages ADD COLUMN {name} {decl}")


def _conversation_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "wp_user_id": int(row["wp_user_id"]),
        "mode": row["mode"],
        "title": row["title"],
        "status": row["status"],
        "exported_at": float(row["exported_at"]) if row["exported_at"] is not None else None,
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def _decode_attachments(raw: Any) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _message_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    attachments_raw = row["attachments"] if "attachments" in keys else None
    return {
        "id": int(row["id"]),
        "conversation_id": row["conversation_id"],
        "role": row["role"],
        "content": row["content"],
        "attachments": _decode_attachments(attachments_raw),
        "created_at": float(row["created_at"]),
    }


def _derive_title(content: str) -> str:
    text = (content or "").strip()
    if len(text) <= _TITLE_MAX_LEN:
        return text
    return text[:_TITLE_MAX_LEN]


def create_conversation(
    wp_user_id: int,
    mode: str,
    title: str | None = None,
) -> dict[str, Any]:
    conversation_id = uuid.uuid4().hex
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO conversations (
                    id, wp_user_id, mode, title, status, exported_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'active', NULL, ?, ?)
                """,
                (conversation_id, wp_user_id, mode, title, now, now),
            )
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        assert row is not None
        return _conversation_row_to_dict(row)
    finally:
        conn.close()


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return _conversation_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_conversations(
    wp_user_id: int,
    is_full_admin: bool,
    mode: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["status != 'deleted'"]
    params: list[Any] = []

    if not include_archived:
        clauses.append("status != 'archived'")

    if not is_full_admin:
        clauses.append("wp_user_id = ?")
        params.append(wp_user_id)

    if mode is not None:
        clauses.append("mode = ?")
        params.append(mode)

    sql = (
        "SELECT * FROM conversations WHERE "
        + " AND ".join(clauses)
        + " ORDER BY updated_at DESC"
    )

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_conversation_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def append_message(
    conversation_id: str,
    role: str,
    content: str,
    attachments: list[dict] | None = None,
) -> None:
    now = time.time()
    attachments_json = json.dumps(attachments) if attachments else None
    conn = _connect()
    try:
        with conn:
            conv = conn.execute(
                "SELECT title FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if conv is None:
                raise ValueError("conversation not found")

            prior_user_count = 0
            if role == "user" and (conv["title"] is None or conv["title"] == ""):
                prior = conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM conversation_messages
                    WHERE conversation_id = ? AND role = 'user'
                    """,
                    (conversation_id,),
                ).fetchone()
                prior_user_count = int(prior["n"]) if prior is not None else 0

            conn.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, role, content, created_at, attachments
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, now, attachments_json),
            )

            if (
                role == "user"
                and (conv["title"] is None or conv["title"] == "")
                and prior_user_count == 0
            ):
                conn.execute(
                    """
                    UPDATE conversations
                    SET title = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (_derive_title(content), now, conversation_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
    finally:
        conn.close()


def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [_message_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def rename_conversation(conversation_id: str, title: str) -> bool:
    now = time.time()
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, now, conversation_id),
            )
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_conversation(conversation_id: str) -> bool:
    conn = _connect()
    try:
        with conn:
            existing = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if existing is None:
                return False
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )
        return True
    finally:
        conn.close()


def mark_exported(conversation_id: str) -> None:
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE conversations SET exported_at = ? WHERE id = ?",
                (now, conversation_id),
            )
    finally:
        conn.close()


def archive_stale_conversations(days: int = 90) -> dict[str, int]:
    if days < 1:
        raise ValueError("days must be >= 1")
    cutoff = time.time() - (days * 24 * 60 * 60)
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE conversations
                SET status = 'archived'
                WHERE status = 'active' AND updated_at < ?
                """,
                (cutoff,),
            )
        return {"archived": int(cur.rowcount)}
    finally:
        conn.close()


def purge_exported_or_expired_conversations(
    archived_grace_days: int = 30,
) -> dict[str, int]:
    """Hard-delete archived conversations that were exported or past the grace window."""
    if archived_grace_days < 0:
        raise ValueError("archived_grace_days must be >= 0")
    expiry_cutoff = time.time() - (
        (_ARCHIVE_AGE_DAYS + archived_grace_days) * 24 * 60 * 60
    )
    conn = _connect()
    try:
        with conn:
            rows = conn.execute(
                """
                SELECT id FROM conversations
                WHERE status = 'archived'
                  AND (
                    exported_at IS NOT NULL
                    OR updated_at < ?
                  )
                """,
                (expiry_cutoff,),
            ).fetchall()
            ids = [row["id"] for row in rows]
            for conversation_id in ids:
                conn.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                conn.execute(
                    "DELETE FROM conversations WHERE id = ?",
                    (conversation_id,),
                )
        return {"deleted": len(ids)}
    finally:
        conn.close()
