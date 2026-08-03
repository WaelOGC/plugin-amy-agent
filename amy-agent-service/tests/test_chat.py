"""Tests for POST /v1/chat with mocked providers."""

import os
from typing import Sequence
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.base import BaseProvider  # noqa: E402
from app.providers.errors import ProviderError  # noqa: E402
from app.schemas.messages import ChatMessage  # noqa: E402

get_settings.cache_clear()

HEADERS = {"X-Amy-Secret": "test-secret-phase1"}


class _FakeProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self, reply: str = "Hello from Amy") -> None:
        self._reply = reply

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        assert api_key
        assert messages
        return self._reply


class _FailingProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        raise ProviderError("auth failed", code="auth_error")


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)


def _chat_body(**overrides):
    body = {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "mode": "general",
        "messages": [{"role": "user", "content": "hello"}],
        "ai": {"provider": "openai", "api_key": "sk-test", "model": None},
        "context": {},
    }
    body.update(overrides)
    return body


def test_chat_success_shape(client: TestClient) -> None:
    with patch("app.routes.chat.get_provider", return_value=_FakeProvider("Hi there")):
        response = client.post("/v1/chat", headers=HEADERS, json=_chat_body())

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert data["reply"] == {"role": "assistant", "content": "Hi there"}
    assert data["actions"] == []
    assert data["meta"]["provider"] == "openai"
    assert data["meta"]["model"] == "gpt-4o-mini"


def test_chat_provider_failure_returns_502(client: TestClient) -> None:
    with patch("app.routes.chat.get_provider", return_value=_FailingProvider()):
        response = client.post("/v1/chat", headers=HEADERS, json=_chat_body())

    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "auth_error"
    assert "API key" not in data["message"]
    assert "sk-test" not in data["message"]


def test_chat_rejects_empty_key_cleanly(client: TestClient) -> None:
    response = client.post(
        "/v1/chat",
        headers=HEADERS,
        json=_chat_body(ai={"provider": "openai", "api_key": "", "model": None}),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_config"
