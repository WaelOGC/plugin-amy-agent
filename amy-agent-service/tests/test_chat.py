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
from app.routes.chat import (  # noqa: E402
    PRICING_CATALOGUE_PROMPT_HEADER,
    _messages_with_system,
    _public_system_content,
)
from app.schemas.messages import (  # noqa: E402
    ChatMessage,
    ChatRequest,
    PRICING_CATALOGUE_MAX_CHARS,
    sanitize_pricing_catalogue,
)
from app.services.analytics_summary import (  # noqa: E402
    format_analytics_chat_context,
)
from app.services.seo_task_summary import (  # noqa: E402
    format_seo_chat_context,
    format_task_service_chat_context,
)

get_settings.cache_clear()

HEADERS = {"X-Amy-Secret": "test-secret-phase1"}

_EMPTY_ANALYTICS_SNAP = {
    "ok": True,
    "total": 0,
    "counts": {"hot": 0, "warm": 0, "cold": 0, "other": 0},
    "with_email": 0,
    "email_captures": {"total": 0, "last_7d": 0},
    "last_seen": {
        "last_24h": 0,
        "last_7d": 0,
        "most_recent_at": None,
        "most_recent": None,
    },
    "hot_sample": [],
    "hot_sample_count": 0,
    "empty": True,
    "summary": "Analytics summary: 0 lead sessions (hot=0, warm=0, cold=0; with_email=0).",
}

_LIVE_ANALYTICS_SNAP = {
    "ok": True,
    "total": 5,
    "counts": {"hot": 2, "warm": 1, "cold": 2, "other": 0},
    "with_email": 3,
    "email_captures": {"total": 3, "last_7d": 1},
    "last_seen": {
        "last_24h": 2,
        "last_7d": 4,
        "most_recent_at": 1_700_000_000.0,
        "most_recent": "2h ago",
    },
    "hot_sample": [
        {
            "session_id": "hot-1",
            "session_id_short": "hot1",
            "lead_status": "hot",
            "has_email": True,
            "lead_email": "hot@example.com",
            "last_seen": "2h ago",
            "ip_city": "The Hague",
            "ip_country": "NL",
        }
    ],
    "hot_sample_count": 1,
    "empty": False,
    "summary": (
        "Analytics summary: 5 lead sessions "
        "(hot=2, warm=1, cold=2; with_email=3)."
    ),
}

_ERROR_ANALYTICS_SNAP = {
    "ok": False,
    "error": "boom",
    "summary": "Analytics unavailable: could not read visitor lead sessions (service/connection).",
    "total": 0,
    "counts": {"hot": 0, "warm": 0, "cold": 0, "other": 0},
    "with_email": 0,
    "email_captures": {"total": 0, "last_7d": 0},
    "last_seen": {
        "last_24h": 0,
        "last_7d": 0,
        "most_recent_at": None,
        "most_recent": None,
    },
    "empty": True,
}

_EMPTY_SEO_SNAP = {
    "ok": True,
    "total": 0,
    "verdicts": {},
    "statuses": {},
    "open_count": 0,
    "fixed_count": 0,
    "rejected_count": 0,
    "empty": True,
    "summary": "SEO review summary: 0 stored checks (open/pending_approval=0, fixed/approved=0, rejected=0; verdicts={'none': 0}; statuses={'none': 0}).",
}

_LIVE_SEO_SNAP = {
    "ok": True,
    "total": 4,
    "verdicts": {"red": 1, "orange": 1, "green": 2},
    "statuses": {"pending_approval": 2, "approved": 1, "rejected": 1},
    "open_count": 2,
    "fixed_count": 1,
    "rejected_count": 1,
    "empty": False,
    "summary": (
        "SEO review summary: 4 stored checks "
        "(open/pending_approval=2, fixed/approved=1, rejected=1; "
        "verdicts={'red': 1, 'orange': 1, 'green': 2}; "
        "statuses={'pending_approval': 2, 'approved': 1, 'rejected': 1})."
    ),
}

