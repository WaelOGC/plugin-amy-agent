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
    lead_whatsapp: str | None = None
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


class AnalyticsSummaryCounts(BaseModel):
    hot: int = 0
    warm: int = 0
    cold: int = 0
    other: int = 0


class AnalyticsEmailCaptures(BaseModel):
    total: int = 0
    last_7d: int = 0


class AnalyticsLastSeenWindows(BaseModel):
    last_24h: int = 0
    last_7d: int = 0
    most_recent_at: float | None = None
    most_recent: str | None = None


class AnalyticsSummarySampleItem(BaseModel):
    session_id: str | None = None
    session_id_short: str | None = None
    lead_status: str | None = None
    has_email: bool = False
    lead_email: str | None = None
    last_seen_at: float = 0
    last_seen: str | None = None
    ip_country: str | None = None
    ip_city: str | None = None


class AnalyticsSummaryResponse(BaseModel):
    """Shared Analytics summary contract for chat, Overview, and slash shortcuts."""

    ok: bool
    total: int = 0
    counts: AnalyticsSummaryCounts = AnalyticsSummaryCounts()
    with_email: int = 0
    email_captures: AnalyticsEmailCaptures = AnalyticsEmailCaptures()
    last_seen: AnalyticsLastSeenWindows = AnalyticsLastSeenWindows()
    empty: bool = True
    summary: str = ""
    slash_reply: str = ""
    sample: list[AnalyticsSummarySampleItem] = []
    sample_count: int = 0
    hot_sample: list[AnalyticsSummarySampleItem] = []
    hot_sample_count: int = 0
    error: str | None = None


class TrafficWindowCounts(BaseModel):
    pageviews: int = 0
    unique_sessions: int = 0


class TrafficWindows(BaseModel):
    all_time: TrafficWindowCounts = TrafficWindowCounts()
    last_24h: TrafficWindowCounts = TrafficWindowCounts()
    last_7d: TrafficWindowCounts = TrafficWindowCounts()
    last_30d: TrafficWindowCounts = TrafficWindowCounts()


class TrafficTopPathItem(BaseModel):
    path: str
    pageviews: int = 0
    unique_sessions: int = 0


class AnalyticsTrafficResponse(BaseModel):
    """Page-view traffic depth from visitor_events (not GA)."""

    ok: bool
    windows: TrafficWindows = TrafficWindows()
    top_paths_7d: list[TrafficTopPathItem] = []
    top_paths_all: list[TrafficTopPathItem] = []
    empty: bool = True
    summary: str = ""
    error: str | None = None


class EmailAudienceSampleItem(BaseModel):
    session_id: str | None = None
    session_id_short: str | None = None
    lead_status: str | None = None
    lead_email: str | None = None
    ip_country: str | None = None
    ip_city: str | None = None
    last_seen_at: float = 0


class EmailAudienceResponse(BaseModel):
    """Read-only Email Marketing audience (leads with email). No send from API."""

    ok: bool
    total: int = 0
    counts: AnalyticsSummaryCounts = AnalyticsSummaryCounts()
    email_captures: AnalyticsEmailCaptures = AnalyticsEmailCaptures()
    sample: list[EmailAudienceSampleItem] = []
    sample_count: int = 0
    empty: bool = True
    summary: str = ""
    send_policy: str = "approve_then_send"
    notes: str | None = None
    error: str | None = None


class ClosingWishCohortCounts(BaseModel):
    conversations: int = 0
    submit_idea_started: int = 0


class ClosingWishEffectResponse(BaseModel):
    """Last-N-days public chat → Submit Idea, split by closing wish."""

    ok: bool = True
    days: int = 30
    public_chat_conversations: int = 0
    with_closing_wish: ClosingWishCohortCounts = ClosingWishCohortCounts()
    without_closing_wish: ClosingWishCohortCounts = ClosingWishCohortCounts()
