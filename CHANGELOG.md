# Changelog

## Unreleased

- Add Clear workspace to Settings > Local data for starting over with an empty workspace. It saves and checks a full backup in the profile's backups folder first, asks for a typed confirmation and a second prompt, keeps the account and preferences, and disconnects the device from a configured hub so the cleared data is not downloaded again.
- Redraw Map links: every link leaves and enters a card at a right angle with an arrowhead that sits flush on the card edge, links sharing a side are spread along it, dashed links always meet their arrowhead, and rounded step routes follow the channels between columns instead of passing under neighbouring cards.
- Give every stage its own symbol and color (dashed ring, half, three quarters, ring with a core, checked disc) on Kanban lanes and cards, Map cards, the inspector and ticket page status menus, ticket tables, stage filters, the ticket editor, Quick Add and Code ticket cards.
- Add the Tickets page between Projects and Code: an overview with stat tiles, charts of completions, tracked time, created and completed per week, open work by stage and project, and estimate against tracked time, plus a sortable, filterable table of every ticket; and a forum-style ticket page with a Markdown description, comments, pasted or attached screenshots, activity, relations and in-place editing.
- Make the board inspector a compact read-only summary with Edit, Track, Details, Schedule, Code and a status menu, and let Kanban lanes narrow so the Complete lane stays visible beside it.
- Record when tickets are created and completed, and sync comments and screenshots (schema 6).
- On the Map, drag a section together with its nested sections and cards, route links around unrelated cards (with portal markers where a link must pass under one), and highlight a card's links on hover.
- Make the Code badge on cards a centred button with a hover ring and press animation.
- Add a large demo workspace (Settings > Local data) with eight projects, about ninety tickets with history, comments and screenshots, three weeks of tracked time, scheduled work and events. `Preview DayFrame.cmd -Demo` opens a separate demo profile that also includes a git repository for the Code page.
- Add the Code page. Each project connects a Git repository with a checkout folder per device, and each ticket keeps changesets: saved working-tree changes whose diff is stored and synced, with New changeset, Save to selected, Shelve and Switch to for moving between them.
- Run fetch, fast-forward pull, commit, push and branch create/switch from the Code page in the background, with confirmations that show the command and outgoing commits. Push never forces.
- Connect GitHub with an access token in Settings > Sync (kept in the OS credential store) to see checks, the latest release, pull requests and issues, open pull requests and issues, merge pull requests and create tickets from issues.
- Open a ticket on the Code page from a code badge on Kanban and Map cards, their context menus, the inspector, and the work-block dialog in Calendar and Today.
- Rework the Code page for development: tickets as outlined cards in a fixed column, a changeset strip, and a change browser with a changed-file tree, +/− counts per file and folder, and numbered unified or split diffs that highlight in-line edits and line-ending changes. Add Working tree (stage, unstage, discard), History (commit graph with merges, branches and tags, commit details) and Branches (tracking, ahead/behind, tags, stashes, create and safe delete) tabs.
- Move the database to schema 5 for repositories and changesets. Update the hub before syncing from a client that uses the Code page.

## 0.6.0 — 2026-11-08

- Add the Nord, Catppuccin and Editor themes. Editor offers Dracula, Tokyo Night, One Dark, Monokai, Gruvbox, Solarized, Rosé Pine and Everforest schemes; Nord, Catppuccin and Editor include light schemes.
- Add a Custom color scheme to every theme, with a color wheel for the main colors, Advanced per-element colors (buttons, button text, headings, inputs, selection, warnings, clocks) and a live preview.
- Choose interface, heading and number fonts from installed fonts, and a corner style.
- Make 90% the default text size (existing profiles on the old 100% default move once), widen text size to 75–140%, and add heading size, Spacious density, panel widths and window-size presets.
- Pick the time zone from a searchable list sorted by UTC offset showing each zone's current time, including fixed UTC offsets, and show up to three world clocks in the bottom bar.
- Fit the bottom bar's Ticket/Event selector, timer and totals to the text size, and size calendar all-day chips from the font with a "+N more" marker when a day has more than four rows.
- Reorganize the source into layered subpackages (core, data, sync, ui) with one module per main-window page; no behavior change. Format the code with Ruff and add Pyflakes linting.
- Organize documentation into product, engineering, operations and status folders, with an index and writing rules, a code map, CLAUDE.md and a collected ideas list.
- Rename the themes Graphite, Terminal, Paper and Midnight and add color schemes to each (Terminal now has Amber, Green, Ice, Magenta and Mono). A Colors section in Settings > Theme follows the selected theme and remembers a scheme per theme. Saved Terminal/Amber preferences carry over.

## 0.5.2 — 2026-11-05

- Organize Settings into View, Theme, Local data, Sync and Account, keeping every option in a focused page with independent View/Theme saves.
- Show a visible pressed state on buttons, including compact icon controls.
- Remove the redundant List view; open calendar deadlines in Details.
- Give the Options button and its menu icons more room.
- Highlight Kanban project-key prefixes with stable project colors and matching folder icons; keep ticket bodies neutral.
- Show an immediate destination ghost while dragging Kanban tickets, with clean cancellation and status Undo.
- Rename workflow stages to Not Started, In Progress, Processed, Review and Complete while preserving saved ticket stages and sync history.
- Document natural commit/comment wording and frequent, focused commits.
- Keep routine CI to source tests; make packaging opt-in for requested release waves or validation builds.
- Record the packaged baseline and when to suggest the next release.
- Check all Settings pages, the Kanban destination ghost and Details in the packaged smoke run; report the package version.
- Support portable NSIS compiler resources and include its supplied license notice in Windows packages.

## 0.5.1 — 2026-11-04

- Remove superseded implementations, old application marks, obsolete launch/build files, design mockups and outdated screenshots/documentation.
- Keep only current DayFrame branding, native source, current UI references and the active release.
- Remove obsolete branding from import messages and unused theme/notes UI remnants.
- Preserve existing profile/database/login/sync identifiers and user data.

## 0.5.0 — 2026-11-04

- Native Python/PySide6 desktop with Today, tickets, calendar, project map and time tracking.
- DayFrame logo/icon, distinct themes, rich Quick Add and colored labels.
- Private accounts, remembered login, SQLite persistence and optional private LAN sync.
- Python 3.14 packaging/CI, Windows/Linux setup, project specifications and contribution workflow.
