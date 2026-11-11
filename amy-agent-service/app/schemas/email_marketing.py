"""Pydantic schemas for Email Marketing history / opt-out / Amy propose."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmailMessageOut(BaseModel):
    id: str
    thread_id: str
    direction: str
    channel: str
    status: str
    from_email: str | None = None
    to_email: str | None = None
    subject: str | None = None
    body: str
    wp_user_id: int | None = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: float


class EmailThreadOut(BaseModel):
    id: str
    participant_email: str
    subject: str | None = None
    status: str
    created_at: float
    updated_at: float
    last_message: EmailMessageOut | None = None
    suppressed: bool = False


class EmailThreadListResponse(BaseModel):
    threads: list[EmailThreadOut]
    total: int
    limit: int
    offset: int


class EmailThreadDetailResponse(BaseModel):
    thread: EmailThreadOut
    messages: list[EmailMessageOut]
    inbound_limitation: str = (
        "FluentSMTP is outbound-only. Automatic mailbox inbound is not wired "
        "(no AgentMail). Log replies with Add reply note, or POST the optional "
        "inbound webhook if you forward hello@ mail yourself."
    )


class OutboundRecipientResult(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    ok: bool = False
    error: str | None = None


class RecordOutboundRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    from_email: str = Field(min_length=3, max_length=254)
    wp_user_id: int | None = None
    channel: str = "fluentsmtp"
    recipients: list[OutboundRecipientResult] = Field(min_length=1)


class RecordOutboundResponse(BaseModel):
    recorded: int
    items: list[dict[str, Any]]


class AddNoteRequest(BaseModel):
    body: str = Field(min_length=1)
    wp_user_id: int | None = None
    as_inbound: bool = False


class ProposeSendRequest(BaseModel):
    to_email: str = Field(min_length=3, max_length=254)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    from_email: str | None = None
    proposed_by: str = "amy"
    meta: dict[str, Any] = Field(default_factory=dict)


class ProposeSendResponse(BaseModel):
    thread: EmailThreadOut
    message: EmailMessageOut
    requires_human_approve: bool = True


class SuppressionRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    reason: str | None = None
    source: str = "manual"


class SuppressionOut(BaseModel):
    email: str
    reason: str | None = None
    source: str | None = None
    created_at: float


class SuppressionListResponse(BaseModel):
    suppressions: list[SuppressionOut]


class InboundWebhookRequest(BaseModel):
    """Generic inbound payload (optional forwarder). Not AgentMail."""

    from_email: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to_email: str | None = None
    to: str | None = None
    subject: str | None = None
    body: str | None = None
    text: str | None = None
    html: str | None = None
    message: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CheckSuppressedResponse(BaseModel):
    email: str
    suppressed: bool
