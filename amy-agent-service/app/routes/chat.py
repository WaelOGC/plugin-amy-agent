"""Chat endpoint — routes to the selected provider adapter."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.db import conversations_db
from app.prompts import AMY_ADMIN_SYSTEM_PROMPT, AMY_SYSTEM_PROMPT
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
from app.services.admin_chat_tools import (
    detect_admin_tool_intent,
    intent_context_messages,
    run_admin_tool_loop,
)
from app.services.analytics_summary import (
    analytics_summary_for_chat,
    format_analytics_chat_context,
)
from app.services.seo_task_summary import (
    format_seo_chat_context,
    format_task_service_chat_context,
    seo_review_summary_for_chat,
    task_service_summary_for_chat,
)

router = APIRouter(tags=["chat"])


def _admin_identity_message(
    wp_user_name: str | None,
    wp_user_email: str | None,
) -> ChatMessage | None:
    name = (wp_user_name or "").strip()
    email = (wp_user_email or "").strip()
    if not name and not email:
        return None
    if name and email:
        who = f"{name} ({email})"
    elif name:
        who = name
    else:
        who = email
    return ChatMessage(
        role="system",
        content=(
            f"You are currently talking with {who}. Address them by name naturally "
            "in conversation, the way a colleague would — you don't need to repeat "
            "their name every message, just use it when it reads naturally "
            "(e.g. a greeting, or when it adds clarity)."
        ),
    )


def _admin_analytics_context_message() -> ChatMessage:
    snapshot = analytics_summary_for_chat()
    return ChatMessage(
        role="system",
        content=format_analytics_chat_context(snapshot),
    )


def _admin_seo_context_message() -> ChatMessage:
    snapshot = seo_review_summary_for_chat()
    return ChatMessage(
        role="system",
        content=format_seo_chat_context(snapshot),
    )


def _admin_task_service_context_message() -> ChatMessage:
    snapshot = task_service_summary_for_chat()
    return ChatMessage(
        role="system",
        content=format_task_service_chat_context(snapshot),
    )


def _latest_user_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content or ""
    return ""


def _messages_with_system(
    messages: list[ChatMessage],
    *,
    mode: str = "general",
    wp_user_name: str | None = None,
    wp_user_email: str | None = None,
    include_analytics_snapshot: bool = False,
    include_seo_task_snapshots: bool = False,
    auto_invoke_tools: bool = True,
) -> tuple[list[ChatMessage], list[str]]:
    """Prepend Amy's persona prompt unless a system message is already first.

    Admin mode (P3): hybrid orchestrator —
    - No always-on full snapshots by default (token-cheap).
    - Intent auto-invoke injects live tool results for Analytics / SEO / Tasks.
    - Optional ``include_*`` flags force the older P0–P2 snapshot inject.
    - Provider tool loop (caller) can still call allowlisted tools on demand.
    Slash ``/analytics`` remains a WP/Telegram shortcut outside this path.

    Returns ``(messages, tools_auto_invoked)``.
    """
    if messages and messages[0].role == "system":
        return messages, []

    if mode == "admin":
        system_msgs: list[ChatMessage] = [
            ChatMessage(role="system", content=AMY_ADMIN_SYSTEM_PROMPT)
        ]
        tools_used: list[str] = []

        if include_analytics_snapshot:
            system_msgs.append(_admin_analytics_context_message())
        if include_seo_task_snapshots:
            system_msgs.append(_admin_seo_context_message())
            system_msgs.append(_admin_task_service_context_message())

        if auto_invoke_tools and not (
            include_analytics_snapshot and include_seo_task_snapshots
        ):
            # Skip tools already covered by forced snapshots.
            intent_names = detect_admin_tool_intent(_latest_user_text(messages))
            skip = set()
            if include_analytics_snapshot:
                skip.update({"analytics_summary", "analytics_leads_query"})
            if include_seo_task_snapshots:
                skip.update({"seo_summary", "task_stats"})
            intent_names = [n for n in intent_names if n not in skip]
            if intent_names:
                ctx_msgs, used = intent_context_messages(intent_names)
                system_msgs.extend(ctx_msgs)
                tools_used.extend(used)

        identity = _admin_identity_message(wp_user_name, wp_user_email)
        if identity is not None:
            system_msgs.append(identity)
        return [*system_msgs, *messages], tools_used

    return [ChatMessage(role="system", content=AMY_SYSTEM_PROMPT), *messages], []


def _content_for_provider(msg: ChatMessage) -> str:
    """Provider-bound text only — does not mutate stored message content."""
    if not msg.attachments:
        return msg.content
    names = ", ".join(a.filename for a in msg.attachments)
    return f"{msg.content}\n\n[Attached: {names}]"


def _messages_for_provider(messages: list[ChatMessage]) -> list[ChatMessage]:
    out: list[ChatMessage] = []
    for m in messages:
        out.append(
            ChatMessage(
                role=m.role,
                content=_content_for_provider(m) if m.role != "tool" else m.content,
                attachments=list(m.attachments or []),
                tool_calls=list(m.tool_calls or []),
                tool_call_id=m.tool_call_id,
                name=m.name,
            )
        )
    return out


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
        if not conversations_db.can_access_conversation(
            conversation,
            wp_user_id=body.wp_user_id,
            is_full_admin=body.is_full_admin,
            visitor_id=body.visitor_id,
        ):
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
            ChatMessage(
                role=m["role"],
                content=m["content"],
                attachments=m.get("attachments") or [],
            )
            for m in stored
        ]
        history_for_completion.append(new_user_message)
    else:
        history_for_completion = list(body.messages)

    provider = get_provider(provider_slug)
    resolved_model = provider.resolve_model(body.ai.model)
    prepared, auto_tools = _messages_with_system(
        history_for_completion,
        mode=body.mode,
        wp_user_name=body.wp_user_name,
        wp_user_email=body.wp_user_email,
    )
    messages = _messages_for_provider(prepared)

    tools_used: list[str] = list(auto_tools)
    try:
        if body.mode == "admin":
            text, loop_tools = await run_admin_tool_loop(
                provider,
                messages,
                api_key=api_key,
                model=body.ai.model,
            )
            for name in loop_tools:
                if name not in tools_used:
                    tools_used.append(name)
        else:
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
            conversation_id,
            "user",
            new_user_message.content,
            attachments=[a.model_dump() for a in new_user_message.attachments] or None,
        )
        conversations_db.append_message(conversation_id, "assistant", text)

    payload = ChatSuccessResponse(
        session_id=body.session_id,
        reply=ChatReply(content=text),
        actions=[],
        meta=ChatMeta(
            provider=provider_slug,
            model=resolved_model,
            tools_used=tools_used,
        ),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())
