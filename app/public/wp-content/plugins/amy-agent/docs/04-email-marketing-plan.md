# Amy Agent — Email Marketing Plan (Final)

> Location: `amy-agent/docs/04-email-marketing-plan.md`
> Status: **Decisions locked, including outreach-target scope (companies +
> individuals), confirmation rule, storage location, and legal review
> timing. No code yet — spec to build a Cursor prompt from, once Wael gives
> explicit go-ahead to write that prompt.**
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

- **Not a replacement for FluentSMTP.** FluentSMTP keeps handling WordPress's
  own transactional mail (contact forms, notifications) via
  `contact@ogcnewfinity.com`, exactly as configured today. Unrelated to this.
- **Not a bulk newsletter/campaign platform.** If a real mass-broadcast
  newsletter is needed later (thousands of recipients in one send), that is a
  separate, future decision — likely Hostinger Reach — and out of scope here.
- **Not the place where leads get identified or researched.** IP-to-company
  identification lives in Analytics; researching companies and drafting the
  first message is a capability of Amy the Leader herself. This tool's only
  job is the final step: sending.

## 3. Locked decisions

### 3.1 Sending infrastructure: Hostinger Agentic Mail
- Uses **Hostinger Agentic Mail**, a feature built into Hostinger Business
  Email (available on all plan tiers, including the free tier Wael is
  currently on) — not Mailgun, not any third-party email API.
- Integration method: **REST API** (`api.mail.hostinger.com`), not the MCP
  Server — chosen for consistency with the existing Python service, which
  already talks to everything else via REST.
- A **webhook** is configured for the `message.received` event, so the moment
  a contacted lead replies, the Python service is notified in real time (no
  polling) and can surface that reply back through Amy / the Dashboard Chat.
- **Mailbox used:** `contact@ogcnewfinity.com` (existing, already active in
  hPanel).

### 3.2 Plan / limits
- **Development phase (now): free plan.** Current limits (~100 sends/day,
  100 recipients per message) are sufficient for building and testing.
- **At full launch** (theme + plugin both live), Wael will upgrade to at
  least **Business Starter** (1,000 sends/day/mailbox) to support real usage.
  This is a manual upgrade Wael performs later — not part of this build.
- The 100-recipients-per-message cap is a non-issue for this tool's actual
  use case (1-to-1 personalized sends), reinforcing that this was never meant
  to be a bulk-campaign tool.

### 3.3 What triggers a send
- Amy the Leader decides to send, based on:
  - A lead surfaced by Analytics (Hot/Warm/Cold scoring) that has a known
    email address.
  - An explicit task from Wael via Dashboard Chat / Telegram Admin Bot, e.g.
    "search Rotterdam for marketing agencies, check their sites, and draft an
    outreach email" — Amy researches, drafts, and (with confirmation) sends
    via this same infrastructure.
- The tool itself has no automation logic of its own — it exposes "send an
  email" as a capability; all judgment about who/when/what stays with Amy.

## 4. Locked decisions (continued)

### 4.1 Who Amy can reach out to
Cold outreach targets are not limited to companies. Amy can be pointed at
either of two kinds of targets:
- **Companies** — surfaced automatically via Analytics (Hot/Warm/Cold lead
  scoring), as already described in section 3.3.
- **Specific individuals** — e.g. an influencer or creator Wael has noticed
  on TikTok/Instagram/Facebook who doesn't have a website or clear online
  business presence yet. Wael gives Amy the name/profile manually via
  Dashboard Chat or Telegram Admin Bot (e.g. "check if this person has a
  website, and if their social presence suggests they need one, see if we
  can offer to help"). Amy researches via Google/social search, evaluates,
  and — same as with companies — drafts and (per 4.2) requests confirmation
  before sending.

This does not change the sending infrastructure, plan, or trigger logic in
section 3 — it only broadens who counts as a valid outreach target.

### 4.2 Confirmation rule before sending
A single rule governs whether Amy needs Wael's approval before a message
goes out, and it depends only on **who initiated contact first** — not on
message content:
- If **Amy is initiating contact** with a company or individual who has not
  reached out to us before (cold outreach), Amy must present the drafted
  message to Wael and get explicit confirmation before sending.
- If **the customer/lead initiated contact** (they messaged us first, or
  replied to a prior message), Amy can respond freely without asking for
  approval each time — regardless of what the reply contains (including
  pricing or offers).

### 4.3 Message history storage
Sent/received email history is stored in the **same Python-service-side
data store** used for Dashboard Chat conversations (see
`03-dashboard-chat-plan.md`) — not a separate email-specific store. This
keeps all of Amy's memory centralized in one place, consistent with the
project's "single brain" principle, and prepares for the second developer
joining soon.

### 4.4 Legal / GDPR note (non-binding)
Cold outreach (to companies or individuals who have not contacted us first)
has real legal considerations under Dutch/EU direct-marketing rules:
- A documented legitimate-interest basis for the contact.
- A clear opt-out in every cold-outreach message.
- Dutch law treats outreach to a general business address differently from
  outreach to a specifically named individual — this matters more now that
  individual outreach (4.1) is in scope, not just companies.

Wael already has a legal/GDPR adviser he can consult. Per his direction,
this review will happen **before cold outreach goes live with real
recipients**, not before development — development and testing on the free
plan can continue now. This is a scheduling decision, not a technical
open item, and should not block building the feature.