_ERROR_SEO_SNAP = {
    "ok": False,
    "error": "boom",
    "summary": "SEO Tasks unavailable: could not read stored SEO checks (service/connection).",
    "total": 0,
    "verdicts": {},
    "statuses": {},
    "open_count": 0,
    "fixed_count": 0,
    "rejected_count": 0,
    "empty": True,
}

_EMPTY_TASK_SNAP = {
    "ok": True,
    "open_tasks": 0,
    "urgent_tasks": 0,
    "in_progress": 0,
    "running": 0,
    "completed_this_week": 0,
    "team_completion_rate": 0,
    "empty": True,
    "summary": "Task Service summary: open=0, urgent=0, in_progress=0, running=0, completed_this_week=0, team_completion_rate=0%.",
}

_LIVE_TASK_SNAP = {
    "ok": True,
    "open_tasks": 7,
    "urgent_tasks": 2,
    "in_progress": 3,
    "running": 1,
    "completed_this_week": 4,
    "team_completion_rate": 55,
    "empty": False,
    "summary": (
        "Task Service summary: open=7, urgent=2, in_progress=3, running=1, "
        "completed_this_week=4, team_completion_rate=55%."
    ),
}

_ERROR_TASK_SNAP = {
    "ok": False,
    "error": "boom",
    "summary": "Task Service unavailable: could not read task board stats (service/connection).",
    "open_tasks": 0,
    "urgent_tasks": 0,
    "in_progress": 0,
    "running": 0,
    "completed_this_week": 0,
    "team_completion_rate": 0,
    "empty": True,
}


class _FakeProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"
    supports_tools = False

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
    supports_tools = False

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
    assert data["meta"]["tools_used"] == []


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


def test_chat_conversation_full_admin_bypass(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(wp_user_id=5, mode="admin")

    with patch("app.routes.chat.get_provider", return_value=_FakeProvider("ok")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=99,
                is_full_admin=True,
                messages=[{"role": "user", "content": "admin peek"}],
            ),
        )

    assert response.status_code == 200
    assert response.json()["reply"]["content"] == "ok"


def test_chat_visitor_conversation_allows_matching_visitor(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(
        wp_user_id=0, mode="general", visitor_id="abc123"
    )

    with patch("app.routes.chat.get_provider", return_value=_FakeProvider("visitor hi")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=0,
                is_full_admin=False,
                visitor_id="abc123",
                messages=[{"role": "user", "content": "hello visitor"}],
            ),
        )

    assert response.status_code == 200
    assert response.json()["reply"]["content"] == "visitor hi"
    stored = conversations_db.get_messages(conv["id"])
    assert [m["content"] for m in stored] == ["hello visitor", "visitor hi"]


def test_chat_visitor_conversation_rejects_mismatched_visitor(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.db import conversations_db

    get_settings.cache_clear()
    monkeypatch.setattr(conversations_db, "_DB_PATH", tmp_path / "conversations.db")
    conv = conversations_db.create_conversation(
        wp_user_id=0, mode="general", visitor_id="abc123"
    )

    with patch("app.routes.chat.get_provider", return_value=_FakeProvider()):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                conversation_id=conv["id"],
                wp_user_id=0,
                is_full_admin=False,
                visitor_id="other-visitor",
                messages=[{"role": "user", "content": "nope"}],
            ),
        )

    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"
    assert conversations_db.get_messages(conv["id"]) == []


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
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="general",
    )
    assert tools_used == []
    assert messages[0].role == "system"
    assert messages[0].content == AMY_SYSTEM_PROMPT
    assert messages[0].content != AMY_ADMIN_SYSTEM_PROMPT


