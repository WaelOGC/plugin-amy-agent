"""Persistent SQLite store for SEO Tasks checks (no TTL)."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

SeoVerdict = Literal["red", "orange", "green"]
SeoCheckStatus = Literal["pending_approval", "approved", "rejected"]

VALID_VERDICTS = frozenset({"red", "orange", "green"})
VALID_STATUSES = frozenset({"pending_approval", "approved", "rejected"})
VALID_CONTENT_TYPES = frozenset({"post", "page", "category", "tag", "media"})

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "seo_tasks.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Guarded-ALTER registry — applied against an existing seo_tasks.db.
_CHECK_COLUMN_DEFAULTS: dict[str, str] = {
    "content_type": "TEXT NOT NULL DEFAULT 'post'",
    "batch_run_id": "TEXT",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seo_checks (
            id TEXT PRIMARY KEY,
            wp_post_id INTEGER NOT NULL,
            post_type TEXT NOT NULL,
            title TEXT,
            verdict TEXT NOT NULL,
            findings TEXT NOT NULL,
            snapshot TEXT,
            status TEXT NOT NULL,
            approved_fields TEXT,
            reject_reason TEXT,
            checked_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'post',
            batch_run_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seo_checks_status
        ON seo_checks (status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seo_checks_verdict
        ON seo_checks (verdict)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seo_checks_post
        ON seo_checks (wp_post_id, checked_at)
        """
    )
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add new columns safely against an existing seo_tasks.db (PRAGMA table_info)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(seo_checks)").fetchall()}
    for name, decl in _CHECK_COLUMN_DEFAULTS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE seo_checks ADD COLUMN {name} {decl}")


def _decode_json(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    findings = _decode_json(row["findings"])
    if not isinstance(findings, list):
        findings = []
    approved = _decode_json(row["approved_fields"])
    if approved is not None and not isinstance(approved, dict):
        approved = None
    keys = set(row.keys())
    content_type = "post"
    if "content_type" in keys and row["content_type"] in VALID_CONTENT_TYPES:
        content_type = row["content_type"]
    return {
        "check_id": row["id"],
        "wp_post_id": int(row["wp_post_id"]),
        "post_type": row["post_type"],
        "content_type": content_type,
        "title": row["title"] or "",
        "verdict": row["verdict"] if row["verdict"] in VALID_VERDICTS else "orange",
        "findings": findings,
        "status": row["status"] if row["status"] in VALID_STATUSES else "pending_approval",
        "checked_at": float(row["checked_at"]),
        "updated_at": float(row["updated_at"]),
        "approved_fields": approved,
        "reject_reason": row["reject_reason"],
        "batch_run_id": row["batch_run_id"] if "batch_run_id" in keys else None,
    }


def create_check(
    *,
    wp_post_id: int,
    post_type: str,
    title: str,
    verdict: SeoVerdict,
    findings: list[dict[str, Any]],
    snapshot: dict[str, Any] | None = None,
    content_type: str = "post",
    batch_run_id: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if verdict not in VALID_VERDICTS:
        raise ValueError("invalid verdict")
    if content_type not in VALID_CONTENT_TYPES:
        raise ValueError("invalid content_type")
    ts = time.time() if now is None else now
    check_id = str(uuid.uuid4())
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_checks (
                    id, wp_post_id, post_type, title, verdict, findings,
                    snapshot, status, approved_fields, reject_reason,
                    checked_at, updated_at, content_type, batch_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_approval', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    int(wp_post_id),
                    post_type,
                    title or "",
                    verdict,
                    json.dumps(findings),
                    json.dumps(snapshot) if snapshot is not None else None,
                    ts,
                    ts,
                    content_type,
                    batch_run_id,
                ),
            )
        row = conn.execute("SELECT * FROM seo_checks WHERE id = ?", (check_id,)).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def get_check(check_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM seo_checks WHERE id = ?", (check_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_checks(
    *,
    status: SeoCheckStatus | None = None,
    verdict: SeoVerdict | None = None,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError("invalid status")
        clauses.append("status = ?")
        params.append(status)
    if verdict is not None:
        if verdict not in VALID_VERDICTS:
            raise ValueError("invalid verdict")
        clauses.append("verdict = ?")
        params.append(verdict)
    if content_type is not None:
        if content_type not in VALID_CONTENT_TYPES:
            raise ValueError("invalid content_type")
        clauses.append("content_type = ?")
        params.append(content_type)

    sql = "SELECT * FROM seo_checks"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY checked_at DESC"

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def approve_check(
    check_id: str,
    approved_fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    existing = get_check(check_id)
    if existing is None:
        return None
    if existing["status"] != "pending_approval":
        raise ValueError("check is not pending approval")

    ts = time.time()
    payload = json.dumps(approved_fields) if approved_fields is not None else None
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE seo_checks
                SET status = 'approved', approved_fields = ?, updated_at = ?
                WHERE id = ?
                """,
                (payload, ts, check_id),
            )
        row = conn.execute("SELECT * FROM seo_checks WHERE id = ?", (check_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def reject_check(check_id: str, reason: str | None = None) -> dict[str, Any] | None:
    existing = get_check(check_id)
    if existing is None:
        return None
    if existing["status"] != "pending_approval":
        raise ValueError("check is not pending approval")

    ts = time.time()
    reason_text = (reason or "").strip() or None
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE seo_checks
                SET status = 'rejected', reject_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (reason_text, ts, check_id),
            )
        row = conn.execute("SELECT * FROM seo_checks WHERE id = ?", (check_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()
