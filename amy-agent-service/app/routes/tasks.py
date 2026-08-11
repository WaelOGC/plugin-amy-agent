"""Task Service CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import tasks_db
from app.schemas.messages import ErrorBody
from app.schemas.tasks import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatsResponse,
    TaskUpdateRequest,
)
from app.schemas.notifications import (
    DashboardUserSyncRequest,
    DashboardUserSyncResponse,
)

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
    count = tasks_db.sync_dashboard_users([u.model_dump() for u in body.users])
    return DashboardUserSyncResponse(ok=True, count=count)


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
async def create_task(body: TaskCreateRequest) -> TaskResponse | JSONResponse:
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
        )
    except ValueError as exc:
        return _error("invalid_task", str(exc), status.HTTP_400_BAD_REQUEST)
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


@router.patch(
    "/v1/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def update_task(
    task_id: str, body: TaskUpdateRequest
) -> TaskResponse | JSONResponse:
    # exclude_unset so omitted fields are not treated as explicit nulls
    fields = body.model_dump(exclude_unset=True)
    try:
        row = tasks_db.update_task(task_id, fields)
    except ValueError as exc:
        return _error("invalid_task", str(exc), status.HTTP_400_BAD_REQUEST)
    if row is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    return _to_response(row)


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
