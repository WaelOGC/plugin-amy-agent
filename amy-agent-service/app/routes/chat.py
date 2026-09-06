"""Chat endpoint — routes to the selected provider adapter."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import conversations_db
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


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


@router.post("/v1/chat", dependencies=[Depends(require_amy_secret)])
async def chat(body: ChatRequest) -> JSONResponse:
    provider_slug = body.ai.provider
    api_key = (body.ai.api_key or "").strip()

    if not is_known_provider(provider_slug) or not api_key:
        return _error(
            "invalid_config",
            "Unknown provider or empty API key.",
            status.HTTP_400_BAD_REQUEST,
        )

    if not body.messages:
        return _error(
            "invalid_request",
            "At least one message is required.",
            status.HTTP_400_BAD_REQUEST,
        )

    conversation_id = (body.conversation_id or "").strip() or None
    new_user_message: ChatMessage | None = None
    history_for_completion: list[ChatMessage]

    if conversation_id is not None:
        conversation = conversations_db.get_conversation(conversation_id)
        if conversation is None:
            return _error(
                "conversation_not_found",
                "Conversation not found.",
                status.HTTP_404_NOT_FOUND,
            )
        if not body.is_full_admin and conversation["wp_user_id"] != body.wp_user_id:
            return _error(
                "forbidden",
                "You do not have access to this conversation.",
                status.HTTP_403_FORBIDDEN,
            )

        last = body.messages[-1]
        if last.role != "user":
            return _error(
                "invalid_request",
                "Last message must be a user turn when conversation_id is set.",
                status.HTTP_400_BAD_REQUEST,
            )
        new_user_message = last

        stored = conversations_db.get_messages(conversation_id)
        history_for_completion = [
            ChatMessage(role=m["role"], content=m["content"]) for m in stored
        ]
        history_for_completion.append(new_user_message)
    else:
        history_for_completion = list(body.messages)

    provider = get_provider(provider_slug)
    resolved_model = provider.resolve_model(body.ai.model)
    messages = _messages_with_system(history_for_completion)

    try:
        text = await provider.complete(
            messages,
            api_key=api_key,
            model=body.ai.model,
        )
    except ProviderError as exc:
        return _error(
            exc.code,
            "Amy could not reach the AI provider. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )
    except Exception:
        return _error(
            "provider_error",
            "Amy could not reach the AI provider. Please try again shortly.",
            status.HTTP_502_BAD_GATEWAY,
        )

    if conversation_id is not None and new_user_message is not None:
        conversations_db.append_message(
            conversation_id, "user", new_user_message.content
        )
        conversations_db.append_message(conversation_id, "assistant", text)

    payload = ChatSuccessResponse(
        session_id=body.session_id,
        reply=ChatReply(content=text),
        actions=[],
        meta=ChatMeta(provider=provider_slug, model=resolved_model),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())
