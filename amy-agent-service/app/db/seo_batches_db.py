"""Persistent SQLite store for SEO Tasks batch runs (same seo_tasks.db file)."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from app.db import seo_tasks_db
from app.services.seo_check import run_check_for_type

logger = logging.getLogger("amy-agent-service")

SeoBatchMode = Literal["manual", "auto"]
SeoBatchStatus = Literal["in_progress", "stopped", "completed"]

VALID_MODES = frozenset({"manual", "auto"})
VALID_STATUSES = frozenset({"in_progress", "stopped", "completed"})
VALID_CONTENT_TYPES = seo_tasks_db.VALID_CONTENT_TYPES

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _SERVICE_ROOT / "data"
_DB_PATH = _DATA_DIR / "seo_tasks.db"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

_RUN_COLUMN_DEFAULTS: dict[str, str] = {}

BATCH_SIZE_MIN = 1
BATCH_SIZE_MAX = 20


def clamp_batch_size(value: int) -> int:
    try:
        original = int(value)
    except (TypeError, ValueError):
        original = 5
    clamped = max(BATCH_SIZE_MIN, min(BATCH_SIZE_MAX, original))
    if clamped != original:
        logger.warning("SEO batch_size clamped from %s to %s", original, clamped)
    return clamped


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seo_batch_runs (
            id TEXT PRIMARY KEY,
            content_type TEXT NOT NULL,
            mode TEXT NOT NULL,
            batch_size INTEGER NOT NULL,
            items TEXT NOT NULL,
            cursor INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            reports TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_seo_batch_runs_status
        ON seo_batch_runs (status, created_at)
        """
    )
    _ensure_columns(conn)
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(seo_batch_runs)").fetchall()
    }
    for name, decl in _RUN_COLUMN_DEFAULTS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE seo_batch_runs ADD COLUMN {name} {decl}")


