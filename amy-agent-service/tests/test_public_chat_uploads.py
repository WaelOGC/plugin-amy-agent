"""Secure public-chat upload validation, serving, retention, and vision-once behavior."""

from __future__ import annotations

import io
import os
import time
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"
os.environ.setdefault("PUBLIC_BASE_URL", "https://amy-api.example.com")

from app.config import get_settings  # noqa: E402
from app.db import conversations_db  # noqa: E402
from app.db import public_chat_uploads_db as uploads_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.public_chat_upload import (  # noqa: E402
    MAX_FILE_BYTES,
    delete_expired_uploads,
    load_inline_media_for_uploads,
    process_public_chat_upload,
)

get_settings.cache_clear()

AUTH = {"X-Amy-Secret": "test-secret-phase1"}

def _valid_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color="red").save(buf, format="PNG")
    return buf.getvalue()


_PNG = _valid_png()


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    get_settings.cache_clear()
    conv_db_path = tmp_path / "conversations.db"
    upload_db_path = tmp_path / "public_chat_uploads.db"
    upload_root = tmp_path / "public-chat-files"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(conversations_db, "_DB_PATH", conv_db_path)
    monkeypatch.setattr(uploads_db, "_DB_PATH", upload_db_path)
    monkeypatch.setattr(uploads_db, "UPLOAD_ROOT", upload_root)
    return TestClient(app)


def _upload(
    client: TestClient,
    visitor_id: str,
    *,
    data: bytes,
    filename: str = "shot.png",
    content_type: str = "image/png",
    notify: bool = False,
):
    with patch("app.routes.public_chat_uploads.maybe_notify_upload"):
        return client.post(
            "/v1/public-chat/upload",
            headers=AUTH,
            data={
                "visitor_id": visitor_id,
                "notify": "true" if notify else "false",
            },
            files={"file": (filename, io.BytesIO(data), content_type)},
        )


