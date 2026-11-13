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
  "context": {},
  "pricing_catalogue": "Custom WordPress Development\nStarter Website — €549, one-off\n…",
  "visitor_timezone": "Europe/Amsterdam",
  "visitor_language": "nl-NL"
}
```

| Field | Notes |
| --- | --- |
| `mode` | `general` \| `submit_idea` \| `support` \| `admin` |
| `page` | Current page context for routing (later phases) |
| `messages` | Chronological chat turns. Each may include `attachments[]` (`AttachmentRef`: required `url` + `filename`; optional `content_type`, `id`, `kind`, `size`, …). Public WordPress `/chat` sanitizer keeps messages that have non-empty `content` **or** at least one valid attachment (empty text + files is allowed); invalid attachment items (missing `url`/`filename`) are dropped; max 3 attachments per message. `Amy_Api_Client::chat()` JSON-encodes the payload as-is to this endpoint. |
| `context` | Extensible bag for later features |
| `pricing_catalogue` | Optional. Compact plain-text live price list from the active theme (`ogc_get_pricing_data()`), sent by WordPress on **public general** chat only (not admin, not Submit Idea). Service treats it as untrusted: strips control characters and hard-caps at ~6,000 characters. When non-empty, Python appends it to the public system prompt as a delimited “Current public price list” block. When absent/empty, Amy keeps the base public prompt (link to Pricing page, no quoted numbers). |
| `visitor_timezone` | Optional. IANA timezone from the public widget (`Intl…timeZone`), max 64 chars. Sent only when **Friendly closing wishes in public chat** is ON in Amy → Settings. Validated server-side; invalid/missing → no closing-wish hint. Admin mode never uses it. |
| `visitor_language` | Optional. Browser language tag (max 32 chars), same Settings gate as timezone. Validated/capped; not used for calendar occasions. |

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
    "model": "gpt-4o-mini",
    "closing_wish": false
  }
}
```

`meta.closing_wish` is `true` when the service attached a closing-wish hint on an ending turn and marked the conversation (once). The public widget then fires `amyTrack('chat_closing_wish')`.

### `GET /v1/conversations/by-visitor`

Public-widget history for one anonymous visitor. Requires `X-Amy-Secret`.

| Query | Notes |
| --- | --- |
| `visitor_id` | Required. Exact ownership match. |
| `limit` | Optional. Default `20`, max `20`. |

**Response `200`:** `{ "conversations": [ ConversationSummary, … ] }` — newest `updated_at` first. Only rows with matching `visitor_id`, `wp_user_id = 0`, and `mode != "admin"` (never admin chats), **and at least one `role=user` message** (empty shells are omitted). Each summary may include `last_message_preview` (start of the latest message). Wrong/unknown `visitor_id` → empty list.

Conversation detail (`GET /v1/conversations/{id}`) messages may include `created_at` (unix seconds) for the public widget timestamps. Public-chat attachments use secure file ids (see below); expired files surface as `expired: true` / “File expired”.

### `POST /v1/public-chat/upload`

Secure **public widget** uploads only (not Submit Idea, not admin chat). Requires `X-Amy-Secret`. Multipart form:

| Field | Notes |
| --- | --- |
| `file` | Required. JPEG / PNG / WebP / PDF only (magic bytes). Max 5 MB. PDF max 10 pages; encrypted PDFs rejected. |
| `visitor_id` | Required. |
| `conversation_id` | Optional until the first message creates the conversation. |
| `notify` | Optional bool (default true). When true, service relays to WP `POST /amy-agent/v1/chat-upload-notify`. |
| `allow_uploads` | Optional bool. When false → `403 uploads_disabled`. |
| `message_excerpt` | Optional short visitor text for the notify email/Telegram. |

Images are decoded and re-encoded (metadata stripped; longest side capped at 2000px). PDFs are never stored or served — pages are scaled **before** rendering to JPEG (longest side ≤ 2000 px, ≤ 4M pixels; absurd declared page sizes rejected). Files live under `uploads/public-chat/` with random names (not WordPress uploads, not statically mounted). Rate limits: 10 logical files / visitor / hour, 10 / client IP / hour, 200 / hour globally (WP also enforces IP+global via transients and forwards `X-Amy-Client-Ip` with the shared secret). Bodies are read in bounded chunks; oversize → `413 file_too_large`. Total active storage cap configurable (default 1 GB). **Deploy 0.2.22+ with a rebuild** so `Pillow` and `pymupdf` are installed.

