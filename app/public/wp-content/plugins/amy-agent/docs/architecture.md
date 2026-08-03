# Amy Agent — Architecture

## Purpose

Amy Agent is OGC NewFinity’s customer-facing AI layer (“digital employee”). It is a **WordPress plugin** plus a **Python intelligence service**. The separate `ogc-newfinity` theme is not modified; the plugin plugs into theme hooks already reserved for it.

## Three layers

| Layer | Location | Responsibility | Must not do |
| --- | --- | --- | --- |
| WordPress plugin (PHP) | `wp-content/plugins/amy-agent/` | Hooks, Options API, admin UI, floating widget assets, proxy browser → Python | Call any AI provider API |
| Python service | `amy-agent-service/` (sibling of Local `app/`) | Routing, context, provider adapters, reply generation | Hardcode provider or API key; own the source of truth for AI config |
| External AI API | Gemini / OpenAI / Anthropic / DeepSeek / … | Model inference | Called from PHP or the browser |

```
Visitor → WordPress REST (widget) → PHP plugin → Python service → selected AI provider
                              ↑
                    Options API (provider + API key)
```

## Config ownership

- **WordPress** stores: enable flag, Python base URL, shared secret, AI provider slug, API key, optional model.
- On each intelligence request, PHP includes an `ai` object (`provider`, `api_key`, `model`) in the JSON body.
- Python `.env` holds only service concerns (`AMY_SHARED_SECRET`, `PORT`). **No provider API keys in Python env as source of truth.**

## Theme contract (`ogc-newfinity`)

| Hook | Behavior |
| --- | --- |
| Filter `ogc_amy_agent_is_active` | Plugin returns `true` only when Enable is on **and** service URL + shared secret are set |
| Action `ogc_submit_idea_render` | Reserved for Phase 3 conversational Submit Your Idea UI (still a stub) |

Never show the theme manual form and Amy UI at the same time.

## Phase status

**Phase 1:** plugin bootstrap, admin settings, theme bridge stubs, WP REST health, API contract, Python stubs.

**Phase 2 (current):** real provider adapters, working `POST /v1/chat`, public WP REST chat with nonce + per-IP rate limit, site-wide floating chat widget (`mode: general` only).

**Later:** Submit Your Idea conversation, Help/Support FAQ-first routing, Telegram handoff, analytics, newsletters, comments, scheduling.
