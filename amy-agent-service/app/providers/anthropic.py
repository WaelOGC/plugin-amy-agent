"""Anthropic Claude adapter."""

from typing import Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(BaseProvider):
    provider_id = "anthropic"
    default_model = "claude-sonnet-4-20250514"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        if not (api_key or "").strip():
            raise ProviderError("Missing API key.", code="auth_error")

        system_parts: list[str] = []
        api_messages: list[dict] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
                continue
            api_messages.append({"role": msg.role, "content": msg.content})

        if not api_messages:
            raise ProviderError("No messages to send.", code="invalid_request")

        payload: dict = {
            "model": self.resolve_model(model),
            "max_tokens": 2048,
            "messages": api_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

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

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> str:
        if response.status_code in (401, 403):
            raise ProviderError("Provider authentication failed.", code="auth_error")
        if response.status_code == 429:
            raise ProviderError("Provider rate limit exceeded.", code="rate_limit")
        if response.status_code >= 400:
            raise ProviderError("Provider returned an error.", code="provider_error")

        try:
            data = response.json()
            blocks = data.get("content") or []
            texts = [
                b.get("text", "")
                for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            text = "".join(texts).strip()
            if not text:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            return text
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc
