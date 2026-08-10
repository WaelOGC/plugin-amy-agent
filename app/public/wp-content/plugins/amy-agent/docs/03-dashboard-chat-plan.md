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
  Telegram User IDs** held on the Python service. Any message from a
  `user_id` not on the whitelist is ignored / gets an "unauthorized" reply.
  No OAuth or login flow needed for a single admin (or a small, known set of
  admins).
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

- **Not fully multi-agent on day one.** No SEO/Analytics/Email specialist
  tools exist yet for `/` commands to call. Amy the Leader talks using the
  same single-agent loop as the current widget until the first real tool
  (Analytics) is built and the specialist commands are switched on together.
- Building empty delegation logic before there's a real tool to delegate to
  would mean guessing at a shape we don't actually know yet — this plan is
  written so today's build doesn't block that later step, not so it jumps
  ahead of it.

## 5. Build order implication

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

## 6. Still to decide before a Cursor prompt is written

- Exact Telegram bot setup steps (BotFather config for both bots) and where
  the whitelist of admin User IDs is stored/managed on the Python side.
- Exact schema for conversation storage on the Python service (conversation
  list, messages, timestamps) — not yet designed, just located (Python side).
- Whether website→Telegram session-link codes expire, and after how long.
