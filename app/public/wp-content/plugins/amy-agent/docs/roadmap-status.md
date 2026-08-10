# Amy Agent — Roadmap & Real Build Status

> **Purpose of this file:** single source of truth so any session (Claude, Cursor, or Wael)
> can open this file first and know exactly what is built, what is a stub, and what's next —
> without re-discovering it from scratch. **Update this file at the end of every work session,
> before closing.** Keep it in `amy-agent/docs/roadmap-status.md`.
>
> Last verified against code: 2026-08-10 (amy-agent v0.2.11, live Python service confirmed
> running on Dokploy — repo `plugin-amy-agent`, path `/amy-agent-service`, branch `main`).

---

## Priority order (agreed)

1. Submit Your Idea (Finish)
2. Frontend Amy Assistant
3. Dashboard Chat
4. Admin Roles, Permissions & Social Publishing (Telegram, X, LinkedIn, Discord)
5. Analytics Service
6. Task Service
7. SEO Service
8. Email Marketing

---

## ✅ DONE — verified working in production

### 1. Submit Your Idea (full flow)
- Backend (`amy-agent-service`): `POST /v1/submit-idea/{start|answers|confirm|deep-dive-message|contact|upload}`
- Templates for 6 services (`app/data/submit_idea_templates.py`), SQLite sessions w/ 2h TTL
- Frontend (`public/js/submit-idea.js` + `.css`): service cards → dynamic questions → summary
  Yes/No → deep-dive chat (with `choice:` pills) → contact (email + optional WhatsApp) → thank-you
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

---

## 🚧 STUB ONLY — menu item exists, page says "Coming soon.", zero logic behind it

Confirmed by direct code read of `includes/class-amy-admin-menu.php` (the `$placeholders`
array) — these are **not partially built**, they are literally one hardcoded string each:

- **Chat** (`amy-chat`) — priority #3 Dashboard Chat. Nothing built. Plan locked:
  `docs/03-dashboard-chat-plan.md` (WP admin + Telegram Admin Bot as Amy the
  Leader with conversation memory; specialists/`/` deferred until tools exist).
- **Analytics** (`amy-analytics`) — priority #5. Nothing built. Plan approved:
  `docs/07-analytics-plan.md` (decisions locked 2026-08-10; no code yet).
- **SEO Tasks** (`amy-seo-tasks`) — priority #7. Nothing built.
- **Email Marketing** (`amy-email-marketing`) — priority #8 stub page; plan locked:
  `docs/04-email-marketing-plan.md`. Not a newsletter tool — Amy-triggered
  1-to-1 sends via Hostinger Agentic Mail REST + `message.received` webhook.
  Builds after Dashboard Chat + Analytics; FluentSMTP stays for WP transactional.

## ❌ NOT STARTED — no code, no admin page, design-only in the roadmap doc

- **Telegram Notifications** (priority #4) — no integration anywhere in the codebase.
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

- **Priority #3 — Dashboard Chat** (default next): WP admin chat + Telegram Admin
  Bot → Amy the Leader, multi-conversation memory on Python side, `mode: "admin"`.
  Spec: `docs/03-dashboard-chat-plan.md`. Still open before a Cursor prompt:
  BotFather setup + admin User ID whitelist storage, conversation schema,
  website→Telegram link-code expiry. No working `/` specialists in this phase.
- **Submit Your Idea 4.2 improvements** (still priority #1 territory): autosave draft,
  follow-up if visitor abandons page — lead scoring now lives under Analytics
  (`07-analytics-plan.md`), not as a separate SI-only feature.
- **Telegram Notifications** (#4): event alerts (e.g. hot lead) via the pluggable
  notification layer — distinct from the Admin Bot chat surface in #3.

**Do not jump to Analytics/SEO/Email Marketing (#5–#8) implementation yet** —
Analytics plan is approved (`07-analytics-plan.md`) but stays after #3 ships
(then Analytics is the first real tool, per `03-dashboard-chat-plan.md` §5).
Email Marketing plan is locked (`04-email-marketing-plan.md`) but depends on
Dashboard Chat + Analytics; cold-outreach compliance still open before that
goes live. Specialist `/` commands stay off until Analytics + SEO + Email
Marketing all exist.

---

## Session hygiene rule (new, per Wael's request)

- Before starting any new work session on Amy Agent: open this file first.
- Before ending a session: update the "DONE" / "STUB" / "NOT STARTED" sections to match
  reality, based on actual code inspection — not on what was *intended* to be done.
