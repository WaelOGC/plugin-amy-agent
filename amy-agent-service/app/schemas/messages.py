"""Pydantic models matching the PHP ↔ Python API contract."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ProviderSlug = Literal["gemini", "openai", "anthropic", "deepseek"]
ChatMode = Literal["general", "submit_idea", "support", "admin"]
MessageRole = Literal["user", "assistant", "system", "tool"]

# Hard cap for optional live theme price list (plugin also caps ~6000).
PRICING_CATALOGUE_MAX_CHARS = 6000

# Visitor locale hints for public chat (closing wishes).
VISITOR_TIMEZONE_MAX_LEN = 64
VISITOR_LANGUAGE_MAX_LEN = 32


def sanitize_pricing_catalogue(value: str | None) -> str:
    """Treat catalogue as untrusted: strip control chars and cap length."""
    if value is None:
        return ""
    text = str(value)
    cleaned = "".join(
        ch for ch in text if ch in ("\n", "\t") or ord(ch) >= 32
    )
    if len(cleaned) > PRICING_CATALOGUE_MAX_CHARS:
        cleaned = cleaned[:PRICING_CATALOGUE_MAX_CHARS]
    return cleaned.strip()


def sanitize_visitor_timezone(value: str | None) -> str | None:
    """Validate/cap IANA timezone; None when missing or invalid."""
    from app.services.closing_wishes import sanitize_timezone

    return sanitize_timezone(value)


def sanitize_visitor_language(value: str | None) -> str | None:
    """Validate/cap browser language tag; None when missing or invalid."""
    from app.services.closing_wishes import sanitize_language

    return sanitize_language(value)


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


class AttachmentPageRef(BaseModel):
    id: str
    url: str


class AttachmentRef(BaseModel):
    url: str
    filename: str
    content_type: str | None = None
    # Public-chat secure uploads (optional; admin/Submit Idea leave these unset).
    id: str | None = None
    kind: str | None = None  # image | pdf
    size: int | None = None
    expired: bool = False
    description: str | None = None
    page_count: int | None = None
    pages: list[AttachmentPageRef] | None = None


class InlineMediaPart(BaseModel):
    """Provider-only binary part (not persisted on conversation messages)."""

    mime_type: str
    data: str  # base64


class ToolCallPart(BaseModel):
    """Assistant-requested tool call (provider-agnostic)."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Gemini 3+ thought signature; omitted for other providers / older history.
    thought_signature: str | None = None


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = ""
    attachments: list[AttachmentRef] = Field(default_factory=list)
    # Unix timestamp (seconds) when persisted; optional on outbound chat turns.
    created_at: float | None = None
    # Assistant turn that requested tools (P3 tool loop).
    tool_calls: list[ToolCallPart] = Field(default_factory=list)
    # Tool-result turn (role=tool).
    tool_call_id: str | None = None
    name: str | None = None
    # Ephemeral multimodal parts for the current provider call only.
    inline_media: list[InlineMediaPart] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    mode: ChatMode = "general"
    page: PageContext | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    ai: AiConfig
    context: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    wp_user_id: int | None = None
    is_full_admin: bool = False
    wp_user_name: str | None = None
    wp_user_email: str | None = None
    visitor_id: str | None = None
    # Optional compact plain-text price list from the active theme (public chat).
    pricing_catalogue: str | None = None
    # Optional visitor locale for public closing wishes (ignored in admin mode).
    visitor_timezone: str | None = None
    visitor_language: str | None = None

    @field_validator("pricing_catalogue", mode="before")
    @classmethod
    def _sanitize_pricing_catalogue(cls, value: Any) -> str:
        return sanitize_pricing_catalogue(value if value is None else str(value))

    @field_validator("visitor_timezone", mode="before")
    @classmethod
    def _sanitize_visitor_timezone(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return sanitize_visitor_timezone(str(value))

    @field_validator("visitor_language", mode="before")
    @classmethod
    def _sanitize_visitor_language(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return sanitize_visitor_language(str(value))


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
    tools_used: list[str] = Field(default_factory=list)
    # True when a public closing-wish hint was attached this turn (widget may track).
    closing_wish: bool = False


class ChatSuccessResponse(BaseModel):
    session_id: str
    reply: ChatReply
    actions: list[Any] = Field(default_factory=list)
    meta: ChatMeta