def test_general_mode_appends_pricing_catalogue_when_present() -> None:
    catalogue = "Custom WordPress Development\nStarter Website — €549, one-off"
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="How much is a starter site?")],
        mode="general",
        pricing_catalogue=catalogue,
    )
    assert tools_used == []
    assert messages[0].role == "system"
    assert messages[0].content.startswith(AMY_SYSTEM_PROMPT)
    assert messages[0].content != AMY_SYSTEM_PROMPT
    assert PRICING_CATALOGUE_PROMPT_HEADER in messages[0].content
    assert "Starter Website — €549, one-off" in messages[0].content
    assert "Current public price list" in messages[0].content


def test_general_mode_without_catalogue_keeps_base_prompt() -> None:
    assert _public_system_content(None) == AMY_SYSTEM_PROMPT
    assert _public_system_content("") == AMY_SYSTEM_PROMPT
    assert _public_system_content("   ") == AMY_SYSTEM_PROMPT
    messages, _, _seed = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="general",
        pricing_catalogue="",
    )
    assert messages[0].content == AMY_SYSTEM_PROMPT


def test_pricing_catalogue_over_long_input_is_capped() -> None:
    huge = "A" * (PRICING_CATALOGUE_MAX_CHARS + 500)
    cleaned = sanitize_pricing_catalogue(huge)
    assert len(cleaned) == PRICING_CATALOGUE_MAX_CHARS
    # Control characters stripped; newlines preserved.
    dirty = "Line1\n\x00Line2\x07\tOK"
    assert sanitize_pricing_catalogue(dirty) == "Line1\nLine2\tOK"
    req = ChatRequest(
        session_id="550e8400-e29b-41d4-a716-446655440000",
        messages=[ChatMessage(role="user", content="hi")],
        ai={"provider": "openai", "api_key": "sk-test", "model": None},
        pricing_catalogue=huge,
    )
    assert req.pricing_catalogue is not None
    assert len(req.pricing_catalogue) == PRICING_CATALOGUE_MAX_CHARS


def test_admin_mode_never_receives_pricing_catalogue() -> None:
    catalogue = "Custom WordPress Development\nStarter Website — €549, one-off"
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="What are our WP prices?")],
        mode="admin",
        pricing_catalogue=catalogue,
    )
    assert tools_used == []
    joined = "\n".join(m.content for m in messages if m.role == "system")
    assert AMY_ADMIN_SYSTEM_PROMPT in joined
    assert PRICING_CATALOGUE_PROMPT_HEADER not in joined
    assert "€549" not in joined
    assert "Current public price list" not in joined


def test_support_mode_uses_public_prompt_not_admin() -> None:
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="support",
        wp_user_name="Should Be Ignored",
        wp_user_email="ignore@example.com",
    )
    assert tools_used == []
    assert messages[0].content == AMY_SYSTEM_PROMPT
    assert len([m for m in messages if m.role == "system"]) == 1