def _decode_json(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _row_to_dict(row: sqlite3.Row, *, include_detail: bool = True) -> dict[str, Any]:
    items = _decode_json(row["items"])
    if not isinstance(items, list):
        items = []
    reports = _decode_json(row["reports"])
    if not isinstance(reports, list):
        reports = []
    data = {
        "batch_run_id": row["id"],
        "content_type": row["content_type"],
        "mode": row["mode"],
        "batch_size": int(row["batch_size"]),
        "total_items": len(items),
        "status": row["status"] if row["status"] in VALID_STATUSES else "in_progress",
        "processed_count": int(row["cursor"]),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }
    if include_detail:
        data["items"] = items
        data["reports"] = reports
        data["cursor"] = int(row["cursor"])
    return data


def create_batch_run(
    *,
    content_type: str,
    mode: SeoBatchMode,
    batch_size: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    if content_type not in VALID_CONTENT_TYPES:
        raise ValueError("invalid content_type")
    if mode not in VALID_MODES:
        raise ValueError("invalid mode")
    if not items:
        raise ValueError("items is required")
    size = clamp_batch_size(batch_size)
    run_id = str(uuid.uuid4())
    ts = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_batch_runs (
                    id, content_type, mode, batch_size, items, cursor,
                    status, reports, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 'in_progress', '[]', ?, ?)
                """,
                (run_id, content_type, mode, size, json.dumps(items), ts, ts),
            )
        row = conn.execute("SELECT * FROM seo_batch_runs WHERE id = ?", (run_id,)).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def get_batch_run(batch_run_id: str, *, include_detail: bool = True) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_batch_runs WHERE id = ?",
            (batch_run_id,),
        ).fetchone()
        return _row_to_dict(row, include_detail=include_detail) if row else None
    finally:
        conn.close()


def list_batch_runs(
    *,
    content_type: str | None = None,
    status: SeoBatchStatus | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if content_type is not None:
        if content_type not in VALID_CONTENT_TYPES:
            raise ValueError("invalid content_type")
        clauses.append("content_type = ?")
        params.append(content_type)
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError("invalid status")
        clauses.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM seo_batch_runs"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(row, include_detail=False) for row in rows]
    finally:
        conn.close()


def _process_item(
    *,
    content_type: str,
    item: dict[str, Any],
    batch_run_id: str,
) -> dict[str, Any]:
    item_id = int(item.get("item_id") or 0)
    title = str(item.get("title") or "")
    snapshot = item.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    result = run_check_for_type(content_type, snapshot)
    check = seo_tasks_db.create_check(
        wp_post_id=item_id,
        post_type=content_type,
        content_type=content_type,
        title=title,
        verdict=result["verdict"],
        findings=result["findings"],
        snapshot=snapshot,
        batch_run_id=batch_run_id,
    )
    return {
        "item_id": item_id,
        "title": title,
        "check_id": check["check_id"],
        "verdict": check["verdict"],
        "findings": check["findings"],
        "error": None,
    }


def process_next_batch(batch_run_id: str) -> dict[str, Any]:
    existing = get_batch_run(batch_run_id)
    if existing is None:
        raise KeyError("not found")
    if existing["status"] != "in_progress":
        raise ValueError("batch run is not in progress")

    items: list[dict[str, Any]] = existing["items"]
    cursor = int(existing["cursor"])
    size = int(existing["batch_size"])
    content_type = existing["content_type"]
    slice_items = items[cursor : cursor + size]
    if not slice_items:
        return _mark_completed(batch_run_id)

    results: list[dict[str, Any]] = []
    for item in slice_items:
        title = str(item.get("title") or "") if isinstance(item, dict) else ""
        item_id = 0
        try:
            if not isinstance(item, dict):
                raise ValueError("item must be an object")
            item_id = int(item.get("item_id") or 0)
            if item_id < 1:
                raise ValueError("item_id is required")
            results.append(
                _process_item(
                    content_type=content_type,
                    item=item,
                    batch_run_id=batch_run_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 — isolate one bad item
            logger.exception(
                "SEO batch item failed (run=%s item_id=%s)",
                batch_run_id,
                item_id or "?",
            )
            results.append(
                {
                    "item_id": item_id,
                    "title": title,
                    "check_id": None,
                    "verdict": None,
                    "findings": [],
                    "error": str(exc),
                }
            )

    reports = list(existing["reports"])
    reports.append({"batch_index": len(reports), "results": results})
    new_cursor = cursor + len(slice_items)
    new_status = "completed" if new_cursor >= len(items) else "in_progress"
    ts = time.time()

    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE seo_batch_runs
                SET cursor = ?, status = ?, reports = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_cursor, new_status, json.dumps(reports), ts, batch_run_id),
            )
        row = conn.execute(
            "SELECT * FROM seo_batch_runs WHERE id = ?", (batch_run_id,)
        ).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def _mark_completed(batch_run_id: str) -> dict[str, Any]:
    ts = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE seo_batch_runs
                SET status = 'completed', updated_at = ?
                WHERE id = ?
                """,
                (ts, batch_run_id),
            )
        row = conn.execute(
            "SELECT * FROM seo_batch_runs WHERE id = ?", (batch_run_id,)
        ).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()


def stop_batch_run(batch_run_id: str) -> dict[str, Any]:
    existing = get_batch_run(batch_run_id)
    if existing is None:
        raise KeyError("not found")
    if existing["status"] != "in_progress":
        raise ValueError("batch run is not in progress")
    ts = time.time()
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                UPDATE seo_batch_runs
                SET status = 'stopped', updated_at = ?
                WHERE id = ?
                """,
                (ts, batch_run_id),
            )
        row = conn.execute(
            "SELECT * FROM seo_batch_runs WHERE id = ?", (batch_run_id,)
        ).fetchone()
        assert row is not None
        return _row_to_dict(row)
    finally:
        conn.close()
