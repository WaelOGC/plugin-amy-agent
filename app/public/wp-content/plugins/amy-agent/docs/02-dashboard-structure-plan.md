# Amy Agent — Dashboard Structure Plan (Sidebar Menu + Per-Page Design)

> Location: `amy-agent/docs/02-dashboard-structure-plan.md`
> Ties together every individual tool plan (`03`–`08`) into one coherent WP admin
> dashboard. Read alongside `docs/00-extensibility-principles.md` and the
> relevant per-tool plan when building any single page.

## Status: Locked (planning decisions), 2026-08-10 — no code yet

## 0. Purpose

Each tool (Chat, Analytics, SEO Tasks, Email Marketing, Task Service, Admin
Roles & Social) has its own plan doc. This document defines the piece that
was still missing: how those tools are actually organized inside the WP
admin — the sidebar menu itself, what each item is called, what order they
appear in, and the internal layout of each individual page — so the dashboard
reads as one product, not a pile of separate stubs.

## 1. Final sidebar menu (top-level "Amy" menu)

Locked order, top to bottom:

1. **Overview**
2. **My Profile**
3. **Task Service**
4. **Analytics**
5. **SEO Tasks**
6. **Email Marketing**
7. **Chat**
8. **Admin Roles & Social**
9. **Settings**
10. **Brand & Avatar**

This is both the sidebar order and the intended build order once
implementation starts (see §9).

## 2. Visual reference

The approved visual reference for the Overview page (card layout, color
system, card hierarchy, decorative orbit motif) was generated externally
based on a Claude-written design brief and approved by Wael on 2026-08-10.
It is referred to below as "the approved Overview reference." It is not
saved as a project file — treat this document's descriptions as the source
of truth; the reference image only illustrates the same decisions.

### 2.1 Typography correction (applies everywhere, including the reference)

The approved Overview reference uses an italic serif display font for the
page title ("Overview"). **This is outdated** — per an earlier locked
decision, the site/dashboard heading font was changed from Playfair
Display italic to **Space Grotesk, bold, not italic**. Body/UI text stays
on **Inter**. This correction applies to every page built from this
document: page titles, section/card headers, etc. must render in Space
Grotesk bold (no italic anywhere), with Inter for body copy, labels, table
text, and buttons. Do not carry the italic serif treatment from the
reference image into the actual build.

## 3. Overview (page 1)

Landing page of the "Amy" menu. Purpose: single-glance command center —
status of every tool, without needing to open each one.

- **Header band:** eyebrow pill badge ("AMY · DIGITAL EMPLOYEE"), page
  title "Overview" in Space Grotesk bold, one-line supporting description,
  decorative orbit graphic top-right (existing brand motif, reused from the
  main site).
- **Top stat strip:** 4 small stat cards summarizing cross-tool numbers at
  a glance (e.g. tasks in progress, tasks due soon, chats this week,
  average SEO score). Exact metrics are placeholders until each underlying
  tool exists — wire them up as each tool is actually built (see §9), not
  before.
- **Main grid, one summary card per tool below:** Task Service, Analytics,
  SEO Tasks, Email Marketing, Chat, Admin Roles & Social, Settings, Brand
  & Avatar. Task Service gets the largest/hero card (it's the most
  actively used surface); the rest are uniform-size cards.
- **Each tool's summary card contains:** icon + tool name, one-line
  description, 2–3 key numbers/badges relevant to that tool, a short
  "Recent Activity" list where relevant (Task Service only), and a
  "See more →" link that opens that tool's own full page.
- Cards render "Coming soon" / zero-state content for any tool not yet
  built, per the honest-stub pattern already used elsewhere in the plugin
  — never fake numbers.

## 4. My Profile (page 2)

Personal page, scoped to the logged-in user only — distinct from Task
Service, which is fully transparent/shared across everyone (§6, and
`08-task-service-plan.md` §2).

