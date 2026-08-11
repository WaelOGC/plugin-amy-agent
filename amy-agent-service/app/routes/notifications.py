"""Notification, acknowledgement, and extension endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import notifications_db, tasks_db
from app.schemas.messages import ErrorBody
from app.schemas.notifications import (
    AcknowledgeBody,
    ExtensionActionResponse,
    ExtensionDecisionBody,
    ExtensionRequestBody,
    ExtensionRequestResponse,
    NotificationListResponse,
    NotificationResponse,
)
from app.schemas.tasks import TaskResponse
from app.services import task_escalation as escalation

router = APIRouter(tags=["notifications"])


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


@router.get(
    "/v1/notifications",
    response_model=NotificationListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_notifications(
    wp_user_id: int = Query(...),
    unread_only: bool = Query(default=False),
) -> NotificationListResponse:
    rows = notifications_db.list_notifications(
        wp_user_id=wp_user_id, unread_only=unread_only
    )
    return NotificationListResponse(
        notifications=[NotificationResponse(**row) for row in rows]
    )


@router.post(
    "/v1/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def mark_notification_read(
    notification_id: str,
) -> NotificationResponse | JSONResponse:
    row = notifications_db.mark_notification_read(notification_id)
    if row is None:
        return _error("not_found", "Notification not found.", status.HTTP_404_NOT_FOUND)
    return NotificationResponse(**row)


@router.post(
    "/v1/tasks/{task_id}/acknowledge",
    response_model=TaskResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def acknowledge_task(
    task_id: str, body: AcknowledgeBody
) -> TaskResponse | JSONResponse:
    task = tasks_db.get_task(task_id)
    if task is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    # Only the current human assignee acknowledging themselves is meaningful.
    if (
        task.get("assignee_type") == "human"
        and task.get("assignee_wp_user_id") is not None
        and int(task["assignee_wp_user_id"]) != int(body.requester_wp_user_id)
    ):
        return _error(
            "forbidden",
            "Only the current assignee can acknowledge this task.",
            status.HTTP_403_FORBIDDEN,
        )
    row = tasks_db.acknowledge_task(task_id)
    if row is None:
        return _error("not_found", "Task not found.", status.HTTP_404_NOT_FOUND)
    return TaskResponse(**row)


@router.post(
    "/v1/tasks/{task_id}/extension-request",
    response_model=ExtensionActionResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def extension_request(
    task_id: str, body: ExtensionRequestBody
) -> ExtensionActionResponse | JSONResponse:
    try:
        result = escalation.request_extension(
            task_id,
            body.requester_wp_user_id,
            body.requested_seconds,
        )
    except ValueError as exc:
        return _error("invalid_extension", str(exc), status.HTTP_400_BAD_REQUEST)
    return ExtensionActionResponse(
        outcome=result["outcome"],
        extension_request=ExtensionRequestResponse(**result["extension_request"]),
        task=result.get("task"),
    )


@router.post(
    "/v1/extension-requests/{request_id}/approve",
    response_model=ExtensionActionResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def approve_extension(
    request_id: str, body: ExtensionDecisionBody
) -> ExtensionActionResponse | JSONResponse:
    try:
        result = escalation.approve_extension(
            request_id, actor_wp_user_id=body.requester_wp_user_id
        )
    except PermissionError as exc:
        return _error("forbidden", str(exc), status.HTTP_403_FORBIDDEN)
    except ValueError as exc:
        return _error("invalid_extension", str(exc), status.HTTP_400_BAD_REQUEST)
    return ExtensionActionResponse(
        outcome="approved",
        extension_request=ExtensionRequestResponse(**result["extension_request"]),
        task=result.get("task"),
    )


@router.post(
    "/v1/extension-requests/{request_id}/deny",
    response_model=ExtensionActionResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def deny_extension(
    request_id: str, body: ExtensionDecisionBody
) -> ExtensionActionResponse | JSONResponse:
    try:
        result = escalation.deny_extension(
            request_id, actor_wp_user_id=body.requester_wp_user_id
        )
    except PermissionError as exc:
        return _error("forbidden", str(exc), status.HTTP_403_FORBIDDEN)
    except ValueError as exc:
        return _error("invalid_extension", str(exc), status.HTTP_400_BAD_REQUEST)
    return ExtensionActionResponse(
        outcome="denied",
        extension_request=ExtensionRequestResponse(**result["extension_request"]),
        task=result.get("task"),
    )
