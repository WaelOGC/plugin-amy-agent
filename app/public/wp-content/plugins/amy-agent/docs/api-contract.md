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

## Analytics (Python)

All require `X-Amy-Secret`. Unknown `event_type` values are rejected (`400`); the allowlist is:

`page_view`, `widget_opened`, `widget_message_sent`, `submit_idea_started`, `submit_idea_step_reached`, `submit_idea_abandoned`, `submit_idea_completed`, `contact_form_started`, `contact_form_abandoned`, `contact_form_submitted`.

There is no newsletter event type (the newsletter form has no working backend yet).

### `POST /v1/analytics/event`

```json
{
  "session_id": "uuid",
  "event_type": "page_view",
  "event_data": { "step": "contact" },
  "page_path": "/blog/example",
  "ip": "203.0.113.10"
}
```

`event_data` and `page_path` are optional. `ip` is injected by WordPress (never stored long-term; used once per new session for country/city lookup).

**Response `200`:** `{ "ok": true, "session_id": "…", "lead_status": "cold"|"warm"|"hot" }`

### `GET /v1/analytics/leads`

Optional query `status=cold|warm|hot`. Ranked hot → warm → cold, then `last_seen_at` descending. Each item includes truncated session id, location, last seen, lead email if captured, and a server-built `signal` string.

### `GET /v1/analytics/leads/{session_id}/events`

Full event timeline for one session (`404` if unknown).

---

## SEO Tasks (Python)

All require `X-Amy-Secret`. The Python service never calls WordPress. WordPress fetches live field values via core REST, posts the snapshot here, and writes approved values back through `/wp/v2/posts/{id}` or `/wp/v2/pages/{id}` (Yoast meta registered with `show_in_rest`) plus `/wp/v2/media/{id}` for featured-image `alt_text`.

### `POST /v1/seo-tasks/check`

Body: `wp_post_id`, `post_type`, `title`, `content_excerpt`, `focus_keyphrase`, `seo_title`, `meta_description`, `has_featured_image`, `featured_image_alt`, `og_title`, `og_description`, `og_image`, `twitter_title`, `twitter_description`, `twitter_image`, `category_count`.

Runs rule-based checks (not an AI call). Stores a row with `status: "pending_approval"` and returns `check_id`, `verdict` (`red` / `orange` / `green`), and `findings` (`field`, `severity` `missing`|`weak`, `message`).

### `GET /v1/seo-tasks/checks`

Optional query `status=pending_approval|approved|rejected` and `verdict=red|orange|green`. Newest first. Invalid filter → `400`.

### `GET /v1/seo-tasks/checks/{check_id}`

Single check (`404` if unknown).

### `POST /v1/seo-tasks/checks/{check_id}/approve`

Body: `{ "approved_fields": { … } }` — the values WordPress actually wrote (may differ from empty Task-1 suggestion fields). Marks `status = "approved"`. Not pending → `409`.

### `POST /v1/seo-tasks/checks/{check_id}/reject`

Optional `{ "reason": "…" }`. Marks `status = "rejected"`. No WordPress write. Not pending → `409`.

---

## WordPress REST (browser-facing)

Namespace: `amy-agent/v1`

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| `GET` | `/wp-json/amy-agent/v1/health` | `manage_options` | Settings presence + Python `/v1/health` reachability |
| `POST` | `/wp-json/amy-agent/v1/chat` | Valid `X-WP-Nonce` (`wp_rest`) | Public widget chat; proxies to Python |
| `POST` | `/wp-json/amy-agent/v1/track` | Public (unauthenticated); REST nonce still sent so logged-in visitors are not blocked by cookie CSRF | Tracking beacon; proxies to Python `/v1/analytics/event` |

### Public tracking notes

- Independent rate limit: **20 requests per IP per 60 seconds** (transient prefix `amy_track_rl_`). Exceeded → `429`.
- `event_type` must be one of the fixed allowlist; unknown types → `400`. PHP injects the client IP; the beacon never sends it.
- Returns `200 {"ok": true}` on success. Requires service URL + shared secret (`is_service_configured`); does **not** require the widget to be enabled.
- Public JS contract: `window.amyTrack(eventType, data)`. Abandon events use `navigator.sendBeacon()`.

### Public chat notes

- Returns `503` when Amy is not ready (`amy_agent_enabled` + service URL + secret).
- Rate limit: **20 requests per IP per 60 seconds** (WordPress transient). Exceeded → `429`.
- Browser never receives AI API keys; PHP injects `ai` when calling Python.
- Widget only enqueues when `ogc_amy_agent_is_active` / Amy is ready.

---

## Provider adapters (Python)

Registry maps provider slug → adapter implementing `complete(messages, api_key, model=None)`. Adapters use async `httpx` against each vendor’s chat API and raise `ProviderError` on failure. Adding a provider later: new adapter + WP select option + this contract enum — no PHP intelligence changes.
