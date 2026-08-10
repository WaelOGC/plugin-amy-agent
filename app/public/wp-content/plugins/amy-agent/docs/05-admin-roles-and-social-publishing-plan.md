# Amy Agent — Admin Roles, Permissions & Social Publishing Plan (Final)

> Location: `amy-agent/docs/05-admin-roles-and-social-publishing-plan.md`
> Status: **Decisions locked. No code yet — spec to build a Cursor prompt
> from, once Wael gives explicit go-ahead to write that prompt.**
> Priority: **#4** in the agreed roadmap order (formerly labeled "Telegram
> Notifications" — renamed here because the scope grew to cover the full
> admin/role/permission system plus multi-platform automated publishing,
> not just Telegram).
> Depends on: `03-dashboard-chat-plan.md` (Telegram Admin Bot, Telegram
> Support Bot, and the original Telegram News Channel concept are defined
> there; this document extends and completes those pieces).

---

## 1. What this actually is

Two connected systems being built together because they share the same
underlying admin/role infrastructure:

1. **Admin roles, invitations, and usage limits** — how Wael adds people
   (WordPress users or not) as Amy admins, what each role can and can't do,
   and how AI usage cost is controlled per person.
2. **Automated daily publishing across social platforms** — Amy researches
   and publishes original content daily to Telegram, X, LinkedIn, and
   Discord, each platform receiving content adapted to its own format and
   posted at its own researched best times.

Both systems are designed from day one to also work as a **sellable
product feature** — i.e., not hardcoded to Wael's specific business, so
this plugin can eventually be sold to other WordPress site owners who
configure their own roles, providers, and platforms.

## 2. What it is not (scope boundaries)

- **Not the Telegram Admin Bot / Support Bot build itself** — those
  channels and their behavior (whitelist auth, rate limiting, session
  linking) are already specified in `03-dashboard-chat-plan.md`. This
  document defines *who* gets access (roles/invites/limits) and *what else*
  gets automated (multi-platform publishing), not the bot mechanics
  themselves.
- **Not GitHub.** GitHub is a code host, not a content/social platform, and
  is explicitly excluded from the daily publishing system. If a future need
  arises (e.g. publishing plugin release notes), that is a separate,
  unrelated decision.
- **Not a bulk/mass content blast.** Daily posts are published
  **individually, spaced out**, not all at once — see section 3.4.
- **Not the AI provider settings page itself.** The plugin's existing
  Settings page (provider, API key, model) needs a broader redesign to
  support multiple providers and per-task model selection — that redesign
  is explicitly **out of scope here** and will be its own future session.
  This document only confirms the underlying architecture already supports
  it (see section 3.5).

## 3. Locked decisions

### 3.1 Roles

Seven roles total:

| Role | Conversation scope | Daily token limit |
|---|---|---|
| **Full Admin / Partner** | Unrestricted — any topic, treated as a business partner, not an employee | None (unlimited) |
| **Marketing** | Work-related only | Set per person by Wael |
| **Sales** | Work-related only (includes visibility into leads/outreach) | Set per person by Wael |
| **Support** | Work-related only | Set per person by Wael |
| **Writer** | Work-related only | Set per person by Wael |
| **Research** | Work-related only | Set per person by Wael |
| **Read-Only / Observer** | Can view conversations, analytics, and reports; cannot send messages, take actions, or trigger tools | N/A (view-only) |

- Wael, as the site owner, can promote anyone to **Full Admin / Partner**,
  granting them the exact same unrestricted rules he has himself — this
  is meant for actual business partners, not employees.
- For the five limited roles (Marketing, Sales, Support, Writer, Research):
  Amy only answers work-related requests tied to the role. If asked a
  personal/off-topic question (e.g. "help me plan my own business"), Amy
  declines and responds with a message clarifying she's available for
  company work only.
- This role list is stored so it can be extended later without a rebuild —
  not hardcoded as exactly seven forever, to support future resale of the
  plugin to other businesses with different role needs.

### 3.2 Admin invitation flow

Two entry paths, both configured from an "Amy Admins" section inside the
plugin's WordPress settings:

- **Path A — existing WordPress user.** Wael selects an existing WP user
  (who already has a WP account/email) and assigns them an Amy role.
- **Path B — no WordPress account needed.** Wael enters an email address
  directly in the same settings section and assigns a role — no WP user
  account required at all.

