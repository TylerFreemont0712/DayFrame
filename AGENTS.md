# DayFrame development

Read SPEC.md, docs/DECISIONS.md, docs/ARCHITECTURE.md, and docs/CURRENT_STATUS.md before changing behavior.
Use Python, PySide6 Qt Widgets and QGraphicsView for the application.

Default Graphite/Cyan uses the compact dashboard layout in a compact 1280x800 resizable window, minimum980x640. 1920x1200 is the owner's display size, not the application size. Themes, density, font scale and panel
sizes are independent. Today has no contextual sidebar. Navigation glyphs use bundled scalable fonts; the application icon is a packaged DayFrame raster asset.

Tickets are shared records across all views. Preserve deadlines, manual map placement,
account isolation, transactional SQLite/outbox writes and recoverable sync conflicts.
Never store passwords/tokens in source or share a live SQLite file between devices.
Database imports must preserve the original and must not overwrite a configured native account.

Run .venv/Scripts/python.exe -m unittest discover -s tests -v on Windows, or
.venv/bin/python -m unittest discover -s tests -v on Linux, after functional changes.
Use isolated build/test-data for tests; never use the real profile as a fixture.
Run the packaged smoke check when changing packaging/resources. A Windows pass does not
verify Linux Mint. Keep docs honest about delivered features and tested platforms.

Keep the checkout focused on the current native app, current branding and useful documentation. Do not retain superseded implementations, mockups, logos or version archives. Runtime data belongs outside
the checkout. No remote deployment, publication, firewall or background-service install is
implied by source work. Preserve provided third-party notices when packaging.

The owner authorized the private TylerFreemont0712/DayFrame GitHub source repository.
Follow CONTRIBUTING.md for iterations. The application package is dayframe.
Keep established runtime paths, database filename, keyring service and sync identifiers unchanged;
see docs/BRANDING.md. Never commit live data, local sessions, private keys or generated builds.

The owner explicitly allows simple passwords without a minimum length. Local auto-login persists until Options → Log out. Keep local remembering outside SQLite backups/sync and preserve old verifiers.

Home/Calendar share planning.py and Sunday-first weeks. Keep events/tickets/blocks/timer connected; deadlines stay separate. Notes UI is hidden; preserve data. Map classification/linking/nesting requires a 1.5s target hold, ghost preview and release confirmation. Preserve placement/Undo; reject cycles/cross-project links; separate parentage/dependencies. Update hub with synchronized fields. See docs/CALENDAR_AND_MAP.md.

Label inputs use the shared chip editor; Enter adds a label without saving the ticket. Keep preset colors consistent, preserve custom names and saved suggestions, and prevent chip/control overlap. Quick Add capture/classification must be atomic. Native frame theming is Windows-guarded and must preserve standard OS controls.
