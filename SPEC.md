# DayFrame — Product Specification

Version: 0.5, calendar and nested-map baseline
Date: 2026-11-04
Status: product/infrastructure decisions confirmed; runnable DayFrame 0.5.2 foundation exists; see docs/status/CURRENT_STATUS.md for delivered scope
Owner: personal application for the requesting user
Project destination: C:\Apps\TimeManager on Windows; a normal user-owned project directory on Linux

## 1. Purpose and intended use

DayFrame brings daily planning, tickets, projects, events, routines and tracked time into a dashboard the owner can leave open throughout the day. The goal is detailed organization without forcing every action through a large form.

Desktop is the initial priority. Windows and Linux must be first-class targets. Responsive/mobile work follows later. Team ticket coordination and GitHub repository visibility are planned extensions, not reasons to complicate the first personal workflows.

## 2. Core concepts

| Concept | Meaning |
|---|---|
| Account | A private username/password identity with workspace membership and registered devices. |
| Workspace | A personal or future team authorization boundary. |
| Project | A large container for related tickets, milestones, notes, repository metadata, and map organization. |
| Ticket | An actionable work item with status, details, scheduling, dependencies, and tracked time. |
| Checklist item | A small step inside a ticket without independent workflow or timer. |
| Child ticket | A ticket nested under another ticket when independent status, timing, or dependencies are needed. |
| Work block | A scheduled session for a ticket, separate from its deadline. |
| Event | A fixed or movable calendar item, including appointments and personal plans. |
| Routine | A repeated planned activity with occurrence/completion state. |
| Major event | An explicitly marked event eligible for a readable countdown on Home. |
| Map section | A named visual grouping with optional classification rules. |
| Primary map card | The main map representation of a ticket. |
| Map reference | An additional visual link to the same ticket, never a separate copy of its status or time. |
| Note / concept | Persistent project or personal knowledge with text, links, and attachment references. |

## 3. Product invariants

- A ticket has one persistent identity across all views.
- A project contains tickets; Kanban cards are tickets, not project containers.
- Map organization and workflow status are independent.
- Deadline changes require an explicit user action; moving a work block does not change the deadline.
- Overdue work stays overdue until edited, completed, or explicitly rescheduled.
- Automatic map rules respect preserved manual placement.
- Creating a project ticket makes it visible on the map or in Unsorted.
- Completing or blocking work must never silently discard time entries or notes.
- Core data is persisted transactionally, not only kept in renderer state or browser local storage.
- Settings, errors, recovery actions, and sync status are explicit and understandable.
- No real user data is prefilled from the fictional concept examples.
- The implementation must distinguish planned features from available features.

## 4. Information architecture and shell

### NAV-01: primary navigation

A compact icon rail contains Home, Projects, Calendar, Time, future Code, and Settings. Icons have labels for assistive technology, hover/focus tooltips, and a clear active state.

### NAV-02: contextual navigation

Home has no secondary sidebar. Projects reveals a collapsible contextual pane with All tickets, Schedule, Time tracker, and the project list. Selecting an individual project exposes project-specific overview/map, milestones, and future code information.

### NAV-03: workspace scope

The Personal / Team switch remains near the upper-left of the content masthead. Personal is the initial working scope. Future team features use explicit membership and sharing/linking. The interface must not imply unavailable team sharing works.

### NAV-04: persistent utilities

A persistent bottom utility area exposes the current timer, pause/stop controls, today's tracked total, and Quick Add. Global search is accessible from the shell. Hidden or collapsed panes do not interrupt the timer.

### NAV-05: navigation persistence

Remember selected view, project, panel sizes, density, and filters at appropriate account/device scopes. Layout and text size can be device-specific; project data is not duplicated per view.

### NAV-06: settings sections

Settings uses a keyboard-accessible category menu with View, Theme, Local data, Sync and Account. Show one scrollable section at a time, with bounded form widths. View contains density, text size and time zone; Theme contains the visual profile. Apply those sections independently and preserve entries when switching categories or applying appearance changes. Keep backup/examples, LAN connection credentials, automatic/manual sync, conflict review and account actions available in their corresponding sections. Remember the selected category while the app is open.

## 5. Today / Home

### HOME-01: daily focus

