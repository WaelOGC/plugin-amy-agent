"""Unit tests for SEO + Task Service chat summaries (Analytics tools P2)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.db import seo_tasks_db, tasks_db  # noqa: E402
from app.services.seo_task_summary import (  # noqa: E402
    build_seo_review_summary,
    build_task_service_summary,
    format_seo_chat_context,
    format_task_service_chat_context,
)

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolated_dbs(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(seo_tasks_db, "_DB_PATH", tmp_path / "seo_tasks.db")
    monkeypatch.setattr(tasks_db, "_DB_PATH", tmp_path / "tasks.db")
    get_settings.cache_clear()


def test_seo_summary_empty_db() -> None:
    snap = build_seo_review_summary()
    assert snap["ok"] is True
    assert snap["empty"] is True
    assert snap["total"] == 0
    assert snap["open_count"] == 0
    assert "0 stored checks" in snap["summary"]
    ctx = format_seo_chat_context(snap)
    assert "EMPTY" in ctx
    assert "Do NOT approve" in ctx


def test_seo_summary_counts_open_and_fixed() -> None:
    seo_tasks_db.create_check(
        wp_post_id=1,
        post_type="post",
        title="A",
        verdict="red",
        findings=[{"field": "meta_description", "issue": "missing"}],
    )
    seo_tasks_db.create_check(
        wp_post_id=2,
        post_type="post",
        title="B",
        verdict="green",
        findings=[],
    )
    approved = seo_tasks_db.create_check(
        wp_post_id=3,
        post_type="page",
        title="C",
        verdict="orange",
        findings=[{"field": "title", "issue": "weak"}],
        content_type="page",
    )
    seo_tasks_db.approve_check(approved["check_id"])

    snap = build_seo_review_summary()
    assert snap["ok"] is True
    assert snap["total"] == 3
    assert snap["open_count"] == 2
    assert snap["fixed_count"] == 1
    assert snap["verdicts"]["red"] == 1
    assert snap["statuses"]["pending_approval"] == 2
    assert snap["statuses"]["approved"] == 1
    ctx = format_seo_chat_context(snap)
    assert "open (pending_approval): 2" in ctx
    assert "fixed (approved): 1" in ctx


def test_seo_summary_db_error_honest_fallback() -> None:
    with patch(
        "app.services.seo_task_summary.seo_tasks_db.list_checks",
        side_effect=RuntimeError("db down"),
    ):
        snap = build_seo_review_summary()
    assert snap["ok"] is False
    assert "unavailable" in snap["summary"].lower()
    ctx = format_seo_chat_context(snap)
    assert "UNAVAILABLE" in ctx
    assert "could not reach SEO Tasks" in ctx


def test_task_summary_empty_db() -> None:
    snap = build_task_service_summary()
    assert snap["ok"] is True
    assert snap["open_tasks"] == 0
    assert snap["urgent_tasks"] == 0
    assert snap["in_progress"] == 0
    ctx = format_task_service_chat_context(snap)
    assert "EMPTY" in ctx
    assert "Do NOT reassign" in ctx


def test_task_summary_counts_urgent_and_in_progress() -> None:
    tasks_db.create_task(
        title="Urgent open",
        description="",
        assignee_type="human",
        assignee_wp_user_id=1,
        created_by_wp_user_id=1,
        priority="urgent",
        status="todo",
    )
    tasks_db.create_task(
        title="In progress",
        description="",
        assignee_type="human",
        assignee_wp_user_id=2,
        created_by_wp_user_id=1,
        priority="normal",
        status="in_progress",
    )
    tasks_db.create_task(
        title="Amy running",
        description="",
        assignee_type="amy",
        created_by_wp_user_id=1,
        priority="normal",
        status="running",
    )
    done = tasks_db.create_task(
        title="Done recently",
        description="",
        assignee_type="human",
        assignee_wp_user_id=1,
        created_by_wp_user_id=1,
        priority="normal",
        status="todo",
    )
    tasks_db.update_task(done["id"], {"status": "done"})

    snap = build_task_service_summary()
    assert snap["ok"] is True
    assert snap["open_tasks"] == 3
    assert snap["urgent_tasks"] == 1
    assert snap["in_progress"] == 1
    assert snap["running"] == 1
    assert snap["completed_this_week"] >= 1
    ctx = format_task_service_chat_context(snap)
    assert "urgent_tasks: 1" in ctx
    assert "in_progress: 1" in ctx
    assert "running (Amy execution): 1" in ctx


def test_task_summary_db_error_honest_fallback() -> None:
    with patch(
        "app.services.seo_task_summary.tasks_db.get_stats",
        side_effect=RuntimeError("db down"),
    ):
        snap = build_task_service_summary()
    assert snap["ok"] is False
    assert "unavailable" in snap["summary"].lower()
    ctx = format_task_service_chat_context(snap)
    assert "UNAVAILABLE" in ctx
    assert "could not reach Task Service" in ctx
