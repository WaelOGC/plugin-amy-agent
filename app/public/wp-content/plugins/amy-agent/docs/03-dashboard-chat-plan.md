# Amy Agent — Dashboard Chat & Orchestrator Plan (Final)

> Location: `amy-agent/docs/03-dashboard-chat-plan.md`
> Status: **Decisions locked. No code yet — this is the spec to build a Cursor
> prompt from, once Wael gives explicit go-ahead to write that prompt.**
> Priority: **#3** in the agreed roadmap order — the next thing to build after
> Submit Your Idea + Frontend Amy Assistant (both done).

---

## 1. What this actually is

Not just an admin chat page. This is **Amy becoming a real orchestrator** —
the same Amy, with the same memory and the same abilities, reachable from
three different places:

1. **WordPress admin dashboard** (replaces the `amy-chat` "Coming soon." stub)
2. **Telegram — Admin Bot** (private, Wael + future authorized admins only)
3. **Telegram — Support Bot** (public-facing, for site visitors/customers)

Plus a fourth, separate, non-chat channel:

4. **Telegram — News/Announcements Channel** (broadcast only, one-way)

Wael gives Amy a task from any of the first three surfaces, and she works on
it — this is explicitly meant to feel like "an agent working for you 24/7,"
not just a Q&A widget.

## 2. What already exists and gets reused

- `POST /v1/chat` on the Python service — already routes to the configured AI
  provider and returns a reply. No new provider integration needed.
- `api-contract.md` already defines a `mode` field (`general` | `submit_idea` |
  `support`) — this becomes a 4th value, `mode: "admin"`.
- `X-Amy-Secret` auth between PHP and Python — reused as-is for the WP route.

## 3. Locked architectural decisions

### 3.1 Conversations
- **Multiple named conversations**, ChatGPT-style — not a single endless
  thread. Wael can start a new conversation and browse past ones.
- **Storage: Python service side** (not a WP custom table). This keeps all of
  Amy's memory in one place — same side where Analytics data will live —
  rather than splitting the "brain" across WordPress and Python. This matters
  for the incoming second developer, who needs one system to extend, not two.
- **Business context is loaded from day one.** Amy in admin mode knows the
  services list and current roadmap priorities from the start, rather than
  starting as a blank generic chat and having context bolted on later.

### 3.2 Specialist agents & slash commands
- Typing `/` invokes a specific specialist agent/tool directly, e.g.:
  - `/Analytics`
  - `/SEO Tasks`
  - `/Email Marketing`
  - (and any future tool, added the same way)
- **No `/` = talking directly to Amy the Leader**, the orchestrator herself.
- **Hybrid request style after a command:** typing `/Analytics` surfaces
  ready-made quick suggestions (autocomplete-style), but Wael (or any future
  admin) can also type a fully custom free-form request after the command —
  e.g. `/Analytics compare visitors from the Netherlands over the last 3 days`.
- **Amy the Leader can also auto-invoke a specialist without a `/` command**,
  if she determines from the conversation that a specific tool is the right
  fit. The `/` command is a manual shortcut, not the only path.
- **Rollout timing:** all specialist commands go live together, once all
  underlying tools (Analytics, SEO Tasks, Email Marketing) are actually built
  — not staggered one at a time. Until then, this chat runs as Amy the Leader
  only, with no working `/` commands yet.

### 3.3 Channels in detail

**WordPress Admin Dashboard + Telegram Admin Bot** — same Amy, same memory,
same slash commands, same specialist agents. Effectively two front doors to
one orchestrator.
- Telegram Admin Bot is **private**: authenticated via a **whitelist of
  Telegram User IDs** stored in WordPress (`amy_agent_telegram_admins`).
  Telegram posts updates to
  `POST /wp-json/amy-agent/v1/telegram/webhook` (secret header); WordPress
  proxies to Python `POST /v1/chat` with `mode: "admin"` and replies via
  `sendMessage`. Any message from a `user_id` not on the whitelist gets a
  one-per-minute reply with that user's Telegram ID and setup instructions.
  No OAuth or login flow needed for a small, known admin set.
- Slash-command autocomplete should work in this bot too, not just in
  WordPress.

**Telegram Support Bot** — public, customer-facing.
- No whitelist — anyone can start a conversation, same as the public floating
  widget on the site today.
