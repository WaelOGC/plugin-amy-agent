"""Persistent SQLite store for visitor analytics (90-day retention)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

LeadStatus = Literal["cold", "warm", "hot"]

VALID_EVENT_TYPES = frozenset(
    {
        "page_view",
        "widget_opened",
        "widget_message_sent",
        "submit_idea_started",
        "submit_idea_step_reached",
        "submit_idea_abandoned",
        "submit_idea_completed",
        "contact_form_started",
        "contact_form_abandoned",
        "contact_form_submitted",
    }
)
VALID_LEAD_STATUSES = frozenset({"cold", "warm", "hot"})

EMAIL_CAPTURE_EVENT_TYPES = frozenset(
    {
        "submit_idea_completed",
        "contact_form_submitted",
    }
)

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "analytics.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Guarded-ALTER registry — empty in v1; add column name → SQL type/default
# here when a future migration needs a new column on an existing analytics.db.
_SESSION_COLUMN_DEFAULTS: dict[str, str] = {}
_EVENT_COLUMN_DEFAULTS: dict[str, str] = {}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_sessions (
            id TEXT PRIMARY KEY,
            ip_country TEXT,
            ip_city TEXT,
            first_seen_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            lead_status TEXT NOT NULL DEFAULT 'cold',
            lead_email TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            page_path TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES visitor_sessions(id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_visitor_events_session
        ON visitor_events (session_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_visitor_events_created
        ON visitor_events (created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_visitor_sessions_status_seen
        ON visitor_sessions (lead_status, last_seen_at)
        """
    )
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add new columns safely against an existing analytics.db (PRAGMA table_info)."""
    existing_sessions = {
        row[1] for row in conn.execute("PRAGMA table_info(visitor_sessions)").fetchall()
    }
    for name, decl in _SESSION_COLUMN_DEFAULTS.items():
        if name not in existing_sessions:
            conn.execute(f"ALTER TABLE visitor_sessions ADD COLUMN {name} {decl}")

    existing_events = {
        row[1] for row in conn.execute("PRAGMA table_info(visitor_events)").fetchall()
    }
    for name, decl in _EVENT_COLUMN_DEFAULTS.items():
        if name not in existing_events:
            conn.execute(f"ALTER TABLE visitor_events ADD COLUMN {name} {decl}")


def _decode_event_data(raw: Any) -> dict[str, Any] | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ip_country": row["ip_country"],
        "ip_city": row["ip_city"],
        "first_seen_at": float(row["first_seen_at"]),
        "last_seen_at": float(row["last_seen_at"]),
        "lead_status": row["lead_status"] if row["lead_status"] in VALID_LEAD_STATUSES else "cold",
        "lead_email": row["lead_email"],
    }


def _event_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "session_id": row["session_id"],
        "event_type": row["event_type"],
        "event_data": _decode_event_data(row["event_data"]),
        "page_path": row["page_path"],
        "created_at": float(row["created_at"]),
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM visitor_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return _session_row_to_dict(row) if row else None
    finally:
        conn.close()


def create_session(
    session_id: str,
    *,
    ip_country: str | None = None,
    ip_city: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    ts = time.time() if now is None else now
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO visitor_sessions (
                    id, ip_country, ip_city, first_seen_at, last_seen_at,
                    lead_status, lead_email
                ) VALUES (?, ?, ?, ?, ?, 'cold', NULL)
                """,
                (session_id, ip_country, ip_city, ts, ts),
            )
        row = conn.execute(
            "SELECT * FROM visitor_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        assert row is not None
        return _session_row_to_dict(row)
    finally:
        conn.close()


def insert_event(
    *,
    session_id: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
    page_path: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError("invalid event_type")
    ts = time.time() if now is None else now
    payload = json.dumps(event_data) if event_data is not None else None
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO visitor_events (
                    session_id, event_type, event_data, page_path, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, event_type, payload, page_path, ts),
            )
            event_id = cur.lastrowid
            conn.execute(
                """
                UPDATE visitor_sessions
                SET last_seen_at = ?
                WHERE id = ?
                """,
                (ts, session_id),
            )
        row = conn.execute(
            "SELECT * FROM visitor_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        assert row is not None
        return _event_row_to_dict(row)
    finally:
        conn.close()


def list_events(session_id: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM visitor_events
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [_event_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def set_lead_status(session_id: str, status: LeadStatus) -> None:
    if status not in VALID_LEAD_STATUSES:
        raise ValueError("invalid lead_status")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE visitor_sessions SET lead_status = ? WHERE id = ?",
                (status, session_id),
            )
    finally:
        conn.close()


def set_lead_email(session_id: str, email: str) -> None:
    email = (email or "").strip()
    if not email:
        return
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE visitor_sessions SET lead_email = ? WHERE id = ?",
                (email, session_id),
            )
    finally:
        conn.close()


def list_leads(*, status: LeadStatus | None = None) -> list[dict[str, Any]]:
    if status is not None and status not in VALID_LEAD_STATUSES:
        raise ValueError("invalid status")

    sql = "SELECT * FROM visitor_sessions"
    params: list[Any] = []
    if status is not None:
        sql += " WHERE lead_status = ?"
        params.append(status)
    sql += """
        ORDER BY CASE lead_status
            WHEN 'hot' THEN 0
            WHEN 'warm' THEN 1
            ELSE 2
        END, last_seen_at DESC
    """

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_session_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def purge_old_events(days: int = 90) -> dict[str, int]:
    """Delete events older than `days` and any sessions left with zero events."""
    if days < 1:
        raise ValueError("days must be >= 1")
    cutoff = time.time() - (days * 24 * 60 * 60)
    conn = _connect()
    try:
        with conn:
            cur_events = conn.execute(
                "DELETE FROM visitor_events WHERE created_at < ?",
                (cutoff,),
            )
            cur_sessions = conn.execute(
                """
                DELETE FROM visitor_sessions
                WHERE id NOT IN (SELECT DISTINCT session_id FROM visitor_events)
                """
            )
        return {
            "events_deleted": int(cur_events.rowcount),
            "sessions_deleted": int(cur_sessions.rowcount),
        }
    finally:
        conn.close()
