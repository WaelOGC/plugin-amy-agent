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

All require `X-Amy-Secret`. The Python service never calls WordPress. WordPress fetches live field values via core REST (posts/pages/media) or the category/tag AJAX bridge below, posts the snapshot here, and writes approved values back through `/wp/v2/posts/{id}` or `/wp/v2/pages/{id}` (Yoast meta registered with `show_in_rest`), `/wp/v2/media/{id}` for attachment fields, or `amy_seo_term_write` for Yoast taxonomy title/description.

`content_type` is `post` | `page` | `category` | `tag` | `media` (default `post` on check requests so existing callers stay valid). Post/page checks still use `check_snapshot()`. Categories/tags use `check_term_snapshot()` (`seo_title` and `meta_description` drive red; missing `term_description` is orange). Media uses `check_media_snapshot()` (only missing `alt_text` drives red).

### `POST /v1/seo-tasks/check`

Body: `wp_post_id`, `post_type`, `content_type` (optional, default `post`), `title`, `content_excerpt`, `focus_keyphrase`, `seo_title`, `meta_description`, `has_featured_image`, `featured_image_alt`, `og_title`, `og_description`, `og_image`, `twitter_title`, `twitter_description`, `twitter_image`, `category_count`, plus type-specific optionals `term_description`, `filename`, `alt_text`, `caption`, `description`.

Runs the type-aware rule-based check (not an AI call). Stores a row with `status: "pending_approval"` and returns `check_id`, `content_type`, `verdict` (`red` / `orange` / `green`), `findings` (`field`, `severity` `missing`|`weak`, `message`), and optional `batch_run_id` (null for single-target checks).

### `GET /v1/seo-tasks/checks`

Optional query `status=pending_approval|approved|rejected`, `verdict=red|orange|green`, and `content_type=post|page|category|tag|media`. Newest first. Invalid filter → `400`.

### `GET /v1/seo-tasks/checks/{check_id}`

Single check (`404` if unknown).

### `POST /v1/seo-tasks/checks/{check_id}/approve`

Body: `{ "approved_fields": { … } }` — the values WordPress actually wrote (may differ from empty Task-1 suggestion fields). Marks `status = "approved"`. Not pending → `409`. Batch-originated checks use this same endpoint.

### `POST /v1/seo-tasks/checks/{check_id}/reject`

Optional `{ "reason": "…" }`. Marks `status = "rejected"`. No WordPress write. Not pending → `409`.

### `POST /v1/seo-tasks/checks/{check_id}/generate`

AI-suggested SEO copy for missing/weak text fields. Body: `{ "ai": { provider, api_key, model }, "fields": string[] | omit }`. When `fields` is omitted, the service derives keys from stored findings (`og_social` → `og_title`/`og_description`, `twitter_social` → `twitter_title`/`twitter_description`; `featured_image` and `categories` are skipped). Returns `{ check_id, generated_fields, provider, model }`. Suggestions are **not persisted**; WordPress holds them in the modal until Approve. Unknown check → `404`. Nothing to generate → `400 nothing_to_generate`. Unparseable model output → `502 generation_parse_error`. Provider failures → `502`.

### `POST /v1/seo-tasks/checks/{check_id}/generate-image`

Gemini-only featured image. Body: `{ "ai": { provider, api_key, model } }`. Non-Gemini → `400 unsupported_provider`. Returns `{ check_id, image_base64, mime_type, suggested_alt_text }`. Not persisted. Unknown check → `404`. Provider failures → `502`.

### `POST /v1/seo-tasks/batches`

Start a batch run. Body: `content_type`, `mode` (`manual` | `auto`), `batch_size` (default `5`, clamped server-side to `1`–`20`), `items` (non-empty list of `{ item_id, title, snapshot }`). `snapshot` is the same field shape as a check request minus `content_type` / `wp_post_id`.

- `manual`: process the first slice only. Status is `in_progress`, or `completed` if that slice finished the list.
- `auto`: loop remaining slices inside this one HTTP request and return every batch report together. Status is `completed`.

Each successful item creates a pending-approval row in the existing checks table (`check_id` on the item result). A malformed item is recorded as `{ error, check_id: null, verdict: null, findings: [] }` and does not abort the rest of the slice.

### `POST /v1/seo-tasks/batches/{batch_run_id}/continue`

Manual mode only. Process the next slice and return the updated run (all reports so far). `409` if the run is auto, already `completed`, or `stopped`. `404` if unknown.

### `POST /v1/seo-tasks/batches/{batch_run_id}/stop`

Mark `status = "stopped"`. `409` if already `completed` or `stopped`. `404` if unknown.

### `GET /v1/seo-tasks/batches/{batch_run_id}`

Full current state, including every report produced so far. `404` if unknown.

### `GET /v1/seo-tasks/batches`

List recent runs as summaries (no item/report payloads). Optional query `content_type` and `status=in_progress|stopped|completed`. Invalid filter → `400`.

---

## SEO Tasks (WordPress admin-ajax)

Nonce action: `amy_agent_seo_tasks` (field name `nonce`). Capability for existing check proxies and `amy_seo_term_get`: `manage_options`. `amy_seo_term_write` requires `manage_categories`.

| Action | Purpose |
| --- | --- |
| `amy_seo_check` | Proxy snapshot to Python `POST /v1/seo-tasks/check` (posts/pages; existing UI) |
| `amy_seo_checks_list` | Proxy `GET /v1/seo-tasks/checks` (optional `status`, `verdict`, `content_type`) |
| `amy_seo_check_get` | Proxy one stored check |
| `amy_seo_check_approve` | Proxy approval record (WordPress write happens separately via core REST) |
| `amy_seo_check_reject` | Proxy rejection record |
| `amy_seo_generate_fields` | Proxy `POST /v1/seo-tasks/checks/{id}/generate`. AI config is injected from Settings. Optional `fields` JSON array. |
| `amy_seo_generate_image` | Proxy `POST /v1/seo-tasks/checks/{id}/generate-image`. Gemini only; AI config from Settings. |
| `amy_seo_term_get` | Read category/tag name, Yoast SEO title, Yoast meta description, and `term_description()`. Taxonomy allow-list: `category` or `tag` (`tag` maps to `post_tag`). Requires Yoast `WPSEO_Taxonomy_Meta`. |
| `amy_seo_term_write` | Write Yoast SEO title / meta description via `WPSEO_Taxonomy_Meta::set_value()` using keys `title` and `desc`. Only non-empty present fields are written. |
| `amy_seo_batch_start` | Proxy to Python `POST /v1/seo-tasks/batches`. Body: `content_type`, `mode`, `batch_size`, `items` (JSON array; empty rejected; capped at 500). Same nonce as the other SEO Tasks actions. |
| `amy_seo_batch_continue` | Proxy to `POST /v1/seo-tasks/batches/{batch_run_id}/continue`. |
| `amy_seo_batch_stop` | Proxy to `POST /v1/seo-tasks/batches/{batch_run_id}/stop`. |
| `amy_seo_batch_get` | Proxy to `GET /v1/seo-tasks/batches/{batch_run_id}`. |

Media alt/title/caption/description stay on core REST `/wp/v2/media/{id}` — no extra PHP.

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
