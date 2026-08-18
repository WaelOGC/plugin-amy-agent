"""Pydantic models for SEO Tasks batch runs."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.seo_tasks import SeoContentType, SeoFinding, SeoVerdict

SeoBatchMode = Literal["manual", "auto"]
SeoBatchStatus = Literal["in_progress", "stopped", "completed"]


class SeoBatchItemInput(BaseModel):
    item_id: int = Field(ge=1)
    title: str = ""
    snapshot: Any = Field(default_factory=dict)


class SeoBatchStartRequest(BaseModel):
    content_type: SeoContentType
    mode: SeoBatchMode
    batch_size: int = 5
    items: list[SeoBatchItemInput] = Field(min_length=1)


class SeoBatchItemResult(BaseModel):
    item_id: int
    title: str = ""
    check_id: str | None = None
    verdict: SeoVerdict | None = None
    findings: list[SeoFinding] = Field(default_factory=list)
    error: str | None = None


class SeoBatchReport(BaseModel):
    batch_index: int
    results: list[SeoBatchItemResult]


class SeoBatchRunResponse(BaseModel):
    batch_run_id: str
    content_type: SeoContentType
    mode: SeoBatchMode
    batch_size: int
    total_items: int
    status: SeoBatchStatus
    processed_count: int
    reports: list[SeoBatchReport] = Field(default_factory=list)
    created_at: float
    updated_at: float


class SeoBatchRunSummary(BaseModel):
    batch_run_id: str
    content_type: SeoContentType
    mode: SeoBatchMode
    batch_size: int
    total_items: int
    status: SeoBatchStatus
    processed_count: int
    created_at: float
    updated_at: float


class SeoBatchRunListResponse(BaseModel):
    runs: list[SeoBatchRunSummary]