Show up to three pinned priority tickets first. Display due-today tickets and overdue tickets in distinct groups. Avoid duplicating the same ticket unnecessarily across priority and due groups; a due badge or a small secondary reference may indicate both roles.

### HOME-02: Day Agenda

Display appointments, ticket work blocks, personal plans, and optional routines against a chronological time ruler. Visually distinguish fixed events, work sessions, and routines. Show the current-time indicator and the active work session.

At wider widths, priorities/due work and agenda appear side by side. A countdown module fits below the work list or in a reserved supporting area. Do not stretch this arrangement into a single cramped strip.

### HOME-03: countdowns

Show the next three upcoming events explicitly marked major. Allow pinning a farther-away event into the three slots. Sort automatic slots by event date; prevent duplicate entries when a pinned event is already among the next events.

Display event name, date, and a readable day countdown. Use Today for day zero. Calculate day differences using the event's applicable calendar date/timezone rather than raw milliseconds divided by 24 hours. Past major events leave automatic slots after their occurrence; recurring events target the next occurrence.

### HOME-04: unfinished work

Do not silently roll unfinished work into tomorrow or change its deadline. Overdue items offer an explicit reschedule action.

### HOME-05: focus behavior

Pinning a priority does not change its project or workflow status. Marking a ticket done updates the shared record and removes it from active-only Home sections. Preserve completion in history.

## 6. Projects and tickets

### TKT-01: Projects landing

Projects opens an all-ticket Kanban, with project filters and optional grouping. An individual project opens its Map; its Kanban and Details views remain available.

### TKT-02: workflow

Default status sequence: Not Started → In Progress → Processed → Review → Complete. Stored values remain inbox, ready, doing, review and done respectively, preserving existing tickets and sync history. Home's In Progress group follows the ready stage and any actively timed ticket. Per-project customization is a later feature.

Blocked is an independent indicator. When unfinished prerequisites block work, compute that flag without moving the ticket out of its chosen workflow status. Keep manual blocking reason distinguishable from dependency blocking.

### TKT-03: editing and viewing

Click a ticket to open a side inspector without losing board/map context. Provide a distinct full Details workspace with a ticket list/table and the selected ticket's richer detail.

### TKT-04: default ticket fields

Title, description, status, priority, owning project, labels, component, deadline, estimated duration, tracked time, checklist, and dependencies. Use optional fields rather than forcing data entry for every ticket. Include creation/update metadata, archive state, and stable identity.

Current inspector tabs are Details and Time. Notes is hidden; activity, files and Code remain planned. Child tickets have their own identity, workflow, and time entries. Checklist items do not.

### TKT-05: board behavior

Dragging across status columns immediately shows a translucent ghost plate in the destination, with no hold timer or confirmation. The preview occupies the position the ticket will have in the existing board order. Leaving the lane or cancelling removes it without saving. Drop updates the shared ticket status with Undo; a same-column drop makes no change. Map hold/confirmation behavior stays separate. Filters must not cause hidden items to be deleted or statuses to change. Ticket selection remains stable after unrelated updates. Manual within-column ordering remains planned.

On Kanban cards, highlight only the project prefix of the ticket key with its project color; the ticket suffix and card body remain neutral. Project folder icons repeat that color. Assign hues deterministically from the stable project identity, matching across devices and surviving project renames; adapt brightness to the theme for contrast. This does not add a database field or change identifiers.

### TKT-06: project and ticket lifecycle

Support create, edit, archive, restore, and recoverable deletion. Project archive hides it from default active views without removing its tickets or history. Moving a ticket to a different project must preview the impact on identifier, map placement, and project-specific metadata; define the precise identifier policy before implementing project moves.

### TKT-07: dependencies

Disallow self-dependencies and dependency cycles. Relationship editing is validated in the authoritative data layer. Deleting or archiving a prerequisite must not silently claim its dependents are complete. Related-ticket links do not block work.

## 7. Robust project Map

### MAP-01: common ticket data

Adding a ticket inside a project creates its primary map representation or places it in Unsorted. Existing ticket IDs, status, deadlines, descriptions, and timers remain identical across Map, Kanban, and Details.

### MAP-02: subsections and rules

Sections have names, optional descriptions, visible rule summaries, and optional automatic classification rules. Supported initial rule fields should be deliberately bounded: labels, component, milestone, and explicit ticket fields chosen for the implementation.

