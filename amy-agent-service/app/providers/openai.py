"""OpenAI adapter (chat completions + function calling)."""

from __future__ import annotations

import json
from typing import Any, Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.providers.tool_types import CompletionTurn, ToolCallRequest, ToolSpec
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_API_URL = "https://api.openai.com/v1/chat/completions"


def _tools_payload(tools: Sequence[ToolSpec] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _openai_messages(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "tool":
            item: dict[str, Any] = {
                "role": "tool",
                "tool_call_id": msg.tool_call_id or "",
                "content": msg.content or "",
            }
            if msg.name:
                item["name"] = msg.name
            out.append(item)
            continue
        if msg.role == "assistant" and msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments or {}),
                        },
                    }
                )
            out.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tool_calls,
                }
            )
            continue
        out.append({"role": msg.role, "content": msg.content})
    return out


class OpenAIProvider(BaseProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"
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

        payload: dict[str, Any] = {
            "model": self.resolve_model(model),
            "messages": _openai_messages(messages),
        }
        tools_payload = _tools_payload(tools)
        if tools_payload:
            payload["tools"] = tools_payload
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    _API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key.strip()}",
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
            choices = data.get("choices") or []
            if not choices:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            message = choices[0].get("message") or {}
            text = (message.get("content") or "").strip() or None
            tool_calls: list[ToolCallRequest] = []
            for raw in message.get("tool_calls") or []:
                if not isinstance(raw, dict):
                    continue
                fn = raw.get("function") or {}
                name = (fn.get("name") or "").strip()
                if not name:
                    continue
                args_raw = fn.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                tool_calls.append(
                    ToolCallRequest(
                        id=str(raw.get("id") or ""),
                        name=name,
                        arguments=args,
                    )
                )
            if not tool_calls and not text:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            return CompletionTurn(text=text, tool_calls=tool_calls)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc
