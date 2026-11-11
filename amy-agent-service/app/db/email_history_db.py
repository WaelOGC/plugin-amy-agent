"""Email marketing send/reply history in the conversations SQLite store.

FluentSMTP / wp_mail is outbound-only. Durable history + manual inbound notes
live here (same DB file as Dashboard Chat). No AgentMail / Agentic Mail client.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from app.db.conversations_db import _DB_PATH, _DATA_DIR

_DATA_DIR.mkdir(parents=True, exist_ok=True)

VALID_DIRECTIONS = frozenset({"outbound", "inbound", "note", "proposed"})
VALID_CHANNELS = frozenset({"fluentsmtp", "manual", "amy_propose", "inbound_webhook"})
VALID_STATUSES = frozenset(
    {"sent", "failed", "received", "note", "proposed", "suppressed", "skipped"}
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_threads (
            id TEXT PRIMARY KEY,
            participant_email TEXT NOT NULL,
            subject TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            from_email TEXT,
            to_email TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            wp_user_id INTEGER,
            error TEXT,
            meta_json TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (thread_id) REFERENCES email_threads(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_suppressions (
            email TEXT PRIMARY KEY,
            reason TEXT,
            source TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_email_threads_participant
        ON email_threads (participant_email, updated_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_email_messages_thread
        ON email_messages (thread_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_email_messages_created
        ON email_messages (created_at)
        """
    )
    return conn


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _thread_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "participant_email": row["participant_email"],
        "subject": row["subject"],
        "status": row["status"],
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def _message_row(row: sqlite3.Row) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    raw = row["meta_json"]
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                meta = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            meta = {}
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "direction": row["direction"],
        "channel": row["channel"],
        "status": row["status"],
        "from_email": row["from_email"],
        "to_email": row["to_email"],
        "subject": row["subject"],
        "body": row["body"],
        "wp_user_id": int(row["wp_user_id"]) if row["wp_user_id"] is not None else None,
        "error": row["error"],
        "meta": meta,
        "created_at": float(row["created_at"]),
    }


def is_suppressed(email: str) -> bool:
    key = _normalize_email(email)
    if not key:
        return False
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM email_suppressions WHERE email = ?",
            (key,),
        ).fetchone()
        return row is not None


def list_suppressions(limit: int = 500) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 2000))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT email, reason, source, created_at
            FROM email_suppressions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "email": r["email"],
                "reason": r["reason"],
                "source": r["source"],
                "created_at": float(r["created_at"]),
            }
            for r in rows
        ]


