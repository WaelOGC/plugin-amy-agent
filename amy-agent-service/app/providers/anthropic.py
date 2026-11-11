"""Anthropic Claude adapter (messages API + tool use)."""

from __future__ import annotations

from typing import Any, Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.providers.tool_types import CompletionTurn, ToolCallRequest, ToolSpec
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_API_URL = "https://api.anthropic.com/v1/messages"


def _tools_payload(tools: Sequence[ToolSpec] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


def _anthropic_messages(messages: Sequence[ChatMessage]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    api_messages: list[dict[str, Any]] = []

    pending_tool_results: list[dict[str, Any]] = []

    def _flush_tool_results() -> None:
        nonlocal pending_tool_results
        if not pending_tool_results:
            return
        api_messages.append({"role": "user", "content": pending_tool_results})
        pending_tool_results = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
            continue
        if msg.role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content or "",
                }
            )
            continue
        _flush_tool_results()
        if msg.role == "assistant" and msg.tool_calls:
            blocks: list[dict[str, Any]] = []
            if (msg.content or "").strip():
                blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments or {},
                    }
                )
            api_messages.append({"role": "assistant", "content": blocks})
            continue
        api_messages.append({"role": msg.role, "content": msg.content})

    _flush_tool_results()
    system = "\n\n".join(system_parts) if system_parts else None
    return system, api_messages


class AnthropicProvider(BaseProvider):
    provider_id = "anthropic"
    default_model = "claude-sonnet-4-20250514"
    supports_tools = True

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        turn = await self.complete_turn(messages, api_key=api_key, model=model, tools=None)
        text = (turn.text or "").strip()
        if not text:
            raise ProviderError("Provider returned an empty reply.", code="empty_reply")
        return text

    async def complete_turn(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
        tools: Sequence[ToolSpec] | None = None,
    ) -> CompletionTurn:
        if not (api_key or "").strip():
            raise ProviderError("Missing API key.", code="auth_error")

        system, api_messages = _anthropic_messages(messages)
        if not api_messages:
            raise ProviderError("No messages to send.", code="invalid_request")

        payload: dict[str, Any] = {
            "model": self.resolve_model(model),
            "max_tokens": 2048,
            "messages": api_messages,
        }
        if system:
            payload["system"] = system
        tools_payload = _tools_payload(tools)
        if tools_payload:
            payload["tools"] = tools_payload

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    _API_URL,
                    headers={
                        "x-api-key": api_key.strip(),
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("Provider request timed out.", code="timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach provider.", code="network_error") from exc

        return self._parse_turn(response)

    def _parse_turn(self, response: httpx.Response) -> CompletionTurn:
        if response.status_code in (401, 403):
            raise ProviderError("Provider authentication failed.", code="auth_error")
        if response.status_code == 429:
            raise ProviderError("Provider rate limit exceeded.", code="rate_limit")
        if response.status_code >= 400:
            raise ProviderError("Provider returned an error.", code="provider_error")

        try:
            data = response.json()
            blocks = data.get("content") or []
            texts: list[str] = []
            tool_calls: list[ToolCallRequest] = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    texts.append(block.get("text") or "")
                elif btype == "tool_use":
                    name = (block.get("name") or "").strip()
                    if not name:
                        continue
                    raw_input = block.get("input") or {}
                    args = raw_input if isinstance(raw_input, dict) else {}
                    tool_calls.append(
                        ToolCallRequest(
                            id=str(block.get("id") or ""),
                            name=name,
                            arguments=args,
                        )
                    )
            text = "".join(texts).strip() or None
            if not tool_calls and not text:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            return CompletionTurn(text=text, tool_calls=tool_calls)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc
