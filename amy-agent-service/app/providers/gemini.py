"""Google Gemini adapter (generateContent + function calling)."""

from __future__ import annotations

from typing import Any, Sequence

import httpx

from app.providers.base import BaseProvider
from app.providers.errors import ProviderError
from app.providers.tool_types import CompletionTurn, ToolCallRequest, ToolSpec
from app.schemas.messages import ChatMessage

_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
_IMAGE_MODEL = "gemini-3.1-flash-image"  # verify against a real key before shipping
_IMAGE_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Gemini functionDeclarations.parameters is a narrow Schema subset — not full JSON Schema.
# Unknown keys (e.g. additionalProperties) cause HTTP 400 "Cannot find field".
_GEMINI_SCHEMA_UNSUPPORTED_KEYS = frozenset(
    {
        "additionalProperties",
        "additionalItems",
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "definitions",
        "examples",
        "example",
        "default",
        "const",
        "contentMediaType",
        "contentEncoding",
        "if",
        "then",
        "else",
        "dependentRequired",
        "dependentSchemas",
        "unevaluatedProperties",
        "unevaluatedItems",
        "prefixItems",
        "propertyNames",
        "patternProperties",
        "not",
        "oneOf",
        "allOf",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "uniqueItems",
        "writeOnly",
        "readOnly",
        "deprecated",
        "title",
    }
)


def sanitize_gemini_schema(node: Any) -> Any:
    """Recursively strip JSON Schema keys Gemini's Schema proto rejects.

    Keeps internal/OpenAPI tool specs intact; only the Gemini request payload
    should pass through this helper.
    """
    if isinstance(node, list):
        return [sanitize_gemini_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _GEMINI_SCHEMA_UNSUPPORTED_KEYS:
            continue
        out[key] = sanitize_gemini_schema(value)
    return out


class GeminiImageResult:
    def __init__(self, data_base64: str, mime_type: str) -> None:
        self.data_base64 = data_base64
        self.mime_type = mime_type


def _tools_payload(tools: Sequence[ToolSpec] | None) -> dict[str, Any] | None:
    if not tools:
        return None
    return {
        "functionDeclarations": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": sanitize_gemini_schema(t.parameters),
            }
            for t in tools
        ]
    }


def _gemini_contents(
    messages: Sequence[ChatMessage],
) -> tuple[list[str], list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
            continue
        if msg.role == "tool":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": msg.name or "",
                                "response": {"result": msg.content or ""},
                            }
                        }
                    ],
                }
            )
            continue
        if msg.role == "assistant" and msg.tool_calls:
            parts: list[dict[str, Any]] = []
            if (msg.content or "").strip():
                parts.append({"text": msg.content})
            for tc in msg.tool_calls:
                parts.append(
                    {
                        "functionCall": {
                            "name": tc.name,
                            "args": tc.arguments or {},
                        }
                    }
                )
            contents.append({"role": "model", "parts": parts})
            continue
        role = "user" if msg.role == "user" else "model"
        parts: list[dict[str, Any]] = []
        if (msg.content or "").strip() or not getattr(msg, "inline_media", None):
            parts.append({"text": msg.content or ""})
        for media in getattr(msg, "inline_media", None) or []:
            mime = (getattr(media, "mime_type", None) or "").strip() or "image/jpeg"
            data = (getattr(media, "data", None) or "").strip()
            if not data:
                continue
            parts.append({"inline_data": {"mime_type": mime, "data": data}})
        if not parts:
            parts.append({"text": msg.content or ""})
        contents.append({"role": role, "parts": parts})

    return system_parts, contents


class GeminiProvider(BaseProvider):
    provider_id = "gemini"
    default_model = "gemini-3.6-flash"
    supports_tools = True
    supports_vision = True

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

        # Remap retired model IDs WordPress may still send from older settings.
        if (model or "").strip() == "gemini-2.0-flash":
            model = None
        resolved = self.resolve_model(model)
        print(f"[amy-gemini] using model={resolved}", flush=True)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{resolved}:generateContent"
        )

        system_parts, contents = _gemini_contents(messages)
        if not contents:
            raise ProviderError("No messages to send.", code="invalid_request")

        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        tools_payload = _tools_payload(tools)
        if tools_payload:
            payload["tools"] = [tools_payload]

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

        return self._parse_turn(response)

    def _parse_turn(self, response: httpx.Response) -> CompletionTurn:
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
            texts: list[str] = []
            tool_calls: list[ToolCallRequest] = []
            for idx, part in enumerate(parts):
                if not isinstance(part, dict):
                    continue
                if "text" in part and part.get("text"):
                    texts.append(str(part.get("text") or ""))
                fn = part.get("functionCall")
                if isinstance(fn, dict):
                    name = (fn.get("name") or "").strip()
                    if not name:
                        continue
                    raw_args = fn.get("args") or fn.get("arguments") or {}
                    args = raw_args if isinstance(raw_args, dict) else {}
                    tool_calls.append(
                        ToolCallRequest(
                            id=f"gemini_call_{idx}",
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
