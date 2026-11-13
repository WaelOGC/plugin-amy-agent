# Amy Agent — Revenue Intelligence Concepts (Proposed)

> Location: `amy-agent/docs/10-revenue-intelligence-concepts.md`
> Status: **Not implemented — proposed.** Planning / prioritization only.
> No new endpoints, UI, DB tables, or version bumps in this document.

## What this document is

Five expansion concepts adapted from an earlier OGC “AI Revenue Intelligence”
brief (originally written for e-commerce / WooCommerce merchants) so they fit
**Amy Agent as a general-purpose, sellable site assistant** for any business
site — agencies, service businesses, publications, and similar — not a store.

These ideas are recorded so a future session can prioritize them. They are
**not** committed roadmap work and must not be treated as shipped features.

## What this document deliberately excludes

Do **not** import the rest of that e-commerce brief. Out of scope here (and
not proposed for Amy): cart recovery, margin / pricing engines, Shopify,
checkout funnels, product catalog intelligence, or any store-only revenue
mechanics. Amy remains a site assistant + lead / ops companion, not a commerce
platform.

Design lens: `00-extensibility-principles.md` (sellable across business types).
Status tracking: `roadmap-status.md` (each item marked
**Not implemented — proposed**). Existing contracts to reuse where possible:
`api-contract.md`, Analytics plan `07-analytics-plan.md`.

---

## 1. Visitor Journey Context

**Status: Not implemented — proposed**

### Purpose

Give Amy (and later the site owner) the pages a visitor viewed **before**
opening chat — e.g. Pricing, About, a specific service page — so replies are
grounded in what they already saw, and so owners can later inspect common
pre-chat paths.

### Signals / data already in the architecture (no new tables invented)

Reuse what Analytics and public chat already collect:

| Existing surface | Relevance |
| --- | --- |
| `page_view` on `POST /v1/analytics/event` (WP `POST /wp-json/amy-agent/v1/track`) | Ordered path via `visitor_events.page_path` per `session_id` |
| `widget_opened` / `widget_message_sent` | Marks when the journey intersects chat |
| `GET /v1/analytics/leads/{session_id}/events` | Full session timeline for one visitor |
| `GET /v1/analytics/traffic` | Aggregate top paths from `visitor_events` (`event_type=page_view`) |
| `POST /v1/chat` `page` (`url` / `slug`) | Current page only, already on the chat contract |
| Public `visitor_id` + `conversations` / `conversation_messages` | Tie chat turns to the same anonymous visitor |

**Gap today (conceptual only):** chat receives the *current* page, not the
prior path; admin lead list does not yet surface “pages before chat” as a
first-class summary. A future build would join session `page_view` rows before
`widget_opened` — still on `analytics.db` (`visitor_sessions` /
`visitor_events`), not a new store.

---

## 2. Missed-Opportunity Detection

**Status: Not implemented — proposed**

### Purpose

Flag visitors who asked in chat about **pricing or a specific service** (or
reached an equivalent high-intent step) but left **without** leaving contact
info or submitting a request — a **lead-recovery** signal for the site owner.

This generalizes the source brief’s “Revenue Leak Detection” away from
checkout / cart abandonment to **lead conversion** on a general business site.

### Signals / data already in the architecture

| Existing surface | Relevance |
| --- | --- |
| `visitor_sessions.lead_status` (`cold` / `warm` / `hot`) | Existing lead scoring on ingest |
| `visitor_sessions.lead_email` | Contact captured vs missing |
| Funnel events: `submit_idea_*`, `contact_form_*` (incl. `*_abandoned`) | Near-convert / abandon without completion |
| `submit_idea_contact_captured` | Email shared early in Submit Idea |
| `GET /v1/analytics/leads` (+ `signal` string) | Ranked lead list for owners |
| `GET /v1/analytics/summary` | Aggregate hot / with-email / capture windows |
| `conversation_messages` (public `mode: general`) | Content that mentions pricing / services |
| Closing-wish cohort pattern (`GET /v1/analytics/closing-wish-effect`) | Precedent for “chat cohort → Submit Idea started” splits |

**Gap today (conceptual only):** hot/warm scoring and abandon events already
exist; there is no dedicated “asked about X in chat, no contact, left”
detector or owner alert. Any future flag should derive from the existing
Analytics allowlist + conversation history — not a commerce checkout model.

