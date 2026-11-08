# DayFrame development

Read SPEC.md, docs/product/DECISIONS.md, docs/engineering/ARCHITECTURE.md, and docs/status/CURRENT_STATUS.md before changing behavior.
docs/engineering/CODE_MAP.md maps the package layout; docs/README.md holds the documentation layout and rules. Future ideas go in docs/status/IDEAS.md.
Use Python, PySide6 Qt Widgets and QGraphicsView for the application.

## Writing and commit history

Write commit messages, code comments, PR descriptions, review comments and release notes in plain, natural language. Describe the actual change and its reason. Avoid boilerplate, promotional wording, process narration and unnecessary mentions of assistants, models or generation tools. Do not add automatic generation footers or co-author trailers. Preserve required third-party attribution.

Keep commit titles short and concrete, such as "Fix overlapping calendar events". Add a body only when it explains a useful reason, tradeoff or validation result. Code comments should explain non-obvious intent or constraints rather than repeat the code.

Commit regularly as coherent pieces of work become complete and checked. Each commit should have one clear purpose and be independently understandable and revertible; include the tests and documentation needed for that change. Split unrelated fixes and formatting into separate commits. Avoid both large end-of-task dumps and trivial filler commits. Keep shared history intact; do not rewrite or squash published commits unless the owner asks.

Follow existing session authorization for committing and pushing. These conventions do not grant new permission to publish or contact others.

## Release cadence

Ordinary development changes source only. Keep useful Unreleased changelog notes, but do not bump versions, build installers/portable bundles, replace the current release, tag or publish unless the owner explicitly requests that action. Ship releases in deliberate waves. See docs/operations/RELEASES.md for the current packaged baseline and release checklist.

At a natural completion point, suggest a release if significant unreleased work is ready, or if the last package is at least 14 calendar days old and source changes are waiting. Summarize the changes and validation first, then ask whether to prepare a release. Documentation/comment-only work does not need a release suggestion. Ask once per task; respect a deferral and wait for an explicit answer. Age or significance is a reason to ask, never permission to build. This is a check during active work, not a background reminder.

Routine CI runs source tests only. Package builds and packaged smoke checks require an explicitly requested release or validation build; manual CI packaging is opt-in and must not be dispatched without that request. Keep validation builds separate from the current release. If packaging/resource changes need a packaged check, report that verification as pending until authorized rather than rebuilding automatically. Preview source changes through the source entry point; the regular launcher may still open the last packaged version.

## Application rules

Default Graphite/Cyan uses the compact dashboard layout in a compact 1280x800 resizable window, minimum980x640. 1920x1200 is the owner's display size, not the application size. Text size defaults to 90%. Themes, density, font scale and panel
sizes are independent. Today has no contextual sidebar. Navigation glyphs use bundled scalable fonts; the application icon is a packaged DayFrame raster asset.

Tickets are shared records across all views. Preserve deadlines, manual map placement,
account isolation, transactional SQLite/outbox writes and recoverable sync conflicts.
Never store passwords/tokens in source or share a live SQLite file between devices.
Database imports must preserve the original and must not overwrite a configured native account.

Run .venv/Scripts/python.exe -m unittest discover -s tests -v on Windows, or
.venv/bin/python -m unittest discover -s tests -v on Linux, after functional changes.
Use isolated build/test-data for tests; never use the real profile as a fixture.
Packaging/resource changes require a packaged smoke check before release; follow the
release authorization rules above. A Windows pass does not verify Linux Mint. Keep docs
honest about delivered features and tested platforms.

Keep the checkout focused on the current native app, current branding and useful documentation. Do not retain superseded implementations, mockups, logos or version archives. Runtime data belongs outside
the checkout. No remote deployment, publication, firewall or background-service install is
implied by source work. Preserve provided third-party notices when packaging.

The owner authorized the private TylerFreemont0712/DayFrame GitHub source repository.
Follow CONTRIBUTING.md for iterations. The application package is dayframe.
Keep established runtime paths, database filename, keyring service and sync identifiers unchanged;
see docs/operations/BRANDING.md. Never commit live data, local sessions, private keys or generated builds.

The owner explicitly allows simple passwords without a minimum length. Local auto-login persists until Options → Log out. Keep local remembering outside SQLite backups/sync and preserve old verifiers.

Home/Calendar share planning.py and Sunday-first weeks. Keep events/tickets/blocks/timer connected; deadlines stay separate. Notes UI is hidden; preserve data. Map classification/linking/nesting requires a 1.5s target hold, ghost preview and release confirmation. Preserve placement/Undo; reject cycles/cross-project links; separate parentage/dependencies. Update hub with synchronized fields. See docs/product/CALENDAR_AND_MAP.md.

Label inputs use the shared chip editor; Enter adds a label without saving the ticket. Keep preset colors consistent, preserve custom names and saved suggestions, and prevent chip/control overlap. Quick Add capture/classification must be atomic. Native frame theming is Windows-guarded and must preserve standard OS controls.
