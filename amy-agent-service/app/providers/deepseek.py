"""DeepSeek adapter (OpenAI-compatible chat completions)."""

from typing import Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_API_URL = "https://api.deepseek.com/v1/chat/completions"


class DeepSeekProvider(BaseProvider):
    provider_id = "deepseek"
    default_model = "deepseek-chat"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        if not (api_key or "").strip():
            raise ProviderError("Missing API key.", code="auth_error")

        payload = {
            "model": self.resolve_model(model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

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
            choices = data.get("choices") or []
            if not choices:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            message = choices[0].get("message") or {}
            text = (message.get("content") or "").strip()
            if not text:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            return text
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc
