# Amy Agent — Roadmap & Real Build Status

> **Purpose of this file:** single source of truth so any session (Claude, Cursor, or Wael)
> can open this file first and know exactly what is built, what is a stub, and what's next —
> without re-discovering it from scratch. **Update this file at the end of every work session,
> before closing.** Keep it in `amy-agent/docs/roadmap-status.md`.
>
> **Design principle:** every tool in this roadmap follows
> `docs/00-extensibility-principles.md` — read it once, alongside whichever
> individual tool plan you're working from.
>
> Last verified against code: 2026-11-11 (amy-agent v0.2.46 / amy-agent-service v0.2.9 — BotFather setup help + Task Service P4).
> SEO Tasks original Task 1 (engine wiring) plus redesign Task 1 (batch engine +
> category/tag/media checks), redesign Task 2 (chat/card UI), and AI content +
> image generation are implemented. Dokploy `data/` volume already covers
> `seo_tasks.db`. Generated SEO copy/images are **not** stored in SQLite;
> WordPress holds them in the modal until Approve.
> **Overview (v0.2.38):** top strip + tool cards now show live metrics for built
> tools (Task Service, Analytics leads, SEO checks, Email audience, Chat
> conversations, Settings health, Brand avatar). Fail soft (`—` /
> connection hint) when the Python service is unreachable — never fake zeros.
> Admin Roles & Social remains an honest coming-soon stub (not started).
> **Settings (v0.2.39):** dark Amy theme + General / Connection tabs, readiness
> banner, health check button, marketing From UI validation.
> **Telegram Admin Bot (v0.2.40 / help v0.2.46):** Settings → Telegram tab; WP
> webhook + whitelist; shared admin conversations with Dashboard Chat —
> **reused** by Task Service outbound (no second bot). v0.2.46 adds BotFather
> deeplink + create-bot/token steps (tokens are buyer-created; no API mint).
> **Task Service P0 (v0.2.41 / service 0.2.5):** Amy vs Someone create/edit mode
> + `amy_capable` + board/list badges.
> **Task Service P1 (v0.2.42 / service 0.2.6):** assign/mid/expiry templates;
> email via FluentSMTP/`wp_mail` From Settings hello@; Telegram via Admin Bot;
> My Profile chat-id link; progress notes on mid Telegram reply; dashboard bell
> kept.
> **Task Service P2 (v0.2.43 / service 0.2.7):** APScheduler state machine
> `none` → `mid_report_asked` (50% of created→due) → `expired`; one mid ask
> (final warning deferred); P1 notify reused; `amy_capable` expiry hook only.
> **Task Service P3 (v0.2.44 / service 0.2.8):** owner/backup escalate on
> expiry (creator → site default → backup); reassign UX in bell + modal.
> **Task Service P4 (v0.2.45 / service 0.2.9):** Amy execution capability
> matrix; Amy-at-create + expiry/`amy_capable` + Amy-take CTA; no fake done.

---

## Priority order (agreed)

1. Submit Your Idea (Finish)
2. Frontend Amy Assistant
3. Dashboard Chat
4. Admin Roles, Permissions & Social Publishing (Telegram, X, LinkedIn, Discord)
5. Analytics Service
6. Task Service — see `08-task-service-plan.md`
7. SEO Tasks — see `06-seo-tasks-plan.md`
8. Email Marketing

---

## ✅ DONE — verified working in production

### 1. Submit Your Idea (full flow)
- Backend (`amy-agent-service`): `POST /v1/submit-idea/{start|answers|confirm|deep-dive-message|contact|upload}`
- Templates for 6 services (`app/data/submit_idea_templates.py`), SQLite sessions w/ 2h TTL
- Frontend (`public/js/submit-idea.js` + `.css`): service cards → dynamic questions → summary
  email + optional WhatsApp first → service cards → questions → summary
  Yes/No → deep-dive chat (with `choice:` pills) → finalize → thank-you
  (`submit_idea_contact_captured` persists `lead_email` as soon as email is shared)
- File uploads (image/PDF) with chip UI, reject bad types
- Emails: admin brief (`contact@ogcnewfinity.com`) + client confirmation
  (`class-amy-submit-idea-mail.php`)
