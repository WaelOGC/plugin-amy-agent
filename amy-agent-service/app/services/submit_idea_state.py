"""SQLite-backed Submit Your Idea session store with lazy TTL cleanup."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SubmitIdeaStatus = Literal[
    "collecting",
    "confirming",
    "deep_dive",
    "awaiting_contact",
    "completed",
]

SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "submit_idea_sessions.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SubmitIdeaSession:
    session_id: str
    selected_service: str | None = None
    answers: dict[str, Any] = field(default_factory=dict)
    free_conversation: list[dict[str, str]] = field(default_factory=list)
    status: SubmitIdeaStatus = "collecting"
    contact: dict[str, str | None] = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    return conn


def _session_payload(sess: SubmitIdeaSession) -> dict[str, Any]:
    return {
        "selected_service": sess.selected_service,
        "answers": sess.answers,
        "free_conversation": sess.free_conversation,
        "status": sess.status,
        "contact": sess.contact,
        "attachments": sess.attachments,
        "created_at": sess.created_at,
    }


def _session_from_row(session_id: str, data_json: str, updated_at: float) -> SubmitIdeaSession:
    raw = json.loads(data_json)
    return SubmitIdeaSession(
        session_id=session_id,
        selected_service=raw.get("selected_service"),
        answers=dict(raw.get("answers") or {}),
        free_conversation=list(raw.get("free_conversation") or []),
        status=raw.get("status") or "collecting",
        contact=dict(raw.get("contact") or {}),
        attachments=list(raw.get("attachments") or []),
        created_at=float(raw.get("created_at") or updated_at),
        updated_at=float(updated_at),
    )


def _cleanup_expired() -> None:
    """Drop sessions older than TTL. Runs on every state access."""
    now = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "DELETE FROM sessions WHERE (? - updated_at) > ?",
                (now, SESSION_TTL_SECONDS),
            )
    finally:
        conn.close()


def save_session(sess: SubmitIdeaSession) -> None:
    """Persist a mutated session row (routes must call this before returning)."""
    payload = json.dumps(_session_payload(sess), ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE sessions
                SET data = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (payload, sess.updated_at, sess.session_id),
            )
    finally:
        conn.close()


def get_session(session_id: str) -> SubmitIdeaSession | None:
    _cleanup_expired()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data, updated_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    sess = _session_from_row(session_id, row[0], row[1])
    sess.touch()
    save_session(sess)
    return sess


def create_session(session_id: str, service_slug: str) -> SubmitIdeaSession:
    _cleanup_expired()
    sess = SubmitIdeaSession(
        session_id=session_id,
        selected_service=service_slug,
        status="collecting",
    )
    payload = json.dumps(_session_payload(sess), ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (session_id, data, updated_at)
                VALUES (?, ?, ?)
                """,
                (sess.session_id, payload, sess.updated_at),
            )
    finally:
        conn.close()
    return sess


def require_session(session_id: str) -> SubmitIdeaSession:
    sess = get_session(session_id)
    if sess is None:
        raise KeyError(f"Unknown or expired session: {session_id}")
    return sess
