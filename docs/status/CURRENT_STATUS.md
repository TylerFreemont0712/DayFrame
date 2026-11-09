# Current implementation — DayFrame 0.6.0

Python/PySide6 Qt Widgets, SQLite and a private Python sync hub. Normal 1280×800 resizable window, minimum 980×640.

## Delivered

- Today priorities, due/overdue/recent work, agenda, major-event countdowns, upcoming events and live timer.
- Shared Kanban/Map/Details tickets, inspector, checklist, dependencies and work blocks.
- Month/Upcoming/Sunday-first Week calendar, event presets, detailed and multi-day events, yearly birthdays, click editing and 15-minute move/resize with Undo.
- Nested map sections, inherited rules, parent/child tickets, sequence links and collapsible Unsorted.
- Map 1.5-second hover ghosts, confirmation, cancellation, cycle checks and Undo.
- Rich Quick Add and reusable preset/custom label chips; colored board/map labels.
- Durable/manual/unassigned time, overlap review, private accounts, simple passwords and remembered login until Logout.
- Graphite, Terminal, Paper, Midnight, Nord, Catppuccin, Editor and System themes with per-theme color schemes, a Custom scheme with color wheel and advanced element colors, font and corner choices, and independent density, text size (90% default) and heading size.
- Time zone picker sorted by UTC offset with current times and fixed offsets; up to three world clocks in the bottom bar.
- Native Windows frame theming, current DayFrame logo/icon and Windows/Linux launch/build templates.
- SQLite backup/import, transactional sync outbox, private LAN hub, certificate pinning, independent field merges and conflict review.
- Private GitHub repository, issue/PR templates, contribution guide and Windows/Linux CI.
- Code page (unreleased): one Git repository per project with a device-local checkout folder; per-ticket changesets with stored, synced diffs; shelve, save and switch between changesets; fetch, fast-forward pull, commit and push with confirmations; branch create/switch; GitHub token in Settings > Sync with checks, release, pull requests and issues, new pull requests and issues, merges and tickets from issues; code badges and Open in Code links from Kanban, Map, inspector and calendar work blocks. The page has Tickets (ticket cards, changeset strip), Working tree, History (commit graph) and Branches tabs, with a change browser (file tree, line counts, numbered unified/split diffs with in-line edit highlighting) for every diff.

The checkout retains current branding, native source and useful documentation. The current release and development environment stay local. Current packaged UI references live in docs/screenshots/current/.

## Changes in 0.6.0

Three themes join Graphite, Terminal, Paper and Midnight: Nord, Catppuccin and Editor. Editor collects popular editor palettes (Dracula, Tokyo Night, One Dark, Monokai, Gruvbox, Solarized, Rosé Pine, Everforest), and the new themes include light schemes. Every theme has a Custom scheme: a color wheel sets the nine main colors, Advanced colors override single elements, and a preview shows the result before applying.

Fonts (interface, headings, numbers) and corners can be overridden. 90% is the default text size, and profiles on the old 100% default move to it once. Text size ranges 75–140% with a separate heading size; density adds Spacious, and panel widths and window-size presets are in Settings > View.

The time zone is picked from a searchable list sorted by UTC offset that shows each zone's current time, and up to three world clocks show in the bottom bar.

The bottom bar's Ticket/Event selector, timer and totals, and the calendar's all-day chips, now size themselves from the font; a day with more than four all-day rows shows "+N more".

The source is organized into layered subpackages with one module per window page, formatted and linted with Ruff, and the documentation is grouped by topic with a code map and writing rules. Stored data, runtime paths, keyring and sync identifiers are unchanged.

## Data and compatibility

Schema 5 preserves saved records/passwords; databases on versions 1–4 migrate transactionally. Schema 5 (unreleased) adds repositories and changesets; update the hub before syncing them from a client. Import changes only the copied database. Established storage, session, keyring and sync identifiers are documented in [BRANDING.md](../operations/BRANDING.md). Notes data is retained with its UI hidden.

## Verification

The cleanup release passed 58 Windows tests and a 19-screen packaged UI smoke check using Python 3.14. Windows and Ubuntu 24.04 CI also passed setup, tests, packaging and smoke checks for that baseline. Routine CI now runs source tests only; packaging requires an explicitly requested build. Tests never open the live profile. See [RELEASES.md](../operations/RELEASES.md) for the packaged baseline.

The 0.5.2 release passed all 77 Windows source tests. Coverage includes saved-stage compatibility, shared status labels, Home grouping, Kanban previews/cancellation/Undo, prefix-only project colors and contrast, title containment and Details navigation. The Windows portable bundle and extracted installer payload each passed the expanded 61-screen smoke check using isolated profiles. All 881 installer payload files matched the bundle, including the supplied NSIS license notice. The verified package is now the local release used by Start DayFrame.cmd; see [RELEASES.md](../operations/RELEASES.md) for its build commit and checksum.

The 0.6.0 release passed all 106 Windows source tests, including new coverage for preferences validation, custom and advanced colors, the color wheel, fonts and sizes, the time zone picker and world clocks, the one-time move to 90% text, bottom-bar control widths and all-day chip fitting. The Windows portable bundle passed a 97-screen packaged smoke check covering all seven themes at both window sizes, and a profile created by 0.5.2 opened in 0.6.0 with its sign-in, records and theme. No 0.6.0 installer was built because NSIS is not installed on the build machine; see [RELEASES.md](../operations/RELEASES.md).

Seven Settings tests cover category and keyboard navigation, independent saves, invalid preference retention, field persistence, existing data/sync/account actions and conflict updates. Packaged layout checks cover all four themes, both window sizes and 100–125% text. Source checks also cover long conflict descriptions. Windows/Ubuntu source CI is linked from the release pull request. Linux Mint has not been verified.

The Windows installer is unsigned. Ubuntu CI does not verify the owner's exact Linux Mint installation. No hub/service/firewall or external integration is installed by source setup.

## Code page verification

Source tests cover the schema 5 migration, repository and changeset rules, the diff size limit, syncing a large Unicode diff between two devices through the hub, git status parsing, shelving with untracked files, restoring a stored diff in a second clone, snapshots, committing selected files, push and pull against a bare remote (including the refusal to push while behind), the GitHub client against a local fake API (errors never include the token), and the page itself: capture, shelve, switch with automatic shelving, commit with changeset archiving, confirmed push, recoverable delete, the GitHub settings and tab, and the links from Kanban, Map, inspector and calendar work blocks. The diff parser (renames, deletions, binary files, quoted names, line endings), folder tree, in-line spans, split pairing and graph lanes (branch, merge, fold) have unit tests; the Working tree (stage, unstage, discard), History (graph, commit details) and Branches (create from remote, safe delete, jump to History) tabs are tested against real repositories. Layouts were checked by screenshot in the Catppuccin theme at 1280×800 only. Verified on Windows with git 2.45 from source only: not packaged, not checked on Linux Mint, and not exercised against the real GitHub API.

## Remaining

Recurrence exceptions and weekly/monthly rules, reminders, goal/reference objects, attachments/activity, durable history/recovery, large-data paging, stronger timer leasing, device/recovery management, sync-aware historical restore, Subversion shelves, Team and mobile. Conflict resolution currently chooses local or hub data. The full list of planned and proposed work is in [IDEAS.md](IDEAS.md).

## Desktop runtime

Use Python 3.12–3.14, with Python 3.14 recommended and used for packaging/CI. A Python 3.11.17 Ubuntu run aborted in the Qt binding during repeated theme changes; the application passes on Python 3.14. The headless hub retains its current protocol and configuration.