---

## 3. Conversion Experiments

**Status: Not implemented — proposed**

### Purpose

Let the site owner A/B test two variants of Amy’s **opening message** or how
she **presents pricing**, and measure which variant produces more leads /
contact submissions.

### Signals / data already in the architecture

| Existing surface | Relevance |
| --- | --- |
| Public widget + `POST /v1/chat` (`mode: general`) | Surface where opening copy / pricing tone lives |
| Optional `pricing_catalogue` on public general chat | Live price list already injected for quoting |
| Outcome events: `submit_idea_started`, `submit_idea_contact_captured`, `submit_idea_completed`, `contact_form_submitted` | Conversion proxies already on the Analytics allowlist |
| `GET /v1/analytics/closing-wish-effect` | Closest existing pattern: split public-chat cohorts and compare `submit_idea_started` rates |
| `chat_closing_wish` + `conversations.closing_wish_sent` | Example of a once-per-conversation chat treatment already measured |

**Gap today (conceptual only):** closing-wish measurement is a fixed feature
toggle, not a general experiment framework. A future experiments layer would
assign a variant, record it against the same session / conversation, and
reuse Analytics outcomes — without inventing store conversion metrics.

---

## 4. Evidence-Based Recommendation Format

**Status: Not implemented — proposed**

### Purpose

Any report or suggestion Amy or the admin dashboard surfaces to the site
owner should follow one consistent structure so recommendations never read as
guaranteed outcomes:

1. **Finding** — what was observed  
2. **Evidence** — which sessions, events, or counts support it  
3. **Confidence** — how strong / stable the signal is  
4. **Limitations** — what the data does *not* prove  
5. **Recommended action** — what the owner might do next (still optional)

### Signals / data already in the architecture

| Existing surface | Relevance |
| --- | --- |
| Admin chat allowlisted tools (`analytics_summary`, `analytics_leads_query`, `analytics_traffic`, `email_audience_summary`, `seo_summary`, `task_stats`) | Report-only; cite figures, do not execute sends/writes |
| `GET /v1/analytics/summary`, `/leads`, `/traffic`, `/closing-wish-effect` | Concrete evidence sources for lead / path claims |
| SEO Tasks `findings` (`field`, `severity`, `message`) + Approve flow | Precedent for structured findings before action |
| Email Marketing `send_policy: approve_then_send` | Recommendations stay proposals until human send |

**Gap today (conceptual only):** admin replies and Overview cards are useful
but not forced into Finding / Evidence / Confidence / Limitations /
Recommended action. This is a **presentation and prompt contract**, not a
new datastore.

---

## 5. Human Approval for Consequential Actions

**Status: Not implemented — proposed**

### Purpose

Any action with a **real-world effect** — sending an email or discount,
scheduling something, publishing content — must wait for the site owner’s
**explicit approval** before Amy executes it. On her own, Amy may only
**observe, analyze, and recommend**.

### Signals / patterns already in the architecture

| Existing surface | Relevance |
| --- | --- |
| Email Marketing: Approve draft → **Send now** (`send_policy: approve_then_send`) | Outbound mail never auto-fires from Amy alone |
| SEO Tasks: generate → human **Approve** / Reject before WP write | Writes only after owner confirmation |
| Admin `POST /v1/chat`: tools are report-only | Chat may cite Analytics / SEO / Tasks / Email audience; does not approve SEO, reassign tasks, or send mail |
| Task Service P4 capability matrix | Amy may summarize in-system data; must **not** contact leads or send marketing mail |
| Planned Admin Roles & Social Publishing (`05-…`) | Daily publishing still assumes owner-configured / controlled automation — not silent unsupervised blast |

**Gap today (conceptual only):** the rule is already followed in Email and SEO;
it should be stated as a **product-wide invariant** for any future
consequential tool (scheduling, social publish, discounts, outreach), so new
surfaces inherit Approve-before-execute by default.

---

## Relationship to the live product

- These five items sit **outside** the agreed priority order in
  `roadmap-status.md` until explicitly pulled into a build session.
- Prefer extending Analytics (`analytics.db`), public chat, and existing
  Approve patterns over inventing parallel commerce systems.
- When prioritized, each item should get its own implementation plan and
  contract updates — this file stays the concept brief only.

---

*The Hague, Netherlands — OGC NewFinity*
