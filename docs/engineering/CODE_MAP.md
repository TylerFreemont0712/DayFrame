# Code map

Where things live in the `dayframe` package, how the pieces call each other, and which thread runs what. [ARCHITECTURE.md](ARCHITECTURE.md) explains why the boundaries exist; this file is the navigation guide. Update it in the same commit whenever a module is added, moved or renamed.

## Package layout

```
dayframe/
├── __init__.py          package version (__version__)
├── __main__.py          python -m dayframe
├── app.py               desktop entry point, profile lock, --smoke-test screen capture
├── hub.py               stable `python -m dayframe.hub` launch path (re-exports sync/hub.py)
├── resources/           packaged runtime images (application icon)
├── core/                pure Python: no Qt, no SQLite
│   ├── domain.py        validation, dates, password hashing, field merges, map rules, cycle checks
│   ├── planning.py      calendar projections shared by Today and Calendar (Sunday-first weeks)
│   ├── ticket_stats.py  Tickets overview numbers, daily/weekly series, breakdowns and quick views
│   ├── palettes.py      themes, color schemes, custom/advanced color roles, contrast helpers
│   ├── preferences.py   device preference defaults and validation (used by Store.settings)
│   └── timezones.py     time zone list, UTC offsets and labels for pickers and world clocks
├── data/                persistence: no Qt
│   ├── store.py         Store: migrations, accounts, commands, snapshot, outbox, backup/import
│   ├── schema.sql       initial SQLite schema
│   ├── demo.py          seeded large demo workspace (Settings > Local data, scripts/seed-demo.py)
│   └── schema_definitions.json   entity field definitions used by validation and sync
├── code/                version control for the Code page: no Qt, no SQLite
│   ├── git.py           GitRepo: status, shelve/restore, stage/discard, history, refs, stashes, branches, commit, fetch/pull/push
│   ├── diff.py          unified diff parser: files, hunks, numbered lines, folder tree, in-line edit spans
│   ├── graph.py         commit graph lane layout (rows, lanes, merge and fold segments)
│   └── github.py        GitHub REST client (overview, pull requests, issues) and TokenStore (keyring)
├── sync/                networking: no Qt (the hub runs with requirements-hub.txt only)
│   ├── client.py        Sync: pairing, push/pull, certificate pinning, keyring, conflict resolution
│   └── hub.py           Hub: private HTTPS change feed and device registry; main() for the service
└── ui/                  PySide6 Qt Widgets
    ├── window/          the main window, one mixin module per page or concern
    ├── views/           self-contained painted widgets
    ├── dialogs.py       Quick Add (AddDialog), SectionDialog, ConflictDialog, ClearWorkspaceDialog
    ├── code_dialogs.py  Code page dialogs: RepoDialog, CommitDialog, SwitchDialog, GitHub forms, confirm()
    ├── ticket_editor.py TicketEditor (every editable ticket field) and TicketEditDialog
    ├── widgets.py       label/button/row/column/panel helpers, FormDialog, ElidingLabel, error()
    ├── labels.py        LabelsEditor chip input, preset label colors, label pill painting
    ├── status.py        stage symbols: painted glyph, color and icon for each workflow status
    ├── theme.py         apply_theme(), CURRENT palette, fonts and sizes, Qt style sheet, icon()
    ├── color_picker.py  color wheel dialog, swatch buttons and the palette preview
    ├── zone_picker.py   searchable time zone drop-down with offsets and current times
    ├── window_frame.py  Windows-only DWM title-bar colors (guarded; no-op elsewhere)
    ├── workers.py       Worker / WorkerSignals for QThreadPool jobs
    └── dragdrop.py      TICKET_MIME, the drag contract shared by Kanban, Map and Unsorted
```

Import direction is one way: `ui → sync → data → core`, `ui → code → core`, and `ui → data`, `ui → core`. Nothing in `core`, `data`, `sync` or `code` imports Qt or anything from `ui`. Keep it that way so the hub stays headless and the domain rules stay testable without a display.

## The main window

`ui/window/main.py` defines `DayFrame(QMainWindow)`. It is assembled from mixins so that each page lives in its own file while sharing one `self`:

