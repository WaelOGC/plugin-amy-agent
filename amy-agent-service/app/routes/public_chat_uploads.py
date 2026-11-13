"""Authenticated public-chat file upload + serve (never static-mounted)."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.auth import require_amy_secret
from app.db import conversations_db, public_chat_uploads_db as uploads_db
from app.schemas.messages import AttachmentRef, ErrorBody
from app.services.public_chat_upload import (
    MAX_FILE_BYTES,
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

_IP_RE = re.compile(r"^[0-9a-fA-F:.]+$")
_READ_CHUNK = 64 * 1024


def _error(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=ErrorBody(error=code, message=message).model_dump(),
    )


def _sanitize_client_ip(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not value or len(value) > 64:
        return None
    # Only accept a single IP token (plugin sends REMOTE_ADDR).
    if "," in value:
        value = value.split(",", 1)[0].strip()
    if not _IP_RE.match(value):
        return None
    return value


async def _read_upload_bounded(file: UploadFile, content_length: int | None) -> bytes:
    """Read upload body in chunks; abort as soon as MAX_FILE_BYTES+1 is exceeded."""
    if content_length is not None and content_length > MAX_FILE_BYTES:
        raise UploadRejected(
            "file_too_large",
            "Each file must be 5 MB or smaller.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await file.read(_READ_CHUNK)
        if not piece:
            break
        total += len(piece)
        if total > MAX_FILE_BYTES:
            raise UploadRejected(
                "file_too_large",
                "Each file must be 5 MB or smaller.",
            )
        chunks.append(piece)
    return b"".join(chunks)


@router.post(
    "/v1/public-chat/upload",
    response_model=AttachmentRef,
    dependencies=[Depends(require_amy_secret)],
)
async def upload_public_chat_file(
    request: Request,
    file: UploadFile = File(...),
    visitor_id: str = Form(...),
    conversation_id: str | None = Form(None),
    notify: bool = Form(True),
    message_excerpt: str | None = Form(None),
    allow_uploads: bool = Form(True),
    x_amy_client_ip: str | None = Header(default=None, alias="X-Amy-Client-Ip"),
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

    # Trusted only because the caller already authenticated with X-Amy-Secret
    # (WordPress plugin forwards the browser REMOTE_ADDR).
    client_ip = _sanitize_client_ip(x_amy_client_ip)

    raw_cl = request.headers.get("content-length")
    if raw_cl and raw_cl.isdigit():
        # Multipart overhead means Content-Length is larger than the file alone;
        # still reject clearly impossible bodies early.
        if int(raw_cl) > MAX_FILE_BYTES + (512 * 1024):
            return _error(
                "file_too_large",
                "Each file must be 5 MB or smaller.",
                status.HTTP_413_CONTENT_TOO_LARGE,
            )

    try:
        data = await _read_upload_bounded(file, None)
    except UploadRejected as exc:
        http = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if exc.code == "file_too_large"
            else status.HTTP_400_BAD_REQUEST
        )
        return _error(exc.code, exc.message, http)

    try:
        processed = process_public_chat_upload(
            data=data,
            original_filename=file.filename or "upload",
            visitor_id=vid,
            conversation_id=conv_id,
            claimed_content_type=file.content_type,
            client_ip=client_ip,
        )
    except UploadRejected as exc:
        http = status.HTTP_400_BAD_REQUEST
        if exc.code in ("rate_limited", "storage_full"):
            http = status.HTTP_429_TOO_MANY_REQUESTS
        elif exc.code == "file_too_large":
            http = status.HTTP_413_CONTENT_TOO_LARGE
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
