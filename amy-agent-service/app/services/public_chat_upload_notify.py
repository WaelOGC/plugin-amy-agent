"""Relay public-chat upload alerts to WordPress (admin email + Telegram)."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.db import public_chat_uploads_db as uploads_db

logger = logging.getLogger("amy-agent-service.public_chat_upload_notify")

# Attach processed images when under this size (bytes each).
MAX_ATTACH_BYTES = 1_500_000


def maybe_notify_upload(
    *,
    visitor_id: str,
    conversation_id: str | None,
    upload: dict[str, Any],
    message_excerpt: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    base = (settings.wordpress_base_url or "").strip().rstrip("/")
    if not base:
        logger.info(
            "Public chat upload notify skipped — wordpress_base_url unset (file=%s)",
            upload.get("id"),
        )
        return {"email": "no_wordpress_url", "telegram": "no_wordpress_url"}

    filename = upload.get("original_filename") or "file"
    kind = upload.get("kind") or "image"
    excerpt = (message_excerpt or "").strip()[:500]
    conv_link = ""
    if conversation_id:
        # Admin deep link into Amy chat is not standardized; use Settings Overview hint.
        conv_link = (
            f"{base}/wp-admin/admin.php?page=amy-overview"
            f"&amy_conversation={conversation_id}"
        )

    subject = f"Amy chat upload: {filename}"
    body_lines = [
        "A visitor uploaded a file in the public Amy chat.",
        "",
        f"File: {filename}",
        f"Type: {kind}",
        f"Visitor id: {visitor_id}",
    ]
    if conversation_id:
        body_lines.append(f"Conversation id: {conversation_id}")
    if conv_link:
        body_lines.append(f"Conversation link: {conv_link}")
    if excerpt:
        body_lines.extend(["", "Visitor message:", excerpt])
    body = "\n".join(body_lines)

    telegram_html = (
        "<b>Amy chat upload</b>\n"
        f"File: <code>{_escape(filename)}</code>\n"
        f"Visitor: <code>{_escape(visitor_id[:12])}…</code>\n"
    )
    if conversation_id:
        telegram_html += f"Conversation: <code>{_escape(conversation_id[:12])}…</code>\n"
    if conv_link:
        telegram_html += f'<a href="{_escape(conv_link)}">Open admin</a>\n'
    if excerpt:
        telegram_html += f"\n{_escape(excerpt[:280])}"

    attachments: list[dict[str, str]] = []
    path = uploads_db.absolute_path(upload["stored_name"])
    if path.is_file() and path.stat().st_size <= MAX_ATTACH_BYTES:
        raw = path.read_bytes()
        attachments.append(
            {
                "filename": f"{upload['id']}.jpg",
                "content_type": upload.get("content_type") or "image/jpeg",
                "data_base64": base64.b64encode(raw).decode("ascii"),
            }
        )

    url = f"{base}/wp-json/amy-agent/v1/chat-upload-notify"
    payload = {
        "subject": subject,
        "body": body,
        "telegram_html": telegram_html,
        "attachments": attachments,
        "conversation_id": conversation_id,
        "visitor_id": visitor_id,
        "filename": filename,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Amy-Secret": settings.amy_shared_secret,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            response = client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "WP chat-upload-notify failed status=%s file=%s",
                response.status_code,
                upload.get("id"),
            )
            return {"email": "wp_error", "telegram": "wp_error"}
        data = response.json() if response.content else {}
        channels = data.get("channels") if isinstance(data, dict) else None
        if isinstance(channels, dict):
            return {
                "email": str(channels.get("email", "unknown")),
                "telegram": str(channels.get("telegram", "unknown")),
            }
        return {"email": "ok", "telegram": "ok"}
    except Exception:
        logger.exception(
            "WP chat-upload-notify relay failed file=%s", upload.get("id")
        )
        return {"email": "relay_error", "telegram": "relay_error"}


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
