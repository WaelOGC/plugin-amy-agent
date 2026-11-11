"""DeepSeek adapter (OpenAI-compatible chat completions + function calling)."""

from __future__ import annotations

from typing import Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.providers.openai import OpenAIProvider, _openai_messages, _tools_payload
from app.providers.tool_types import CompletionTurn, ToolSpec
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekProvider(BaseProvider):
    provider_id = "deepseek"
    default_model = "deepseek-chat"
    supports_tools = True

    def __init__(self) -> None:
        # Reuse OpenAI turn parsing (compatible wire format).
        self._openai = OpenAIProvider()

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

        payload: dict = {
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

        return self._openai._parse_turn(response)
