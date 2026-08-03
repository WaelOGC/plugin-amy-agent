"""Smoke tests for /v1/health."""

import os

import pytest
from fastapi.testclient import TestClient

# Ensure a known secret before app settings are cached.
os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)


def test_health_requires_secret(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 401


def test_health_ok_with_secret(client: TestClient) -> None:
    response = client.get(
        "/v1/health",
        headers={"X-Amy-Secret": "test-secret-phase1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "version" in data


def test_config_validate_rejects_empty_key(client: TestClient) -> None:
    response = client.post(
        "/v1/config/validate",
        headers={"X-Amy-Secret": "test-secret-phase1"},
        json={"ai": {"provider": "gemini", "api_key": "", "model": None}},
    )
    assert response.status_code == 400


def test_chat_rejects_empty_api_key(client: TestClient) -> None:
    response = client.post(
        "/v1/chat",
        headers={"X-Amy-Secret": "test-secret-phase1"},
        json={
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "mode": "general",
            "messages": [{"role": "user", "content": "hello"}],
            "ai": {"provider": "openai", "api_key": "", "model": None},
            "context": {},
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_config"
