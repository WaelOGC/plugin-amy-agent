# Amy Agent — SEO Tasks Plan

> Priority #7 in `roadmap-status.md` (labeled "SEO Service" there — correct name is
> **SEO Tasks**; a follow-up fix to that file is included at the end of this prompt).

## Status: Task 1 implemented 2026-08-18 (Yoast REST wiring + single-target approval). Task 2 (full sweep + image generation) is not built.

## 1. What this is

A surface where Amy inspects the actual content of a specific post, page, or category
on the WordPress site, understands what that content is about, and then checks and
(on approval, or automatically depending on mode — see §3) fixes its SEO configuration
via the site's SEO plugin, so the content ranks well organically for relevant search
queries.

## 2. SEO plugin in use

The site uses **Yoast SEO**. Yoast's own REST API is currently read-only (does not
accept POST/PUT to update its fields). Yoast stores its data as standard WordPress
post meta, so the accepted approach — used by this plan — is: the Amy Agent plugin
registers Yoast's meta keys via `register_post_meta()` with `show_in_rest` enabled,
which exposes them for reading and writing through WordPress's own core REST API
(which the Amy Agent plugin already talks to). This avoids depending on any
undocumented or unofficial Yoast endpoint.

Per the extensibility principle (`00-extensibility-principles.md`), this integration
should be built so the SEO-fetch/SEO-write logic is not hard-locked to Yoast
specifically at the architecture level, even though Yoast is the only plugin
supported today.

## 3. Two task modes

**3.1 — Single target, approval required.**
Wael (or an authorized admin) points Amy at one specific post/page/category. Amy
checks it, reports what's missing or weak, and proposes fixes. Nothing is written
until Wael approves. This mirrors the approval pattern already used elsewhere (e.g.
Submit Your Idea confirmation step).

**3.2 — Full-site sweep, auto-fix + report.**
Wael asks Amy to check the whole site. In this mode Amy does **not** ask for
per-page approval — she checks each piece of content, fixes what she finds directly,
and at the end delivers one consolidated report (item by item — what was checked,
what was found, what was changed). Wael reviews the report afterward and can ask for
specific reversals or further changes to individual items.

The task mode (targeted-with-approval vs. full-sweep-autonomous) is chosen by how
the task is requested, not by a separate setting.

## 4. Fields in scope

All fields below are treated with **equal priority** — none is optional or
lower-priority than another when Amy evaluates a piece of content:

- **Core SEO fields:** SEO title, focus keyword, meta description.
- **Featured image metadata:** alt text, image title, caption, description.
- **Social fields (Yoast's "Social" tab — separate from core SEO):**
  - Facebook/Open Graph: custom title, description, and image.
  - X/Twitter Card: custom title, description, and image.
  (If left empty, Yoast falls back to the core SEO title/description for these —
  but an empty custom social field is still flagged by Amy as something to fill in,
  same as an empty core SEO field.)

## 5. Open items (not yet decided — resolve before implementation)

- Exact wording/format of the full-site sweep report.
- Whether there's a size/scope limit on a single full-sweep run (e.g. batching for
  very large sites).
- Whether Amy should re-check previously "good" content periodically/automatically,
  or only on explicit request (currently: only on request, per this plan — automatic
  re-checks are not in scope unless decided otherwise later).

---
*The Hague, Netherlands — OGC NewFinity*
