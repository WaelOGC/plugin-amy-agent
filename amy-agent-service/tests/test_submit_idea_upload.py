"""Submit Idea upload returns a public HTTP URL and serves the file."""

from __future__ import annotations

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"
os.environ["PUBLIC_BASE_URL"] = "https://amy-api.example.com"
os.environ["PORT"] = "8765"

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import submit_idea_state as state  # noqa: E402

get_settings.cache_clear()

HEADERS = {"X-Amy-Secret": "test-secret-phase1"}


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)


def _start_session(client: TestClient) -> str:
    session_id = str(uuid.uuid4())
    response = client.post(
        "/v1/submit-idea/start",
        headers=HEADERS,
        json={"session_id": session_id, "service_slug": "software-app"},
    )
    assert response.status_code == 200
    return session_id


def test_upload_returns_public_https_url_and_file_is_served(client: TestClient) -> None:
    session_id = _start_session(client)
    pdf_bytes = b"%PDF-1.4 test upload content"

    response = client.post(
        "/v1/submit-idea/upload",
        headers=HEADERS,
        data={"session_id": session_id},
        files={"file": ("brief.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "brief.pdf"
    url = body["url"]
    assert url.startswith("https://amy-api.example.com/uploads/submit-idea/")
    assert session_id in url
    assert url.endswith(".pdf")
    assert not url.startswith("/") or url.startswith("https://")
    # Must not be a raw filesystem path.
    assert ":\\" not in url
    assert "/app/uploads/" not in url

    # Public GET (no secret) returns the file bytes.
    path = url.replace("https://amy-api.example.com", "")
    get_resp = client.get(path)
    assert get_resp.status_code == 200
    assert get_resp.content == pdf_bytes

    sess = state.require_session(session_id)
    assert url in sess.attachments


def test_upload_rejects_disallowed_type(client: TestClient) -> None:
    session_id = _start_session(client)
    response = client.post(
        "/v1/submit-idea/upload",
        headers=HEADERS,
        data={"session_id": session_id},
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_file_type"


def test_upload_image_served(client: TestClient) -> None:
    session_id = _start_session(client)
    # Minimal 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = client.post(
        "/v1/submit-idea/upload",
        headers=HEADERS,
        data={"session_id": session_id},
        files={"file": ("shot.png", io.BytesIO(png), "image/png")},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith("https://amy-api.example.com/uploads/submit-idea/")
    path = url.replace("https://amy-api.example.com", "")
    get_resp = client.get(path)
    assert get_resp.status_code == 200
    assert get_resp.content == png
