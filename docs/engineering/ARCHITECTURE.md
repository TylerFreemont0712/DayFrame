# Native application architecture

DayFrame 0.6.0 uses **PySide6 / Qt Widgets**, SQLite and a Python LAN hub.

## Boundaries

The package is split by layer. Lower layers never import higher ones: `core` has no Qt or SQLite, `data` and `sync` have no Qt, and only `ui` touches widgets. [CODE_MAP.md](CODE_MAP.md) lists every module, how the window mixins connect, and which threads run what.

| Path | Responsibility |
|---|---|
| app.py, \_\_main\_\_.py | QApplication lifecycle, platform data path, per-profile process lock, isolated smoke check |
| hub.py | Stable `python -m dayframe.hub` launch path for installed hub services |
| core/domain.py | Shared validation, dates, password hashing, rules, dependencies, field comparisons |
| core/planning.py | Shared calendar projections for Home and Calendar (Sunday-first weeks, occurrences, overlap lanes) |
| core/palettes.py, preferences.py, timezones.py | Themes, color schemes and custom color roles; preference defaults/validation; time zone lists for pickers and world clocks |
| data/store.py, schema.sql, schema_definitions.json | SQLite migrations, account scope, normalized relations, transactions/outbox, backup/import |
| sync/client.py | Authenticated push/pull, certificate pinning, OS keyring, conflict reconciliation |
| sync/hub.py | Optional private HTTP/TLS service with SQLite change feed and device registry |
| ui/window/ | Main window: `main.py` owns state, async jobs and refresh; one mixin module per page or concern |
| ui/views/ | Painted view widgets: Kanban lanes, project Map, Calendar, Today agenda, Settings panel |
| ui/dialogs.py, widgets.py, labels.py | Quick Add/section/conflict dialogs, small widget helpers, label chip editor and painting |
| ui/theme.py, window_frame.py | Palette, font and size application, Qt style rules, QtAwesome glyphs; guarded Windows DWM frame colors |
| ui/color_picker.py, zone_picker.py | Color wheel and swatches for custom colors; searchable time zone picker |
| ui/workers.py, dragdrop.py | QThreadPool worker delivery; the shared ticket drag MIME type |

Qt style sheets provide the native control appearance. User content is displayed as plain text or edited in QPlainTextEdit.

Password hashing and network requests run through QThreadPool workers. Qt widgets are touched only on the GUI thread. SQLite access shares an RLock and transaction/savepoint boundary. Timer drawing uses a one-second GUI tick; durations come from persisted timestamps, not tick counts. Automatic sync polls every five seconds while open.

Editor drafts block destructive navigation with Save/Discard/Cancel. Unrelated refreshes leave a dirty editor open. Ticket saves send changed fields rather than rewriting every field, reducing accidental overwrite of synchronized changes.

## Persistence and compatibility

Each device has its own SQLite database, using foreign keys, WAL, schema version 5, normalized label/dependency tables, and atomic domain/outbox writes. Sequential migrations preserve saved records and password parameters while adding work blocks, event metadata and map relationships. Database import uses SQLite's backup API from a read-only source connection.

Native runtime paths are %LOCALAPPDATA%\TimeManager and $XDG_DATA_HOME/TimeManager. The source directory is never the default data directory. Window geometry and view settings are local preferences, not ticket entities.

The hub synchronizes application-level changes between independent databases. The Python client and Python hub are integration-tested together. Schema 5 and sync protocol 1 are the current baseline. Schema 5 adds repository and changeset records; a hub must be updated before clients that use the Code page sync them.

## Packaging and icons

PySide6-Essentials supplies Qt Widgets, Gui, Core and Svg without WebEngine. QtAwesome supplies bundled scalable navigation icon fonts. assets/DayFrame.png and .ico are exported from the image-generated DayFrame icon master, and the PNG is packaged as a Python resource. The original master, logo and prompts are retained; see [BRANDING.md](../operations/BRANDING.md).

PyInstaller builds a standalone platform-specific folder. Windows gets a per-user NSIS installer; Linux must be built/tested on Linux. requirements.txt pins direct dependencies; requirements-windows.lock.txt records the tested Windows environment. The headless hub only needs its own smaller requirements file.

The current in-memory snapshots rebuild native views after committed changes. This is appropriate for the foundation; large collections need paged database queries and virtual/delegate rendering before claiming stress-tested scale. The current map renders the project's loaded cards and has a table alternative.

## References

- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [QGraphicsView](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsView.html)
- [Qt deployment](https://doc.qt.io/qtforpython-6/deployment/index.html)
- [QtAwesome](https://qtawesome.readthedocs.io/)
- [SQLite backup API](https://www.sqlite.org/backup.html)


## Compact window and trusted local session

The current window defaults to 1280×800 with a 980×640 minimum. Text uses an 8.5 pt design size scaled by the text-size preference, which defaults to 90%. Layout revision 3 replaced old oversized geometry once; revision 4 moved profiles on the old 100% default to 90%. The inspector preserves small-window usability and Today can use Tasks/Agenda tabs.

Store.restore_session() reads a local account/device marker, register/login remember it, and logout removes it. The marker contains no password and lives outside SQLite backups/outbox. This implements the owner's preference for local convenience, not a new encryption boundary. Short/blank passwords use the same verifier format.

Home/Calendar share planning.py. Map hierarchy/rules/sequence are validated in domain.py and enforced by Store/Hub. Confirmed map changes and Undo restore transactional records. UI history is session-local. See [CALENDAR_AND_MAP.md](../product/CALENDAR_AND_MAP.md).

The local ticket.capture action composes existing ticket/relationship/placement commands under one outer transaction and uses existing outbox fields. Labels are ordinary ticket labels; color presets are UI definitions. Native frame theming is a guarded application event filter and has no account/profile access.
