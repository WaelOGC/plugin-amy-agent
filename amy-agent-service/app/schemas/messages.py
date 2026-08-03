"""Pydantic models matching the PHP ↔ Python API contract."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderSlug = Literal["gemini", "openai", "anthropic", "deepseek"]
ChatMode = Literal["general", "submit_idea", "support"]
MessageRole = Literal["user", "assistant", "system"]


class AiConfig(BaseModel):
    """AI provider config owned by WordPress, passed per request."""

    provider: ProviderSlug
    api_key: str = Field(min_length=0)
    model: str | None = None


class ConfigValidateRequest(BaseModel):
    ai: AiConfig


class ConfigValidateResponse(BaseModel):
    ok: bool
    provider: ProviderSlug | None = None
    error: str | None = None
    message: str | None = None


class PageContext(BaseModel):
    url: str | None = None
    slug: str | None = None


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    session_id: str
    mode: ChatMode = "general"
    page: PageContext | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    ai: AiConfig
    context: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    ok: bool
    version: str


class ErrorBody(BaseModel):
    error: str
    message: str


class ChatReply(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatMeta(BaseModel):
    provider: ProviderSlug
    model: str


class ChatSuccessResponse(BaseModel):
    session_id: str
    reply: ChatReply
    actions: list[Any] = Field(default_factory=list)
    meta: ChatMeta
