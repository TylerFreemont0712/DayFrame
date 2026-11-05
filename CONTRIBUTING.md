# Working on DayFrame

Read AGENTS.md, SPEC.md, docs/DECISIONS.md, docs/ARCHITECTURE.md and docs/CURRENT_STATUS.md before changing behavior. Accepted concepts and direct owner decisions take precedence over incidental differences in old screenshots.

## Local development

Clone https://github.com/TylerFreemont0712/DayFrame.git. Use Python 3.14 and a separate virtual environment on each OS. Run scripts/setup-windows.ps1 or sh scripts/setup-linux.sh, then install requirements-dev.txt using that environment.

Windows:

```powershell
.venv\Scripts\python.exe app.py --data-dir build/dev-profile
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux:

```sh
.venv/bin/python app.py --data-dir build/dev-profile
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Use the source entry point to preview ongoing changes. Start DayFrame.cmd prefers an existing packaged release, which stays unchanged between release waves. Never use the normal runtime profile as a test fixture.

## Iteration workflow

Commit small, complete changes regularly during development. Keep each commit focused on one purpose, with related tests and docs alongside the code. Separate unrelated fixes or formatting; do not leave all completed work for one large final commit or create filler commits just to increase the count. Preserve published history unless the owner requests a rewrite.

Use short, concrete commit titles and natural language in code comments, PRs and discussions. Explain what changed and why. Avoid canned narration, unnecessary tool/assistant attribution and automatic generation footers or co-author trailers. Keep required third-party attribution. Comments should explain intent or constraints rather than obvious code.

1. Pull main and create a descriptive branch, such as feature/calendar-reminders.
2. Keep changes focused. Use the shared store/domain layer so every view sees the same tickets.
3. Run relevant source checks. Functional changes require the full unit suite. Packaged checks wait for an explicitly requested build; record them as pending when needed.
4. Update affected specification/status docs and the Unreleased section of CHANGELOG.md. Bump versions only for an explicitly requested release.
5. Open a PR with validation and screenshots for visible changes. Check affected themes and window sizes.
6. Review the diff and Windows/Linux CI results before merging.

Pushes and PRs run Windows and Ubuntu source tests. Manual runs also default to tests only. After an explicit request for a release or validation build, the Native desktop checks workflow can be dispatched with Build and verify portable packages enabled; it adds portable bundles, packaged smoke checks and temporary Actions artifacts. It does not build the NSIS installer, publish a release or replace the local package. Ubuntu CI does not establish compatibility with the owner's specific Mint installation. No branch protection rule is automatically enforced; the owner controls repository policy.

## Version and release

Follow [the release policy](docs/RELEASES.md): ship in waves only when the owner requests it. Routine commits do not rebuild packages, replace the current release or bump its version. At task completion, suggest a release for significant unreleased work or when the last package is at least 14 days old with source changes waiting; documentation/comment-only work does not need a suggestion. Ask once and wait for an explicit answer before building.

For an authorized release, keep versions aligned in pyproject.toml, dayframe/__init__.py, scripts/installer.nsi and Start DayFrame.cmd. QApplication reads the package version. Build on the target OS. For an authorized validation build, leave the release version and current package alone.

Windows packaging:

```powershell
.venv\Scripts\python.exe -m PyInstaller DayFrame.spec --noconfirm
$env:QT_QPA_PLATFORM = 'offscreen'
dist\DayFrame\DayFrame.exe --smoke-test --data-dir build/smoke-profile --screenshots build/smoke-screens
```

Linux packaging:

```sh
.venv/bin/python -m PyInstaller DayFrame.spec --noconfirm
QT_QPA_PLATFORM=offscreen dist/DayFrame/DayFrame --smoke-test --data-dir build/smoke-profile --screenshots build/smoke-screens
```

Smoke checks require a new, unconfigured profile each time; choose a fresh path for a repeat run. Keep the complete portable folder. For an authorized Windows installer, install NSIS and run:

```powershell
.venv\Scripts\python.exe scripts/build-installer.py 'C:\Program Files (x86)\NSIS\makensis.exe'
```

Verify with an isolated profile before updating the stable package. Tagging vX.Y.Z and publishing GitHub Release assets require an explicit request; a local build alone does not authorize publication. If requested, publish binaries as Release assets rather than committing them. Pushing a tag does not automatically publish a binary. Record the packaged version, date, source commit and validation in docs/RELEASES.md when a release is actually built.

Keep the NSIS compiler with its Include, Contrib, Stubs and COPYING files. The installer helper locates its resource root for both installed and portable compilers and copies COPYING into the packaged notices. The smoke report includes the package version and 61 screens covering the main views plus Settings across four themes and two window sizes. An installer payload can be extracted with the full 7-Zip executable, compared with the portable folder and smoke-tested with another fresh profile.

## Compatibility and design

Profile directories, SQLite filename, keyring service, drag MIME type, TM_HUB_* variables and sync protocol remain stable. See docs/BRANDING.md. Changing storage identity requires an explicit migration and continuity tests.

Keep the app native Python/PySide6, with transactional SQLite/outbox writes, account isolation, explicit map confirmations and manual placement. Third-party notices are in docs/THIRD_PARTY.md. Never commit runtime profiles, device credentials, private certificates, local archives or builds.