| Module | Mixin | Owns |
|---|---|---|
| main.py | `DayFrame` | window state, `run_async`, `execute`, `refresh`/`refresh_page`, `navigate`, Undo, draft guard (`has_draft`/`leave_editor`), close/resize events |
| records.py | `RecordLookups` | read-only lookups on `self.data`: `find_ticket`, `ticket_key`, `blocked`, `project_name`, `tracked_ms`, `code_repo`, `changeset_count` |
| account.py | `AccountMixin` | sign-in screen, register/login, database and LAN imports, local password, logout |
| shell.py | `ShellMixin` | navigation rail, masthead, utility bar (timer, totals, world clocks), search, inline capture, the one-second `tick` |
| today.py | `TodayPage` | `show_today`, layout modes, focus and figures, ticket rows, week strip and day selection, Day Agenda, countdowns and upcoming events, completion |
| projects.py | `ProjectsPage` | `show_projects`, project tree, Map/Kanban/Details, filters, sections, rules, milestones |
| inspector.py | `InspectorMixin` | compact read-only inspector, status menu, `edit_ticket` (Edit dialog), archive, work-block scheduling, `open_ticket` |
| tickets.py | `TicketsPage` | `show_tickets`, `open_ticket_details`, quick views, overview tiles/charts/table, ticket page with comments, screenshots and in-place editing |
| schedule.py | `CalendarPage` | `show_calendar`, opening and moving calendar items |
| tracking.py | `TimePage` | `show_time`, manual time entry dialog |
| settings.py | `SettingsPage` | Settings host, backup, clear workspace, conflict review, automatic and manual sync |
| capture.py | `CaptureMixin` | `quick_add` for new and existing tickets/events |
| code.py | `CodePage` | `show_code`, `open_code`, repository connection, status and `code_load` caches, git actions, Tickets tab and changesets, GitHub tab |
| code_repo.py | `CodeRepoViews` | Code page Working tree (stage/unstage/discard), History (commit graph and commit details) and Branches tabs |

Page dispatch is by name: `refresh_page()` calls `getattr(self, "show_" + self.page.lower())()`, so a page called "Time" must provide `show_time`. The navigation rail in `shell.py` lists the pages.

### Shared window state

Mixins communicate only through attributes on `self`. The important ones:

| Attribute | Set by | Meaning |
|---|---|---|
| `store`, `sync` | main | the account's `Store` and `Sync` client |
| `data` | main (`refresh`, `execute`), settings (`sync_finished`) | latest `Store.snapshot()`; every page renders from it |
| `page`, `project_id`, `project_view`, `selected` | main, projects, inspector | navigation and selection |
| `home_day`, `home_today` | today | day shown in Home's week strip and Day Agenda; resets when the date changes |
| `filter_project`, `filter_status`, `filter_label`, `search_text` | projects, shell | ticket filters |
| `draft_reader`, `draft_save` | inspector | unsaved-editor guard used by `leave_editor` |
| `undo_action` | any page, views | single-level Undo callable (Ctrl+Z) |
| `work_layout`, `context_layout`, `inspect_layout`, `page_header`, `toast` | shell, main | layout slots that pages fill |
| `jobs`, `busy` | main, account | in-flight background jobs |

### Views and how they reach the window

Each widget in `ui/views/` takes the window as its first argument and stores it as `self.window`. It reads `window.data` and calls window methods; it never talks to `Store` directly except through `window.execute(...)`.

