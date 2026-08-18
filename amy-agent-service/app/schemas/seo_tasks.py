"""Pydantic models for the SEO Tasks check + approval API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.messages import AiConfig

SeoVerdict = Literal["red", "orange", "green"]
SeoSeverity = Literal["missing", "weak"]
SeoCheckStatus = Literal["pending_approval", "approved", "rejected"]
SeoContentType = Literal["post", "page", "category", "tag", "media"]


class SeoFinding(BaseModel):
    field: str
    severity: SeoSeverity
    message: str


class SeoCheckRequest(BaseModel):
    wp_post_id: int = Field(ge=1)
    post_type: str = Field(min_length=1, max_length=32)
    content_type: SeoContentType = "post"
    title: str = ""
    content_excerpt: str = ""
    focus_keyphrase: str = ""
    seo_title: str = ""
    meta_description: str = ""
    has_featured_image: bool = False
    featured_image_alt: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    twitter_title: str = ""
    twitter_description: str = ""
    twitter_image: str = ""
    category_count: int = Field(default=0, ge=0)
    term_description: str = ""
    filename: str = ""
    alt_text: str = ""
    caption: str = ""
    description: str = ""


class SeoCheckResponse(BaseModel):
    check_id: str
    wp_post_id: int
    post_type: str
    content_type: SeoContentType = "post"
    title: str = ""
    verdict: SeoVerdict
    findings: list[SeoFinding]
    status: SeoCheckStatus
    checked_at: float
    updated_at: float
    approved_fields: dict[str, Any] | None = None
    reject_reason: str | None = None
    batch_run_id: str | None = None


class SeoCheckListResponse(BaseModel):
    checks: list[SeoCheckResponse]


class SeoApproveRequest(BaseModel):
    approved_fields: dict[str, Any] = Field(default_factory=dict)


class SeoRejectRequest(BaseModel):
    reason: str | None = None


class SeoGenerateRequest(BaseModel):
    ai: AiConfig
    fields: list[str] | None = None  # None = auto-derive from stored findings


class SeoGenerateResponse(BaseModel):
    check_id: str
    generated_fields: dict[str, str]
    provider: str
    model: str


class SeoGenerateImageRequest(BaseModel):
    ai: AiConfig


class SeoGenerateImageResponse(BaseModel):
    check_id: str
    image_base64: str
    mime_type: str
    suggested_alt_text: str