- **Rate limiting required**, mirroring the existing `/v1/chat` protection
  (20 req/IP/60s on the web), adapted to Telegram's `chat_id` instead of IP.
- Can route a customer toward a relevant page based on conversation context —
  conceptually the same behavior as the Submit Idea widget, just via Telegram.
- **Session linking with the website widget**: when a customer wants to
  continue a website conversation inside Telegram, a short link/code is
  issued (e.g. "send this code to the support bot: `#A93F`") to connect the
  two sessions. This is a deliberate manual step, not automatic — there is no
  reliable technical way to recognize "this is the same visitor" across a
  website session and a Telegram `chat_id` without one.

**Telegram News/Announcements Channel** — broadcast only.
- One-way publishing of articles, news, and updates.
- Followers can react (e.g. likes) but **cannot comment or message** — no
  two-way interaction of any kind. This is explicitly not a chat surface.

## 4. What this is *not*, yet

- **Specialist tools (P3/P4 live for Analytics / traffic / Email audience /
  SEO / Tasks):** Admin chat (`mode: admin`) runs an Amy-the-Leader tool
  loop with allowlisted `analytics_summary`, `analytics_leads_query`,
  `analytics_traffic`, `email_audience_summary`, `seo_summary`, and
  `task_stats`. Intent auto-invokes without slash; `/analytics` /
  `/Analytics` remain shortcuts. Email audience is read-only (Approve → Send
  unchanged; no AgentMail).
- **No attachment-source picker yet.** The attach control is a single
  "upload from your device" path only — not a menu to choose upload vs.
  screenshot vs. import from GitHub/Drive/etc. the way some AI chat products
  offer behind their attach button.
- **No live internet search/browsing yet.** Amy only has her own general
  knowledge, not live search, so she cannot look up competitor pricing or
  current market info on demand.

## 5. Public widget memory (visitor-scoped)

The public floating widget now persists conversation memory in the same
`conversations` table used by the admin dashboard chat, using a sentinel
`wp_user_id = 0` for anonymous rows and a browser-generated `visitor_id`
(stored in `localStorage`) as the actual ownership key. Retention follows
the same existing 90-day policy — no separate policy was introduced.

There is intentionally no admin-facing UI for these conversations yet
(no list/rename/delete/export support for the public path) — this step is
backend continuity only. Admin visibility, if wanted, is a future step
alongside Analytics.

## 6. Build order implication

This plan confirms the multi-channel orchestrator shape, but the actual
sequence stays as previously agreed:
1. Dashboard Chat (WordPress) + Telegram Admin Bot, talking to Amy the Leader
   only, with conversation memory — no working specialist commands yet.
2. Analytics gets built next (per `07-analytics-plan.md`) as the first real
   tool.
3. Slash commands (`/Analytics`, `/SEO Tasks`, `/Email Marketing`) go live
   together once their underlying tools all exist.
4. Telegram Support Bot and News Channel can be built in parallel or after,
   depending on priority — not blocking the admin-side orchestrator.

## 7. Telegram Admin Bot (implemented — plugin 0.2.40)

- **Webhook:** Telegram → WordPress
  `POST /wp-json/amy-agent/v1/telegram/webhook` with header
  `X-Telegram-Bot-Api-Secret-Token`. Wrong/missing secret → 403.
- **Ownership:** Bot token, webhook secret, and admin whitelist live in
  WordPress options only; Python is unchanged (no stored Telegram or AI
  secrets on the service).
- **Conversations:** Same Python `conversations` rows as Dashboard Chat
  (`mode: "admin"`, linked `wp_user_id`). Chat→conversation map in
  `amy_agent_telegram_chats`.
- **Settings UI:** Amy → Settings → **Telegram** tab — enable flag, token,
  Connect / Disconnect / status / test, whitelist table (max 10).
- **Commands:** `/start`, `/help`, `/whoami`, `/new` (other `/` → unknown).
  Plain text → Amy reply (HTML from Markdown). Non-text → text-only notice.
- **Not built yet:** Telegram Support Bot, News/Announcements Channel (still
  §3.3 concepts only).

## 8. Still to decide

- Exact BotFather steps for the **Support** bot (when built).
- Whether website→Telegram session-link codes expire, and after how long.