| View | Used by | Calls back into the window |
|---|---|---|
| kanban.py `TicketList`, `BoardDelegate` | projects.py, inspector.py | `execute`, `find_ticket`, `blocked`, `project_name`, `tracked_ms`, `select_ticket`, `selected`, `undo_action`, `code_repo`, `changeset_count`, `open_code`, `schedule_ticket` |
| project_map.py `ProjectMap`, `UnsortedList` | projects.py | `execute`, `refresh`, `select_ticket`, `edit_section`, `new_section`, `new_child_ticket`, `blocked`, `ticket_key`, `undo_action`, `toast`, `code_repo`, `changeset_count`, `open_code` |
| calendar.py `MiniMonth`, `UpcomingPanel`, `WeekCalendar` | schedule.py | `open_calendar_item`, `move_calendar_item`, `quick_add`, `calendar_selected` |
| agenda.py `Agenda` | today.py, shell.py (`tick`) | `open_calendar_item` |
| home.py `WeekStrip`, `CountdownTiles`, `StatChip`, event symbols | today.py, shell.py (`tick`) | `data`, `home_select_day`, `quick_add`, `open_calendar_item` |
| charts.py `ColumnChart`, `BarList`, `stat_tile` | tickets.py | none |
| ticket_thread.py `MarkdownView`, `Thumb`, `PasteEdit`, `prepare_image` | tickets.py | `store` (reads attachment images) |
| diff_view.py `ChangeBrowser`, `DiffCanvas`, `StatBar` | code.py, code_repo.py | none; state dict owned by the page |
| commit_graph.py `CommitGraph` | code_repo.py | none |
| code_cards.py `TicketCards`, `ChangesetStrip` | code.py | `data`, `code_ticket`, `code_item` |
| settings_panel.py `SettingsPanel` | settings.py | `execute`, `build_shell`, `refresh`, `backup`, `clear_workspace`, `sync_now`, `sync_finished`, `run_async`, `review_conflict`, `change_local_password`, `logout`, `settings_section`, `github_token`, `set_github_token` |

## Writes: one path into the database

All user changes go through `Store.command(method, payload)` (usually via `window.execute`, which also refreshes the page and reports errors). Commands such as `ticket.save`, `ticket.capture`, `ticket.relate`, `section.save`, `placement.save`, `map.restore`, `event.save`, `block.save`, `time.add`, `timer.action`, `workspace.clear` and `settings.save` run inside `Store.atomic()`, which wraps the domain write and its outbox row in one SQLite transaction or savepoint. Sync later pushes the outbox. Do not write SQL from the UI or add a second write path.

## Threads, timers and signals

| What | Thread | Notes |
|---|---|---|
| All widgets, painting, `Store` reads/writes from the UI | GUI thread | Qt widgets are never touched off the GUI thread |
| `window.run_async(fn, done)` | QThreadPool worker | used for login/register (password hashing), LAN import/pairing, local password change, sync runs. `Worker.signals.done/failed` are queued back to the GUI thread, where `done(result)` runs |
| `Store` | any | one SQLite connection with `check_same_thread=False`, guarded by `Store.lock` (RLock); `atomic()` holds it for the whole transaction |
| `Sync` | worker | `Sync.guard` (Lock) prevents overlapping runs |
| `Hub` | its own threads | `ThreadingHTTPServer` in a daemon thread; `Hub.lock` (RLock) serializes database work |
| `self.timer` (1 s) | GUI | `tick()`: utility-bar timer, today total, sync label, day rollover, Home focus panel, agenda/week strip/week repaint |
| `self.sync_timer` (5 s) | GUI | `auto_sync()` when sync is enabled and no job is running |
| `ProjectMap.hover_timer` (50 ms) | GUI | drives the 1.5 s hold-to-confirm ghost preview |
| `QTimer.singleShot(0, ...)` | GUI | defers rebuilds until the current mouse/paint event has finished; do not replace these with direct calls |

Custom signals: `WorkerSignals.done/failed`, `LabelsEditor.textChanged/labelsChanged`, `MonthGrid.daySelected/dayActivated`, `ProjectMap.scaleChanged`.

The window refuses to close or log out while `self.jobs` is non-empty, so a worker never outlives the `Store` it uses.

## Tests

`tests/` mirrors the layers: `test_store.py`, `test_sync.py` (client and hub together), `test_palettes.py`, `test_preferences.py` (preferences, custom colors, time zones) for core/data; `test_ui.py`, `test_home.py`, `test_kanban.py`, `test_map_ui.py`, `test_calendar_map.py`, `test_dialogs.py`, `test_settings.py`, `test_capture_polish.py`, `test_code_ui.py` for the window and views; `test_code.py` for the git runner, GitHub client and code records; `test_branding.py` for stable runtime identifiers. `check_native_frame.py` is a manual Windows check, not part of discovery. Every test creates its own profile under `build/test-data/`.
