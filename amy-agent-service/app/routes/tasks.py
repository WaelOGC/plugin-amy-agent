"""Task Service CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import progress_notes_db, tasks_db
from app.schemas.messages import ErrorBody
from app.schemas.tasks import (
    ExpiryActionRequest,
    ExpiryActionResponse,
    ProgressNoteCreateRequest,
    ProgressNoteListResponse,
    ProgressNoteResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatsResponse,
    TaskUpdateRequest,
    TelegramProgressReplyRequest,
    TelegramProgressReplyResponse,
)
from app.schemas.notifications import (
    DashboardUserSyncRequest,
    DashboardUserSyncResponse,
)
from app.services import task_amy_execution, task_escalation, task_notify
from app import config_task_rules as rules

router = APIRouter(tags=["tasks"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _to_response(row: dict) -> TaskResponse:
    return TaskResponse(**row)


@router.get(
    "/v1/tasks/stats",
    response_model=TaskStatsResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def task_stats() -> TaskStatsResponse:
    return TaskStatsResponse(**tasks_db.get_stats())


@router.post(
    "/v1/tasks/sync-dashboard-users",
    response_model=DashboardUserSyncResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def sync_dashboard_users(
    body: DashboardUserSyncRequest,
) -> DashboardUserSyncResponse:
    count = tasks_db.sync_dashboard_users(
        [u.model_dump() for u in body.users],
        site_default_owner_wp_user_id=body.site_default_owner_wp_user_id,
    )
    return DashboardUserSyncResponse(
        ok=True,
        count=count,
        site_default_owner_wp_user_id=tasks_db.get_site_default_owner(),
    )


@router.get(
    "/v1/tasks",
    response_model=TaskListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    assignee_wp_user_id: int | None = None,
) -> TaskListResponse | JSONResponse:
    try:
        rows = tasks_db.list_tasks(
            status=status_filter,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            assignee_wp_user_id=assignee_wp_user_id,
        )
    except ValueError as exc:
        return _error("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
    return TaskListResponse(tasks=[_to_response(row) for row in rows])


@router.post(
    "/v1/tasks",
    response_model=TaskResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def create_task(
    body: TaskCreateRequest, background_tasks: BackgroundTasks
) -> TaskResponse | JSONResponse:
    try:
        row = tasks_db.create_task(
            title=body.title,
            description=body.description,
            assignee_type=body.assignee_type,
            assignee_wp_user_id=body.assignee_wp_user_id,
            created_by_wp_user_id=body.created_by_wp_user_id,
            priority=body.priority,
            status=body.status,
            due_date=body.due_date,
            amy_capable=body.amy_capable,
            owner_wp_user_id=body.owner_wp_user_id,
            backup_wp_user_id=body.backup_wp_user_id,
        )
    except ValueError as exc:
        return _error("invalid_task", str(exc), status.HTTP_400_BAD_REQUEST)
    if row.get("assignee_type") == "human" and row.get("assignee_wp_user_id"):
        task_notify.dispatch_task_notify("assign", row)
    elif (
        row.get("assignee_type") == "amy"
        and rules.AMY_EXECUTION_ENABLED
        and row.get("status") not in {"done", "running", "failed"}
    ):
        # Locked: Amy-at-create runs now in background (todo → running → done/failed).
        background_tasks.add_task(
            task_amy_execution.queue_amy_task, row["id"], trigger="create"
        )
    return _to_response(row)


@router.get(
    "/v1/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def get_task(task_id: str) -> TaskResponse | JSONResponse:
    row = tasks_db.get_task(task_id)
    if row is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(row)


@router.post(
    "/v1/tasks/{task_id}/expiry-action",
    response_model=ExpiryActionResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def expiry_action(
    task_id: str, body: ExpiryActionRequest
) -> ExpiryActionResponse | JSONResponse:
    """P3/P4: owner/backup reassign, acknowledge, or Amy take (capability-gated)."""
    try:
        result = task_escalation.handle_expiry_action(
            task_id,
            actor_wp_user_id=body.actor_wp_user_id,
            action=body.action,
            assignee_wp_user_id=body.assignee_wp_user_id,
            due_date=body.due_date,
        )
    except ValueError as exc:
        return _error("invalid_action", str(exc), status.HTTP_400_BAD_REQUEST)
    return ExpiryActionResponse(
        outcome=result["outcome"],
        task=_to_response(result["task"]),
        amy_execution_enabled=bool(
            result.get("amy_execution_enabled", rules.AMY_EXECUTION_ENABLED)
        ),
    )


@router.patch(
    "/v1/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def update_task(
    task_id: str, body: TaskUpdateRequest, background_tasks: BackgroundTasks
) -> TaskResponse | JSONResponse:
    # exclude_unset so omitted fields are not treated as explicit nulls
    fields = body.model_dump(exclude_unset=True)
    previous = tasks_db.get_task(task_id)
    try:
        row = tasks_db.update_task(task_id, fields)
    except ValueError as exc:
        return _error("invalid_task", str(exc), status.HTTP_400_BAD_REQUEST)
    if row is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    if _assignee_changed(previous, row) and row.get("assignee_type") == "human":
        task_notify.dispatch_task_notify("assign", row)
    elif (
        _assignee_changed(previous, row)
        and row.get("assignee_type") == "amy"
        and rules.AMY_EXECUTION_ENABLED
        and row.get("status") not in {"done", "running", "failed"}
    ):
        background_tasks.add_task(
            task_amy_execution.queue_amy_task, row["id"], trigger="create"
        )
    return _to_response(row)


def _assignee_changed(previous: dict | None, current: dict) -> bool:
    if previous is None:
        return True
    return (
        previous.get("assignee_type") != current.get("assignee_type")
        or previous.get("assignee_wp_user_id") != current.get("assignee_wp_user_id")
    )


@router.get(
    "/v1/tasks/{task_id}/progress-notes",
    response_model=ProgressNoteListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_progress_notes(task_id: str) -> ProgressNoteListResponse | JSONResponse:
    if tasks_db.get_task(task_id) is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    rows = progress_notes_db.list_progress_notes(task_id)
    return ProgressNoteListResponse(
        notes=[ProgressNoteResponse(**row) for row in rows]
    )


@router.post(
    "/v1/tasks/{task_id}/progress-notes",
    response_model=ProgressNoteResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def create_progress_note(
    task_id: str, body: ProgressNoteCreateRequest
) -> ProgressNoteResponse | JSONResponse:
    if tasks_db.get_task(task_id) is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    try:
        row = progress_notes_db.create_progress_note(
            task_id=task_id,
            wp_user_id=body.wp_user_id,
            note=body.note,
            source=body.source,
        )
    except ValueError as exc:
        return _error("invalid_note", str(exc), status.HTTP_400_BAD_REQUEST)
    return ProgressNoteResponse(**row)


@router.post(
    "/v1/tasks/progress-notes/from-telegram",
    response_model=TelegramProgressReplyResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def consume_telegram_progress_reply(
    body: TelegramProgressReplyRequest,
) -> TelegramProgressReplyResponse | JSONResponse:
    """Webhook hook: save free-text as progress note when a mid ask is pending."""
    try:
        saved = progress_notes_db.consume_telegram_progress_reply(
            wp_user_id=body.wp_user_id,
            note=body.note,
        )
    except ValueError as exc:
        return _error("invalid_note", str(exc), status.HTTP_400_BAD_REQUEST)
    if saved is None:
        return TelegramProgressReplyResponse(saved=False, note=None)
    return TelegramProgressReplyResponse(
        saved=True, note=ProgressNoteResponse(**saved)
    )


@router.delete(
    "/v1/tasks/{task_id}",
    response_model=None,
    dependencies=[Depends(require_amy_secret)],
)
async def delete_task(task_id: str) -> dict | JSONResponse:
    deleted = tasks_db.delete_task(task_id)
    if not deleted:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    return {"ok": True, "id": task_id}
