"""Gemini thoughtSignature round-trip for tool / function calls."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import httpx

from app.providers.gemini import GeminiProvider, _gemini_contents
from app.providers.tool_types import CompletionTurn, ToolCallRequest
from app.schemas.messages import ChatMessage, ToolCallPart
from app.services.admin_chat_tools import (
    _assistant_tool_call_message,
    _normalize_tool_call,
    run_admin_tool_loop,
)


def _fake_gemini_response(
    *,
    name: str = "analytics_summary",
    args: dict[str, Any] | None = None,
    thought_signature: str | None = "SIG_abc123",
    signature_key: str = "thoughtSignature",
) -> httpx.Response:
    part: dict[str, Any] = {
        "functionCall": {
            "name": name,
            "args": args if args is not None else {},
        }
    }
    if thought_signature is not None:
        part[signature_key] = thought_signature
    body = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [part],
                }
            }
        ]
    }
    return httpx.Response(
        200,
        json=body,
        request=httpx.Request("POST", "https://example.test/generateContent"),
    )


def test_parse_turn_captures_thought_signature() -> None:
    provider = GeminiProvider()
    turn = provider._parse_turn(_fake_gemini_response())
    assert turn.has_tool_calls
    assert len(turn.tool_calls) == 1
    call = turn.tool_calls[0]
    assert call.name == "analytics_summary"
    assert call.thought_signature == "SIG_abc123"


def test_parse_turn_accepts_snake_case_thought_signature() -> None:
    provider = GeminiProvider()
    turn = provider._parse_turn(
        _fake_gemini_response(signature_key="thought_signature", thought_signature="SIG_snake")
    )
    assert turn.tool_calls[0].thought_signature == "SIG_snake"


def test_parse_turn_without_signature_leaves_none() -> None:
    provider = GeminiProvider()
    turn = provider._parse_turn(_fake_gemini_response(thought_signature=None))
    assert turn.tool_calls[0].thought_signature is None


def test_tool_call_request_to_part_preserves_signature() -> None:
    turn = CompletionTurn(
        text=None,
        tool_calls=[
            ToolCallRequest(
                id="gemini_call_0",
                name="analytics_summary",
                arguments={},
                thought_signature="SIG_persist",
            )
        ],
    )
    msg = _assistant_tool_call_message(turn)
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].thought_signature == "SIG_persist"

    normalized = _normalize_tool_call(turn.tool_calls[0])
    assert normalized.thought_signature == "SIG_persist"


def test_gemini_contents_reproduces_thought_signature() -> None:
    messages = [
        ChatMessage(role="user", content="how are leads doing"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCallPart(
                    id="gemini_call_0",
                    name="analytics_summary",
                    arguments={},
                    thought_signature="SIG_replay",
                )
            ],
        ),
        ChatMessage(
            role="tool",
            content='{"ok": true}',
            tool_call_id="gemini_call_0",
            name="analytics_summary",
        ),
        ChatMessage(role="user", content="and traffic?"),
    ]
    _system, contents = _gemini_contents(messages)
    model_turn = next(c for c in contents if c["role"] == "model" and "functionCall" in c["parts"][0])
    part = model_turn["parts"][0]
    assert part["functionCall"]["name"] == "analytics_summary"
    assert part["thoughtSignature"] == "SIG_replay"
    assert "thoughtSignature" not in part["functionCall"]


def test_gemini_contents_omits_thought_signature_when_none() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                ToolCallPart(
                    id="call_1",
                    name="task_stats",
                    arguments={},
                    thought_signature=None,
                )
            ],
        )
    ]
    _system, contents = _gemini_contents(messages)
    part = contents[0]["parts"][0]
    assert "functionCall" in part
    assert "thoughtSignature" not in part
    assert "thought_signature" not in part


def test_two_turn_tool_loop_sends_thought_signature_on_followup() -> None:
    """Admin-style: turn 1 functionCall+sig → tool result → turn 2 must replay sig."""

    captured_payloads: list[dict[str, Any]] = []

    first_body = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "analytics_summary",
                                "args": {},
                            },
                            "thoughtSignature": "SIG_roundtrip",
                        }
                    ],
                }
            }
        ]
    }
    second_body = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "Leads look healthy this week."}],
                }
            }
        ]
    }

    responses = [
        httpx.Response(
            200,
            json=first_body,
            request=httpx.Request("POST", "https://example.test/a"),
        ),
        httpx.Response(
            200,
            json=second_body,
            request=httpx.Request("POST", "https://example.test/b"),
        ),
    ]

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, params: Any = None, json: Any = None) -> httpx.Response:
            captured_payloads.append(json)
            return responses[len(captured_payloads) - 1]

    async def _run() -> tuple[str, list[str]]:
        with (
            patch("app.providers.gemini.httpx.AsyncClient", _FakeAsyncClient),
            patch(
                "app.services.admin_chat_tools.analytics_summary_for_chat",
                return_value={
                    "ok": True,
                    "tool": "analytics_summary",
                    "chat_context": "3 visitors this week.",
                    "summary": "3 visitors",
                },
            ),
        ):
            return await run_admin_tool_loop(
                GeminiProvider(),
                [ChatMessage(role="user", content="how are leads doing")],
                api_key="test-key",
                model="gemini-3.6-flash",
            )

    text, used = asyncio.run(_run())
    assert text == "Leads look healthy this week."
    assert used == ["analytics_summary"]
    assert len(captured_payloads) == 2

    followup = captured_payloads[1]
    model_parts = []
    for content in followup["contents"]:
        if content.get("role") == "model":
            for part in content.get("parts") or []:
                if "functionCall" in part:
                    model_parts.append(part)
    assert model_parts, "follow-up request must include prior functionCall"
    assert model_parts[0].get("thoughtSignature") == "SIG_roundtrip"
