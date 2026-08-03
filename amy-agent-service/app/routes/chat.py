"""Chat endpoint — routes to the selected provider adapter."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.prompts import AMY_SYSTEM_PROMPT
from app.providers import get_provider, is_known_provider
from app.providers.errors import ProviderError
from app.schemas.messages import (
    ChatMessage,
    ChatMeta,
    ChatReply,
    ChatRequest,
    ChatSuccessResponse,
    ErrorBody,
)

router = APIRouter(tags=["chat"])


def _messages_with_system(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Prepend Amy's persona prompt unless a system message is already first."""
    if messages and messages[0].role == "system":
        return messages
    return [ChatMessage(role="system", content=AMY_SYSTEM_PROMPT), *messages]


@router.post("/v1/chat", dependencies=[Depends(require_amy_secret)])
async def chat(body: ChatRequest) -> JSONResponse:
    provider_slug = body.ai.provider
    api_key = (body.ai.api_key or "").strip()

    if not is_known_provider(provider_slug) or not api_key:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorBody(
                error="invalid_config",
                message="Unknown provider or empty API key.",
            ).model_dump(),
        )

    if not body.messages:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorBody(
                error="invalid_request",
                message="At least one message is required.",
            ).model_dump(),
        )

    provider = get_provider(provider_slug)
    resolved_model = provider.resolve_model(body.ai.model)
    messages = _messages_with_system(list(body.messages))

    try:
        text = await provider.complete(
            messages,
            api_key=api_key,
            model=body.ai.model,
        )
    except ProviderError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorBody(
                error=exc.code,
                message="Amy could not reach the AI provider. Please try again shortly.",
            ).model_dump(),
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorBody(
                error="provider_error",
                message="Amy could not reach the AI provider. Please try again shortly.",
            ).model_dump(),
        )

    payload = ChatSuccessResponse(
        session_id=body.session_id,
        reply=ChatReply(content=text),
        actions=[],
        meta=ChatMeta(provider=provider_slug, model=resolved_model),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())
