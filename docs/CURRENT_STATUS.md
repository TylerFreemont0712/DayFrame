# Current implementation — DayFrame 0.5.1

Python/PySide6 Qt Widgets, SQLite and a private Python sync hub. Normal 1280×800 resizable window, minimum 980×640.

## Delivered

- Today priorities, due/overdue/recent work, agenda, major-event countdowns, upcoming events and live timer.
- Shared Kanban/Map/List/Details tickets, inspector, checklist, dependencies and work blocks.
- Month/Upcoming/Sunday-first Week calendar, event presets, detailed and multi-day events, yearly birthdays, click editing and 15-minute move/resize with Undo.
- Nested map sections, inherited rules, parent/child tickets, sequence links and collapsible Unsorted.
- Map 1.5-second hover ghosts, confirmation, cancellation, cycle checks and Undo.
- Rich Quick Add and reusable preset/custom label chips; colored board/map labels.
- Durable/manual/unassigned time, overlap review, private accounts, simple passwords and remembered login until Logout.
- Graphite/Cyan, Terminal/Amber, Paper/Linen, Midnight/Studio and System, with independent density/text scale.
- Native Windows frame theming, current DayFrame logo/icon and Windows/Linux launch/build templates.
- SQLite backup/import, transactional sync outbox, private LAN hub, certificate pinning, independent field merges and conflict review.
- Private GitHub repository, issue/PR templates, contribution guide and Windows/Linux CI.

The checkout retains current branding, native source and useful documentation. The current release and development environment stay local. Current UI reference screenshots live in screenshots/current/.

## Unreleased source changes

The workflow now reads Not Started → In Progress → Processed → Review → Complete across ticket views and capture. Stored stage IDs remain unchanged; Home's In Progress group follows the renamed stage. These changes are source-only; the 0.5.1 package and reference screenshots remain the last packaged baseline.

## Data and compatibility

Schema 4 preserves saved records/passwords; databases on versions 1–3 migrate transactionally. Import changes only the copied database. Established storage, session, keyring and sync identifiers are documented in BRANDING.md. Notes data is retained with its UI hidden.

## Verification

The cleanup release passed 58 Windows tests and a 19-screen packaged UI smoke check using Python 3.14. Windows and Ubuntu 24.04 CI also passed setup, tests, packaging and smoke checks for that baseline. Routine CI now runs source tests only; packaging requires an explicitly requested build. Tests never open the live profile. See RELEASES.md for the packaged baseline.

The unreleased workflow rename passes 60 Windows source tests, including saved-stage compatibility, shared status labels, completion/Undo and Home grouping. It has not been packaged.

The Windows installer is unsigned. Ubuntu CI does not verify the owner's exact Linux Mint installation. No hub/service/firewall or external integration is installed by source setup.

## Remaining

Recurrence exceptions and weekly/monthly rules, reminders, goal/reference objects, attachments/activity, durable history/recovery, large-data paging, stronger timer leasing, device/recovery management, sync-aware historical restore, GitHub overview, Team and mobile. Conflict resolution currently chooses local or hub data.

## Desktop runtime

Use Python 3.12–3.14, with Python 3.14 recommended and used for packaging/CI. A Python 3.11.17 Ubuntu run aborted in the Qt binding during repeated theme changes; the application passes on Python 3.14. The headless hub retains its current protocol and configuration.