def test_rejects_text_file_with_png_extension(client: TestClient) -> None:
    response = _upload(
        client,
        "visitor-1",
        data=b"not an image at all",
        filename="fake.png",
        content_type="image/png",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def test_rejects_png_bytes_with_claimed_jpeg_mismatch(client: TestClient) -> None:
    response = _upload(
        client,
        "visitor-1",
        data=_PNG,
        filename="shot.png",
        content_type="image/jpeg",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "content_mismatch"


def test_rejects_oversized_file(client: TestClient) -> None:
    oversized = b"x" * (MAX_FILE_BYTES + 1)
    response = _upload(
        client,
        "visitor-1",
        data=oversized,
        filename="big.bin",
        content_type="application/octet-stream",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "file_too_large"


def test_rejects_svg(client: TestClient) -> None:
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
    response = _upload(
        client,
        "visitor-1",
        data=svg,
        filename="icon.svg",
        content_type="image/svg+xml",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def test_rejects_gif(client: TestClient) -> None:
    gif = b"GIF89a" + b"\x00" * 64
    response = _upload(
        client,
        "visitor-1",
        data=gif,
        filename="anim.gif",
        content_type="image/gif",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def _pdf_with_page_count(n: int) -> bytes:
    doc = pymupdf.open()
    try:
        for _ in range(n):
            doc.new_page(width=72, height=72)
        return doc.tobytes()
    finally:
        doc.close()


def test_rejects_pdf_with_too_many_pages(client: TestClient) -> None:
    pdf = _pdf_with_page_count(11)
    response = _upload(
        client,
        "visitor-1",
        data=pdf,
        filename="long.pdf",
        content_type="application/pdf",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "pdf_too_many_pages"


def test_rate_limit_eleventh_upload_in_hour_returns_429(client: TestClient) -> None:
    visitor = "rate-visitor"
    for i in range(10):
        resp = _upload(
            client,
            visitor,
            data=_PNG,
            filename=f"shot-{i}.png",
        )
        assert resp.status_code == 200, resp.text

    blocked = _upload(client, visitor, data=_PNG, filename="shot-11.png")
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"


def test_other_visitor_cannot_fetch_file(client: TestClient) -> None:
    owner = "owner-visitor"
    uploaded = _upload(client, owner, data=_PNG)
    assert uploaded.status_code == 200
    file_id = uploaded.json()["id"]

    denied = client.get(
        f"/v1/public-chat/files/{file_id}",
        headers=AUTH,
        params={"visitor_id": "someone-else"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"] == "forbidden"


def test_owner_can_fetch_with_nosniff_and_image_content_type(client: TestClient) -> None:
    owner = "owner-visitor"
    uploaded = _upload(client, owner, data=_PNG)
    assert uploaded.status_code == 200
    file_id = uploaded.json()["id"]

    served = client.get(
        f"/v1/public-chat/files/{file_id}",
        headers=AUTH,
        params={"visitor_id": owner},
    )
    assert served.status_code == 200
    assert served.headers.get("x-content-type-options") == "nosniff"
    assert served.headers.get("content-type", "").startswith("image/")
    assert len(served.content) > 0


def test_delete_expired_uploads_removes_old_files(client: TestClient) -> None:
    visitor = "expire-visitor"
    uploaded = _upload(client, visitor, data=_PNG)
    assert uploaded.status_code == 200
    file_id = uploaded.json()["id"]
    row = uploads_db.get_upload(file_id)
    assert row is not None
    stored = row["stored_name"]
    path = uploads_db.absolute_path(stored)
    assert path.is_file()

    old_ts = time.time() - (8 * 86400)
    conn = uploads_db._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE public_chat_uploads SET created_at = ? WHERE id = ?",
                (old_ts, file_id),
            )
    finally:
        conn.close()

    result = delete_expired_uploads(days=uploads_db.RETENTION_DAYS)
    assert result["expired_rows"] >= 1
    assert not path.is_file()

    refreshed = uploads_db.get_upload(file_id)
    assert refreshed is not None
    assert refreshed["deleted_at"] is not None

    expired_get = client.get(
        f"/v1/public-chat/files/{file_id}",
        headers=AUTH,
        params={"visitor_id": visitor},
    )
    assert expired_get.status_code == 404
    assert expired_get.json()["error"] == "file_expired"


def test_vision_inline_media_sent_only_once(client: TestClient, tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "vision-once"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(uploads_db, "UPLOAD_ROOT", upload_root)
    db_path = tmp_path / "vision-uploads.db"
    monkeypatch.setattr(uploads_db, "_DB_PATH", db_path)

    processed = process_public_chat_upload(
        data=_PNG,
        original_filename="once.png",
        visitor_id="vision-visitor",
        claimed_content_type="image/png",
    )
    row = uploads_db.get_upload(processed.row["id"])
    assert row is not None

    first = load_inline_media_for_uploads([row])
    assert len(first) == 1
    assert first[0]["mime_type"] == "image/png"
    assert first[0]["upload_id"] == row["id"]

    uploads_db.mark_vision_sent([row["id"]])
    row_after = uploads_db.get_upload(row["id"])
    assert row_after is not None
    assert row_after["vision_sent"] is True

    second = load_inline_media_for_uploads([row_after])
    assert second == []


def test_list_visitor_public_conversations_excludes_empty_and_includes_preview(
    client: TestClient,
) -> None:
    visitor = "preview-visitor"
    empty = conversations_db.create_conversation(
        wp_user_id=0, mode="general", visitor_id=visitor
    )
    with_user = conversations_db.create_conversation(
        wp_user_id=0, mode="general", visitor_id=visitor
    )
    conversations_db.append_message(
        with_user["id"], "user", "Hello Amy, I need pricing details please"
    )
    conversations_db.append_message(
        with_user["id"], "assistant", "Happy to help with pricing."
    )

    listed = client.get(
        "/v1/conversations/by-visitor",
        headers=AUTH,
        params={"visitor_id": visitor, "limit": 20},
    )
    assert listed.status_code == 200
    api_rows = listed.json()["conversations"]
    api_ids = {r["id"] for r in api_rows}
    assert empty["id"] not in api_ids
    assert with_user["id"] in api_ids

    rows = conversations_db.list_visitor_public_conversations(visitor, limit=20)
    db_ids = {r["id"] for r in rows}
    assert empty["id"] not in db_ids
    assert with_user["id"] in db_ids
    match = next(r for r in rows if r["id"] == with_user["id"])
    preview = match.get("last_message_preview") or ""
    assert "happy" in preview.lower() or "pricing" in preview.lower()
