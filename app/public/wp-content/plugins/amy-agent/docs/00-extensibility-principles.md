# Amy Agent — Extensibility Principles

> **Purpose:** this is a foundational, cross-cutting document — not a plan for one
> specific tool. It states the design principle that every current and future Amy
> Agent tool must follow. Read this alongside any individual tool's plan doc
> (`03-`, `04-`, `05-`, `06-`, `07-`, `08-`, etc).

## Status: Locked (principle-level decisions), 2026-08-10

## 1. What this document is

Amy Agent is not being built as a fixed set of tools frozen at launch. It is being
built — from day one — as a system whose surfaces (Dashboard Chat, SEO Tasks, Task
Service, Analytics, Email Marketing, Admin Roles & Social Publishing, and any future
surface) are each designed to accept new functions later, and where the overall
system is designed to accept entirely new surfaces later, without requiring the
existing architecture to be rebuilt.

This applies for two reasons:
- Amy Agent is planned to become a sellable product (theme + plugin, and potentially
  a licensed/standalone version of Amy Agent itself), not just an internal tool for
  one business. Different buyers will have different needs.
- Amy Agent must remain usable across different business types (digital agency,
  e-commerce/WooCommerce stores, personal sites, publications, and others) — not
  only the business model it is first built for.

## 2. The two levels of extensibility

**Level 1 — Each existing surface can grow new functions.**
Every tool (SEO Tasks, Analytics, Task Service, Email Marketing, Dashboard Chat,
Admin Roles & Social Publishing) should be built so that new functions can be added
to it later without a rebuild of that surface's core logic.

**Level 2 — The system as a whole can grow new surfaces.**
The underlying architecture (agent orchestration, permissions/roles, memory,
provider/model configuration) should be built generally enough that a completely new
surface — one not yet identified today — can be added later without redesigning the
foundation.

## 3. What this document deliberately does NOT do

This document does not name, promise, or commit to any specific future function,
integration, or surface. No examples of "what might be added later" are listed here
or in any tool's plan doc. The commitment is to the *capability* to extend, not to
any particular extension. What gets built next, and when, is decided later, one
planning conversation at a time — same as everything else in this project.

## 4. How this applies in practice

- When writing a plan doc for any tool, keep the tool's core logic decoupled from
  any single integration choice where reasonably possible (e.g. a specific
  third-party plugin, a specific channel, a specific data source), so that swapping
  or adding to that integration later does not require re-architecting the tool.
- When implementing (later, in code — not part of this documentation task), prefer
  patterns that don't hardcode assumptions that only hold for one business type.
- This principle does not block or delay any current plan. It is a design lens
  applied while building what's already agreed, not new scope on top of it.

---
*The Hague, Netherlands — OGC NewFinity*