- **Header:** page title "My Profile" (static label for all users, not
  personalized per name), short description ("Your personal task
  activity"), and a right-aligned **"+ New Task"** button. Until Task
  Service exists, that button is present but disabled with a clear
  "coming soon" note; once Task Service is live it becomes the personal
  entry point for creating a task from this page.
- **Employee identity block:** circular avatar, full name, role pill
  badge (WP primary role for now; later the Admin Roles & Social role),
  email, and join date. Includes an **Edit Profile** control that opens a
  **separate custom form inside this plugin** (modal) — not WordPress
  core `profile.php` — for editing display name, email, and avatar
  (Media Library picker, same UX pattern as Brand & Avatar; avatar stored
  as per-user meta, mirroring Brand's URL-based storage approach).
- **Stat strip:** Open Tasks / Completed Tasks / This Week summary cards
  (honest empty/"coming soon" values until Task Service can supply real
  numbers).
- **Main layout (two columns on wide screens):**
  - **Open Tasks** (larger left column): tasks assigned to this user that
    are not yet completed — title, assigned by, due date, status,
    extension status if relevant (ties to `08-task-service-plan.md`
    §4–5). Empty state includes a disabled **"Go to Task Service"**
    button until that menu page exists.
  - **Completed Tasks** (upper right): collapsed/paginated history —
    title, completed date, who assigned it.
  - **Recent Activity** (lower right, timeline): reverse-chronological
    feed of this user's own actions across tools where relevant (task
    updates, chat sessions with Amy, etc.) — expand as each underlying
    tool actually exists; do not invent activity types ahead of the tools
    that produce them.
- Personal controls that belong here (Edit Profile, New Task entry point)
  are allowed; system-admin / team-wide settings stay on Settings, Admin
  Roles & Social, and Task Service.

## 5. Task Service (page 3)

Full spec: `08-task-service-plan.md`. Dashboard layout for this page:

- **Header:** page title, short description, a primary "New Task" button.
- **Top stat row:** Open / Urgent / Completed counts (matches the approved
  Overview reference's Task Service card, expanded to full page here).
- **Board/list view** of all tasks, system-wide (full transparency per
  `08-task-service-plan.md` §2) — columns or filters for status (open,
  in progress, urgent, completed), assignee (human or Amy), creator, due
  date, and extension state.
- **Recent Activity feed** (full version of the Overview card's short
  list) — every task event across the whole system, not just this user's.
- Clicking a task opens task detail (assignee, deadline, Amy's
  reminder/escalation state per `08-task-service-plan.md` §3–5,
  reassignment controls for the creator).

## 6. Analytics (page 4)

Full spec: `07-analytics-plan.md`. Dashboard layout:

- **Header:** page title, short description.
- **Chart card:** 7-day (default range, adjustable later) performance bar
  chart, matching the approved Overview reference's Analytics card style.
- **Key metric cards:** visitors, page views, and any other metrics locked
  in `07-analytics-plan.md`, each with a period-over-period % change
  indicator.
- **See more / detail sections** as defined in `07-analytics-plan.md` —
  do not add metrics here that aren't already decided in that doc.

## 7. SEO Tasks (page 5)

Full spec: `06-seo-tasks-plan.md`. Dashboard layout:

- **Header:** page title, short description.
- **Issue summary cards:** counts by issue type (e.g. missing meta
  descriptions, issues fixed), styled as the small stat/badge pairs shown
  in the approved Overview reference's SEO Tasks card.
- **Full issues list/table:** one row per detected issue — page/post
  affected, issue type, status (open/fixed), and an action to let Amy fix
  it or mark it reviewed, per whatever fix flow is locked in
  `06-seo-tasks-plan.md`.

## 8. Email Marketing (page 6)

Full spec: `04-email-marketing-plan.md`. Dashboard layout:

- **Header:** page title, short description.
- **Performance summary cards:** open rate, draft campaign count, and any
  other metrics locked in `04-email-marketing-plan.md`.
- **Campaign/send list:** history of Amy-triggered 1-to-1 sends (this is
  not a bulk newsletter tool — see `04-email-marketing-plan.md`), with
  status per send.

## 9. Chat (page 7)

Full spec: `03-dashboard-chat-plan.md`. Dashboard layout:

- **Header:** page title, short description.
- **Top stat row:** Active Now / This Week counts (matches the approved
  Overview reference's Chat card).
- **Conversation list/inbox** on one side, active conversation thread on
  the other (standard admin chat UI) — WP admin surface talking to Amy the
  Leader, per `03-dashboard-chat-plan.md` (v1: no specialist delegation).

## 10. Admin Roles & Social (page 8)

Full spec: `05-admin-roles-and-social-publishing-plan.md`. Dashboard
layout:

- **Header:** page title, short description.
- **Team Members panel:** avatar list + count, add/invite control, click
  through to per-member role/permission detail.
- **Connected Platforms panel:** one row per platform (Telegram, Discord,
  Facebook, Instagram, X/Twitter, YouTube, etc. — exact platform list per
  `05-admin-roles-and-social-publishing-plan.md`) with connection status
  and a connect/disconnect action.

## 11. Settings (page 9)

Redesigned per this session's decision: a **tabbed page with 2 tabs**,
because the previous single-page version mixed one-time technical plumbing
with ongoing config.

- **Tab 1 — General:** basic, rarely-touched settings.
- **Tab 2 — Connection / Advanced:** Python service URL, shared secret, AI
  provider selection + API key + model.
- Each individual tool (SEO Tasks, Email Marketing, Task Service, etc.)
  keeps its **own** settings inside its **own** page — nothing tool-specific
  gets centralized here.

## 12. Brand & Avatar (page 10)

Expanded scope per this session's decision — no longer just the avatar
image:

- **Amy's name** (editable).
- **Brand/theme color** (editable, drives the dashboard's accent color).
- **Personality tone** (editable — how Amy speaks across chat/email/tasks).
- **Avatar image** (existing functionality, kept as-is).

## 13. Build order

Once this document and all referenced per-tool plans are locked, real
implementation proceeds one page at a time, in this exact order (same as
the sidebar order in §1):

1. Overview
2. My Profile
3. Task Service
4. Analytics
5. SEO Tasks
6. Email Marketing
7. Chat
8. Admin Roles & Social
9. Settings
10. Brand & Avatar

Do not start building any page out of this order, and do not start code at
all until Wael explicitly says so — this document being finished is a
planning milestone, not a signal to begin implementation.