**Response `200`:** `AttachmentRef` with `id`, proxy `url` (`/wp-json/amy-agent/v1/chat/files/{id}`), `kind`, `size`, `description`, and for PDFs `pages[]` / `page_count`.

### `GET /v1/public-chat/files/{file_id}`

Authenticated serve of a **processed** image. Requires `X-Amy-Secret` plus matching `visitor_id` **or** `is_full_admin=true`. Response includes `X-Content-Type-Options: nosniff` and a fixed image content type. Missing/deleted → `404 file_expired`.

WordPress proxies: `POST /wp-json/amy-agent/v1/chat/upload`, `GET /wp-json/amy-agent/v1/chat/files/{id}` (nonce `wp_rest`). Settings gates: **Allow file uploads in public chat** and **Notify me about uploads** (both default ON).

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

`page_view`, `widget_opened`, `widget_message_sent`, `chat_closing_wish`, `submit_idea_started`, `submit_idea_step_reached`, `submit_idea_abandoned`, `submit_idea_completed`, `submit_idea_contact_captured`, `contact_form_started`, `contact_form_abandoned`, `contact_form_submitted`.

`submit_idea_contact_captured` fires as soon as the visitor shares email (email-first Submit Idea step) and is an email-capture event (`event_data.email` → `lead_email`). `submit_idea_completed` still fires when the brief is finalized.

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

`chat_closing_wish` is recorded by the public widget (via `window.amyTrack`) when `meta.closing_wish` is true on a public chat reply.

### `GET /v1/analytics/closing-wish-effect`

Requires `X-Amy-Secret`. Optional query `days` (1–90, default 30).

Returns public-chat conversation counts for the window, split by whether the session also has `chat_closing_wish`, plus how many in each split also have `submit_idea_started`:

```json
{
  "ok": true,
  "days": 30,
  "public_chat_conversations": 40,
  "with_closing_wish": { "conversations": 12, "submit_idea_started": 4 },
  "without_closing_wish": { "conversations": 28, "submit_idea_started": 5 }
}
```

Cohort = distinct sessions with `widget_message_sent` in the window.

**Response `200`:** `{ "ok": true, "session_id": "…", "lead_status": "cold"|"warm"|"hot" }`

### `GET /v1/analytics/summary`

Shared Analytics summary for admin chat, Telegram `/analytics`, and (later) Overview. Returns lead-session `total`, `counts` (hot/warm/cold/other), `with_email`, `email_captures` (Submit Idea / contact capture totals + `last_7d`), `last_seen` windows (`last_24h` / `last_7d` / `most_recent`), optional `hot_sample` / `sample`, plus `summary` and deterministic `slash_reply` text. Optional query `include_emails=true` adds `lead_email` on sample rows (admin channels only). This is **not** GA pageviews.

Admin `POST /v1/chat` (`mode: admin`) runs an orchestrator tool loop (service **0.2.16+**; Gemini schema sanitize **0.2.17+**). Allowlisted report-only tools: `analytics_summary`, `analytics_leads_query`, `analytics_traffic`, `email_audience_summary`, `seo_summary`, `task_stats` (same Analytics / SEO / Task Service / Email audience sources as Overview). Intent auto-invokes tools without slash; providers that support function calling (Gemini / OpenAI / Anthropic / DeepSeek) may request additional tools in the same turn. Gemini `functionDeclarations.parameters` are sanitized on the request path (strips `additionalProperties` and other unsupported JSON Schema keys). Response `meta.tools_used` lists tools invoked. Slash `/analytics` / `/Analytics` remains a WP/Telegram shortcut. Chat may cite figures but does not approve SEO writes, reassign tasks, or send Email Marketing (Approve → Send stays in wp-admin; no AgentMail).

### `GET /v1/analytics/traffic`

Page-view traffic depth from `visitor_events` (`event_type=page_view`). Returns `windows` (`all_time` / `last_24h` / `last_7d` / `last_30d` with `pageviews` + `unique_sessions`), `top_paths_7d` / `top_paths_all`, plus `summary`. Amy Analytics beacon data — **not** Google Analytics.

