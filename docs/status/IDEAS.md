# Ideas and future work

The single place to collect everything DayFrame might do next. Nothing here is delivered; [CURRENT_STATUS.md](CURRENT_STATUS.md) is the source of truth for what works today. When an idea is accepted, record the decision in [DECISIONS.md](../product/DECISIONS.md), specify it in [SPEC.md](../../SPEC.md), and remove or mark it here once it ships.

## How to use this file

- Add new ideas under the matching area with a one-line summary and, when useful, a short "why" and the source (owner request, spec section, decision ID).
- Keep each entry small. If an idea grows a design, give it its own document under `docs/product/` and link to it from here.
- Status tags: **planned** (already promised in the spec or decisions), **proposed** (not yet accepted by the owner), **parked** (deliberately postponed).
- Never describe an idea as available in README, CURRENT_STATUS or the UI until it is implemented and tested (SPEC §3).

## New feature proposals

These three fit the existing data model and would reuse current records rather than adding new storage concepts. They are **proposed** and need an owner decision before work starts.

### 1. Weekly review: plan versus actual

A Time-page view (or a Today card on Sundays/Mondays) that compares, per ticket and per project for the selected Sunday-first week:

- estimate (`ticket.estimate_min`) versus tracked time (`time_entry` rows),
- scheduled work blocks (`block`) versus time actually tracked inside or outside those blocks,
- tickets completed, tickets that went overdue, and carried-over pinned priorities.

Why: DayFrame already captures estimates, blocks and entries but never closes the loop. A short weekly reflection makes estimates more accurate and shows where unplanned work went. Reuses `planning.py` week bounds and `domain.day_bounds`, so totals split at midnight in the configured timezone exactly like the utility bar. Read-only at first; no schema change.

### 2. Command palette

Extend Ctrl+K from ticket search into a keyboard palette that searches tickets, events and projects and also runs actions: "Start timer on…", "Go to Calendar", "New event tomorrow 14:00", "Pin…", "Sync now", "Switch theme".

Why: the spec asks for keyboard-operable essential workflows (SPEC §15) and event search is already planned (SPEC §10). A palette gives one consistent entry point, and every action maps onto an existing `Store.command` method or window navigation call, so it adds no new write paths.

### 3. Ticket templates

Save a ticket's checklist, labels, estimate, component and description as a named template per project, then create new tickets (or a parent with children) from it in Quick Add.

Why: recurring kinds of work (release checklists, bug triage, weekly chores) currently need retyping. Templates would be ordinary synced records owned by the account, created through the same transactional command/outbox path as tickets, and Quick Add would prefill fields rather than bypass validation.

## Planned and previously requested work

Collected from [SPEC.md](../../SPEC.md), [DECISIONS.md](../product/DECISIONS.md), [CURRENT_STATUS.md](CURRENT_STATUS.md) and the area documents.

### Calendar and reminders
- **planned** Weekly/monthly recurrence rules with exceptions instead of generated rows (SPEC §8, CALENDAR_AND_MAP).
- **planned** Reminders, only for explicitly enabled events and deadlines (D-028).
- **planned** Event search alongside ticket search (SPEC §10).
- **planned** Routines with occurrence/completion state (SPEC §2).

### Tickets, Kanban and Map
- **planned** Manual ordering within a Kanban lane (TKT-05).
- **planned** Per-project workflow customization (TKT-02).
- **planned** Goal and reference objects; linked map references (D-018, D-022).
- **planned** Inspector Activity, Files/attachments and Code tabs (TKT-04, D-026).
- **parked** Notes UI and note capture; saved notes stay intact (SPEC §10).

### Time tracking
- **planned** Stronger cross-device timer leasing instead of the advisory shared record (TIME-01).
- **planned** Audit trail for manual time corrections; daily and project summaries (TIME-03).
- **planned** Review policy for device sleep and large clock changes (TIME-02).

### Data, sync and accounts
- **planned** Durable history and recovery, including sync-aware historical restore.
- **planned** Device management and revocation UI on top of the hub's `/devices` and `/revoke` routes.
- **planned** Hub password change and account recovery.
- **planned** Field-level conflict resolution beyond "keep local / keep hub".
- **planned** Paged queries and virtualized rendering for large collections.

### Code area and team
- **planned** Repository overview: repository, branch, latest commit, release/tag, checks and linked issues/PRs (SPEC §14, D-029, D-030).
- **planned** Team workspaces with memberships, explicit sharing and assignees (SPEC §13, D-015, D-016).

### Platforms and packaging
- **planned** Responsive and mobile clients (D-001).
- **planned** Tested Linux Mint installer or AppImage; live check on the owner's Mint machine.
- **proposed** Signed Windows installer.

## Engineering ideas

- **proposed** Add Ruff linting to CI once the formatted baseline has settled, so unused imports and undefined names are caught before review.
- **proposed** Replace the per-page full rebuild in `refresh_page` with targeted updates for the Today agenda and Kanban lanes, which would also help the large-data goal above.