def test_admin_mode_uses_admin_prompt_without_always_on_snapshots() -> None:
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="admin",
    )
    assert messages[0].role == "system"
    assert messages[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert messages[0].content != AMY_SYSTEM_PROMPT
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 1
    assert tools_used == []
    assert "you have no live access" not in AMY_ADMIN_SYSTEM_PROMPT.lower()
    assert "connections are not built yet" not in AMY_ADMIN_SYSTEM_PROMPT.lower()
    assert "seo tasks, task service board stats, and live web search are not wired" not in AMY_ADMIN_SYSTEM_PROMPT.lower()
    assert "analytics_summary" in AMY_ADMIN_SYSTEM_PROMPT
    assert "analytics_traffic" in AMY_ADMIN_SYSTEM_PROMPT
    assert "email_audience_summary" in AMY_ADMIN_SYSTEM_PROMPT
    assert "seo_summary" in AMY_ADMIN_SYSTEM_PROMPT
    assert "task_stats" in AMY_ADMIN_SYSTEM_PROMPT
    assert "email marketing audience depth are not wired" not in AMY_ADMIN_SYSTEM_PROMPT.lower()
    assert "Approve → Send" in AMY_ADMIN_SYSTEM_PROMPT


def test_admin_mode_appends_identity_when_name_or_email_present() -> None:
    messages, tools_used, _seed = _messages_with_system(
        [ChatMessage(role="user", content="hello")],
        mode="admin",
        wp_user_name="Wael",
        wp_user_email="wael@example.com",
    )
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 2
    assert tools_used == []
    assert system_msgs[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert "Wael" in system_msgs[1].content
    assert "wael@example.com" in system_msgs[1].content


def test_admin_mode_intent_auto_invokes_multi_tools() -> None:
    with (
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=_LIVE_ANALYTICS_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_LIVE_SEO_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            return_value=_LIVE_TASK_SNAP,
        ),
    ):
        messages, tools_used, _seed = _messages_with_system(
            [
                ChatMessage(
                    role="user",
                    content="How many visitors and any urgent tasks? Also SEO open count?",
                )
            ],
            mode="admin",
        )
    assert tools_used == ["analytics_summary", "seo_summary", "task_stats"]
    joined = "\n".join(m.content for m in messages if m.role == "system")
    assert "total_sessions: 5" in joined
    assert "urgent_tasks: 2" in joined
    assert "open (pending_approval): 2" in joined


def test_admin_mode_can_force_legacy_snapshots() -> None:
    with (
        patch(
            "app.routes.chat.analytics_summary_for_chat",
            return_value=_EMPTY_ANALYTICS_SNAP,
        ),
        patch(
            "app.routes.chat.seo_review_summary_for_chat",
            return_value=_EMPTY_SEO_SNAP,
        ),
        patch(
            "app.routes.chat.task_service_summary_for_chat",
            return_value=_EMPTY_TASK_SNAP,
        ),
    ):
        messages, tools_used, _seed = _messages_with_system(
            [ChatMessage(role="user", content="hello")],
            mode="admin",
            include_analytics_snapshot=True,
            include_seo_task_snapshots=True,
            auto_invoke_tools=False,
        )
    system_msgs = [m for m in messages if m.role == "system"]
    assert tools_used == []
    assert len(system_msgs) == 4
    assert "Live Amy Analytics snapshot" in system_msgs[1].content
    assert "Live SEO Tasks snapshot" in system_msgs[2].content
    assert "Live Task Service snapshot" in system_msgs[3].content


def test_admin_mode_can_skip_forced_seo_task_snapshots() -> None:
    with patch(
        "app.routes.chat.analytics_summary_for_chat",
        return_value=_EMPTY_ANALYTICS_SNAP,
    ):
        messages, _tools, _seed = _messages_with_system(
            [ChatMessage(role="user", content="hello")],
            mode="admin",
            include_analytics_snapshot=True,
            include_seo_task_snapshots=False,
            auto_invoke_tools=False,
        )
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 2
    assert system_msgs[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert "Live Amy Analytics snapshot" in system_msgs[1].content


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
                messages=[{"role": "user", "content": "hello"}],
            ),
        )

    assert response.status_code == 200
    assert response.json()["meta"]["tools_used"] == []
    system_msgs = [m for m in captured if m.role == "system"]
    assert system_msgs[0].content == AMY_ADMIN_SYSTEM_PROMPT
    assert any("Wael" in m.content for m in system_msgs)
    assert system_msgs[0].content != AMY_SYSTEM_PROMPT
    assert "you have no live access" not in system_msgs[0].content.lower()
    assert "connections are not built yet" not in system_msgs[0].content.lower()
    assert "analytics_summary" in system_msgs[0].content


