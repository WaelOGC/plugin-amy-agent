"""Authenticated public-chat file upload + serve (never static-mounted)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.auth import require_amy_secret
from app.db import conversations_db, public_chat_uploads_db as uploads_db
from app.schemas.messages import AttachmentRef, ErrorBody
from app.services.public_chat_upload import (
    MAX_FILES_PER_MESSAGE,
    UploadRejected,
    attachment_ref_for_row,
    process_public_chat_upload,
)
from app.services.public_chat_upload_notify import maybe_notify_upload

logger = logging.getLogger("amy-agent-service.public_chat_uploads")

router = APIRouter(tags=["public-chat-uploads"])

# WP proxies file GETs under this path; stored attachment URLs use the same shape.
PROXY_FILE_BASE = "/wp-json/amy-agent/v1/chat/files"


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


@router.post(
    "/v1/public-chat/upload",
    response_model=AttachmentRef,
    dependencies=[Depends(require_amy_secret)],
)
async def upload_public_chat_file(
    file: UploadFile = File(...),
    visitor_id: str = Form(...),
    conversation_id: str | None = Form(None),
    notify: bool = Form(True),
    message_excerpt: str | None = Form(None),
    allow_uploads: bool = Form(True),
) -> AttachmentRef | JSONResponse:
    if not allow_uploads:
        return _error(
            "uploads_disabled",
            "File uploads are turned off for public chat.",
            status.HTTP_403_FORBIDDEN,
        )

    vid = (visitor_id or "").strip()
    if not vid:
        return _error(
            "invalid_request",
            "A valid visitor id is required.",
            status.HTTP_400_BAD_REQUEST,
        )

    conv_id = (conversation_id or "").strip() or None
    if conv_id:
        row = conversations_db.get_conversation(conv_id)
        if row is None:
            return _error(
                "conversation_not_found",
                "Conversation not found.",
                status.HTTP_404_NOT_FOUND,
            )
        if not conversations_db.can_access_conversation(
            row,
            wp_user_id=0,
            is_full_admin=False,
            visitor_id=vid,
        ):
            return _error(
                "forbidden",
                "You do not have access to this conversation.",
                status.HTTP_403_FORBIDDEN,
            )

    data = await file.read()
    try:
        processed = process_public_chat_upload(
            data=data,
            original_filename=file.filename or "upload",
            visitor_id=vid,
            conversation_id=conv_id,
            claimed_content_type=file.content_type,
        )
    except UploadRejected as exc:
        http = status.HTTP_400_BAD_REQUEST
        if exc.code in ("rate_limited", "storage_full"):
            http = status.HTTP_429_TOO_MANY_REQUESTS
        return _error(exc.code, exc.message, http)

    ref = attachment_ref_for_row(processed.row, proxy_base=PROXY_FILE_BASE)
    if notify:
        try:
            maybe_notify_upload(
                visitor_id=vid,
                conversation_id=conv_id or processed.row.get("conversation_id"),
                upload=processed.row,
                message_excerpt=message_excerpt,
            )
        except Exception:
            logger.exception("Upload notify failed for %s", processed.row.get("id"))

    return AttachmentRef.model_validate(ref)


@router.get(
    "/v1/public-chat/files/{file_id}",
    dependencies=[Depends(require_amy_secret)],
)
async def serve_public_chat_file(
    file_id: str,
    visitor_id: str | None = Query(None),
    wp_user_id: int = Query(0),
    is_full_admin: bool = Query(False),
) -> Response:
    row = uploads_db.get_upload(file_id)
    if row is None or row.get("deleted_at") is not None:
        return _error(
            "file_expired",
            "File expired",
            status.HTTP_404_NOT_FOUND,
        )

    allowed = False
    if is_full_admin:
        allowed = True
    elif visitor_id and visitor_id.strip() == row["visitor_id"]:
        allowed = True
    elif wp_user_id and int(wp_user_id) > 0 and is_full_admin:
        allowed = True

    if not allowed:
        return _error(
            "forbidden",
            "You do not have access to this file.",
            status.HTTP_403_FORBIDDEN,
        )

    path = uploads_db.absolute_path(row["stored_name"])
    if not path.is_file():
        return _error(
            "file_expired",
            "File expired",
            status.HTTP_404_NOT_FOUND,
        )

    # Always serve the processed image bytes with a fixed safe type.
    mime = row.get("content_type") or "image/jpeg"
    if not str(mime).startswith("image/"):
        mime = "image/jpeg"
    data = path.read_bytes()
    return Response(
        content=data,
        media_type=mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{row["id"]}.bin"',
        },
    )


# Re-export for chat helpers / docs.
__all__ = ["router", "PROXY_FILE_BASE", "MAX_FILES_PER_MESSAGE"]