Both paths trigger the same outcome: the person receives an **email with a
Telegram deep link** to join the appropriate bot (Admin Bot), and that link
**expires after a set time window** (exact duration is an open item — see
section 4).

- If the link expires before the person joins, **nothing is resent
  automatically.** Wael must manually trigger a resend.
- Wael can trigger that resend two ways:
  - From the WordPress "Amy Admins" settings screen directly, if he's at a
    computer.
  - By telling Amy through the **Telegram Admin Bot** itself if he's away
    from the dashboard — e.g. "resend the invite to this email" — and Amy
    triggers the same resend flow from there.

### 3.3 Usage limits (tokens)

- **Full Admin / Partner:** no limit, ever.
- **All five limited roles:** a daily token limit, set individually per
  person by Wael — there is no fixed default number; Wael decides per
  person based on their role and expected workload. Exact starting numbers
  are not fixed in this document (see section 4 — this is a post-launch
  tuning item, not a design decision).
- **Mid-task behavior:** if Amy is actively executing a task for someone
  and their daily limit is crossed *during* that task, she finishes the
  task rather than cutting off mid-way. Once that task is done, any further
  new message from that person is met with a message telling them they've
  reached their daily limit.
- **Top-ups:** Wael can grant additional tokens to a specific person for
  the remainder of that day. The amount is decided by Wael each time,
  case-by-case, based on the size/importance of the task — there is no
  fixed top-up amount. Wael can do this two ways:
  - From the WordPress dashboard, if online.
  - By telling Amy through the Telegram Admin Bot if offline — e.g. "give
    this email an extra X tokens today."

### 3.4 Multi-platform automated daily publishing

- **Platforms:** Telegram (news channel), X, LinkedIn, and Discord.
  GitHub is explicitly excluded (see section 2).
- **Daily content volume:** 5 breaking-news posts + 3 educational/learning
  posts = 8 pieces of original content per day.
- **Breaking news posts:** must be based on real research, never invented.
  Amy checks roughly 10–20 real articles/sources spanning 20+ general
  technology categories (not limited to just AI/Blockchain/Web — broader
  tech news in general) before selecting the best 5 stories of the day
  worth sharing.
- **Educational/learning posts:** also based on real research, not written
  from imagination. Amy researches a real topic within the company's
  actual service categories (AI, Blockchain, Web, Security, etc.), finds
  an interesting angle, and writes it up as an educational post.
- **Per-platform adaptation:** the same underlying 8 pieces of content are
  reformatted appropriately for each platform's format and tone — not
  copy-pasted identically across all four.
- **Posting cadence:** posts are published **individually, spaced
  throughout the day** — never as a single batch dump. Each platform has
  its **own** best-times schedule, researched separately per platform
  (audience behavior differs by platform). As a starting reference for
  Telegram specifically: avoid late-night posting (push-notification
  fatigue risk) and favor spaced morning/midday/evening windows; X,
  LinkedIn, and Discord each need their own dedicated best-time research
  before the posting schedule is finalized (see section 4).

### 3.5 Multi-AI-provider architecture (confirmation only)

The existing Python service architecture already supports a
provider-adapter pattern — provider and API key are configured in
WordPress settings, not hardcoded — so adding providers beyond Gemini
(OpenAI, Anthropic, DeepSeek, etc.) in the future is already supported at
the architecture level. This section is a **confirmation, not a new
decision**: the actual Settings page UI to let Wael assign a specific
provider/model per task type (e.g. a cheap model for daily content
generation, a stronger model for admin/customer conversations) is a
**separate future session** (see section 2) — not part of this document
or this build.

## 4. Open items (still to define before a Cursor prompt is written for the actual build)

- **Invite link expiration duration** — exact number of hours/days before
  an unused Telegram invite link expires.
- **Starting daily token-limit numbers per role** — deferred intentionally
  to post-launch tuning based on real usage data, rather than guessed now.
- **Exact posting-time schedule per platform** — Telegram has a research
  starting point (see 3.4); X, LinkedIn, and Discord each still need their
  own dedicated best-time-to-post research before implementation.
- **Permission matrix detail** — exactly which specialist slash-commands
  (`/Analytics`, `/SEO Tasks`, `/Email Marketing`, etc., as they get built)
  each of the five limited roles can invoke is not yet itemized role-by-role.
- **AI provider Settings page redesign** — separate future session, not
  part of this document.
