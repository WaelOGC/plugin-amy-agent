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
- **Not the AI provider settings page itself.** The plugin's existing Settings
