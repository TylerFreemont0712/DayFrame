# Implementation Plan and Verification

Status: documentation and infrastructure choices are complete. A runnable foundation spans parts of milestones 1–5; CURRENT_STATUS.md is the implementation checklist.

## Milestone 0 — Project foundation documents

Deliver README, SPEC, design system, architecture, data model, account/sync design, decision log, and concept archive. Record selected Graphite/Cyan direction and the roomier dashboard requirement. Resolve outstanding infrastructure questions before product code.

Exit: the chosen architecture and pending items are explicit; all accepted interaction decisions are preserved.

## Milestone 1 — Cross-platform runnable foundation

Choose and pin framework/runtime versions. Create the native Qt Widgets interface and validated Python application layer, database migrations, account/profile initialization matching the chosen model, and persistent settings.

Implement real theme tokens from the start, default Graphite/Cyan, alternate theme selection, density, text scale, and window/panel sizing. Add a truthful setup/empty state and local data location.

Exit: app launches on Windows; Linux build instructions/configuration exist and are verified on the actual selected Linux runner before a Linux support claim. Settings and sample records survive restart. No passwords or database are committed to source control.

## Milestone 2 — Functional daily ticket workflow

Projects/tickets CRUD, labels, default statuses, board/list/detail inspector, pinned priorities, due/overdue queries, Quick Add, and durable single-device timer.

Exit: A-01/A-02/A-03/A-06 pass against a real database. Navigation does not reset timer/drafts. Errors are actionable. Data is not merely seeded JSON in renderer memory.

## Milestone 3 — Planning and knowledge

Day/Week agenda, work blocks, events, three major-event countdowns, notes/concepts, reminder preferences, and manual time correction.

Exit: date-only deadlines survive timezone changes; moving a block leaves deadline unchanged; countdown dates and midnight time allocation are verified.

## Milestone 4 — Project Map

Shared ticket-backed cards, named rule sections, Unsorted tray, manual-placement preservation, references, goals/milestones, dependency editing, classification-aware drag/drop, and Undo.

Exit: A-07 through A-11 pass. No orphan tickets, no independent duplicated ticket records, and dependency cycles cannot be stored.

## Milestone 5 — Account/device sync

The exact first release boundary depends on the user's answers. Domain IDs, workspace scopes, revisions, and an atomic outbox must exist before this milestone.

Implement hub setup, authentication, device pairing/revocation, transport trust, push/pull, deduplication, conflict review, timer overlap review, backup/export, and tested restore.

Exit: two independent databases and actual clients synchronize through the chosen service; offline edits, same-field conflicts, deletion, retries, interrupted batches, and revoked devices are tested. No direct shared database file.

## Milestone 6 — Repository overview

Connect a project to repository metadata and optionally a local checkout. Show accurate branch, commit ID, release/tag, checks, linked issues/PRs, observation time, and disconnected/error state. Read-only file/diff exploration can follow.

Exit: remote versus local metadata is distinguished; secrets stay out of renderer/logs. No fake connected state.

## Later — Team, customization, responsive/mobile

Workspace memberships, explicit sharing/linking, role authorization, team queue, custom project workflows, advanced map rule editor, custom theme editor, and smaller-screen adaptations.

## Meaningful tests

- Unit: countdown calendar math, due-date semantics, timer segments, dependency cycles, rule matching/precedence, conflict comparisons.
- Database integration: migrations, foreign keys, atomic domain+outbox writes, failure rollback, restart recovery, backups.
- UI integration: essential navigation/creation/editing, side inspector, keyboard use, theme/density persistence, drafts.
- End-to-end: Today → ticket → timer → restart; board → map → shared edit; event scheduling; two-device sync and restore.
- Platform: Windows and selected Linux package launch, data paths, secure credential availability, notifications, window scaling.

Do not write tests that only assert copied implementation constants. Prefer tests for user-visible invariants and data-loss boundaries.

## Definition of done for each delivered slice

Python checks, packaging and applicable tests pass; working controls have real effects; empty/error/offline states are honest; persistence survives restart; docs reflect the delivered behavior; limitations and unverified platforms are reported clearly.

## Initial code boundary

Start with milestone 1 plus a narrow working slice of milestone 2. Do not attempt to label the entire specification finished after creating a themed static dashboard. Continue through agreed milestones with concrete, tested outcomes.
