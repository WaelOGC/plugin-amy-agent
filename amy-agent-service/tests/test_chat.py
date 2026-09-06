"""Tests for POST /v1/chat with mocked providers."""

import os
from typing import Sequence
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AMY_SHARED_SECRET"] = "test-secret-phase1"

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.prompts import AMY_ADMIN_SYSTEM_PROMPT, AMY_SYSTEM_PROMPT  # noqa: E402
from app.providers.base import BaseProvider  # noqa: E402
from app.providers.errors import ProviderError  # noqa: E402
from app.routes.chat import _messages_with_system  # noqa: E402
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


def test_chat_with_conversation_persists_on_success(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(wp_user_id=5, mode="admin")
    conversations_db.append_message(conv["id"], "user", "earlier")
    conversations_db.append_message(conv["id"], "assistant", "prior reply")

    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with patch("app.routes.chat.get_provider", return_value=_CaptureProvider("New reply")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=5,
                is_full_admin=False,
                messages=[{"role": "user", "content": "newest"}],
            ),
        )

    assert response.status_code == 200
    assert response.json()["reply"]["content"] == "New reply"
    roles = [m.role for m in captured]
    assert roles[0] == "system"
    assert [m.content for m in captured if m.role != "system"] == [
        "earlier",
        "prior reply",
        "newest",
    ]
    stored = conversations_db.get_messages(conv["id"])
    assert [m["content"] for m in stored] == [
        "earlier",
        "prior reply",
        "newest",
        "New reply",
    ]


def test_chat_with_conversation_does_not_persist_on_provider_failure(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(wp_user_id=5, mode="admin")

    with patch("app.routes.chat.get_provider", return_value=_FailingProvider()):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=5,
                messages=[{"role": "user", "content": "should not stick"}],
            ),
        )

    assert response.status_code == 502
    assert conversations_db.get_messages(conv["id"]) == []


def test_chat_conversation_forbidden(client: TestClient, tmp_path, monkeypatch) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(wp_user_id=5, mode="admin")

    with patch("app.routes.chat.get_provider", return_value=_FakeProvider()):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=99,
                is_full_admin=False,
                messages=[{"role": "user", "content": "nope"}],
            ),
        )

    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


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


def test_general_mode_system_prompt_unchanged() -> None:
    messages = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="general",
    )
    assert messages[0].role == "system"
    assert messages[0].content == AMY_SYSTEM_PROMPT
    assert messages[0].content != AMY_ADMIN_SYSTEM_PROMPT


def test_support_mode_uses_public_prompt_not_admin() -> None:
    messages = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="support",
        wp_user_name="Should Be Ignored",
        wp_user_email="ignore@example.com",
    )
    assert messages[0].content == AMY_SYSTEM_PROMPT
    assert len([m for m in messages if m.role == "system"]) == 1


def test_admin_mode_uses_admin_prompt() -> None:
    messages = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="admin",
    )
    assert messages[0].role == "system"
    assert messages[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert messages[0].content != AMY_SYSTEM_PROMPT
    assert len([m for m in messages if m.role == "system"]) == 1


def test_admin_mode_appends_identity_when_name_or_email_present() -> None:
    messages = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="admin",
        wp_user_name="Wael",
        wp_user_email="wael@example.com",
    )
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 2
    assert system_msgs[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert "Wael" in system_msgs[1].content
    assert "wael@example.com" in system_msgs[1].content


def test_admin_mode_without_identity_has_no_extra_system_message() -> None:
    messages = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="admin",
        wp_user_name=None,
        wp_user_email=None,
    )
    assert [m.role for m in messages if m.role == "system"] == ["system"]
    assert messages[0].content == AMY_ADMIN_SYSTEM_PROMPT


def test_chat_admin_mode_sends_admin_prompt_to_provider(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                mode="admin",
                wp_user_name="Wael",
                wp_user_email="wael@example.com",
            ),
        )

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert system_msgs[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert "Wael" in system_msgs[1].content
    assert system_msgs[0].content != AMY_SYSTEM_PROMPT


def test_chat_general_mode_sends_public_prompt_to_provider(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")):
        response = client.post("/v1/chat", headers=HEADERS, json=_chat_body(mode="general"))

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert len(system_msgs) == 1
    assert system_msgs[0].content == AMY_SYSTEM_PROMPT
