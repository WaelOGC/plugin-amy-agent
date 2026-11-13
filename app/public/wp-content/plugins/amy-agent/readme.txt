=== Amy Agent ===
Contributors: ogcnewfinity
Tags: ai, chat, assistant, ogc-newfinity
Requires at least: 6.0
Tested up to: 6.8
Requires PHP: 8.0
Stable tag: 0.2.66
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Digital employee for OGC NewFinity. Floating chat widget powered by a Python service and admin-selected AI providers.

== Description ==

Amy Agent is the customer-facing AI layer for OGC NewFinity. The WordPress plugin handles hooks, admin settings, and the floating chat widget; a separate Python service owns intelligence and calls the admin-selected AI provider.

== Installation ==

1. Activate the plugin in WordPress.
2. Go to Amy → Settings and configure the Python service URL, shared secret, AI provider, and API key. Turn on Enable Amy.
3. Run the sibling `amy-agent-service` Python process (see that service's README).
4. Reload any front-end page — the floating Amy widget should appear.
5. For Email Marketing: each site sets Marketing From in Amy → Settings (own domain mailbox + FluentSMTP). Empty falls back to hello@ogcnewfinity.com. Deploy service 0.2.12+ for send/reply history.
6. For Task Service outbound: set `WORDPRESS_BASE_URL` on the Python service; enable Telegram under Amy → Settings → Telegram; assignees link chat id from Amy → My Profile. Create the Admin Bot via BotFather (Settings → Telegram has the deeplink + steps).

== Changelog ==

= 0.2.66 =
* Telegram Admin Bot: Markdown→HTML converter turns headings (`###` / `##`) into bold lines and `*`/`-` bullets into `•` (no raw `#` / list markers in replies). Supports blockquotes for Next-step boxes.
* Requires service 0.2.26+ for consistent admin-chat reply structure (bold sections, pill counts, 📍 rows, no repeated numbers).

= 0.2.65 =
* UI-only: redesign Amy → Overview and Amy → Settings (General / Connection / Telegram) with a card grid, pill toggle switches, and (?) help popovers (explanatory text no longer permanently inline).
* Shared admin-ui CSS/JS primitives for reuse on other Amy admin pages in a follow-up.

= 0.2.64 =
* Public chat uploads: show a friendly rate-limit message when the server returns 429 / error `rate_limited` (i18n key `uploadRateLimited`), instead of the generic upload-failed string.

= 0.2.63 =
* Fix public chat attachments: sanitize_messages keeps empty-content messages that have files, and forwards AttachmentRef fields (url, filename, content_type, id, kind, size) to the service /v1/chat.
* Attachment-only messages (PDF/image, no typed text) no longer fail with “At least one message is required.”

= 0.2.62 =
* Upload security: early 5 MB / UPLOAD_ERR checks; per-IP (10/h) + global (200/h) rate limits; forward X-Amy-Client-Ip to service.
* Widget: one-line textarea auto-grow; attach popover (image/PDF); upload-info "?" popover; one-time sensitive-data notice; history titles from generated title / first message.
* Requires service 0.2.22+ (rebuild for Pillow + PyMuPDF if not already).

= 0.2.61 =
* Public chat polish: history date+time + preview, lazy conversation create, subtitle modes, custom scrollbars, auto-growing textarea.
* Secure visitor file uploads (JPEG/PNG/WebP/PDF), Settings toggles, admin email + Telegram notify. Requires service 0.2.21+.

= 0.2.60 =
* Public widget: message times + date separators; New chat; History list; desktop expand mode (backdrop, focus trap, Esc, localStorage).
* Stronger emoji + closing-wish rules (wish only when hint present; already-sent system line).
* Service 0.2.20: `GET /v1/conversations/by-visitor`; message `created_at` on conversation detail.

= 0.2.59 =
* Friendlier public chat tone; widget Markdown headings/lists; optional closing wishes (timezone + Settings toggle).
* Analytics: `chat_closing_wish` event + last-30d with/without closing-wish → Submit Idea split.
* Service 0.2.19: closing-wish calendar module, once-per-conversation hint, `/v1/analytics/closing-wish-effect`.

= 0.2.58 =
* Public chat: live theme price catalogue (`pricing_catalogue`) from `ogc_get_pricing_data()` via theme bridge; cached 1h.
* Service 0.2.18: optional `pricing_catalogue` on `/v1/chat`; append delimited price list to public system prompt; Amy quotes listed EUR prices.

= 0.2.57 =
* Fix admin chat 502 with Gemini: strip unsupported JSON Schema keys (e.g. additionalProperties) from functionDeclarations.parameters before generateContent.
* Service 0.2.17: sanitize Gemini tool parameter schemas on the request path; unit test covers no additionalProperties in payload.

= 0.2.56 =
* Admin chat P4: page_view traffic depth + read-only Email Marketing audience tools (analytics_traffic, email_audience_summary); Approve → Send unchanged; no AgentMail.
* Service 0.2.16: GET /v1/analytics/traffic + GET /v1/analytics/email-audience; wire into admin tool loop / intent auto-invoke.

= 0.2.55 =
* Admin chat P3: Amy the Leader tool-calling loop (analytics_summary, analytics_leads_query, seo_summary, task_stats); intent auto-invoke; slash remains shortcut.
* Service 0.2.15: provider function calling (Gemini/OpenAI/Anthropic/DeepSeek) for mode:admin.

= 0.2.54 =
* Admin chat P2: SEO Tasks + Task Service live summaries on Telegram + Dashboard Chat (report-only).
* Service 0.2.14: inject SEO/open + task board stats into mode:admin alongside Analytics.

= 0.2.53 =
* Analytics P1: richer admin chat snapshot (with_email, hot sample, last-seen windows, Submit Idea email captures).
* Telegram `/analytics` + Dashboard Chat `/Analytics` shortcut; Help lists `/analytics`.
* Service 0.2.13: `GET /v1/analytics/summary` shared contract (+ optional `include_emails`).

= 0.2.52 =
* Client help P3: WP Screen Help tabs on Amy Settings, Email Marketing, and Task Service mirroring in-panel cards (shared PHP string getters).
* Whitelist column tooltips (Telegram user ID vs label vs linked WP user).
* Soften client-facing “Dokploy” jargon to “Amy Python service host”; BotFather/ID copy notes messaging the bot first (Telegram tutorial alignment).

= 0.2.51 =
* Client help P2: Settings → General FluentSMTP buyer playbook (mailbox → FluentSMTP → SPF/DKIM → Amy From → test send).
* Links FluentSMTP → Connections when active; otherwise Install FluentSMTP / Plugins note.
* Email Marketing From banner: expandable playbook; hello@ only as example default; no AgentMail.

= 0.2.50 =
* Client help P1: Settings readiness lists Telegram (enabled / token / webhook), optional Marketing From, and optional AI key — each item deep-links to the fix card (#telegram, #general-from, Connection, #ai-key).
* Task Service empty-state and load-error point to Settings → Connection plus Telegram + My Profile.
* My Profile: clearer Amy → Settings → Telegram path; three-step bot status (token → Enable → Connect).

= 0.2.49 =
* Email Marketing: FluentSMTP send history + reply notes in Amy service (no AgentMail / Agentic Mail).
* Opt-out footer + public unsubscribe + suppression check before send.
* Amy propose hook (stores draft only; still requires human Approve → Send).
* Optional authenticated email-inbound webhook; FluentSMTP remains outbound-only.
* Settings: each site configures its own Marketing From; buyers use their domain mailbox + FluentSMTP. Empty → hello@ogcnewfinity.com. Blocked From keeps the previous valid address.
* Service 0.2.12: `email_threads` / `email_messages` / `email_suppressions` APIs.

= 0.2.48 =
* Client help P0: fix Telegram ID instructions (/whoami + unlisted deny path; @userinfobot fallback).
* Settings → Telegram: Not-connected next-steps list; actionable missing-config errors (token / Enable / HTTPS / Connect).
* Email Marketing + Settings: dynamic From in errors; FluentSMTP → Connections where-link; Marketing From name hint.
* Empty From still defaults to hello@ogcnewfinity.com as example; no AgentMail.

= 0.2.46 =
* Settings → Telegram: prominent BotFather deeplink (opens in a new tab) plus concise create-bot / copy-token steps.
* Notes that Telegram does not mint tokens via API — each buyer/team creates their own bot.

= 0.2.45 =
* Task Service P4: Amy execution capability matrix — Amy-at-create runs in background (`todo` → `running` → `done`/`failed`).
* Expiry + `amy_capable`: Amy runs real digital/in-system allowlisted work (never fake done from the clock).
* “Let Amy take it” CTA enabled for capable tasks (bell + modal).
* Board columns: Amy Running + Failed. Service 0.2.9: `AMY_EXECUTION_ENABLED=True`, `task_amy_execution` engine + audit progress notes.

= 0.2.44 =
* Task Service P3: expiry escalates to resolved owner (creator → site default owner if no Telegram/gone → backup).
* Settings: site default task owner; My Profile: designate personal backup; sync includes Telegram link flags.
* Expiry UX: bell + task modal reassign (same/other), acknowledge; “Let Amy take it” shown when amy_capable but disabled until P4.
* Service 0.2.8: owner/backup fields, expiry-action API, owner resolution + grace reassign window.

= 0.2.43 =
* Task Service P2: scheduler state machine assign → one mid progress ask at 50% of deadline window → expiry (no +4h final warning).
* Stage `mid_report_asked` (legacy `midpoint_sent` / `final_warning_sent` still recognized, no double-fire).
* Expiry keeps P1 notify + creator handoff; `amy_capable` logs a P4 hook only — never fake Amy completion.
* Service 0.2.7: APScheduler + SQLite stages aligned to locked mid/expiry decisions.

= 0.2.42 =
* Task Service P1: assign / mid-progress / expiry templates with outbound email (wp_mail → FluentSMTP From Settings hello@) and Telegram (reuses Admin Bot #11).
* Dashboard bell kept; new `task_assigned` + `mid_progress_ask` notification types.
* My Profile: Telegram connect/unlink for task alerts (deep link `/start connect_<code>`).
* Progress notes: free-text Telegram replies after a mid ask are stored on the task.
* Service 0.2.6: `WORDPRESS_BASE_URL` relay to `/wp-json/amy-agent/v1/task-notify`; progress-notes API.

= 0.2.41 =
* Task Service P0: create/edit modal uses clear **Amy does this** vs **Someone does this** (human picker) wired to `assignee_type`.
* Task Service: `amy_capable` boolean on tasks (create/update/list/get); light Amy/Human + Amy-capable badges on board/list. No Amy execution yet — honest status only.
* Service 0.2.5: persist `amy_capable` on `tasks.db` (migrated).

= 0.2.40 =
* Telegram Admin Bot: Settings → Telegram tab (token, whitelist, Connect/Disconnect/test).
* Webhook at `/wp-json/amy-agent/v1/telegram/webhook`; WordPress owns token, secret, and whitelist; proxies to Python `/v1/chat` (`mode: admin`). Conversations shared with Dashboard Chat.

= 0.2.39 =
* Settings: dark Amy admin theme (Space Grotesk / Inter) matching Overview / Email Marketing.
* Settings: tabbed UI — General (Enable Amy, marketing From) and Connection (service URL, secret, AI provider/key/model).
* Settings: readiness banner, “what Enable Amy controls” note, connection health check via `/wp-json/amy-agent/v1/health`, and From-email UI validation (blocks Gmail / AgentMail / free webmail).

= 0.2.38 =
* Overview: wire top strip + tool cards to real Task Service / Analytics / SEO / Email audience / Chat counts (server-side via Amy_Api_Client). Fail soft with — when the service is down; no fake zeros. Admin Roles & Social stays honest coming-soon. Settings/Brand show configured/health/avatar status.

= 0.2.37 =
* Email Marketing: after Approve, explicit admin **Send now** delivers via wp_mail (FluentSMTP) From hello@ogcnewfinity.com (configurable in Settings). Never silent; no Gmail/AgentMail.
* Settings: Marketing From email/name; UI shows From clearly. Docs: FluentSMTP/DNS setup for hello@.

= 0.2.36 =
* Analytics / Email Marketing: surface the real Amy service proxy error when admin-ajax fails (connection refused, missing URL/secret, upstream 401), instead of only the generic "Could not load leads" copy. Connection failures now return HTTP 502.

= 0.2.35 =
* Submit Idea: ask for email (and optional WhatsApp) first, before service Q&A, and fire `submit_idea_contact_captured` so Analytics stores `lead_email` even if the visitor abandons later.

= 0.2.34 =
* Email Marketing: multi-select audience (checkboxes + select-all) feeds draft recipients; approve still stores local draft only (no send).
* Email Marketing: lightweight SVG/CSS charts — Hot/Warm/Cold donut, last-seen buckets, signal mix bars.
* Email Marketing extras: email search, Needs follow-up (Hot), export selected CSV, sticky selected count bar.

= 0.2.33 =
* Email Marketing: give draft message its own DOM id so the composer is not tied to the audience table body.

= 0.2.32 =
* Email Marketing: audience analysis strip — With email / Hot / Warm / Cold counts, coverage meter, recent signals (Analytics-matched theme).

= 0.2.31 =
* Analytics: "With email" filter on the lead list (API `has_email`).
* Email Marketing: audience from Analytics visitor emails, draft composer, human approve only — no auto-send (Hostinger send still pending).

= 0.2.28 =
* Dashboard Chat: stop horizontal scrollbar on long conversation titles in the sidebar list.

= 0.2.27 =
* Dashboard Chat: render Markdown "* item" lines as real bullet lists in Amy's replies.

= 0.2.26 =
* Dashboard Chat visual rework: sidebar user avatar footer, flatter message bubbles, and a single-boundary composer with an icon send button.

= 0.2.25 =
* Dashboard Chat: admin persona with staff identity, safe Markdown in Amy's bubbles, compact sidebar rows, auto-growing composer, and draft-first new chats (create on first send).

= 0.2.24 =
* Dashboard Chat: talk with Amy the Leader from wp-admin, with persistent conversations, rename/delete/export, and image or PDF attachments.

= 0.2.23 =
* SEO Tasks: write Title and Caption on AI-generated featured images (not only alt text).
* SEO Tasks: when Amy uploads a featured image, fill empty Facebook/X image URL fields with that image.
* SEO Tasks: show Yoast SEO and Readability score dots next to Amy's verdict on cards and history.

= 0.2.22 =
* Fixed %1$d placeholder showing literally instead of a number in the AI log message.
* Approving a check now auto-rechecks the item so the badge shows the fresh verdict.

= 0.2.21 =
* SEO Tasks: AI-generated suggested copy (focus keyphrase, SEO title, meta
  description, OG/Twitter fields) via the configured provider, pre-filled and
  editable in the modal before approval.
* SEO Tasks: AI-generated featured image (Gemini only), previewed and uploaded
  to the Media Library on approval.
* Fixed a generic "Request failed." error that hid the real cause of failed
  Amy Agent service requests.

= 0.2.20 =
* SEO Tasks redesign Task 2: chat-driven card UI for pages, posts, categories, tags, and media, with batch start/continue/stop.

= 0.2.19 =
* SEO Tasks: Yoast category/tag title and meta-description bridge (WPSEO_Taxonomy_Meta), plus optional content_type filter on check history.

= 0.2.18 =
* SEO Tasks Task 1: Yoast meta on core REST, single-target SEO check, and approval-before-write admin page.

= 0.2.11 =
* Temporary build watermark for live deployment verification.

= 0.2.10 =
* Stronger Amy/You bubble distinction (accent edge + sender dots, chat padding); restore terminal centered success card on submit.

= 0.2.9 =
* WhatsApp country-code dropdown on the in-chat contact step; finer LED-style dot-pattern tray background.

= 0.2.8 =
* Auto-growing composer with Shift+Enter newlines, in-chat contact step, and chat-clearing confirmation message.

= 0.2.7 =
* Phase 2: unified conversational chat tray for Submit Your Idea (service pills, one-at-a-time questions, deep-dive in one scroll view).

= 0.2.0 =
* Phase 2: public chat REST route, floating widget, rate limiting. Python providers call real APIs.

= 0.1.0 =
* Phase 1 scaffold: admin settings, theme bridge stubs, REST health, API contract docs.
