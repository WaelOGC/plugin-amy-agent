"""Pydantic models for the Task Service CRUD API."""

from typing import Literal

from pydantic import BaseModel, Field

AssigneeType = Literal["amy", "human"]
Priority = Literal["normal", "urgent"]
TaskStatus = Literal[
    "todo", "in_progress", "running", "waiting_extension", "done", "failed"
]


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    assignee_type: AssigneeType = "human"
    assignee_wp_user_id: int | None = None
    created_by_wp_user_id: int
    priority: Priority = "normal"
    status: TaskStatus = "todo"
    due_date: str | None = None
    amy_capable: bool = False
    owner_wp_user_id: int | None = None
    backup_wp_user_id: int | None = None


class TaskUpdateRequest(BaseModel):
    """All fields optional for PATCH partial update."""

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_wp_user_id: int | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    due_date: str | None = None
    amy_capable: bool | None = None
    owner_wp_user_id: int | None = None
    backup_wp_user_id: int | None = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    assignee_type: AssigneeType
    assignee_wp_user_id: int | None = None
    created_by_wp_user_id: int
    owner_wp_user_id: int
    backup_wp_user_id: int | None = None
    priority: Priority
    status: TaskStatus
    due_date: str | None = None
    amy_capable: bool = False
    created_at: float
    updated_at: float
    escalation_stage: str = "none"
    escalation_stage_updated_at: float | None = None
    acknowledged_at: float | None = None
    extension_total_seconds: float = 0


class ExpiryActionRequest(BaseModel):
    """Owner/backup actions after a task expires (P3)."""

    actor_wp_user_id: int
    action: Literal[
        "reassign_same",
        "reassign_other",
        "acknowledge_manual",
        "amy_take",
    ]
    assignee_wp_user_id: int | None = None
    due_date: str | None = None


class ExpiryActionResponse(BaseModel):
    outcome: str
    task: TaskResponse
    amy_execution_enabled: bool = False


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]


class TaskStatsResponse(BaseModel):
    """Aggregate counts for Task Service stat cards.

    team_completion_rate: percentage of tasks created in the last 30 days
    that currently have status == done (0–100 integer).
    """

    open_tasks: int
    urgent_tasks: int
    completed_this_week: int
    team_completion_rate: int


class ProgressNoteCreateRequest(BaseModel):
    wp_user_id: int
    note: str = Field(min_length=1)
    source: Literal["telegram", "dashboard", "api", "amy"] = "api"


class TelegramProgressReplyRequest(BaseModel):
    """Inbound free-text reply from the Admin Bot webhook (WP)."""

    wp_user_id: int
    note: str = Field(min_length=1)


class ProgressNoteResponse(BaseModel):
    id: str
    task_id: str
    wp_user_id: int
    source: str
    note: str
    created_at: float


class ProgressNoteListResponse(BaseModel):
    notes: list[ProgressNoteResponse]


class TelegramProgressReplyResponse(BaseModel):
    saved: bool
    note: ProgressNoteResponse | None = None