def test_chat_admin_mode_intent_injects_live_tool_context(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with (
        patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")),
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=_LIVE_ANALYTICS_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_LIVE_SEO_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            return_value=_LIVE_TASK_SNAP,
        ),
    ):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                mode="admin",
                messages=[
                    {
                        "role": "user",
                        "content": "How many visitors and any urgent tasks? SEO open?",
                    }
                ],
            ),
        )

    assert response.status_code == 200
    data = response.json()
    assert "analytics_summary" in data["meta"]["tools_used"]
    assert "task_stats" in data["meta"]["tools_used"]
    assert "seo_summary" in data["meta"]["tools_used"]
    joined = "\n".join(m.content for m in captured if m.role == "system")
    assert "total_sessions: 5" in joined
    assert "urgent_tasks: 2" in joined
    assert "open (pending_approval): 2" in joined


def test_chat_admin_mode_empty_analytics_honest_fallback(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with (
        patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")),
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=_EMPTY_ANALYTICS_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_EMPTY_SEO_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            return_value=_EMPTY_TASK_SNAP,
        ),
    ):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                mode="admin",
                messages=[
                    {
                        "role": "user",
                        "content": "How many visitors, SEO open count, any urgent tasks?",
                    }
                ],
            ),
        )

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert any("EMPTY" in m.content for m in system_msgs)
    assert any("No visitor sessions recorded yet" in m.content for m in system_msgs)
    assert any("No SEO checks stored yet" in m.content for m in system_msgs)
    assert any("No tasks on the board yet" in m.content for m in system_msgs)
    joined = "\n".join(m.content.lower() for m in system_msgs)
    assert "you have no live access" not in joined
    assert "connections are not built yet" not in joined
    assert "cannot pull that yet" not in joined or "email marketing" in joined


def test_chat_admin_mode_analytics_error_honest_fallback(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with (
        patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")),
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            return_value=_ERROR_ANALYTICS_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            return_value=_ERROR_SEO_SNAP,
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            return_value=_ERROR_TASK_SNAP,
        ),
    ):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                mode="admin",
                messages=[
                    {
                        "role": "user",
                        "content": "visitor traffic, SEO issues, urgent tasks?",
                    }
                ],
            ),
        )

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert any("UNAVAILABLE" in m.content and "Analytics" in m.content for m in system_msgs)
    assert any("could not reach Analytics" in m.content for m in system_msgs)
    assert any("could not reach SEO Tasks" in m.content for m in system_msgs)
    assert any("could not reach Task Service" in m.content for m in system_msgs)
    joined = "\n".join(m.content.lower() for m in system_msgs)
    assert "you have no live access" not in joined
    assert "connections are not built yet" not in joined


def test_chat_general_mode_sends_public_prompt_to_provider(client: TestClient) -> None:
    captured: list = []

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with (
        patch("app.routes.chat.get_provider", return_value=_CaptureProvider("Hi")),
        patch(
            "app.services.admin_chat_tools.analytics_summary_for_chat",
            side_effect=AssertionError("general mode must not fetch analytics"),
        ),
        patch(
            "app.services.admin_chat_tools.seo_review_summary_for_chat",
            side_effect=AssertionError("general mode must not fetch SEO"),
        ),
        patch(
            "app.services.admin_chat_tools.task_service_summary_for_chat",
            side_effect=AssertionError("general mode must not fetch tasks"),
        ),
    ):
        response = client.post("/v1/chat", headers=HEADERS, json=_chat_body(mode="general"))

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert len(system_msgs) == 1
    assert system_msgs[0].content == AMY_SYSTEM_PROMPT
    assert "Live Amy Analytics snapshot" not in system_msgs[0].content
    assert "Live SEO Tasks snapshot" not in system_msgs[0].content
    assert "Live Task Service snapshot" not in system_msgs[0].content


def test_chat_general_mode_includes_pricing_catalogue_in_system(
    client: TestClient,
) -> None:
    captured: list = []
    catalogue = "UI/UX Design\nUI Starter — €350, one-off"

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with patch("app.routes.chat.get_provider", return_value=_CaptureProvider("€350")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(mode="general", pricing_catalogue=catalogue),
        )

    assert response.status_code == 200
    system_msgs = [m for m in captured if m.role == "system"]
    assert len(system_msgs) == 1
    assert PRICING_CATALOGUE_PROMPT_HEADER in system_msgs[0].content
    assert "UI Starter — €350, one-off" in system_msgs[0].content


