"""Google Gemini adapter."""

from typing import Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_IMAGE_MODEL = "gemini-3.1-flash-image"  # verify against a real key before shipping
_IMAGE_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class GeminiImageResult:
    def __init__(self, data_base64: str, mime_type: str) -> None:
        self.data_base64 = data_base64
        self.mime_type = mime_type


class GeminiProvider(BaseProvider):
    provider_id = "gemini"
    default_model = "gemini-3.6-flash"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        api_key: str,
        model: str | None = None,
    ) -> str:
        if not (api_key or "").strip():
            raise ProviderError("Missing API key.", code="auth_error")

        # Remap retired model IDs WordPress may still send from older settings.
        if (model or "").strip() == "gemini-2.0-flash":
            model = None
        resolved = self.resolve_model(model)
        print(f"[amy-gemini] using model={resolved}", flush=True)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{resolved}:generateContent"
        )

        contents: list[dict] = []
        system_parts: list[str] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
                continue
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        if not contents:
            raise ProviderError("No messages to send.", code="invalid_request")

        payload: dict = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    url,
                    params={"key": api_key.strip()},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("Provider request timed out.", code="timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach provider.", code="network_error") from exc

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> str:
        if response.status_code >= 400:
            print(
                f"[amy-gemini] HTTP {response.status_code}: {response.text}",
                flush=True,
            )
        if response.status_code in (401, 403):
            raise ProviderError("Provider authentication failed.", code="auth_error")
        if response.status_code == 429:
            raise ProviderError("Provider rate limit exceeded.", code="rate_limit")
        if response.status_code >= 400:
            raise ProviderError("Provider returned an error.", code="provider_error")

        try:
            data = response.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            parts = (candidates[0].get("content") or {}).get("parts") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            text = "".join(texts).strip()
            if not text:
                raise ProviderError("Provider returned an empty reply.", code="empty_reply")
            return text
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc

    async def generate_image(self, prompt: str, api_key: str) -> GeminiImageResult:
        if not (api_key or "").strip():
            raise ProviderError("Missing API key.", code="auth_error")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{_IMAGE_MODEL}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        try:
            async with httpx.AsyncClient(timeout=_IMAGE_TIMEOUT) as client:
                response = await client.post(url, params={"key": api_key.strip()}, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError("Provider request timed out.", code="timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not reach provider.", code="network_error") from exc

        if response.status_code in (401, 403):
            raise ProviderError("Provider authentication failed.", code="auth_error")
        if response.status_code == 429:
            raise ProviderError("Provider rate limit exceeded.", code="rate_limit")
        if response.status_code >= 400:
            print(f"[amy-gemini-image] HTTP {response.status_code}: {response.text}", flush=True)
            raise ProviderError("Provider returned an error.", code="provider_error")

        try:
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (candidates[0].get("content") or {}).get("parts") or []
            for part in parts:
                inline = part.get("inlineData") if isinstance(part, dict) else None
                if inline and inline.get("data"):
                    return GeminiImageResult(
                        data_base64=inline["data"],
                        mime_type=inline.get("mimeType") or "image/png",
                    )
            raise ProviderError("Provider returned no image.", code="empty_reply")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Could not parse provider response.", code="parse_error") from exc
