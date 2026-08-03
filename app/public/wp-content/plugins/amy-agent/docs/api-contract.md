# Amy Agent — PHP ↔ Python API Contract (v0.2)

Source of truth for Phase 2. PHP never calls AI providers; Python never reads provider keys from its own `.env`.

## Base URL

Configured in WordPress as **Python service URL** (e.g. `http://127.0.0.1:8765`). Paths below are appended to that base.

## Authentication

Every `/v1/*` request must include:

```
X-Amy-Secret: <shared_secret>
```

The value must match WordPress option `amy_agent_shared_secret` and Python env `AMY_SHARED_SECRET`.

| Condition | HTTP status |
| --- | --- |
| Missing or wrong secret | `401` |
| Valid | proceed |

## AI config fragment

Included on intelligence-related POSTs. WordPress is the source of truth.

```json
{
  "ai": {
    "provider": "gemini",
    "api_key": "…",
    "model": null
  }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `provider` | string | One of: `gemini`, `openai`, `anthropic`, `deepseek` |
| `api_key` | string | Provider API key from WP Options |
| `model` | string \| null | Optional override; `null` = provider default |

### Default models (when `model` is null)

| Provider | Default |
| --- | --- |
| `gemini` | `gemini-3.6-flash` |
| `openai` | `gpt-4o-mini` |
| `anthropic` | `claude-sonnet-4-20250514` |
| `deepseek` | `deepseek-chat` |

---

## `GET /v1/health`

No AI call. Requires `X-Amy-Secret`.

**Response `200`:**

```json
{
  "ok": true,
  "version": "0.1.0"
}
```

---

## `POST /v1/config/validate`

Validates that `ai.provider` is known and `ai.api_key` is non-empty. Does not call the provider.

**Request:**

```json
{
  "ai": {
    "provider": "openai",
    "api_key": "sk-…",
    "model": null
  }
}
```

**Response `200`:**

```json
{
  "ok": true,
  "provider": "openai"
}
```

**Response `400`:**

```json
{
  "ok": false,
  "error": "invalid_config",
  "message": "Unknown provider or empty API key."
}
```

---

## `POST /v1/chat`

Routes messages to the selected provider adapter and returns the assistant reply.

**Request:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "general",
  "page": {
    "url": "https://example.com/submit-idea/",
    "slug": "submit-idea"
  },
  "messages": [
    { "role": "user", "content": "I want to build a web app." }
  ],
  "ai": {
    "provider": "openai",
    "api_key": "…",
    "model": null
  },
  "context": {}
}
```

| Field | Notes |
| --- | --- |
| `mode` | `general` \| `submit_idea` \| `support` (Phase 2 always sends `general`) |
| `page` | Current page context for routing (later phases) |
| `messages` | Chronological chat turns |
| `context` | Extensible bag for later features |

**Success `200`:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": {
    "role": "assistant",
    "content": "…"
  },
  "actions": [],
  "meta": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

**Provider failure `502`:**

```json
{
  "error": "provider_error",
  "message": "Amy could not reach the AI provider. Please try again shortly."
}
```

(No raw provider payloads or API keys in the response.)

**Invalid config `400`:** unknown provider or empty API key (`error: invalid_config`).

---

## WordPress REST (browser-facing)

Namespace: `amy-agent/v1`

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| `GET` | `/wp-json/amy-agent/v1/health` | `manage_options` | Settings presence + Python `/v1/health` reachability |
| `POST` | `/wp-json/amy-agent/v1/chat` | Valid `X-WP-Nonce` (`wp_rest`) | Public widget chat; proxies to Python |

### Public chat notes

- Returns `503` when Amy is not ready (`amy_agent_enabled` + service URL + secret).
- Rate limit: **20 requests per IP per 60 seconds** (WordPress transient). Exceeded → `429`.
- Browser never receives AI API keys; PHP injects `ai` when calling Python.
- Widget only enqueues when `ogc_amy_agent_is_active` / Amy is ready.

---

## Provider adapters (Python)

Registry maps provider slug → adapter implementing `complete(messages, api_key, model=None)`. Adapters use async `httpx` against each vendor’s chat API and raise `ProviderError` on failure. Adding a provider later: new adapter + WP select option + this contract enum — no PHP intelligence changes.