Rules support preview before applying a bulk reclassification. Rule order and overlap are deterministic. A ticket has one primary placement; optional linked references may be shown in other relevant sections.

### MAP-03: unmatched work

Unsorted is a visible tray with a count and actual ticket cards. No ticket is lost because it lacks a label or a rule has been deleted.

### MAP-04: manual placement

Manual placement is preserved until the user chooses Return to automatic placement. Show a small pin/manual-placement indicator. Adding or changing a rule does not override that placement silently.

### MAP-05: section-aware dragging

Dragging into a rule-based section previews any classification field changes. On drop, change only the relevant field(s) and placement in one transaction and offer Undo. Ambiguous rules require a clear choice rather than guessing which labels to remove. Layout-only movement within a section changes coordinates, not classification.

### MAP-06: relationships and visual hierarchy

Section boundaries express containment. Goals and milestones provide structure. Directional arrows show prerequisite/dependent relationships. Related links have a separate visual treatment. Avoid graph clutter with selection highlighting, collapse/expand, fit-to-view, zoom, and optional minimap.

### MAP-07: card density

Default card: ID, title, status, priority marker, and estimate. Selection or zoom reveals additional fields. Keyboard navigation and an accessible list alternative are required for important map actions.

### MAP-08: reference safety

Editing a reference opens/edits its underlying ticket. Removing a reference does not delete the primary ticket. Removing a section returns its contents to an appropriate remaining placement or Unsorted, subject to a preview.

## 8. Calendar, events, and routines

Store date-only deadlines as dates, not arbitrary UTC midnight instants. Store actual event/work-session instants with timezone context. Support ticket work blocks independently of deadlines and allow several blocks for one ticket.

Calendar has Month, Upcoming/presets and Sunday-first Week. Home provides Day Agenda. Rescheduling shows the new times before confirmation where fixed-event semantics are involved. Routines and recurring events require a recurrence rule plus exceptions, rather than creating unbounded future rows.

Use the user's configured timezone and locale; do not infer them from a source path. The initial known user timezone is Asia/Tokyo, but the application must permit changing it.

## 9. Time tracking

### TIME-01: global timer

One active timer in the current application/account model; one timer per account is the target; the first implementation synchronizes the active record and flags offline overlaps, with stronger online coordination still to be hardened. Timer can attach to a ticket or be unassigned. Starting another session offers a clear switch/pause action without losing elapsed time.

### TIME-02: persistence and recovery

Persist timer start, pause, resume, stop, and association changes. Recover after restart/crash. Calculate duration from persisted timestamps and explicit segments, not only an interval counter in the renderer. Device sleep and large clock changes require a user-visible review policy.

### TIME-03: manual entries and summaries

Support editable manual time entries. Keep an audit trail for corrections. Show estimate versus tracked time on tickets, and daily/project summaries. Split daily totals across midnight in the display timezone while retaining original entry instants.

### TIME-04: overlap

Never silently double-count or discard overlapping sessions. Local validation and future cross-device sync must surface overlaps for review according to the selected timer policy.

## 10. Quick Add and search

Quick Add is title-first and supports ticket and event types. Optional project/date/priority/estimate chips expand only as needed. Preserve drafts when switching views. A ticket requires a valid project or an explicitly defined personal inbox destination; settle the inbox policy during implementation.

Notes UI/capture is deferred to reduce clutter; preserve saved data and backup/sync compatibility.

Current search covers ticket titles, descriptions, labels, keys and project names; event search is planned. Search results open the same underlying objects rather than copies.

## 11. Themes and dashboard sizing

Accepted baseline: Graphite / Cyan, using the first combined concept, adapted to a normal compact window used as a dashboard.

Separate color palette, density, typography scale, and panel layout. Provide themes from the first implementation slice. Current set: Graphite, Terminal, Paper, Midnight and System. Profiles change typography, shape and surfaces; each theme also offers several color schemes (default Graphite/Cyan, Terminal/Amber, Paper/Sage, Midnight/Lavender) chosen in a Theme-tab section that follows the selected theme.

Support resizable contextual panel and ticket inspector, saved widths, flexible main canvas, Comfortable and Compact density, and text scaling. On a large screen, use available width for useful information rather than oversized padding or huge KPI cards.

