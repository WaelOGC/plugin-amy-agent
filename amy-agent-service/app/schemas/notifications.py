"""Pydantic models for Task Service notifications and extensions."""

from typing import Any, Literal

from pydantic import BaseModel, Field

NotificationType = Literal[
    "reminder_midpoint",
    "reminder_final",
    "urgent_checkin",
    "task_expired",
    "reassigned_to_you",
    "reassigned_notice",
    "extension_auto_granted",
    "extension_needs_approval",
    "extension_approved",
    "extension_denied",
    "no_one_available",
]

ExtensionStatus = Literal["pending", "auto_approved", "approved", "denied"]


class NotificationResponse(BaseModel):
    id: str
    task_id: str
    wp_user_id: int
    type: NotificationType
    message: str
    requires_action: bool
    action_payload: dict[str, Any] | None = None
    created_at: float
    read_at: float | None = None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]


class ExtensionRequestResponse(BaseModel):
    id: str
    task_id: str
    requested_by_wp_user_id: int
    requested_seconds: float
    status: ExtensionStatus
    created_at: float
    resolved_at: float | None = None


class ExtensionRequestBody(BaseModel):
    requester_wp_user_id: int
    requested_seconds: float = Field(gt=0)


class ExtensionDecisionBody(BaseModel):
    requester_wp_user_id: int  # actor (must be task creator)


class AcknowledgeBody(BaseModel):
    requester_wp_user_id: int


class ExtensionActionResponse(BaseModel):
    outcome: str
    extension_request: ExtensionRequestResponse
    task: dict[str, Any] | None = None


class DashboardUserSyncItem(BaseModel):
    wp_user_id: int
    display_name: str = ""


class DashboardUserSyncRequest(BaseModel):
    users: list[DashboardUserSyncItem]


class DashboardUserSyncResponse(BaseModel):
    ok: bool
    count: int