- **Known bug fixed:** deep-dive affirmative-detection (clicking "Yes, everything looks
  correct!" now reliably transitions to `awaiting_contact` instead of looping)
- Confirmation UI: centered `.amy-si-success` card (🎉 copy), accent dot + border on bubbles

### 2. Frontend Amy Assistant (site-wide floating widget)
- `public/js/widget.js` + `public/css/widget.css`, mounted via `class-amy-assets.php`
- `POST /wp-json/amy-agent/v1/chat` → proxies to Python `/v1/chat` → real AI provider
  (Gemini configured) — **confirmed working live**, returns real rendered Markdown
  (clickable links, bold)
- Rate-limited 20 req/IP/60s, nonce-protected, only loads when `ogc_amy_agent_is_active`
- Gated behind: `amy_agent_enabled` option = on + Service URL + Shared Secret set in
  `Settings → Amy Agent` (wp-admin)

### 3. Infrastructure
- Python service deployed on **Dokploy**, separate from the WP host, always-on
  (green/running as of last check), Nixpacks build, GitHub `plugin-amy-agent` repo,
  build path `/amy-agent-service`, branch `main`, autodeploy on push
- Admin pages exist for: Overview, Settings, Brand & Avatar (all functional)
- **Settings (plugin 0.2.39):** dark Amy theme; **General** / **Connection**
  tabs; readiness banner + Enable Amy controls note (widget + Submit Idea);
  marketing From email/name with blocked free-webmail UI; **Check connection**
  against WP `/amy-agent/v1/health` → Python `/v1/health`. Option names
  unchanged; `amy_agent_enabled` checkbox normalize fix kept.
- **Overview metrics (plugin 0.2.38):** live counts for built tools (Task Service
  in-progress/open/urgent, Analytics visitors + hot leads, SEO open/fixed checks,
  Email audience with email, Chat active/this-week). Settings shows service
  configured + health; Brand shows custom vs default avatar. Service-down fails
  soft with `—` / connection hint (never fake zeros). **Admin Roles & Social**
  card remains honest coming-soon (tool not started).

### 4. Task Service — complete (Task 1 + Task 2) + P0–P4 escalation
- Backend: persistent SQLite at `data/tasks.db` (no TTL), FastAPI CRUD + stats,
  escalation schema (`escalation_stage`, `acknowledged_at`, extensions,
  `owner_wp_user_id` / `backup_wp_user_id`), statuses include `running` /
  `failed`, `notifications` + `extension_requests` tables, APScheduler every
  5 minutes, `task_amy_execution` capability matrix
- Behavior: standard **mid@50% progress ask → expiry** (P2; final warning
  deferred); P3 owner escalate on expiry; P4 Amy run on create / expiry
  `amy_capable` / Amy-take; urgent 60m check-ins / any-available-user
  reassignment / `no_one_available`; extension auto-cap (24h normal) vs
  always-approve (urgent)
- WP: Task Service + My Profile notification bell (shared JS/CSS), acknowledge on
  assignee open, Request Extension in edit modal, AJAX proxies for notifications /
  extensions / ack / expiry-action; dashboard user sync (Telegram + backup +
  site default owner); board columns for Amy Running / Failed
- **P0 (plugin 0.2.41 / service 0.2.5):** create/edit **Amy does this** vs
  **Someone does this** (human picker) → `assignee_type`; boolean `amy_capable`
  on create/update/list/get; light mode + Amy-capable badges on board/list.
- **P1 (plugin 0.2.42 / service 0.2.6):** outbound assign/mid/expiry templates
  (dashboard + email + Telegram). Email = FluentSMTP/`wp_mail` From Settings
  (hello@ — not AgentMail/Gmail). Telegram = same Admin Bot token/webhook as
  Settings → Telegram; assignees connect chat id from My Profile. Mid free-text
  Telegram reply → `task_progress_notes`. Service needs `WORDPRESS_BASE_URL`
  for channel relay.
- **P2 (plugin 0.2.43 / service 0.2.7):** scheduler stages
  `none` → `mid_report_asked` → `expired` from `created_at`→`due_date`;
  idempotent mid (legacy `midpoint_sent` / `final_warning_sent` skip re-fire).
- **P3 (plugin 0.2.44 / service 0.2.8):** expiry → resolved owner (creator if
  Telegram-linked + present, else site default owner, else backup); Settings
  site default owner + My Profile backup; bell/modal reassign UX.
- **P4 (plugin 0.2.45 / service 0.2.9):** `AMY_EXECUTION_ENABLED=True`;
  Amy-at-create background run; expiry/`amy_capable` auto-run; Amy-take CTA
  live; allowlisted digital tools only; `done` only after verified audit.

### 5. Analytics — complete (Task 1: plugin + service)
- Backend: persistent SQLite at `data/analytics.db` (90-day retention, purged by
  a second APScheduler job alongside task escalation). Lives in the existing
  Dokploy `data/` volume — no extra volume config needed.
- Event ingestion: `POST /v1/analytics/event` with a fixed event-type allowlist
  (`page_view`, widget, Submit Idea funnel, `contact_form_*`). Unknown types
  rejected with 400. IP geolocation via ip-api.com on first event of a session
  (country/city only; raw IP is not stored). Failures never drop the event.
- Lead scoring: `cold` / `warm` / `hot` computed on ingest and stored on the
  session row. Admin list is ranked hot → warm → cold, then last seen.
- WP: public `POST /wp-json/amy-agent/v1/track` (rate-limited independently of
  chat) forwards via `Amy_Api_Client`. Site-wide `tracking-beacon.js` always
  loads on the front end (not gated by the widget). Public contract:
  `window.amyTrack(eventType, data)`. Widget + Submit Idea fire real events.
- Admin: `amy-analytics` is a real lead list (Visitor / Location / Last seen /
  Signal / Status) with All / Hot / Warm / Cold filter. No charts, no fake
  numbers. Empty state is a genuine empty table when no sessions exist.
- **Theme-side Contact form hooks are NOT in this task.** The backend accepts
  `contact_form_*` events, but nothing fires them until the separate theme
  task lands. The admin page will show real data for page views, widget, and
  Submit Idea immediately; Contact-form-based leads will not populate until
  then.
- **Newsletter tracking is excluded** until the newsletter subscribe feature
  itself has a working backend (would be fake data today). See
  `07-analytics-plan.md`.

### 6. SEO Tasks — original Task 1 + redesign Task 1 (engine) + redesign Task 2 (UI) + AI generation complete
- WP: `class-amy-seo-meta.php` registers Yoast post-meta keys for `post` and
  `page` with `show_in_rest`, so core REST (`/wp/v2/posts/{id}`, `/wp/v2/pages/{id}`)
  can read and write them. Scores (`_yoast_wpseo_linkdex`,
  `_yoast_wpseo_content_score`) are read-only. Featured-image alt is **not**
  re-registered — core already exposes `alt_text` on `/wp/v2/media/{id}`.
- WP taxonomy bridge: `class-amy-seo-taxonomy-meta.php` exposes
  `amy_seo_term_get` / `amy_seo_term_write` through Yoast's
  `WPSEO_Taxonomy_Meta` (`wpseo_taxonomy_meta` option; keys `title`/`desc`).
  Core term meta is not used for Yoast fields. Media still has no extra PHP.
- WP batch proxy: `class-amy-seo-batches-ajax.php` (`amy_seo_batch_start` /
  `continue` / `stop` / `get`) reuses the existing SEO Tasks nonce and
  `manage_options` guard. Python service is unchanged in this UI task.
- Backend: rule-based `check_snapshot()` (posts/pages, unchanged) plus
  `check_term_snapshot()` and `check_media_snapshot()`. FastAPI
  `/v1/seo-tasks/*` behind `X-Amy-Secret`, including the batch engine
  (`/v1/seo-tasks/batches`, continue/stop, per-item isolation, batch_size
  clamped 1–20). Persistent SQLite at `data/seo_tasks.db` (same Dokploy
  `data/` volume — `seo_batch_runs` table, plus `content_type` /
  `batch_run_id` on checks). Successful batch items land in the existing
  pending-approval pool.
- Admin: `amy-seo-tasks` is the chat/card UI — five type buttons (Pages /
  Posts / Categories / Tags / Media), every published item as a card (no
  search box), All/5/10 then Manual/Automatic, or hand-pick cards then Start.
  Manual continue/stop; auto reveals each batch's cards in turn. Checked
  cards open a modal with findings + blank fix-fields + approve/reject.
  Writes: posts/pages via core REST, categories/tags via `amy_seo_term_write`,
  media via `/wp/v2/media/{id}`. History table still uses `amy_seo_checks_list`,
  filtered by the active type.
- **AI generation (0.2.21 / service 0.1.7):** modal "Generate with AI" calls
  `POST /v1/seo-tasks/checks/{id}/generate` and pre-fills missing/weak text
  fields (still editable; still requires Approve). "Generate image" (Gemini
  only) calls `.../generate-image`, previews the image, and uploads to the
  Media Library on approval. Suggestions are not stored in `seo_tasks.db`.
- **Not in this task:** full-site auto-write sweep, Telegram UI, periodic
  re-check scheduling, websockets / live progress streaming, non-Gemini image
  providers. Auto mode is still one HTTP request; the UI just reveals
  reports in sequence.

---

## 🚧 PARTIAL / NEXT

- **Email Marketing** (`amy-email-marketing`) — audience UI wired (2026-11-10),
  Send in **0.2.37**, history/opt-out/Amy propose in **0.2.49** (service
  **0.2.12**). Flow: select audience → Approve draft → **Send now** →
  `wp_mail` / FluentSMTP From **`hello@ogcnewfinity.com`**. Durable thread
  history + manual reply notes + unsubscribe footer. FluentSMTP is
  outbound-only (no AgentMail / Agentic Mail). Optional inbound webhook if
  ops forward mail. Setup: `docs/09-email-marketing-fluentsmtp.md`, plan
  `docs/04-email-marketing-plan.md`.
- **Brand & Avatar** — still stock WP-looking admin UI (avatar only); expanded
  brand/name/tone from `02-dashboard-structure-plan.md` §12 not built yet.
  Settings no longer hosts avatar.

## ❌ NOT STARTED — no code, no admin page, design-only in the roadmap doc

- **Admin Roles, Permissions & Social Publishing** (priority #4) — no
  integration anywhere in the codebase. Formerly labeled "Telegram
  Notifications"; scope expanded and renamed, see
  `05-admin-roles-and-social-publishing-plan.md`.
  Note: Telegram *Admin Bot* (chat surface) is scoped under Dashboard Chat (#3),
  not under this notifications item. Support Bot + News Channel are also in
  `03-dashboard-chat-plan.md` but deferred relative to the admin surfaces.
- **Agent Orchestrator** layer — design locked in `03-dashboard-chat-plan.md`;
  not implemented. `/v1/chat` currently handles everything itself. v1 of #3 is
  Amy the Leader only (no specialist delegation until tools exist).
- **Event-Driven Architecture** (Events / Tasks / Job Queue, e.g. `visitor_started_submit_idea`,
  `high_value_lead`) — not implemented.
- **Shared Memory Service** (company-wide memory: past clients, projects, pricing,
  preferences) — not implemented. Each request is stateless beyond the Submit-Idea
  session TTL.
- **Agent permission system** (Marketing / Analytics / SEO / Task / Support / Admin roles)
  — not implemented, no multi-agent structure exists yet, only one `/v1/chat` endpoint.
- **Confidence Score / Business Health Monitor / Gap Detection** (BI features) — not started.
- **Amy as a Product** (license keys, multi-tenant SaaS) — explicitly deferred, not a
  current priority.

---

## Immediate next candidates (pick one — don't try to do all at once)

Given the agreed priority order and what's already live:

- **Priority #3 — Dashboard Chat**: WP admin chat is live; **Telegram Admin Bot**
  shipped in plugin **0.2.40** (see `docs/03-dashboard-chat-plan.md` §7).
  Admin Analytics: P0 snapshot inject (service) + **P1** richer Q&A / `/analytics`
  + `/Analytics` slash + `GET /v1/analytics/summary` + **P2** SEO Tasks + Task
  Service report-only summaries in admin chat (plugin **0.2.54** / service
  **0.2.14**). Still open: Support Bot, News Channel, website→Telegram link-code
  expiry. Full multi-tool specialists / tool-calling remain later (P3+).
- **Theme-side Analytics Task 2** (does not block the plugin/service pipeline):
  Clarity script tag + Contact form `window.amyTrack(...)` hooks so
  `contact_form_*` events actually fire. Cookie-policy copy update
  (`legal-cookie-policy.md`) is also still outstanding from `07-analytics-plan.md` §5.
- **Submit Your Idea 4.2 improvements** (still priority #1 territory): autosave draft,
  follow-up if visitor abandons page — lead scoring now lives under Analytics
  (`07-analytics-plan.md`) and is implemented for Task 1.
- **Admin Roles, Permissions & Social Publishing** (#4): admin roles,
  invitations, usage limits, and multi-platform (Telegram/X/LinkedIn/
  Discord) automated publishing via the pluggable
  notification layer — distinct from the Admin Bot chat surface in #3.

Analytics Task 1 (plugin + service) shipped 2026-08-18. SEO Tasks original
Task 1 (Yoast REST wiring + single-target approval) shipped 2026-08-18;
redesign Task 1 (batch engine + category/tag/media checks) shipped
2026-08-18; redesign Task 2 (chat/card UI) shipped 2026-08-19; AI content
+ image generation shipped 2026-08-19 (plugin 0.2.21 / service 0.1.7). The
full SEO Tasks flow is now live end to end in wp-admin, including
pre-filled AI suggestions before approval. Email Marketing (#8)
stays after Dashboard Chat. Email Marketing still depends on Dashboard Chat +
Analytics; cold-outreach compliance still open before that goes live.
Specialist `/` commands stay off until Analytics + SEO + Email Marketing all
exist (Analytics Task 1 is the plugin/service half; theme Contact hooks are
the remaining Analytics gap).

---

## Session hygiene rule (new, per Wael's request)

- Before starting any new work session on Amy Agent: open this file first.
- Before ending a session: update the "DONE" / "STUB" / "NOT STARTED" sections to match
  reality, based on actual code inspection — not on what was *intended* to be done.