Detailed values and breakpoints are in the design-system document.

## 12. Accounts, persistence, and local sync

A real transactional database stores workspaces, projects, tickets, events, work blocks, time entries, notes, settings, and account/device metadata. Attachment bytes may live in a managed file store with database metadata and hashes.

Selected architecture: native Python + PySide6 / Qt Widgets, one local SQLite database per device, and an optional authenticated Python sync hub. The owner confirmed an always-on Linux LAN hub, private username/password accounts with registered devices, merge/review conflict handling, and reliance on OS/disk encryption.

Do not open one live SQLite file from several machines over a shared network folder. Sync application-level changes through an authenticated service. Never put the working database inside the Git checkout or a folder that a consumer file-sync tool overwrites while the application is using it.

Account authentication, offline local unlock, workspace authorization, device registration, and encryption are separate concerns. Store password hashes with suitable salts and parameters, never plaintext. Device credentials are protected by an OS credential mechanism where available; document safe Linux fallback behavior.

## 13. Future team capabilities

Personal application first. Team support later introduces memberships, owners/admins/members, explicit sharing/linking, assignees, auditability, and appropriate access controls.

Plan stable workspace IDs and authorization boundaries now. Do not implement team access as a client-side filter over otherwise accessible personal records. A shared link is an explicit object/authorization relationship, not a hidden duplication of personal work.

## 14. Future GitHub / Code area

Initial code integration is a repository overview: repository identity/URL, current or tracked branch, latest commit ID, release/tag when available, last update, checks, and linked issues/PRs.

Distinguish remote repository metadata from local checkout state. Working-tree changes, ahead/behind counts, and local branch require a selected accessible local checkout. Files and diffs follow later. Editing, terminal, pushing, merging, and shell execution are outside the initial overview.

Store provider secrets in credential storage and redact logs. Never show fictional mockup repository metadata as a connected real repository.

## 15. Data reliability, accessibility, and quality

- Transactional migrations, foreign keys, integrity constraints, and backups.
- Recoverable deletions, durable outbox for sync, and visible conflict state.
- Keyboard-operable essential workflows and focus management.
- Status conveyed by text/icon as well as color.
- Accessible text contrast, scalable text, reduced-motion support, and no mandatory drag-only actions.
- Long titles, empty states, loading, errors, offline state, and no-connection states designed explicitly.
- No fake success toasts or functional-looking controls without an implemented action.
- Local logs omit passwords, session tokens, personal note bodies, and unnecessary ticket content.
- Cross-platform paths and native build verification; no hardcoded Windows runtime data path.

## 16. Milestones and implementation status

1. Documentation and infrastructure decisions.
2. Cross-platform scaffold, theme system, settings persistence, and account/database foundation.
3. Working local Today, ticket CRUD, Kanban/Details, and durable timer.
4. Calendar/work blocks, major-event countdowns, and notes.
5. Project Map with rule-based sections and robust manual placement.
6. Authenticated local sync, conflict review, device management, and backup/restore.
7. Repository overview and later team features.

Some foundation work for sync begins in milestone 2 even if the network feature ships later. Do not postpone stable IDs, revision metadata, or workspace authorization until the sync UI is built.

## 17. Acceptance examples

| ID | Observable acceptance |
|---|---|
| A-01 | Home has no secondary sidebar; Projects reveals one and it can collapse. |
| A-02 | Editing a ticket's title/status in one view updates every other view and survives restart. |
| A-03 | Overdue deadlines stay unchanged after midnight and restart. |
| A-04 | Three major-event countdowns handle Today, pinned events, and timezone date changes. |
| A-05 | Moving a scheduled work session does not change the ticket deadline. |
| A-06 | Starting, pausing, and stopping a timer survives navigation and restart without lost time. |
| A-07 | A new map ticket matches a section or appears in Unsorted. |
| A-08 | New rules preserve manually placed cards; releasing a pin restores automatic placement. |
| A-09 | A map drag previews classification changes and Undo reverses both fields and placement. |
| A-10 | A linked map reference edits one shared ticket and removing it does not delete the ticket. |
| A-11 | A dependency block does not silently change workflow status. |
| A-12 | Themes, density, text scale, and panel widths persist at their documented scopes. |
| A-13 | Database writes and failed migrations cannot leave a partial ticket or corrupt its relations. |
| A-14 | Two-device sync, when implemented, survives duplicate requests, offline edits, conflict, and deletion. |
| A-15 | Another account/workspace cannot read unauthorized private records through the data/API layer. |
| A-16 | Windows and the selected Linux target launch from their own native package and preserve user data. |
| A-17 | Unimplemented Code/Team controls explain availability rather than pretending to complete actions. |

