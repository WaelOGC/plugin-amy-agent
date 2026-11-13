"""SQLite metadata for secure public-chat uploads (not Submit Idea / admin chat)."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "public_chat_uploads.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_ROOT = _SERVICE_ROOT / "uploads" / "public-chat"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

RETENTION_DAYS = 7
DEFAULT_MAX_FILES_PER_HOUR = 10
DEFAULT_STORAGE_CAP_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public_chat_uploads (
            id TEXT PRIMARY KEY,
            visitor_id TEXT NOT NULL,
            conversation_id TEXT,
            original_filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            kind TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            page_count INTEGER,
            description TEXT,
            vision_sent INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            deleted_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pcu_visitor_created
        ON public_chat_uploads (visitor_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pcu_created
        ON public_chat_uploads (created_at)
        """
    )
    cols = {
        str(r[1])
        for r in conn.execute("PRAGMA table_info(public_chat_uploads)").fetchall()
    }
    if "client_ip" not in cols:
        conn.execute(
            "ALTER TABLE public_chat_uploads ADD COLUMN client_ip TEXT"
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pcu_ip_created
        ON public_chat_uploads (client_ip, created_at)
        """
    )
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": row["id"],
        "visitor_id": row["visitor_id"],
        "conversation_id": row["conversation_id"],
        "original_filename": row["original_filename"],
        "stored_name": row["stored_name"],
        "content_type": row["content_type"],
        "kind": row["kind"],
        "size_bytes": int(row["size_bytes"]),
        "width": int(row["width"]) if row["width"] is not None else None,
        "height": int(row["height"]) if row["height"] is not None else None,
        "page_count": int(row["page_count"]) if row["page_count"] is not None else None,
        "description": row["description"],
        "vision_sent": bool(int(row["vision_sent"] or 0)),
        "created_at": float(row["created_at"]),
        "deleted_at": float(row["deleted_at"]) if row["deleted_at"] is not None else None,
        "client_ip": row["client_ip"] if "client_ip" in keys else None,
    }


def create_upload(
    *,
    visitor_id: str,
    original_filename: str,
    stored_name: str,
    content_type: str,
    kind: str,
    size_bytes: int,
    conversation_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    page_count: int | None = None,
    description: str | None = None,
    client_ip: str | None = None,
) -> dict[str, Any]:
    upload_id = uuid.uuid4().hex
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO public_chat_uploads (
                    id, visitor_id, conversation_id, original_filename, stored_name,
                    content_type, kind, size_bytes, width, height, page_count,
                    description, vision_sent, created_at, deleted_at, client_ip
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)
                """,
                (
                    upload_id,
                    visitor_id,
                    conversation_id,
                    original_filename,
                    stored_name,
                    content_type,
                    kind,
                    int(size_bytes),
                    width,
                    height,
                    page_count,
                    description,
                    now,
                    (client_ip or "").strip() or None,
                ),
            )
        row = conn.execute(
            "SELECT * FROM public_chat_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def get_upload(upload_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM public_chat_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None
    finally:
        conn.close()


def get_uploads_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    clean = [i for i in ids if isinstance(i, str) and i.strip()]
    if not clean:
        return []
    placeholders = ",".join("?" for _ in clean)
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT * FROM public_chat_uploads WHERE id IN ({placeholders})",
            clean,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def bind_conversation(upload_ids: list[str], conversation_id: str, visitor_id: str) -> int:
    clean = [i for i in upload_ids if isinstance(i, str) and i.strip()]
    if not clean:
        return 0
    placeholders = ",".join("?" for _ in clean)
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                f"""
                UPDATE public_chat_uploads
                SET conversation_id = ?
                WHERE id IN ({placeholders})
                  AND visitor_id = ?
                  AND deleted_at IS NULL
                """,
                [conversation_id, *clean, visitor_id],
            )
            return int(cur.rowcount or 0)
    finally:
        conn.close()


def mark_vision_sent(upload_ids: list[str]) -> None:
    clean = [i for i in upload_ids if isinstance(i, str) and i.strip()]
    if not clean:
        return
    placeholders = ",".join("?" for _ in clean)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                f"""
                UPDATE public_chat_uploads
                SET vision_sent = 1
                WHERE id IN ({placeholders})
                """,
                clean,
            )
    finally:
        conn.close()


def set_description(upload_id: str, description: str) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE public_chat_uploads SET description = ? WHERE id = ?",
                (description, upload_id),
            )
    finally:
        conn.close()


def count_uploads_since(visitor_id: str, since_ts: float) -> int:
    """Count logical uploads (images + primary PDFs), not PDF page siblings."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM public_chat_uploads
            WHERE visitor_id = ?
              AND created_at >= ?
              AND deleted_at IS NULL
              AND kind IN ('image', 'pdf')
            """,
            (visitor_id, since_ts),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        conn.close()


def count_uploads_since_ip(client_ip: str, since_ts: float) -> int:
    """Count logical uploads for one client IP in the rolling window."""
    ip = (client_ip or "").strip()
    if not ip:
        return 0
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM public_chat_uploads
            WHERE client_ip = ?
              AND created_at >= ?
              AND deleted_at IS NULL
              AND kind IN ('image', 'pdf')
            """,
            (ip, since_ts),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        conn.close()


def count_uploads_since_global(since_ts: float) -> int:
    """Count all logical public-chat uploads in the rolling window."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM public_chat_uploads
            WHERE created_at >= ?
              AND deleted_at IS NULL
              AND kind IN ('image', 'pdf')
            """,
            (since_ts,),
        ).fetchone()
        return int(row["n"] if row else 0)
    finally:
        conn.close()


def total_active_storage_bytes() -> int:
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(size_bytes), 0) AS total
            FROM public_chat_uploads
            WHERE deleted_at IS NULL
            """,
        ).fetchone()
        return int(row["total"] if row else 0)
    finally:
        conn.close()


def soft_delete(upload_id: str) -> dict[str, Any] | None:
    now = time.time()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM public_chat_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
        if row is None:
            return None
        with conn:
            conn.execute(
                "UPDATE public_chat_uploads SET deleted_at = ? WHERE id = ?",
                (now, upload_id),
            )
        refreshed = conn.execute(
            "SELECT * FROM public_chat_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
        return _row_to_dict(refreshed) if refreshed is not None else None
    finally:
        conn.close()


def list_expired(days: int = RETENTION_DAYS) -> list[dict[str, Any]]:
    cutoff = time.time() - (max(1, int(days)) * 86400)
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM public_chat_uploads
            WHERE deleted_at IS NULL AND created_at < ?
            """,
            (cutoff,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def absolute_path(stored_name: str) -> Path:
    name = Path(stored_name).name
    return UPLOAD_ROOT / name