def add_suppression(
    email: str,
    *,
    reason: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    key = _normalize_email(email)
    if not key:
        raise ValueError("email is required")
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO email_suppressions (email, reason, source, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                reason = excluded.reason,
                source = excluded.source
            """,
            (key, reason, source, now),
        )
        # Mark matching threads opted_out.
        conn.execute(
            """
            UPDATE email_threads
            SET status = 'opted_out', updated_at = ?
            WHERE participant_email = ?
            """,
            (now, key),
        )
        conn.commit()
    return {"email": key, "reason": reason, "source": source, "created_at": now}


def remove_suppression(email: str) -> bool:
    key = _normalize_email(email)
    if not key:
        return False
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM email_suppressions WHERE email = ?",
            (key,),
        )
        conn.commit()
        return cur.rowcount > 0


def get_or_create_thread(
    participant_email: str,
    *,
    subject: str | None = None,
) -> dict[str, Any]:
    key = _normalize_email(participant_email)
    if not key:
        raise ValueError("participant_email is required")
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM email_threads
            WHERE participant_email = ? AND status != 'closed'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (key,),
        ).fetchone()
        if row:
            if subject and (not row["subject"] or row["subject"] != subject):
                conn.execute(
                    """
                    UPDATE email_threads
                    SET subject = COALESCE(?, subject), updated_at = ?
                    WHERE id = ?
                    """,
                    (subject, now, row["id"]),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM email_threads WHERE id = ?",
                    (row["id"],),
                ).fetchone()
            return _thread_row(row)

        thread_id = uuid.uuid4().hex
        suppressed_row = conn.execute(
            "SELECT 1 FROM email_suppressions WHERE email = ?",
            (key,),
        ).fetchone()
        status = "opted_out" if suppressed_row else "active"
        conn.execute(
            """
            INSERT INTO email_threads (
                id, participant_email, subject, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_id, key, subject, status, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM email_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        return _thread_row(row)


def get_thread(thread_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM email_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        return _thread_row(row) if row else None


def list_threads(
    *,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    params: list[Any] = []
    where = "1=1"
    if q:
        where += " AND (participant_email LIKE ? OR IFNULL(subject, '') LIKE ?)"
        like = f"%{q.strip().lower()}%"
        params.extend([like, like])

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM email_threads WHERE {where}",
            params,
        ).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT * FROM email_threads
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        threads = [_thread_row(r) for r in rows]
        # Attach last message preview.
        for t in threads:
            last = conn.execute(
                """
                SELECT * FROM email_messages
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (t["id"],),
            ).fetchone()
            t["last_message"] = _message_row(last) if last else None
            t["suppressed"] = is_suppressed(t["participant_email"])
        return {"threads": threads, "total": int(total), "limit": limit, "offset": offset}


def list_messages(thread_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM email_messages
            WHERE thread_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (thread_id, limit),
        ).fetchall()
        return [_message_row(r) for r in rows]


def add_message(
    *,
    thread_id: str,
    direction: str,
    channel: str,
    status: str,
    body: str,
    from_email: str | None = None,
    to_email: str | None = None,
    subject: str | None = None,
    wp_user_id: int | None = None,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"invalid direction: {direction}")
    if channel not in VALID_CHANNELS:
        raise ValueError(f"invalid channel: {channel}")
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    body = (body or "").strip()
    if not body:
        raise ValueError("body is required")

    now = time.time()
    msg_id = uuid.uuid4().hex
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    with _connect() as conn:
        thread = conn.execute(
            "SELECT id FROM email_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        if not thread:
            raise ValueError("thread not found")

        conn.execute(
            """
            INSERT INTO email_messages (
                id, thread_id, direction, channel, status,
                from_email, to_email, subject, body, wp_user_id,
                error, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                thread_id,
                direction,
                channel,
                status,
                from_email,
                to_email,
                subject,
                body,
                wp_user_id,
                error,
                meta_json,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE email_threads
            SET updated_at = ?, subject = COALESCE(?, subject)
            WHERE id = ?
            """,
            (now, subject, thread_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM email_messages WHERE id = ?",
            (msg_id,),
        ).fetchone()
        return _message_row(row)


def record_outbound_batch(
    *,
    recipients: list[dict[str, Any]],
    subject: str,
    body: str,
    from_email: str,
    wp_user_id: int | None = None,
    channel: str = "fluentsmtp",
) -> dict[str, Any]:
    """Persist one outbound (or skipped/failed) message per recipient."""
    recorded: list[dict[str, Any]] = []
    for item in recipients:
        email = _normalize_email(str(item.get("email") or ""))
        if not email:
            continue
        ok = bool(item.get("ok"))
        err = str(item.get("error") or "") or None
        suppressed = is_suppressed(email)
        if suppressed:
            status = "suppressed"
            direction = "outbound"
            msg_body = body
            err = err or "Recipient is on the opt-out / suppression list."
        elif ok:
            status = "sent"
            direction = "outbound"
            msg_body = body
        else:
            status = "failed"
            direction = "outbound"
            msg_body = body

        thread = get_or_create_thread(email, subject=subject)
        msg = add_message(
            thread_id=thread["id"],
            direction=direction,
            channel=channel,
            status=status,
            body=msg_body,
            from_email=from_email,
            to_email=email,
            subject=subject,
            wp_user_id=wp_user_id,
            error=err,
            meta={"batch": True},
        )
        recorded.append({"thread": thread, "message": msg})
    return {"recorded": len(recorded), "items": recorded}


def propose_send(
    *,
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    proposed_by: str = "amy",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Amy-triggered draft hook: store a proposed send pending human approve."""
    email = _normalize_email(to_email)
    if not email:
        raise ValueError("to_email is required")
    if is_suppressed(email):
        raise ValueError("recipient is opted out")
    thread = get_or_create_thread(email, subject=subject)
    payload = dict(meta or {})
    payload["proposed_by"] = proposed_by
    msg = add_message(
        thread_id=thread["id"],
        direction="proposed",
        channel="amy_propose",
        status="proposed",
        body=body,
        from_email=from_email,
        to_email=email,
        subject=subject,
        meta=payload,
    )
    return {"thread": thread, "message": msg}


def record_inbound(
    *,
    from_email: str,
    to_email: str | None,
    subject: str | None,
    body: str,
    channel: str = "inbound_webhook",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    email = _normalize_email(from_email)
    if not email:
        raise ValueError("from_email is required")
    thread = get_or_create_thread(email, subject=subject)
    msg = add_message(
        thread_id=thread["id"],
        direction="inbound",
        channel=channel if channel in VALID_CHANNELS else "inbound_webhook",
        status="received",
        body=body,
        from_email=email,
        to_email=_normalize_email(to_email or "") or None,
        subject=subject,
        meta=meta,
    )
    return {"thread": thread, "message": msg}


def add_manual_note(
    *,
    thread_id: str,
    body: str,
    wp_user_id: int | None = None,
    as_inbound: bool = False,
) -> dict[str, Any]:
    thread = get_thread(thread_id)
    if not thread:
        raise ValueError("thread not found")
    if as_inbound:
        return add_message(
            thread_id=thread_id,
            direction="inbound",
            channel="manual",
            status="received",
            body=body,
            from_email=thread["participant_email"],
            to_email=None,
            subject=thread.get("subject"),
            wp_user_id=wp_user_id,
            meta={"manual_inbound": True},
        )
    return add_message(
        thread_id=thread_id,
        direction="note",
        channel="manual",
        status="note",
        body=body,
        from_email=None,
        to_email=thread["participant_email"],
        subject=thread.get("subject"),
        wp_user_id=wp_user_id,
        meta={"manual_note": True},
    )
