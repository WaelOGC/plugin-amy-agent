"""Conversation memory request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.messages import ChatMessage, ChatMode


class ConversationSummary(BaseModel):
    id: str
    wp_user_id: int
    mode: ChatMode
    title: str | None = None
    status: str
    created_at: float
    updated_at: float


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessage] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    wp_user_id: int
    mode: ChatMode = "admin"
    title: str | None = None


class RenameConversationRequest(BaseModel):
    title: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
