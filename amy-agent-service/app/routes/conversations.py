"""Conversation memory CRUD, export, and attachment upload endpoints."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.auth import require_amy_secret
from app.config import get_settings
from app.db import conversations_db
from app.schemas.conversations import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    CreateConversationRequest,
    RenameConversationRequest,
)
from app.schemas.messages import AttachmentRef, ChatMessage, ChatMode, ErrorBody
from app.services.upload_rules import (
    ALLOWED_UPLOAD_CONTENT_TYPES,
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    SAFE_STORED_NAME_RE,
)

router = APIRouter(tags=["conversations"])

_SERVICE_ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_UPLOAD_ROOT = _SERVICE_ROOT / "uploads" / "conversations"


def public_conversation_upload_url(conversation_id: str, stored_name: str) -> str:
    """Absolute HTTP(S) URL for a conversation upload (served via StaticFiles)."""
    settings = get_settings()
    base = (settings.public_base_url or f"http://127.0.0.1:{settings.port}").rstrip("/")
    return f"{base}/uploads/conversations/{conversation_id}/{stored_name}"


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _to_summary(row: dict) -> ConversationSummary:
    return ConversationSummary(
        id=row["id"],
        wp_user_id=row["wp_user_id"],
        mode=row["mode"],
        title=row.get("title"),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_detail(row: dict, messages: list[dict]) -> ConversationDetail:
    return ConversationDetail(
        **_to_summary(row).model_dump(),
        messages=[
            ChatMessage(
                role=m["role"],
                content=m["content"],
                attachments=m.get("attachments") or [],
            )
            for m in messages
        ],
    )


def _check_access(
    conversation: dict,
    *,
    wp_user_id: int | None,
    is_full_admin: bool,
) -> JSONResponse | None:
    if is_full_admin:
        return None
    if wp_user_id is None or conversation["wp_user_id"] != wp_user_id:
        return _error(
            "forbidden",
            "You do not have access to this conversation.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


@router.post(
    "/v1/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_amy_secret)],
)
async def create_conversation(
    body: CreateConversationRequest,
) -> ConversationSummary:
    row = conversations_db.create_conversation(
        wp_user_id=body.wp_user_id,
        mode=body.mode,
        title=body.title,
    )
    return _to_summary(row)


@router.get(
    "/v1/conversations",
    response_model=ConversationListResponse,
    dependencies=[Depends(require_amy_secret)],
)
async def list_conversations(
    wp_user_id: int = Query(...),
    is_full_admin: bool = Query(False),
    mode: ChatMode | None = Query(None),
    include_archived: bool = Query(False),
) -> ConversationListResponse:
    rows = conversations_db.list_conversations(
        wp_user_id=wp_user_id,
        is_full_admin=is_full_admin,
        mode=mode,
        include_archived=include_archived,
    )
    return ConversationListResponse(conversations=[_to_summary(r) for r in rows])


@router.get(
    "/v1/conversations/{conversation_id}",
    response_model=ConversationDetail,
    dependencies=[Depends(require_amy_secret)],
)
async def get_conversation(
    conversation_id: str,
    wp_user_id: int = Query(...),
    is_full_admin: bool = Query(False),
) -> ConversationDetail | JSONResponse:
    row = conversations_db.get_conversation(conversation_id)
    if row is None:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    denied = _check_access(row, wp_user_id=wp_user_id, is_full_admin=is_full_admin)
    if denied is not None:
        return denied
    messages = conversations_db.get_messages(conversation_id)
    return _to_detail(row, messages)


@router.patch(
    "/v1/conversations/{conversation_id}",
    response_model=ConversationSummary,
    dependencies=[Depends(require_amy_secret)],
)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    wp_user_id: int = Query(...),
    is_full_admin: bool = Query(False),
) -> ConversationSummary | JSONResponse:
    row = conversations_db.get_conversation(conversation_id)
    if row is None:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    denied = _check_access(row, wp_user_id=wp_user_id, is_full_admin=is_full_admin)
    if denied is not None:
        return denied

    updated = conversations_db.rename_conversation(conversation_id, body.title)
    if not updated:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    refreshed = conversations_db.get_conversation(conversation_id)
    assert refreshed is not None
    return _to_summary(refreshed)


@router.delete(
    "/v1/conversations/{conversation_id}",
    response_model=None,
    dependencies=[Depends(require_amy_secret)],
)
async def delete_conversation(
    conversation_id: str,
    wp_user_id: int = Query(...),
    is_full_admin: bool = Query(False),
) -> Response:
    row = conversations_db.get_conversation(conversation_id)
    if row is None:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    denied = _check_access(row, wp_user_id=wp_user_id, is_full_admin=is_full_admin)
    if denied is not None:
        return denied

    deleted = conversations_db.delete_conversation(conversation_id)
    if not deleted:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/v1/conversations/{conversation_id}/export",
    response_model=None,
    dependencies=[Depends(require_amy_secret)],
)
async def export_conversation(
    conversation_id: str,
    wp_user_id: int = Query(...),
    is_full_admin: bool = Query(False),
) -> Response:
    row = conversations_db.get_conversation(conversation_id)
    if row is None:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    denied = _check_access(row, wp_user_id=wp_user_id, is_full_admin=is_full_admin)
    if denied is not None:
        return denied

    conversations_db.mark_exported(conversation_id)
    messages = conversations_db.get_messages(conversation_id)
    refreshed = conversations_db.get_conversation(conversation_id)
    assert refreshed is not None

    payload = {
        **refreshed,
        "messages": messages,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = f"conversation-{conversation_id}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/v1/conversations/{conversation_id}/upload",
    response_model=AttachmentRef,
    dependencies=[Depends(require_amy_secret)],
)
async def upload_conversation_attachment(
    conversation_id: str,
    file: UploadFile = File(...),
    wp_user_id: int = Form(...),
    is_full_admin: bool = Form(False),
) -> AttachmentRef | JSONResponse:
    row = conversations_db.get_conversation(conversation_id)
    if row is None:
        return _error(
            "conversation_not_found",
            "Conversation not found.",
            status.HTTP_404_NOT_FOUND,
        )
    denied = _check_access(row, wp_user_id=wp_user_id, is_full_admin=is_full_admin)
    if denied is not None:
        return denied

    if (
        not conversation_id
        or "/" in conversation_id
        or "\\" in conversation_id
        or ".." in conversation_id
    ):
        return _error(
            "invalid_conversation",
            "Invalid conversation_id.",
            status.HTTP_400_BAD_REQUEST,
        )

    original_name = (file.filename or "upload").strip() or "upload"
    ext = Path(original_name).suffix.lower()
    content_type = (file.content_type or "").lower() or None

    if ext not in ALLOWED_UPLOAD_EXTENSIONS and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        return _error(
            "invalid_file_type",
            "File type not allowed. Accepted: images (jpg, png, gif, webp), PDF, DOC, DOCX.",
            status.HTTP_400_BAD_REQUEST,
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return _error(
            "file_too_large",
            "File exceeds the 10 MB size limit.",
            status.HTTP_400_BAD_REQUEST,
        )
    if not data:
        return _error(
            "empty_file",
            "Uploaded file is empty.",
            status.HTTP_400_BAD_REQUEST,
        )

    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(original_name).stem)[:80] or "file"
    stored_name = f"{safe_stem}-{uuid.uuid4().hex[:8]}{ext or ''}"
    if not SAFE_STORED_NAME_RE.fullmatch(stored_name):
        return _error(
            "invalid_filename",
            "Could not derive a safe filename for this upload.",
            status.HTTP_400_BAD_REQUEST,
        )

    dest_dir = CONVERSATION_UPLOAD_ROOT / conversation_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)

    file_url = public_conversation_upload_url(conversation_id, stored_name)
    return AttachmentRef(
        url=file_url,
        filename=original_name,
        content_type=content_type,
    )
