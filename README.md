![DayFrame](assets/dayframe-logo.png)

# DayFrame

A private desktop dashboard for planning your day, organizing project tickets and tracking time. **Python + PySide6 / Qt Widgets**, with SQLite and optional private LAN synchronization. Windows and Linux source.

Version **0.6.0**. See [branding and storage identifiers](docs/operations/BRANDING.md) for the current assets and persistence conventions.

## What works

- Today: priorities, due/overdue work, agenda, three major-event countdowns and the active timer.
- Projects: shared Kanban, nested Map, Details, ticket inspector, checklists and dependencies.
- Calendar: marked Month, Upcoming events and Sunday-first weekly timeline; clickable event editing and work blocks.
- Map: inherited classification, parent/child tickets, section sequence links, hover ghosts, confirmation, Undo and Unsorted tray.
- Time: persistent ticket/unassigned timer, manual entries and overlap review.
- Rich Quick Add, colored preset/custom labels, private accounts and remembered login until Logout.
- Graphite, Terminal, Paper, Midnight, Nord, Catppuccin, Editor and System themes, each with its own color schemes (Editor: Dracula, Tokyo Night, One Dark, Gruvbox, Solarized and more) plus a Custom scheme with a color wheel and advanced element colors; font, corner, density, text and heading size choices.
- Time zone picker with UTC offsets and current times, and world clocks in the bottom bar.
- Settings organized into View, Theme, Local data, Sync and Account, with independent View/Theme saves.
- SQLite backup/import, transactional sync outbox, private LAN hub, certificate pinning, field merges and conflict review.

See [current status](docs/status/CURRENT_STATUS.md) for verification and limitations. Reminders, richer recurrence, Code/GitHub overview, Team and mobile remain future work.

## Windows

For a source checkout, install Python 3.12+ (3.14 recommended) and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-windows.ps1
.venv\Scripts\python.exe app.py
```

Or open **Start DayFrame.cmd** after setup. The launcher also recognizes a locally built portable bundle. Standalone builds do not require a separate Python installation; keep the entire DayFrame folder with its _internal directory.

On the original development machine the checkout remains at C:\Apps\TimeManager; the folder name does not control the app's identity.

## Linux Mint

Use a user-owned checkout and a fresh Linux environment:

```sh
sh scripts/setup-linux.sh
sh start-dayframe.sh
```

Python 3.12+ (3.14 recommended) and system Qt/X11 libraries are required. See [operations](docs/operations/OPERATIONS.md) for Mint dependencies, hub setup, pairing and packaging. Linux CI targets Ubuntu; the owner's exact Mint installation still needs a live check.

## Accounts and data

Create a private account or connect an unconfigured installation to your existing LAN account. Simple passwords are accepted. Sign-in persists locally until Options → Log out. Example projects load only when explicitly requested.

The established runtime paths remain **%LOCALAPPDATA%\TimeManager** on Windows and **$XDG_DATA_HOME/TimeManager** on Linux (default ~/.local/share/TimeManager). The database remains timemanager.db. Runtime data stays outside the checkout. Do not share a live SQLite file between devices; use the optional hub.

To restore a database backup, import a consistent snapshot into an unconfigured profile. Import preserves the source backup. See [backup and recovery](docs/operations/OPERATIONS.md#backups-and-recovery).

## Development

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check dayframe tests
```

Use .venv/bin/python on Linux. Preview changes with **Preview DayFrame.cmd** (or `sh scripts/preview.sh`), which runs the source in a separate preview profile; the regular launcher may open the last packaged version. [CONTRIBUTING.md](CONTRIBUTING.md) covers branches, checks and isolated profiles. Routine GitHub Actions runs test Windows/Linux source. Packaging is opt-in for an explicitly requested release or validation build. Releases ship in waves; see [the release policy](docs/operations/RELEASES.md).

## Project guide

| Path | Contents |
|---|---|
| [SPEC.md](SPEC.md) | Full accepted product requirements |
| [CHANGELOG.md](CHANGELOG.md) | Version history and Unreleased notes |
| [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md) | Workflow, project rules and assistant guidance |
| [docs/README.md](docs/README.md) | Documentation index, folder layout and writing rules |
| [docs/product/](docs/product/) | Owner decisions, design system, calendar/map and Quick Add/label behavior |
| [docs/engineering/](docs/engineering/) | Architecture, [code map](docs/engineering/CODE_MAP.md), data model, accounts and sync |
| [docs/operations/](docs/operations/) | Running, hub setup, releases, branding identifiers and third-party notices |
| [docs/status/](docs/status/) | [Current status](docs/status/CURRENT_STATUS.md) and [ideas for future work](docs/status/IDEAS.md) |
| docs/screenshots/current/ | Current native UI reference screenshots |
| dayframe/core/ | Domain rules, calendar projections, theme palettes (no Qt) |
| dayframe/data/ | SQLite store, schema, migrations and sync outbox |
| dayframe/sync/ | Sync client and the private LAN hub |
| dayframe/ui/ | Main window (one module per page), views, dialogs and theme |
| tests/ | Database, sync/TLS and native UI tests |
| assets/ | Logo, generated icon master, PNG and ICO exports |

Generated installers, databases, credentials, virtual environments, build folders and temporary source archives are excluded from Git. Third-party components retain their notices; see [THIRD_PARTY.md](docs/operations/THIRD_PARTY.md). No open-source license has been selected for this private project.
