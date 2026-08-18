"""Pydantic models for the Analytics event + lead-list API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

LeadStatus = Literal["cold", "warm", "hot"]


class EventIngestRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=64)
    event_data: dict[str, Any] | None = None
    page_path: str | None = Field(default=None, max_length=500)
    ip: str | None = Field(default=None, max_length=64)


class EventIngestResponse(BaseModel):
    ok: bool = True
    session_id: str
    lead_status: LeadStatus


class LeadListItem(BaseModel):
    session_id: str
    session_id_short: str
    visitor_label: str
    ip_country: str | None = None
    ip_city: str | None = None
    last_seen_at: float
    lead_status: LeadStatus
    lead_email: str | None = None
    signal: str


class LeadListResponse(BaseModel):
    leads: list[LeadListItem]


class LeadEventItem(BaseModel):
    id: int
    event_type: str
    event_data: dict[str, Any] | None = None
    page_path: str | None = None
    created_at: float


class LeadEventListResponse(BaseModel):
    session_id: str
    events: list[LeadEventItem]
