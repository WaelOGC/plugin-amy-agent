# Amy Agent — Analytics Tool Plan

> Location: `amy-agent/docs/07-analytics-plan.md`

## Status: Complete — Task 1 (plugin + service), 2026-08-18

Tracking pipeline, lead scoring, and the admin lead list are built and real
(no placeholder data). Theme-side hooks (Clarity script tag, Contact form
event hook via `window.amyTrack`) are a **separate task** and were not part
of this build.

**Follow-up — newsletter tracking:** intentionally excluded. The site
newsletter form has no working backend yet, so a newsletter event type would
be fake data. Add it when the newsletter subscribe feature itself is built.

**Follow-up — cookie policy:** §5 still requires updating
`legal-cookie-policy.md` (theme/legal content, out of scope for Task 1).

> Original planning note (kept for history): decisions confirmed 2026-08-10.

---

## 1. What this tool actually is

Not a generic pageview counter (Google Analytics already does that if needed later).
This is a **visitor-intelligence / lead-tracking tool**: its job is to answer one
question — *"who is this visitor, what did they do, and are they close to becoming
a client but didn't finish?"* — so Amy (and later, Email Marketing) can act on it.

## 2. What gets tracked per visitor session

- **Origin**: IP address → country, city (via IP geolocation lookup)
- **Path through the site**: which pages visited, in what order
- **Engagement signal**: time spent on each page (especially blog articles — long
  time = real interest, not a bounce)
- **Widget interaction**: did they open the floating Amy Assistant chat? did they
  send a message? how many messages?
- **Submit Your Idea funnel** (the most valuable signal):
  - Did they open the Submit Idea page?
  - Which step did they reach? (service select → questions → summary → deep-dive →
    contact form)
  - Did they complete it, or **abandon** — and if abandoned, at exactly which step?
  - If they reached contact form but didn't submit: that's a hot lead who almost
    converted.

## 3. The core output: a Lead/Visitor list, not just charts

Instead of generic graphs, the dashboard page should surface a **ranked list of
visitors**, something like:

| Visitor | Location | Last seen | Signal | Status |
|---|---|---|---|---|
| Visitor #142 | Amsterdam, NL | 2h ago | Reached contact form, didn't submit | 🔥 Hot — almost converted |
| Visitor #139 | Berlin, DE | 1d ago | Read 4 blog articles, opened chat | 🟠 Warm — researching |
| Visitor #130 | — | 3d ago | Bounced after 5s | ⚪ Cold |

This "hot/warm/cold" categorization is what the roadmap doc calls **Lead Scoring**
(already listed under future Submit Idea improvements) — this Analytics tool is
where lead scoring actually gets computed and displayed.

## 4. How it connects to the rest of the system

- **→ Email Marketing (priority #8)**: a "hot" or "warm" visitor with an email
  captured (e.g. they got as far as the contact-form step) becomes the natural
  target list for a follow-up email — "looks like you were about to submit an
  idea, need help finishing it?"
- **→ Dashboard Chat / Amy orchestrator (priority #3)**: once the orchestrator
  exists, Wael should be able to ask Amy directly — *"who almost contacted us this
  week but didn't finish?"* — and Amy calls this Analytics tool as a function and
  answers in plain language, instead of Wael opening a dashboard page and reading
  a table.
- **→ Telegram Notifications (priority #4)**: a visitor reaching "hot" status
  (e.g. abandoned at the contact-form step) is a natural trigger for an instant
  Telegram alert — this is likely the first real event in the future Event-Driven
  Architecture.

## 5. Important constraint: privacy / GDPR

OGC NewFinity is based in the Netherlands (EU) — IP-based geolocation and behavior
tracking fall under **GDPR**. This needs to be handled correctly, not skipped:
- IP addresses should be treated as personal data (truncated/anonymized where
  possible, e.g. store country/city only, not full raw IP long-term).
- The existing cookie policy on the site already has a placeholder note that it
  "will be updated when the AI Agent widget and analytics tooling are finalized"
  — this needs to actually happen once this tool ships (update
  `legal-cookie-policy.md` content).
- A visitor should not be personally identifiable beyond what's needed for the
  lead-scoring purpose (no need to fingerprint devices, etc.) — just enough to
  connect "this session" to "this potential lead."

## 6. Technical shape (high level)

- A lightweight tracking beacon (small JS, already-loaded on every page since the
  theme loads global assets) sends events to a new endpoint, e.g.
  `POST /wp-json/amy-agent/v1/track` → forwarded to the Python service →
  `POST /v1/analytics/event`.
- Events to capture: `page_view`, `widget_opened`, `widget_message_sent`,
  `submit_idea_started`, `submit_idea_step_reached` (with step name),
  `submit_idea_abandoned`, `submit_idea_completed`.
- Python service stores events in a **dedicated persistent datastore** on Dokploy
  (not the Submit Idea session store — that is a separate SQLite DB with a 2h TTL
  and is not fit for analytics retention/query). This is a new architectural piece.
- New admin page (`amy-analytics`, currently a "Coming soon." stub) renders the
  visitor/lead list described in section 3.
- Hot-lead records are written once, consistently; a pluggable **notification
  layer** sits on top (dashboard-only in v1; Telegram/email later) so a second
  developer can extend alerts without reworking the tracking core.

## 7. Decisions (confirmed by Wael — 2026-08-10)

1. **IP geolocation service**: Researched whether Google offers this — it does not.
   Google's "Geolocation API" is built for device-sensor-based location (cell
   towers / Wi-Fi proximity), returns only raw coordinates (no country/city),
   and requires Google Cloud billing setup. It's the wrong tool for IP→location
   lookup. **Decision: use a dedicated IP geolocation service** — start with a
   free one (e.g. ip-api.com), can upgrade to a paid one (ipapi.co,
   ipgeolocation.io) later if traffic outgrows the free tier.
2. **Retention**: **90 days**, adjustable later.
3. **Storage**: **Python service side (Dokploy)**, with a real persistent
   database — not the existing Submit Idea session store (SQLite + 2h TTL), which
   is only a short-lived conversation cache and not fit for this purpose.
4. **Hot-lead alerting**: **Build the architecture to support both modes from
   day one**, rather than choosing one now. Every "hot lead" event gets recorded
   in a single, consistent way in the Python service. A separate, pluggable
   **notification layer** sits on top of that record — v1 can ship with just the
   dashboard list active, and instant alerts (Telegram, email, etc.) get
   switched on later without re-architecting the tracking core. This matters
   specifically because a second developer (an AI/cybersecurity specialist,
   currently unavailable, expected to join the team in about a month) will need
   to extend this system — it should be something to build on, not rework.