### `GET /v1/analytics/email-audience`

Read-only Email Marketing audience: Analytics leads with a stored `lead_email`, status breakdown, email-capture totals, small admin sample, and `send_policy: approve_then_send`. Does **not** send mail.

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
| `GET` | `/wp-json/amy-agent/v1/admin-chat/analytics-summary` | `manage_options` | Fresh Analytics summary for Dashboard Chat `/Analytics` (proxies Python `GET /v1/analytics/summary?include_emails=true`) |
| `POST` | `/wp-json/amy-agent/v1/chat` | Valid `X-WP-Nonce` (`wp_rest`) | Public widget chat; proxies to Python |
| `POST` | `/wp-json/amy-agent/v1/chat/conversation` | Valid `X-WP-Nonce` (`wp_rest`) | Create visitor-owned public conversation (`visitor_id`); proxies to `POST /v1/conversations` |
| `GET` | `/wp-json/amy-agent/v1/chat/conversation/{id}` | Valid `X-WP-Nonce` (`wp_rest`) | Load one visitor conversation (messages include `created_at`); ownership by `visitor_id` |
| `GET` | `/wp-json/amy-agent/v1/chat/conversations` | Valid `X-WP-Nonce` (`wp_rest`) | List this visitor's public chats (newest first, max 20); proxies to `GET /v1/conversations/by-visitor` |
| `POST` | `/wp-json/amy-agent/v1/track` | Public (unauthenticated); REST nonce still sent so logged-in visitors are not blocked by cookie CSRF | Tracking beacon; proxies to Python `/v1/analytics/event` |

### Public tracking notes

- Independent rate limit: **20 requests per IP per 60 seconds** (transient prefix `amy_track_rl_`). Exceeded → `429`.
- `event_type` must be one of the fixed allowlist; unknown types → `400`. PHP injects the client IP; the beacon never sends it.
- Returns `200 {"ok": true}` on success. Requires service URL + shared secret (`is_service_configured`); does **not** require the widget to be enabled.
- Public JS contract: `window.amyTrack(eventType, data)`. Abandon events use `navigator.sendBeacon()`.

### Public chat notes

- Returns `503` when Amy is not ready (`amy_agent_enabled` + service URL + secret).
- Rate limit: **20 requests per IP per 60 seconds** (WordPress transient). Exceeded → `429`.
- On each public `general` chat proxy, when **Friendly closing wishes in public chat** is ON (default), PHP may forward `visitor_timezone` / `visitor_language` from the widget. When OFF, those fields are omitted and the service never adds a closing-wish hint. Tone changes still apply.
- Closing wishes use a deterministic calendar in the service (`closing_wishes.py`): weekend / Happy holidays (24–26 Dec) / Happy New Year (30 Dec–2 Jan) / day-evening. Hint is once per conversation (`conversations.closing_wish_sent`). When the flag is already set, the service appends a short “wish already given” system line (not a new hint). Public prompt: only say a wish when the Closing wish hint block is present; otherwise a simple goodbye with no wish. Admin chat never receives it.
- Browser never receives AI API keys; PHP injects `ai` when calling Python.
- Widget only enqueues when `ogc_amy_agent_is_active` / Amy is ready.
- On each public `general` chat proxy, PHP may attach `pricing_catalogue` from `Amy_Theme_Bridge::get_pricing_catalogue()` (theme helper `ogc_get_pricing_data()`, 1-hour transient cache, cleared on theme switch and theme/plugin update). Cap ~6,000 characters. Admin chat and Submit Idea never send this field.
- Public conversations are owned by browser `visitor_id` (`localStorage` key `amyAgentVisitorId`). `GET /v1/conversations/by-visitor?visitor_id=…&limit=20` (and WP `GET /chat/conversations`) returns only that visitor's non-admin rows (`wp_user_id = 0`, `mode != admin`), newest first, capped at 20. Wrong `visitor_id` → empty list. Conversation detail messages include `created_at` (unix seconds) for widget timestamps.

---

## Provider adapters (Python)

Registry maps provider slug → adapter implementing `complete(messages, api_key, model=None)`. Adapters use async `httpx` against each vendor’s chat API and raise `ProviderError` on failure. Adding a provider later: new adapter + WP select option + this contract enum — no PHP intelligence changes.
