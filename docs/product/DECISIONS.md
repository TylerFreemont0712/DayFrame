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
| D-008 | Project selection opens its Map; Map/Kanban/Details share tickets (updated by D-066). |
| D-009 | Ticket click opens a side inspector; full Details is separate. |
| D-010 | Full optional ticket structure with checklists, subtasks, dependencies, estimates, deadlines. |
| D-011 | Not Started/In Progress/Processed/Review/Complete (updated by D-063); Blocked is a separate flag. |
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
| D-030 | Repository overview first; files/diffs later (updated by D-075). |
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

## Writing, history and release cadence — 2026-11-04

D-061: Use natural, concrete language in commits and comments, with no unnecessary assistant/tool attribution or automatic generation trailers. Preserve required third-party attribution. Commit regularly in small, complete units with one purpose so earlier behavior is easy to trace and recover; preserve shared history.

D-062: Ship releases in deliberate waves only on the owner's instruction. Routine source commits and CI do not rebuild packages, replace the current release or bump versions. Suggest a release at task completion for significant unreleased changes, or after 14 days with source changes waiting; documentation/comment-only work does not trigger a suggestion. Ask once, respect a deferral and wait for explicit authorization. The 14-day threshold is the initial project default for "a while". Track the actual packaged baseline in [RELEASES.md](../operations/RELEASES.md).

## Kanban refinement — 2026-11-04

D-063: Rename workflow stages to Not Started, In Progress, Processed, Review and Complete in that order. Preserve stored IDs inbox, ready, doing, review and done so existing records and sync history remain valid. Home's In Progress group follows the renamed stage; completion and dependency checks still use done.

D-064: Kanban dragging gets an immediate destination ghost plate, with no hold delay or confirmation. Hover/cancellation never writes data; dropping changes only status and offers Undo. The map retains its separate 1.5-second hold and confirmation rules.

D-065: Differentiate projects on Kanban with a colored project-key prefix, keeping the suffix and card body neutral. Repeat the hue in project folder icons. The initial color assignment derives from stable project UUIDs, with theme-aware brightness; no database or sync migration is needed.

D-066: Remove the redundant project List view; use Details for ticket tables and calendar deadline navigation.

## Settings organization — 2026-11-05

D-067: Replace the long Settings form with View, Theme, Local data, Sync and Account categories. Keep all existing controls and actions, with bounded scrollable forms and independent View/Theme saves. Preserve field entries between categories and appearance changes; remember the selected category for the session. Show unresolved conflict counts beside Sync.

D-068: Themes are renamed Graphite, Terminal, Paper and Midnight so each can offer several color schemes (Graphite: Cyan, Azure, Mint, Orange, Rose; Terminal: Amber, Green, Ice, Magenta, Mono; Paper: Sage, Clay, Ocean, Plum; Midnight: Lavender, Ocean, Forest, Wine, Ember). The first scheme of each theme is the previous look. A dynamic Colors section in Settings > Theme lists the schemes of the theme being chosen, and every theme remembers its own scheme (`themeColors` preference, device-local). The saved theme id `amber` is now `terminal` and old values are read as such. System has no scheme of its own and uses the choices for Paper and Graphite.

## Appearance and time customization — 2026-11-08

D-069: 90% is the base text size. New profiles start at 90%, and a profile still on the old 100% default moves to 90% once (layout revision 4). The text scale range is 75–140%, with a separate 80–160% heading size. Density gains Spacious, and a corner style can override the theme radius.

D-070: Add the Nord, Catppuccin and Editor themes. Editor collects popular code-editor palettes (Dracula, Tokyo Night, One Dark, Monokai, Gruvbox, Solarized, Rosé Pine, Everforest). New themes include light schemes, so light/dark behavior follows each palette's background instead of the theme name.

D-071: Every theme offers a Custom scheme with a color wheel for its main colors and an Advanced section for per-element colors (buttons, button text, hover outline, accent-button text, headings and bold labels, inputs, selection, warnings, clocks). Unset advanced colors follow the main colors. Custom colors are device-local and stored per theme.

D-072: Interface, heading and number fonts can be chosen from installed fonts, defaulting to the theme's own with fallbacks. Fonts are not bundled or downloaded.

D-073: The time zone is chosen from a searchable list sorted by UTC offset that shows each zone's current time, including whole-hour fixed UTC offsets. Up to three world clocks show the current time elsewhere in the bottom bar.

D-074: Bottom-bar controls and calendar all-day chips size themselves from the active font; the all-day band shows up to four rows and summarizes the rest as "+N more".

## Code area — 2026-11-08

D-075: The Code page becomes a working hub for version control, not only a read-only overview. Each project selects its version control; Git ships first and Subversion (shelves) follows later. A project has one active repository connection.

D-076: Tickets own changesets: saved working-tree changes whose diff is stored in the database and synced so other devices can see and restore them. Git stash creates them and remains a local backup. Switching between changesets restores files into the checkout, shelving uncommitted work first so nothing is lost.

D-077: GitHub gets full read/write API access through a personal access token in Settings > Sync, kept only in the OS credential store. Commit, push, pull, branch switches, merges and deletions require confirmation; push never forces and pull only fast-forwards.

D-078: Other views link to the Code page: a code badge on Kanban and Map cards, Open in Code in their context menus, a Code button in the inspector, and Open ticket / Open in Code in the work-block dialog used by Calendar and Today.

D-079 (2026-11-09): The Code page is a developer workspace with as much detail as possible, all inside the Code section. Tickets show as outlined cards in a fixed-width column whose divider does not move. Changes open in a change browser (file tree, per-file and folder line counts, numbered diff with in-line edit highlighting, unified or split). Working tree, History (commit graph with merges and refs) and Branches tabs join Tickets and GitHub.

## Tickets page and Map clarity — 2026-11-09

D-080: Navigation order is Home, Projects, Tickets, Code, Calendar, Time. Tickets is a ticketing centre with an overview of efficiency statistics, charts and the full ticket table, and a forum-style ticket page with comments and screenshots. Assignee shows the signed-in person until Teams arrive.

D-081: The board inspector becomes a compact read-only summary with all its actions; editing is an explicit Edit. It must not hide the Complete lane at the default window size.

D-082: Tickets record when they were created and completed, and comments and screenshots are synced records (schema 6), so statistics and discussions are the same on every device.

D-083: Dragging a section on the Map carries its nested sections and cards. Links route around unrelated cards; where they must pass under one, portal rings mark it, and hovering a card highlights its links.

D-084: A large, seeded demo workspace and a separate demo preview profile exist for exploring the app without touching real data.

## Stage symbols, Map links, fresh start and Home — 2026-11-10

D-085: Every workflow stage has its own small symbol so a ticket's stage reads at a glance on cards, lanes, menus and tables. The shapes fill up as work advances and each has its own color; shape, not color alone, carries the meaning.

D-086: Map connections must look smooth and whole: arrowheads sit flush on the card they point at, links meet cards at a right angle, and links sharing a side do not overlap.

D-087: Settings > Local data offers Clear workspace for starting with a fresh database. It must be confirmed (typed word and a second prompt) and saves a checked backup first. The account and preferences stay. Because sync has no delete operation, clearing disconnects the device from its hub instead of deleting anything there.

D-088: Home becomes a compact dashboard in the style of the rest of the app: focus and figures, task rows, a week strip of clickable day cards that are filled in with each day's events, a Day Agenda for the selected day, countdown tiles for major events, and upcoming events with a symbol per event type, including birthdays. D-003, D-004 and D-006 still hold.
