# Amy Agent — Task Service Plan

> Priority #6 in `roadmap-status.md`.

## Status: Complete (Task 2 of 2), 2026-08-11

**Task 1:** persistent SQLite store (`data/tasks.db`), FastAPI CRUD + stats,
WordPress API client + admin-ajax proxies, real assignees, board/list CRUD,
My Profile **+ New Task** entry point, My Profile per-user stat cards.

**Task 2:** Amy's active follow-up — midpoint / final reminders, deadline expiry
notifications for creators, urgent check-ins + simplified reassignment,
extension requests (auto-cap for normal / always-approve for urgent), dashboard
notification bell on Task Service + My Profile, 5-minute background scheduler.

## Implementation notes (scoping vs original plan)

Built for Task 2 with these intentional simplifications (so future work knows
what still differs from §3–§6 above):

1. **Notifications are dashboard-only.** Telegram (and other channels in §6)
   are not in the codebase yet (priority #4 / Admin Roles & Social Publishing).
   No Telegram hooks or placeholders were added.
2. **No department/section system yet.** Urgent auto-reassignment offers the
   task to any other synced dashboard user (`manage_options` pool pushed from
   WordPress), not department-scoped. Code comments mark where
   `docs/05-admin-roles-and-social-publishing-plan.md` should narrow this.
3. **No autonomous Amy task execution.** Where §3 / §5 say Amy would complete
   the task herself, the implementation notifies the creator (and for urgent
   exhaustion, all dashboard admins as an owner stand-in) with
   `no_one_available` / expired actions — never fakes auto-completion. Code
   comments mark the wire-up point for a future execution engine.

Default timings live in `amy-agent-service/app/config_task_rules.py`
(midpoint 50%, final warning 4h, urgent check-in / ack window 60m, extension
cap 24h).

## 1. What this is

A full task-management surface inside the Amy Agent plugin/dashboard — a "Task
Surface" comparable to team task-management tools (e.g. Trello/Asana-style boards),
but with Amy participating actively in the workflow under the business owner/leader's
authority, not just displaying a passive list.

This is aimed both at internal use now and at future buyers of the product who run
their own teams and need a way to assign and track work between human team members,
not only between a human and Amy.

## 2. Who can create tasks, and for whom

- Any authorized person (owner/full admin, or an employee with the right role/
  position per `05-admin-roles-and-social-publishing-plan.md`) can create a task and
  assign it to another team member.
- Tasks can be assigned to Amy directly, or to a human team member, or effectively to
  both (Amy follows/manages the task even when the assignee is a human — see §3).
- **Full transparency:** every user with dashboard access can see all tasks in the
  system — who created each task, who it's assigned to, and its current status. This
  is not scoped per-person; visibility is system-wide for anyone with access to the
  Task Surface.

## 3. Amy's role on tasks assigned to a human

When a task is assigned to a human team member with a deadline, Amy actively follows
and manages it — she is not a passive log:

- **Progress reminder:** partway through the deadline window (e.g. at the midpoint),
  Amy sends a reminder to the assignee.
- **Final warning:** a stronger reminder shortly before the deadline (a few hours
  out).
- **On deadline expiry without completion:** Amy closes the task (the assignee can no
  longer act on it) and reports back to the task's creator with options: reassign to
  the same person, contact them personally, or — if the task is the kind of work Amy
  can do herself (digital/in-system work, not something requiring action outside the
  website) — Amy completes it herself.

## 4. Extension requests (normal-priority tasks)

If the assignee is actively working but needs more time near the deadline, they can
message Amy directly (via Telegram or the dashboard):

- Amy can **grant an extension herself, automatically, up to a hard cap of 24 hours**
  total, regardless of the task's original length.
- Any request beyond that 24-hour cap is **not** decided by Amy — she escalates to
  the task's original creator for approval before extending further.

This 24-hour cap is fixed and applies uniformly; it is not configured per task.

## 5. Urgent/critical tasks — no silent extensions, auto-escalation

Some tasks are time-critical by nature (e.g. a security issue, an urgent client
question) where any delay — even the extensions allowed in §4 — could damage the
business or brand. These are marked as **urgent/critical** at creation time and
follow a different flow:

- **No auto-extension at all.** Any extension request on an urgent task, however
  small, must go to the task's original creator for approval — Amy never grants time
  on her own for urgent tasks.
- **Faster, more frequent follow-up** than the standard midpoint/final-warning
  pattern in §3 (e.g. periodic check-ins rather than a single midpoint reminder),
  given the shorter tolerance for delay.
- **Auto-reassignment within the same department/section if the original assignee
  doesn't respond:**
  1. The task is first given to a specific employee in a specific
     department/section (e.g. Cybersecurity).
  2. If that employee doesn't respond or start work within a short window (e.g. 60
     minutes), Amy automatically looks for another available employee in the *same*
     section and sends them the task, flagged urgent, asking for acknowledgement
     within a similar short window.
  3. Whoever acknowledges first ("I'm on it") keeps the task; Amy notifies the other
     candidates in that section that it's been picked up.
  4. If **no one** in the section responds, Amy attempts to complete the task herself
     if it's work she is capable of doing (digital/in-system).
  5. If Amy cannot complete it herself, she notifies **both** the task's original
     creator **and** the business owner/leader directly — even if the owner isn't the
     task creator — since a full escalation failure within a department is
     significant enough to warrant the leader's direct awareness regardless of the
     normal reporting chain.

## 6. Notification channels

Reminders, warnings, and escalation messages reach the assignee through **both**:
- The Telegram employee group/channel (if the employee is part of it), and
- The dashboard, where each employee (already a WordPress admin-level user granted
  Amy Agent access) has their own profile showing what they're responsible for, task
  history, and current load.

## 7. Open items (not yet decided — resolve before implementation)

- Exact default timing intervals for standard-task reminders (midpoint / final
  warning) and urgent-task check-in frequency — to be tuned based on real usage,
  similar to token-limit tuning in `05-admin-roles-and-social-publishing-plan.md`.
  *(Task 2 shipped defaults in `config_task_rules.py`; still tunable.)*
- Exact UI layout of the Task Surface (board view vs. list view vs. both).
- Whether task history/analytics (e.g. completion rates per employee) belongs here or
  under Analytics (`07-analytics-plan.md`) — needs a decision when both are closer to
  implementation.

---
*The Hague, Netherlands — OGC NewFinity*
