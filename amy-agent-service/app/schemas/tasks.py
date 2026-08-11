"""Pydantic models for the Task Service CRUD API."""

from typing import Literal

from pydantic import BaseModel, Field

AssigneeType = Literal["amy", "human"]
Priority = Literal["normal", "urgent"]
TaskStatus = Literal["todo", "in_progress", "waiting_extension", "done"]


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    assignee_type: AssigneeType = "human"
    assignee_wp_user_id: int | None = None
    created_by_wp_user_id: int
    priority: Priority = "normal"
    status: TaskStatus = "todo"
    due_date: str | None = None


class TaskUpdateRequest(BaseModel):
    """All fields optional for PATCH partial update."""

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_wp_user_id: int | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    due_date: str | None = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    assignee_type: AssigneeType
    assignee_wp_user_id: int | None = None
    created_by_wp_user_id: int
    priority: Priority
    status: TaskStatus
    due_date: str | None = None
    created_at: float
    updated_at: float
    escalation_stage: str = "none"
    escalation_stage_updated_at: float | None = None
    acknowledged_at: float | None = None
    extension_total_seconds: float = 0


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
