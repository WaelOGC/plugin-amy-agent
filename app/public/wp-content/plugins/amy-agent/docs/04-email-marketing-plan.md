# Amy Agent — Email Marketing Plan (Final)

> Location: `amy-agent/docs/04-email-marketing-plan.md`
> Status: **Decisions locked.** Outbound = FluentSMTP / `wp_mail` From
> **`hello@ogcnewfinity.com`**. History + opt-out + Amy propose hooks ship in
> plugin **0.2.49** / service **0.2.12**. **No AgentMail**, no personal Gmail,
> no Hostinger Agentic Mail client for marketing.
> Priority: comes after Dashboard Chat (#3) and Analytics, since Email
> Marketing consumes data Analytics produces and is triggered through the
> Dashboard Chat / Amy the Leader orchestrator.

---

## 1. What this actually is

The **sending layer** Amy uses to reach out to a specific person by email —
follow-ups after a visitor is identified as a lead (via Analytics), or after
Amy researches a company and drafts an outreach message on request.

This is explicitly **not** a mass-newsletter/campaign tool. It is built for
**personalized, individually-triggered sends**, decided and drafted by Amy
herself — matching the project's core principle that Amy is the "brain" and
her tools are simple executors.

## 2. What it is not (scope boundaries)

- **Not a bulk newsletter/campaign platform.** If a real mass-broadcast
  newsletter is needed later (thousands of recipients in one send), that is a
  separate, future decision — likely Hostinger Reach — and out of scope here.
- **Not AgentMail / Hostinger Agentic Mail.** Marketing never uses
  `@agentmail.to` or the Agentic Mail REST send path. Transactional WP mail
  and marketing both ride FluentSMTP; marketing overrides From to hello@.
- **Not the place where leads get identified or researched.** IP-to-company
  identification lives in Analytics; researching companies and drafting the
  first message is a capability of Amy the Leader herself. This tool's only
  job is the final step: sending (after human Approve → Send for cold
  outreach).

## 3. Locked decisions

### 3.1 Sending infrastructure: FluentSMTP + per-site From
- **Outbound:** WordPress `wp_mail()` → **FluentSMTP**. Each site sets
  **Marketing From** in Amy → Settings (own domain mailbox + FluentSMTP auth).
- **OGC NewFinity default / empty fallback:** `hello@ogcnewfinity.com`.
- Hard rules: no personal Gmail, no AgentMail (`@agentmail.to`), human
  **Approve** then explicit **Send** click. Cap recipients per batch (default
  50). See `09-email-marketing-fluentsmtp.md`.
- **Inbound limitation:** FluentSMTP is outbound-only. Automatic hello@
  mailbox receive is **not** wired. Durable send history + **manual reply
  notes** live in the Python service. Optional authenticated webhook
  `POST /wp-json/amy-agent/v1/email-inbound` (and service
  `/v1/email-marketing/inbound`) can store forwarded mail if ops set that up
  later — still not AgentMail.

### 3.2 Plan / limits
- Personalized 1-to-1 / small-batch follow-ups only.
- Soft plugin cap (filter `amy_email_marketing_max_recipients`, default 50).
- Deliverability depends on hello@ mailbox + FluentSMTP auth + SPF/DKIM
  (Abdulla ops — not code).

### 3.3 What triggers a send
- Human admin: Email Marketing UI (audience → draft → Approve → Send).
- **Amy propose hook** (service/WP): `POST …/email-marketing/propose` stores a
  `proposed` message in history and **never sends**. Cold outreach still
  requires Wael/admin Approve → Send in the UI.
- WP actions for integrators: `amy_email_marketing_before_send`,
  `amy_email_marketing_send_result`, `amy_email_marketing_after_send`,
  `amy_email_marketing_propose`.

## 4. Locked decisions (continued)

### 4.1 Who Amy can reach out to
Cold outreach targets are not limited to companies. Amy can be pointed at
either of two kinds of targets:
- **Companies** — surfaced automatically via Analytics (Hot/Warm/Cold lead
  scoring), as already described in section 3.3.
- **Specific individuals** — e.g. an influencer or creator Wael has noticed
  on TikTok/Instagram/Facebook who doesn't have a website or clear online
  business presence yet. Wael gives Amy the name/profile manually via
  Dashboard Chat or Telegram Admin Bot. Amy researches, drafts, and — same
  as with companies — proposes / requests confirmation before sending.

### 4.2 Confirmation rule before sending
A single rule governs whether Amy needs Wael's approval before a message
goes out, and it depends only on **who initiated contact first** — not on
message content:
- If **Amy is initiating contact** (cold outreach), Amy must present the
  drafted message and get explicit confirmation before sending (UI Approve →
  Send, or an approved propose).
- If **the customer/lead initiated contact** (they messaged us first, or
  replied to a prior message), Amy can respond freely without asking for
  approval each time — once inbound is available. Until then, humans log
  inbound via reply notes; automatic Amy reply-without-approve remains
  gated on real inbound.

### 4.3 Message history storage
Sent / proposed / manual inbound / notes are stored in the **same Python
service SQLite file** as Dashboard Chat (`conversations.db` tables
`email_threads`, `email_messages`, `email_suppressions`). Admin UX:
Email Marketing → **Send & reply history**.

### 4.4 Legal / GDPR note (non-binding)
Cold outreach has real legal considerations under Dutch/EU rules:
- Documented legitimate-interest basis.
- **Clear opt-out in every cold-outreach message** (footer Unsubscribe link
  → `GET /wp-json/amy-agent/v1/email-opt-out` + suppression list checked
  before send).
- Legal review before cold outreach goes live with real recipients —
  scheduling decision, not a technical open item.

## 5. Shipped surface (0.2.49 / service 0.2.12)

| Piece | Where |
| --- | --- |
| Approve → Send via FluentSMTP From hello@ | Plugin Email Marketing AJAX |
| Per-recipient history after send | Service `/v1/email-marketing/outbound` |
| History admin list + thread + reply notes | Email Marketing page |
| Opt-out footer + public link + admin Opt out | Plugin + suppressions API |
| Amy propose (no send) | WP + service `/email-marketing/propose` |
| Optional inbound webhook | WP `/email-inbound` → service `/inbound` |
