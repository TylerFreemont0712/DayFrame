# Working on DayFrame

Read AGENTS.md, SPEC.md, docs/DECISIONS.md, docs/ARCHITECTURE.md and docs/CURRENT_STATUS.md before changing behavior. Accepted concepts and direct owner decisions take precedence over incidental differences in old screenshots.

## Local development

Clone https://github.com/TylerFreemont0712/DayFrame.git. Use Python 3.14 and a separate virtual environment on each OS. Run scripts/setup-windows.ps1 or sh scripts/setup-linux.sh, then install requirements-dev.txt using that environment.

Windows:

```powershell
.venv\Scripts\python.exe app.py --data-dir build/dev-profile
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m PyInstaller DayFrame.spec --noconfirm
$env:QT_QPA_PLATFORM = 'offscreen'
dist\DayFrame\DayFrame.exe --smoke-test --data-dir build/smoke-profile --screenshots build/smoke-screens
```

Linux:

```sh
.venv/bin/python app.py --data-dir build/dev-profile
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m PyInstaller DayFrame.spec --noconfirm
QT_QPA_PLATFORM=offscreen dist/DayFrame/DayFrame --smoke-test --data-dir build/smoke-profile --screenshots build/smoke-screens
```

Smoke checks require a new, unconfigured profile each time. Never use the normal runtime profile as a fixture. Keep the complete portable folder.

## Iteration workflow

1. Pull main and create a descriptive branch, such as feature/calendar-reminders.
2. Keep changes focused. Use the shared store/domain layer so every view sees the same tickets.
3. Run relevant checks. Functional changes require the full unit suite; packaging/resource changes also require the packaged smoke check.
4. Update affected specification/status docs and CHANGELOG.md.
5. Open a PR with validation and screenshots for visible changes. Check affected themes and window sizes.
6. Review the diff and Windows/Linux CI results before merging.

CI tests and packages Windows and Ubuntu builds and saves bundles and smoke screenshots as temporary Actions artifacts. Ubuntu CI does not establish compatibility with the owner's specific Mint installation. No branch protection rule is automatically enforced; the owner controls repository policy.

## Version and release

Keep versions aligned in pyproject.toml, dayframe/__init__.py, scripts/installer.nsi and Start DayFrame.cmd. QApplication reads the package version. Build on the target OS. For a Windows installer, install NSIS and run:

```powershell
.venv\Scripts\python.exe scripts/build-installer.py 'C:\Program Files (x86)\NSIS\makensis.exe'
```

Verify with an isolated profile before tagging vX.Y.Z. Publish installers or portable bundles as GitHub Release assets rather than committing binaries. Releases are manual; pushing a tag does not automatically publish a binary.

## Compatibility and design

DayFrame replaces the TimeManager name in 0.5.0. Profile directories, SQLite filename, keyring service, drag MIME type, TM_HUB_* variables and sync protocol remain stable. See docs/BRANDING.md. Changing storage identity requires an explicit migration and continuity tests.

Keep the app native Python/PySide6, with transactional SQLite/outbox writes, account isolation, explicit map confirmations and manual placement. Third-party notices are in docs/THIRD_PARTY.md. Never commit runtime profiles, device credentials, private certificates, local archives or builds.
