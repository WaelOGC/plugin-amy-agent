"""Submit Your Idea conversation-engine endpoints."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.data.submit_idea_templates import SUBMIT_IDEA_TEMPLATES
from app.prompts import (
    AMY_SYSTEM_PROMPT,
    SUBMIT_IDEA_DEEP_DIVE_PROMPT,
    SUBMIT_IDEA_SUMMARY_PROMPT,
)
from app.providers import get_provider, is_known_provider
from app.providers.errors import ProviderError
from app.schemas.messages import AiConfig, ChatMessage, ErrorBody
from app.schemas.submit_idea import (
    SubmitIdeaAnswersRequest,
    SubmitIdeaAnswersResponse,
    SubmitIdeaBrief,
    SubmitIdeaConfirmRequest,
    SubmitIdeaConfirmResponse,
    SubmitIdeaContactInfo,
    SubmitIdeaContactRequest,
    SubmitIdeaContactResponse,
    SubmitIdeaDeepDiveRequest,
    SubmitIdeaDeepDiveResponse,
    SubmitIdeaQuestion,
    SubmitIdeaStartRequest,
    SubmitIdeaStartResponse,
    SubmitIdeaTemplate,
    SubmitIdeaUploadResponse,
)
from app.services import submit_idea_state as state

router = APIRouter(tags=["submit-idea"])

# Uploads live under amy-agent-service/uploads/submit-idea/{session_id}/
_SERVICE_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = _SERVICE_ROOT / "uploads" / "submit-idea"

ALLOWED_UPLOAD_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_AFFIRMATIVE_RE = re.compile(
    r"^\s*(yes|y|yeah|yep|yup|correct|confirmed|looks good|that's right|thats right|"
    r"oui|ja|si|sí|ok|okay|perfect|all good|everything is correct)\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _error(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorBody(error=error, message=message).model_dump(),
    )


def _template_for(slug: str) -> SubmitIdeaTemplate | None:
    raw = SUBMIT_IDEA_TEMPLATES.get(slug)
    if not raw:
        return None
    return SubmitIdeaTemplate(
        slug=slug,
        label=raw["label"],
        questions=[SubmitIdeaQuestion(**q) for q in raw["questions"]],
    )


def _answer_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _validate_answers(template: SubmitIdeaTemplate, answers: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for q in template.questions:
        if not q.required:
            continue
        if _answer_empty(answers.get(q.id)):
            missing.append(q.id)
    return missing


async def _complete(ai: AiConfig, messages: list[ChatMessage]) -> str:
    provider_slug = ai.provider
    api_key = (ai.api_key or "").strip()
    if not is_known_provider(provider_slug) or not api_key:
        raise ValueError("invalid_config")
    provider = get_provider(provider_slug)
    return await provider.complete(messages, api_key=api_key, model=ai.model)


def _parse_summary_json(text: str) -> tuple[str, list[str]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        summary = str(data.get("summary_text") or "").strip()
        items = data.get("numbered_items") or []
        if not isinstance(items, list):
            items = []
        numbered = [str(i).strip() for i in items if str(i).strip()]
        if summary and numbered:
            return summary, numbered
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback: treat whole reply as summary_text with line-split items.
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    numbered = [ln for ln in lines if re.match(r"^\d+\.", ln)]
    summary = lines[0] if lines else cleaned
    if not numbered:
        numbered = lines[1:] if len(lines) > 1 else lines
    return summary, numbered


def _fallback_summary(template: SubmitIdeaTemplate, answers: dict[str, Any]) -> tuple[str, list[str]]:
    items: list[str] = []
    n = 1
    for q in template.questions:
        val = answers.get(q.id)
        if _answer_empty(val):
            continue
        if isinstance(val, list):
            display = ", ".join(str(v) for v in val)
        else:
            display = str(val).strip()
        items.append(f"{n}. {q.text}: {display}")
        n += 1
    summary = f"Here is a summary of your {template.label} project idea:"
    return summary, items


def _is_affirmative(message: str) -> bool:
    return bool(_AFFIRMATIVE_RE.match(message or ""))


@router.post("/v1/submit-idea/start", dependencies=[Depends(require_amy_secret)])
async def submit_idea_start(body: SubmitIdeaStartRequest) -> JSONResponse:
    template = _template_for(body.service_slug)
    if template is None:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_service",
            f"Unknown service_slug: {body.service_slug}",
        )
    if not (body.session_id or "").strip():
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            "session_id is required.",
        )

    sess = state.create_session(body.session_id.strip(), body.service_slug)
    payload = SubmitIdeaStartResponse(
        session_id=sess.session_id,
        status=sess.status,
        template=template,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())


@router.post("/v1/submit-idea/answers", dependencies=[Depends(require_amy_secret)])
async def submit_idea_answers(body: SubmitIdeaAnswersRequest) -> JSONResponse:
    try:
        sess = state.require_session(body.session_id)
    except KeyError:
        return _error(status.HTTP_404_NOT_FOUND, "session_not_found", "Unknown or expired session.")

    if not sess.selected_service:
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_state", "No service selected.")

    template = _template_for(sess.selected_service)
    if template is None:
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_service", "Unknown service on session.")

    missing = _validate_answers(template, body.answers)
    if missing:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "missing_required",
            f"Missing required answers: {', '.join(missing)}",
        )

    sess.answers = dict(body.answers)
    sess.status = "confirming"
    sess.touch()

    answers_blob = json.dumps(
        {
            "service": template.label,
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "answer": body.answers.get(q.id),
                }
                for q in template.questions
            ],
        },
        ensure_ascii=False,
        indent=2,
    )

    messages = [
        ChatMessage(role="system", content=SUBMIT_IDEA_SUMMARY_PROMPT),
        ChatMessage(
            role="user",
            content=f"Turn these project answers into the JSON summary:\n\n{answers_blob}",
        ),
    ]

    try:
        raw = await _complete(body.ai, messages)
        summary_text, numbered_items = _parse_summary_json(raw)
    except ValueError:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_config",
            "Unknown provider or empty API key.",
        )
    except ProviderError:
        summary_text, numbered_items = _fallback_summary(template, body.answers)
    except Exception:
        summary_text, numbered_items = _fallback_summary(template, body.answers)

    if not numbered_items:
        summary_text, numbered_items = _fallback_summary(template, body.answers)

    payload = SubmitIdeaAnswersResponse(
        session_id=sess.session_id,
        status=sess.status,
        summary_text=summary_text,
        numbered_items=numbered_items,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())


@router.post("/v1/submit-idea/confirm", dependencies=[Depends(require_amy_secret)])
async def submit_idea_confirm(body: SubmitIdeaConfirmRequest) -> JSONResponse:
    try:
        sess = state.require_session(body.session_id)
    except KeyError:
        return _error(status.HTTP_404_NOT_FOUND, "session_not_found", "Unknown or expired session.")

    template = _template_for(sess.selected_service or "")
    service_label = template.label if template else "your project"

    if body.confirmed:
        sess.status = "awaiting_contact"
        sess.touch()
        message = (
            "Thank you — that looks good. Please share your email "
            "(and optionally WhatsApp) so our team can follow up within 48 hours."
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=SubmitIdeaConfirmResponse(
                session_id=sess.session_id,
                status=sess.status,
                message=message,
            ).model_dump(),
        )

    sess.status = "deep_dive"
    sess.touch()

    opening = (
        f"No problem — let's refine your {service_label} brief together. "
        "What is missing or incorrect? Tell me what to change, and I'll update the summary."
    )

    # Prefer a language-matched opening when we have free-text answers + AI config.
    if body.ai and template:
        free_bits = [
            str(v)
            for q in template.questions
            if q.type in ("text", "textarea")
            for v in [sess.answers.get(q.id)]
            if not _answer_empty(v)
        ]
        sample = "\n".join(free_bits[:3])
        try:
            opening = await _complete(
                body.ai,
                [
                    ChatMessage(role="system", content=AMY_SYSTEM_PROMPT),
                    ChatMessage(
                        role="user",
                        content=(
                            f"Write ONE short opening message (2-3 sentences) inviting the client "
                            f"to say what is missing or wrong in their {service_label} project brief. "
                            f"Match the language of these prior answers:\n{sample or 'English'}\n"
                            "Do not summarize the answers. Do not use choice: links yet."
                        ),
                    ),
                ],
            )
        except Exception:
            pass

    sess.free_conversation.append({"role": "assistant", "content": opening})

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=SubmitIdeaConfirmResponse(
            session_id=sess.session_id,
            status=sess.status,
            message=opening,
        ).model_dump(),
    )


@router.post("/v1/submit-idea/deep-dive-message", dependencies=[Depends(require_amy_secret)])
async def submit_idea_deep_dive(body: SubmitIdeaDeepDiveRequest) -> JSONResponse:
    try:
        sess = state.require_session(body.session_id)
    except KeyError:
        return _error(status.HTTP_404_NOT_FOUND, "session_not_found", "Unknown or expired session.")

    if sess.status != "deep_dive":
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_state",
            "Deep-dive messages are only allowed when status is deep_dive.",
        )

    message = (body.message or "").strip()
    if not message:
        return _error(status.HTTP_400_BAD_REQUEST, "invalid_request", "message is required.")

    # Clear affirmative → move to contact collection.
    if _is_affirmative(message):
        sess.free_conversation.append({"role": "user", "content": message})
        sess.status = "awaiting_contact"
        sess.touch()
        reply = (
            "Great — thank you. Please share your email "
            "(and optionally WhatsApp) so our team can follow up within 48 hours."
        )
        sess.free_conversation.append({"role": "assistant", "content": reply})
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=SubmitIdeaDeepDiveResponse(
                session_id=sess.session_id,
                status=sess.status,
                reply=reply,
            ).model_dump(),
        )

    template = _template_for(sess.selected_service or "")
    service_label = template.label if template else "your project"
    addendum = SUBMIT_IDEA_DEEP_DIVE_PROMPT.format(service_label=service_label)

    answers_ctx = json.dumps(sess.answers, ensure_ascii=False, indent=2)
    history = list(sess.free_conversation[-12:])
    history.append({"role": "user", "content": message})

    llm_messages: list[ChatMessage] = [
        ChatMessage(role="system", content=f"{AMY_SYSTEM_PROMPT}\n\n{addendum}"),
        ChatMessage(
            role="system",
            content=f"Current structured answers (JSON):\n{answers_ctx}",
        ),
    ]
    for turn in history:
        role = turn.get("role") or "user"
        if role not in ("user", "assistant", "system"):
            role = "user"
        llm_messages.append(ChatMessage(role=role, content=str(turn.get("content") or "")))

    try:
        reply = await _complete(body.ai, llm_messages)
    except ValueError:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_config",
            "Unknown provider or empty API key.",
        )
    except ProviderError:
        return _error(
            status.HTTP_502_BAD_GATEWAY,
            "provider_error",
            "Amy could not reach the AI provider. Please try again shortly.",
        )
    except Exception:
        return _error(
            status.HTTP_502_BAD_GATEWAY,
            "provider_error",
            "Amy could not reach the AI provider. Please try again shortly.",
        )

    sess.free_conversation.append({"role": "user", "content": message})
    sess.free_conversation.append({"role": "assistant", "content": reply})
    sess.touch()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=SubmitIdeaDeepDiveResponse(
            session_id=sess.session_id,
            status=sess.status,
            reply=reply,
        ).model_dump(),
    )


@router.post("/v1/submit-idea/contact", dependencies=[Depends(require_amy_secret)])
async def submit_idea_contact(body: SubmitIdeaContactRequest) -> JSONResponse:
    try:
        sess = state.require_session(body.session_id)
    except KeyError:
        return _error(status.HTTP_404_NOT_FOUND, "session_not_found", "Unknown or expired session.")

    email = (body.email or "").strip()
    if not email or not _EMAIL_RE.match(email):
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_email",
            "A valid email address is required.",
        )

    whatsapp = (body.whatsapp or "").strip() or None
    sess.contact = {"email": email, "whatsapp": whatsapp}
    sess.status = "completed"
    sess.touch()

    template = _template_for(sess.selected_service or "")
    service_label = template.label if template else (sess.selected_service or "")
    service_slug = sess.selected_service or ""

    deep_summary: str | None = None
    if sess.free_conversation:
        deep_summary = (
            "Client refined the brief in a follow-up conversation with Amy "
            f"({len(sess.free_conversation)} messages exchanged)."
        )
        if body.ai:
            try:
                convo = "\n".join(
                    f"{t.get('role', 'user')}: {t.get('content', '')}"
                    for t in sess.free_conversation[-20:]
                )
                deep_summary = await _complete(
                    body.ai,
                    [
                        ChatMessage(
                            role="system",
                            content=(
                                "Summarize this brief-refinement chat in 1-2 sentences for an "
                                "internal project handoff. Neutral tone. No greeting."
                            ),
                        ),
                        ChatMessage(role="user", content=convo),
                    ],
                )
                deep_summary = (deep_summary or "").strip() or deep_summary
            except Exception:
                pass

    brief = SubmitIdeaBrief(
        service_slug=service_slug,
        service_label=service_label,
        answers=dict(sess.answers),
        free_conversation_summary=deep_summary,
        contact=SubmitIdeaContactInfo(email=email, whatsapp=whatsapp),
        attachments=list(sess.attachments),
    )

    payload = SubmitIdeaContactResponse(
        session_id=sess.session_id,
        status=sess.status,
        brief=brief,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())


@router.post("/v1/submit-idea/upload", dependencies=[Depends(require_amy_secret)])
async def submit_idea_upload(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> JSONResponse:
    try:
        sess = state.require_session(session_id)
    except KeyError:
        return _error(status.HTTP_404_NOT_FOUND, "session_not_found", "Unknown or expired session.")

    original_name = (file.filename or "upload").strip() or "upload"
    ext = Path(original_name).suffix.lower()
    content_type = (file.content_type or "").lower()

    if ext not in ALLOWED_UPLOAD_EXTENSIONS and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_file_type",
            "File type not allowed. Accepted: images (jpg, png, gif, webp), PDF, DOC, DOCX.",
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "file_too_large",
            "File exceeds the 10 MB size limit.",
        )
    if not data:
        return _error(status.HTTP_400_BAD_REQUEST, "empty_file", "Uploaded file is empty.")

    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(original_name).stem)[:80] or "file"
    stored_name = f"{safe_stem}-{uuid.uuid4().hex[:8]}{ext or ''}"
    dest_dir = UPLOAD_ROOT / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)

    # TODO(production): serve uploads via a proper static route or move files into the
    # WordPress media library. For now return a local filesystem path placeholder as `url`.
    stored_path = str(dest_path)
    sess.attachments.append(stored_path)
    sess.touch()

    payload = SubmitIdeaUploadResponse(filename=original_name, url=stored_path)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())
