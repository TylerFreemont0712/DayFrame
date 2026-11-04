# Current implementation — DayFrame 0.5.0

Python/PySide6 Qt Widgets, SQLite and a private Python sync hub. Normal 1280×800 resizable window, minimum 980×640. No HTML/browser runtime.

## Delivered in 0.5.0

- DayFrame name, image-generated logo, packaged icon and multi-resolution Windows ICO.
- dayframe Python package/command entry points, Windows launcher, installer and Linux templates.
- Existing profile paths, database, remembered login, keyring service and sync compatibility retained.
- Private GitHub source repository, contribution guide, changelog, issue forms and PR template.
- Windows/Linux Actions tests, standalone build and isolated packaged smoke checks with artifacts.

See BRANDING.md and CONTRIBUTING.md. Local legacy copies and earlier builds are preserved outside Git history.

## Delivered in 0.4.1

- Rounded combo/date/spinner controls, no bright tab separator, correctly fitted project/identifier text.
- Rich Quick Add, preset/status/priority/description/estimate/parent/map/checklist fields and Add + another.
- Shared removable label chips: red bug, teal feature, other common presets and manual/custom labels.
- Saved custom labels in suggestions; compact colored labels on Kanban/map cards.
- Native Windows theme caption/text/border colors with standard OS window behavior.

See QUICK_ADD_AND_LABELS.md. Schema 4 and the 0.4 hub remain compatible.

## Existing 0.4 foundation

- Month + Upcoming/presets + Sunday-first weekly timeline.
- Shared event details, multi-day spans, location/description/color, yearly birthdays and archive/Undo.
- Click editing and 15-minute single-day move/resize; work blocks remain separate from deadlines.
- Home ordinary events, recent undated tickets and live Focus timer.
- Graphite/Cyan, Terminal/Amber, Paper/Linen, Midnight/Studio and System; independent density/text scale.
- Notes UI removed; saved data preserved.
- Nested sections, inherited rules, ticket parent/child and section sequence links.
- 1.5-second hold, ghost/progress, release confirmation, cancellation, cycle checks and Undo.
- Context menus, relationship inspector and collapsible red-count Unsorted tray.

Exact behavior is in CALENDAR_AND_MAP.md. Existing foundation includes Today/Kanban/List/Details, checklists/dependencies, durable/manual/unassigned time and overlap indicators, private accounts, remembered login until Logout, simple passwords, consistent backup/import, transactional outbox, LAN sync, TLS pinning, field merges and conflict review.

## Compatibility and verification

Schema 4 preserves records/passwords. Versions 1–3 migrate; import changes only the copy. Update all clients/hub to 0.4. Earlier source and packages remain separate.

58 Windows tests pass on the Python 3.14 desktop baseline, including rename continuity for profile paths, database records and remembered sign-in. The DayFrame packaged application passes an isolated offscreen smoke check with 19 native UI captures in docs/screenshots/0.5.0. The 0.4.1 frame verification also accepted main/dialog caption, text, border and dark-mode settings for all four themes; that frame implementation is unchanged. Checks use test-only profiles or hidden HWNDs; the live application profile is not opened.

GitHub Actions also passed all tests, standalone packaging and packaged UI smoke checks on Windows and Ubuntu 24.04 with Python 3.14. The successful baseline is run #2 (commit f273d01). Installer is unsigned. Linux Mint source/setup/CI are supplied; the owner's exact Mint runtime is still unverified. No real profile is a test fixture and no live hub/service/firewall/external integration is deployed.

## Remaining

Recurrence exceptions and weekly/monthly rules, reminders, goal/reference objects, attachments/activity, durable history/recovery, large-data paging, stronger timer leasing, device/recovery management, sync-aware historical restore, GitHub, Team and mobile. Conflict resolution currently chooses local or hub data.

## Desktop runtime baseline

Use Python 3.12–3.14 for desktop source, with Python 3.14 recommended and used for current packaging/CI. The first Ubuntu CI run on Python 3.11.17 aborted in the Qt binding during a repeated theme change (none_dealloc in ElidingLabel.changeEvent). The unchanged application passes on Python 3.14; this is a runtime compatibility workaround, not a claimed upstream Qt fix. Older native 3.11 packages and source remain archived locally. The headless hub retains its existing protocol and configuration.