## 18. Confirmed infrastructure decisions

Installable offline-capable Windows/Linux desktop; automatic same-LAN synchronization and manual Sync; an always-on Linux hub; private username/password accounts and registered devices; merge independent fields and review same-field conflicts; target one active account timer with offline-overlap review; Graphite/Cyan, Charcoal/Amber/Sage, Light and System modes with independent density/text size; Linux Mint and 1920×1200 dashboard display; login protection with OS/disk encryption.

Initial packages target x64 as a development assumption. Verify exact Mint version and CPU before native Linux deployment. Hub address/certificate and remote-machine access are operational setup details, not invented configured endpoints. Product development began after these decisions were recorded.

## 19. Provenance

The decision log records accepted product choices. DESIGN_SYSTEM.md defines the native layout and visual profiles; docs/screenshots/current/ provides current UI references. The written specification is authoritative for behavior.


## 20. Latest owner correction — compact native app

The owner explicitly requests a normal windowed app with small text, compact pieces and tight spacing following the compact native dashboard layout. Default1280×800, minimum980×640, resizable; the display resolution1920×1200 must not dictate the window size. Today uses compact rows with Priorities/Due today/Overdue counts, followed by three small next-event rows; Day Agenda sits alongside. Narrow screens use Tasks/Agenda tabs when the inspector needs room. Keep the compact project pane, five Kanban lanes, detail inspector, footer quick capture and daily tracked total.

Passwords have no minimum length; simple values such as tyler are valid. Remember local sign-in after account creation/login, including across application restarts. Explicit Options → Log out clears remembered sign-in and requires the next login. Store a local account/device marker, never the password, outside backups and sync. Existing password verifiers remain valid; an authenticated local-password-change action is available.

Use bounded native modal forms with scrolling content and a fixed action footer. Ticket work blocks are real linked records; moving a block cannot edit its ticket deadline. The project board includes project/status/label filters and real checklist controls. Map sections/rules can be edited, with preserved manual placement and zoom controls. These corrections override the earlier larger-dashboard layout guidance.


## Calendar and map refinement — 2026-11-04

Latest owner instructions override earlier Notes UI/simple calendar/palette-only concepts. Exact behavior: docs/product/CALENDAR_AND_MAP.md and docs/product/DESIGN_SYSTEM.md.

- Month, Upcoming/details/presets, Sunday–Saturday Week; ordered color/duration marks.
- Click event/work editing; 15-minute single-day move/resize and Undo; independent deadlines.
- Multi-day events, yearly birthdays, metadata/color/archive; Home events/new tickets/timer.
- Graphite/Terminal/Paper/Studio change fonts, shapes and surfaces. Hide Notes UI, preserve data.
- Section center nests; right/left means after/before. Ticket right/left means dragged child/parent.
- Hold 1.5 seconds, ghost/progress, release and confirm. Early release/Cancel changes nothing.
- Parentage stays separate from dependency blocking. Preview inherited tags and empty component/milestone values.
- Collapsible Unsorted, red nonzero count. Reject cycles/cross-project links locally/on hub; Undo restores records.


## Quick Add, screenshot and label refinement — 2026-11-04

Correct rounded native control artifacts, bright tab lines and clipped row badges. Polish Quick Add with initial state/priority, preset labels, descriptions, estimates, checklists, parent/map choices and batch capture. Preserve drafts on failure and atomically persist creation/classification/placement.

Preset labels include red bug and teal feature. Enter/comma/Add commits a typed label without submitting the modal; chips are removable and saved custom names appear in suggestions. Use consistent colors across editor/cards, with visible text.

Apply theme-matched native Windows caption/text/border colors on supported systems, preserving ordinary OS window behavior. Exact scope and platform limits: docs/product/QUICK_ADD_AND_LABELS.md.
