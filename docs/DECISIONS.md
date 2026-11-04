# Decision Log

## Confirmed product and visual decisions

| ID | Decision |
|---|---|
| D-001 | Desktop first; responsive/mobile later. |
| D-002 | Compact icon rail with tooltips; collapsible Projects contextual pane. |
| D-003 | Today is Home and has no contextual sidebar. |
| D-004 | Three pinned priorities plus due/overdue work. |
| D-005 | Agenda includes appointments, ticket work blocks, personal plans, and routines. |
| D-006 | Three major-event countdowns with optional pinning. |
| D-007 | Projects landing is an all-ticket Kanban. |
| D-008 | Project selection opens its Map; Map/Kanban/List/Details share tickets. |
| D-009 | Ticket click opens a side inspector; full Details is separate. |
| D-010 | Full optional ticket structure with checklists, subtasks, dependencies, estimates, deadlines. |
| D-011 | Inbox/Ready/Doing/Review/Done; Blocked is a separate flag. |
| D-012 | Deadline and calendar work sessions are separate. |
| D-013 | Single active timer plus editable manual entries and unassigned time. |
| D-014 | Unfinished work stays overdue until explicitly changed. |
| D-015 | Personal app first; team integration later. |
| D-016 | Personal/team scopes separate; sharing/linking explicit. |
| D-017 | Named map sections with optional classification rules and manual placement. |
| D-018 | One primary map card and optional linked references. |
| D-019 | Unmatched tickets go to a visible Unsorted tray. |
| D-020 | Preserve manual placement until released. |
| D-021 | Section drag previews/updates defining fields and offers Undo. |
| D-022 | Distinct goal/milestone containment, dependencies, and related links. |
| D-023 | Dependency blocking is computed without changing workflow status. |
| D-024 | Compact map cards expand information on selection/zoom. |
| D-025 | Independent child tickets plus lightweight checklist items. |
| D-026 | Default inspector fields and secondary Notes/Activity/files/code areas. |
| D-027 | Quick Add supports tickets, events, notes, and optional field chips. |
| D-028 | Reminders only for explicitly enabled events/deadlines. |
| D-029 | Revision means branch + latest commit ID + release/tag. |
| D-030 | Repository overview first; files/diffs later. |
| D-031 | Graphite/Cyan wins over the alternate combined concept. |
| D-032 | Real app is a larger dashboard; do not copy the compressed concept-sheet proportions. |
| D-033 | Smaller text is acceptable with configurable scale/density and readable controls. |
| D-034 | Color/style themes are required from the start. |
| D-035 | Windows and Linux support is required. |
| D-036 | User requests an account system, a real database, and local same-account sync. |
| D-037 | Authoritative project files belong in C:\Apps\TimeManager. |
| D-038 | Questions affecting infrastructure must be asked before product code starts. |

## Confirmed infrastructure answers

| ID | Question | Owner decision |
|---|---|---|
| Q-001 | Launch/package model | Installable Windows/Linux desktop, offline-capable |
| Q-002 | Network scope | Automatic same-LAN sync plus manual Sync |
| Q-003 | Sync host | Always-on Linux machine |
| Q-004 | Initial account model | Private username/password account, registered devices |
| Q-005 | Conflict handling | Merge independent fields, review competing field edits |
| Q-006 | Cross-device timers | One account timer online; review offline overlaps |
| Q-007 | Initial themes | Graphite/Cyan, Charcoal/Amber/Sage, Light, System; separate density/text scale |
| Q-008 | Actual Linux CPU/distro and displays | Linux Mint; 1920×1200; x64 assumed until verified |
| Q-009 | Storage protection | Hashed passwords, OS-protected credentials; database encryption is separate |

The owner accepted the recommended answers in this table and supplied Linux Mint / 1920×1200. Exact Mint version and CPU were not supplied.

## Selected engineering choices

SQLite per device, transactional outbox, stable identities, application-level synchronization, and a separate optional hub remain selected. Native Python + PySide6 / Qt Widgets is the selected desktop stack.

## Native application stack

D-039: Use Python, PySide6-Essentials / Qt Widgets and QGraphicsView.

D-040: Bundle scalable QtAwesome navigation glyphs and the current DayFrame application icon.

D-041: Preserve user data, schema/password compatibility and read-only source import into a fresh native profile.

## Source precedence

Direct user decisions govern. Written accepted requirements govern over incidental visual differences in generated screenshots. Record later changes here and update the affected specifications so old mockups do not silently override new behavior.


## Compact-window and login correction — 2026-11-04

D-042: Use compact task rows, board cards and narrow panes. Default window1280×800; minimum980×640. The display resolution is not the native window size.

D-043: No minimum password length, with existing hashes preserved. Remember local sign-in until explicit Options → Log out.

D-044: Restore inline capture, daily tracked total, separate due/overdue groups, board filters, actual checklist checkboxes, real ticket work blocks and editable section rules. Keep native dialogs bounded with fixed actions.


## Calendar and map refinement — 2026-11-04

D-045: Month marks, Upcoming/details/presets and Sunday-first week; clickable time editing.
D-046: Shared Home events/new tickets/timer. Hide Notes UI, preserve data.
D-047: Font/shape/surface profiles: Graphite, Terminal, Paper, Studio.
D-048: Section center = inside; right = after; left = before. Explicitly confirmed by owner.
D-049: Ticket right = dragged child; left = dragged parent; separate from blocking, preview inheritance.
D-050: Hold 1.5s, ghost/progress, release confirmation, Cancel/early-release protection and Undo.
D-051: Collapsible Unsorted project tray; red nonzero count, muted (0).


## Screenshot and label polish — 2026-11-04

D-052: Fix rounded-control artifacts, bright tab separators and clipped project badges.
D-053: Quick Add should expose useful customization with a compact, polished capture flow.
D-054: Theme the main/dialog Windows border/title bars where the native OS supports it.
D-055: Offer preset labels including bug and feature; manual input adds labels. Bug is red, Feature teal/light green. Reuse saved custom labels in suggestions.

## DayFrame identity and repository — 2026-11-04

D-056: The owner selected DayFrame and requested imagegen branding, followed by a GitHub repository and setup for future iterations.
D-057: Version 0.5.0 uses the dayframe Python package, DayFrame application/bundle names, a generated open-frame D icon and wordmark. Preserve existing TimeManager profile/database/session/keyring/sync identities so the rename does not strand data.
D-058: Establish TylerFreemont0712/DayFrame as a private source repository by default. Keep runtime data, credentials and generated builds out of Git. Include current branding, specifications, contribution instructions, issue/PR templates and Windows/Linux build checks.

D-059: Standardize desktop packaging/CI on Python 3.14 after the Linux 3.11.17 Qt binding crash; require Python 3.12–3.14 in source setup. Keep the application/schema/sync unchanged. The exact Mint installation still needs its own live verification.

D-060: The owner requested removal of obsolete implementations, source/version archives, concepts, old logos and unused references. Retain the current native source, current branding, current release, active environment and useful current documentation. Established account/storage/sync identifiers remain stable.