def test_chat_admin_mode_ignores_pricing_catalogue_field(client: TestClient) -> None:
    captured: list = []
    catalogue = "Custom WordPress Development\nStarter Website — €549, one-off"

    class _CaptureProvider(_FakeProvider):
        async def complete(self, messages, api_key: str, model: str | None = None) -> str:
            captured.extend(messages)
            return await super().complete(messages, api_key, model)

    with patch("app.routes.chat.get_provider", return_value=_CaptureProvider("ok")):
        response = client.post(
            "/v1/chat",
            headers=HEADERS,
            json=_chat_body(
                mode="admin",
                pricing_catalogue=catalogue,
                wp_user_name="Wael",
                messages=[{"role": "user", "content": "hello"}],
            ),
        )

    assert response.status_code == 200
    joined = "\n".join(m.content for m in captured if m.role == "system")
    assert "€549" not in joined
    assert PRICING_CATALOGUE_PROMPT_HEADER not in joined
    assert captured[0].content == AMY_ADMIN_SYSTEM_PROMPT


def test_format_analytics_chat_context_live_and_fallbacks() -> None:
    live = format_analytics_chat_context(_LIVE_ANALYTICS_SNAP)
    assert "total_sessions: 5" in live
    assert "with_email: 3" in live
    assert "email_captures:" in live
    assert "last_seen windows:" in live
    assert "hot@example.com" in live
    assert "hot lead sample" in live
    empty = format_analytics_chat_context(_EMPTY_ANALYTICS_SNAP)
    assert "EMPTY" in empty
    assert "No visitor sessions recorded yet" in empty
    err = format_analytics_chat_context(_ERROR_ANALYTICS_SNAP)
    assert "UNAVAILABLE" in err
    assert "could not reach Analytics" in err


def test_format_seo_and_task_chat_context_live_and_fallbacks() -> None:
    live_seo = format_seo_chat_context(_LIVE_SEO_SNAP)
    assert "open (pending_approval): 2" in live_seo
    assert "REPORT" in live_seo or "report" in live_seo.lower()
    assert "Do NOT approve" in live_seo
    empty_seo = format_seo_chat_context(_EMPTY_SEO_SNAP)
    assert "EMPTY" in empty_seo
    err_seo = format_seo_chat_context(_ERROR_SEO_SNAP)
    assert "UNAVAILABLE" in err_seo

    live_tasks = format_task_service_chat_context(_LIVE_TASK_SNAP)
    assert "urgent_tasks: 2" in live_tasks
    assert "in_progress: 3" in live_tasks
    assert "Do NOT reassign" in live_tasks
    empty_tasks = format_task_service_chat_context(_EMPTY_TASK_SNAP)
    assert "EMPTY" in empty_tasks
    err_tasks = format_task_service_chat_context(_ERROR_TASK_SNAP)
    assert "UNAVAILABLE" in err_tasks


def test_admin_prompt_mentions_tools_and_richer_analytics_fields() -> None:
    lower = AMY_ADMIN_SYSTEM_PROMPT.lower()
    assert "analytics_summary" in lower
    assert "analytics_leads_query" in lower
    assert "seo_summary" in lower
    assert "task_stats" in lower
    assert "with_email" in lower
    assert "last-seen" in lower or "last_seen" in lower
    assert "submit idea" in lower
    assert "/analytics" in lower
    assert "seo" in lower
    assert "urgent" in lower
    assert "pending_approval" in lower or "open" in lower
    assert "report" in lower
    assert "orchestrator" in lower or "allowlisted" in lower
    assert "you have no live access" not in lower
    assert "seo tasks, task service board stats, and live web search are not wired" not in lower
    assert "do not restate conclusions" in lower
    assert "structured recommendations summary" in lower
