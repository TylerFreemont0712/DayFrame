# Native application architecture

DayFrame 0.5.1 uses **PySide6 / Qt Widgets**, SQLite and a Python LAN hub.

## Boundaries

| Module | Responsibility |
|---|---|
| app.py / dayframe.app | QApplication lifecycle, platform data path, per-profile process lock, isolated smoke check |
| ui.py / widgets.py / dialogs.py | Native windows, forms, tables, lists, dialogs, and background-worker delivery |
| settings.py | Settings category navigation and focused View, Theme, Local data, Sync and Account forms |
| kanban.py | Ticket card delegate, status lanes and temporary drag destination plates |
| planning.py / calendar_views.py | Shared calendar projections and month/upcoming/week gestures |
| project_map.py | QGraphicsView scene, cards, section geometry, dependency arrows, pan/zoom |
| labels.py | Native flow/chip editor, label catalog/colors and shared card label painting |
| window_frame.py | Guarded native DWM theme attributes for Windows top-level windows |
| theme.py | Semantic palettes, QApplication font/palette, Qt widget style rules, QtAwesome glyphs |
| domain.py | Shared validation, dates, password hashing, rules, dependencies, field comparisons |
| store.py | SQLite migrations, account scope, normalized relations, transactions/outbox, backup/import |
| sync.py | Authenticated push/pull, certificate pinning, OS keyring, conflict reconciliation |
| hub.py | Optional private HTTP/TLS service with SQLite change feed and device registry |

Qt style sheets provide the native control appearance. User content is displayed as plain text or edited in QPlainTextEdit.

Password hashing and network requests run through QThreadPool workers. Qt widgets are touched only on the GUI thread. SQLite access shares an RLock and transaction/savepoint boundary. Timer drawing uses a one-second GUI tick; durations come from persisted timestamps, not tick counts. Automatic sync polls every five seconds while open.

Editor drafts block destructive navigation with Save/Discard/Cancel. Unrelated refreshes leave a dirty editor open. Ticket saves send changed fields rather than rewriting every field, reducing accidental overwrite of synchronized changes.

## Persistence and compatibility

Each device has its own SQLite database, using foreign keys, WAL, schema version 4, normalized label/dependency tables, and atomic domain/outbox writes. Sequential migrations preserve saved records and password parameters while adding work blocks, event metadata and map relationships. Database import uses SQLite's backup API from a read-only source connection.

Native runtime paths are %LOCALAPPDATA%\TimeManager and $XDG_DATA_HOME/TimeManager. The source directory is never the default data directory. Window geometry and view settings are local preferences, not ticket entities.

The hub synchronizes application-level changes between independent databases. The Python client and Python hub are integration-tested together. Schema 4 and sync protocol 1 are the current baseline.

## Packaging and icons

PySide6-Essentials supplies Qt Widgets, Gui, Core and Svg without WebEngine. QtAwesome supplies bundled scalable navigation icon fonts. assets/DayFrame.png and .ico are exported from the image-generated DayFrame icon master, and the PNG is packaged as a Python resource. The original master, logo and prompts are retained; see BRANDING.md.

PyInstaller builds a standalone platform-specific folder. Windows gets a per-user NSIS installer; Linux must be built/tested on Linux. requirements.txt pins direct dependencies; requirements-windows.lock.txt records the tested Windows environment. The headless hub only needs its own smaller requirements file.

The current in-memory snapshots rebuild native views after committed changes. This is appropriate for the foundation; large collections need paged database queries and virtual/delegate rendering before claiming stress-tested scale. The current map renders the project's loaded cards and has a table alternative.

## References

- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [QGraphicsView](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsView.html)
- [Qt deployment](https://doc.qt.io/qtforpython-6/deployment/index.html)
- [QtAwesome](https://qtawesome.readthedocs.io/)
- [SQLite backup API](https://www.sqlite.org/backup.html)


## Compact window and trusted local session

The current window defaults to1280×800 with980×640 minimum and8.5pt base text. Layout revision3 replaces old oversized geometry once. The inspector preserves small-window usability and Today can use Tasks/Agenda tabs.

Store.restore_session() reads a local account/device marker, register/login remember it, and logout removes it. The marker contains no password and lives outside SQLite backups/outbox. This implements the owner's preference for local convenience, not a new encryption boundary. Short/blank passwords use the same verifier format.

Home/Calendar share planning.py. Map hierarchy/rules/sequence are validated in domain.py and enforced by Store/Hub. Confirmed map changes and Undo restore transactional records. UI history is session-local. See CALENDAR_AND_MAP.md.

The local ticket.capture action composes existing ticket/relationship/placement commands under one outer transaction and uses existing outbox fields. Labels are ordinary ticket labels; color presets are UI definitions. Native frame theming is a guarded application event filter and has no account/profile access.
