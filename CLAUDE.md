# CLAUDE.md

Guidance for Claude Code in this repository. DayFrame is a private desktop planner (Today, project tickets with Kanban/Map/Details, calendar, time tracking) written in Python with PySide6 Qt Widgets, SQLite and an optional private LAN sync hub.

The project rules in AGENTS.md apply in full and take precedence over anything below:

@AGENTS.md

## Before changing behavior

Read, in this order: [SPEC.md](SPEC.md), [docs/product/DECISIONS.md](docs/product/DECISIONS.md), [docs/engineering/ARCHITECTURE.md](docs/engineering/ARCHITECTURE.md), [docs/status/CURRENT_STATUS.md](docs/status/CURRENT_STATUS.md). For navigation, start with [docs/engineering/CODE_MAP.md](docs/engineering/CODE_MAP.md); for which document holds what, see [docs/README.md](docs/README.md).

## Commands

Windows (PowerShell or Git Bash):

```powershell
.venv\Scripts\python.exe app.py --data-dir build/dev-profile          # run from source with a throwaway profile
.venv\Scripts\python.exe -m unittest discover -s tests -v             # full suite (slow: several minutes)
.venv\Scripts\python.exe -m unittest tests.test_store -v              # one module
.venv\Scripts\python.exe -m ruff format dayframe tests                # format
.venv\Scripts\python.exe -m ruff check dayframe tests                 # lint
```

Linux: use `.venv/bin/python` and prefix UI tests with `QT_QPA_PLATFORM=offscreen`. Set `QT_QPA_PLATFORM=offscreen` on Windows too when running tests from a non-interactive shell.

Never point `--data-dir` or a test at the real profile (`%LOCALAPPDATA%\TimeManager`, `~/.local/share/TimeManager`). Tests create their own folders under `build/test-data/`.

## Code layout in one screen

```
dayframe/core/   domain rules, calendar projections, palettes   (no Qt, no SQLite)
dayframe/data/   Store, schema, migrations, outbox              (no Qt)
dayframe/sync/   sync client and private hub                    (no Qt)
dayframe/ui/     window/ (main window + one mixin per page), views/ (painted widgets), shared widgets/theme
dayframe/app.py  desktop entry point;  dayframe/hub.py  stable `python -m dayframe.hub`
```

Rules that keep it navigable:

- Imports point downward only: `ui → sync → data → core`. Never import Qt or `ui` from `core`, `data` or `sync`; the hub must stay headless.
- Every write goes through `Store.command(...)`, normally via `window.execute(...)`. That keeps the domain write and its sync outbox row in one transaction. Do not add SQL to the UI.
- The window is `DayFrame` in `ui/window/main.py`, composed from mixins. A new page is a new mixin module with a `show_<page>()` method, added to the class bases in `main.py` and to the navigation rail in `shell.py`.
- Views in `ui/views/` receive the window as `self.window`, read `window.data`, and call window methods; they do not hold their own Store.
- Widgets are touched only on the GUI thread. Slow work (password hashing, network) goes through `window.run_async(fn, done)`.
- Keep `QTimer.singleShot(0, ...)` deferrals: they avoid deleting a widget inside its own event handler.
- When you add, move or rename a module, update docs/engineering/CODE_MAP.md in the same commit.

## Things that must not change casually

Runtime paths, the `timemanager.db` filename, keyring service, drag MIME type (`ui/dragdrop.py`), `TM_HUB_*` variables, sync protocol and stored status IDs are stable identifiers (see docs/operations/BRANDING.md). Changing them needs an explicit migration and continuity tests.

## Documentation and ideas

Follow the rules in [docs/README.md](docs/README.md). In short: put new future ideas in [docs/status/IDEAS.md](docs/status/IDEAS.md), record owner decisions in DECISIONS.md, keep CURRENT_STATUS.md honest about what is delivered and tested, and add a line to the Unreleased section of CHANGELOG.md for user-visible changes.

## Releases

Source work only. Do not bump versions, build packages, tag or publish unless the owner asks; see docs/operations/RELEASES.md and the release cadence section of AGENTS.md.
