# DayFrame releases

Ship releases in deliberate waves. Everyday work updates source, tests and documentation; it does not rebuild or replace the packaged application. This keeps a stable daily-use version while focused commits record development between releases.

## When to suggest a release

At a natural task completion point, first summarize completed changes and validation. Ask whether to prepare a release when:

- Significant unreleased work is ready: a useful feature group, substantial UI improvements or important fixes.
- Schema, sync, account, startup, dependency or packaging changes need a coordinated rollout.
- The last package is at least 14 calendar days old and unreleased source changes are waiting.

The 14-day threshold is the initial default. Documentation, comments and internal housekeeping alone do not need a release suggestion. Check the packaged baseline below and compare its source commit with the current revision; do not infer release age from a copied file's timestamp.

Ask once per task and respect a deferral. A suggestion, elapsed time, passing CI or a significant change never authorizes a build. Continue source work and wait for an explicit answer. This check happens during active work; no background reminder is configured.

## Source work and CI

- Keep useful changes under Unreleased in CHANGELOG.md. Leave application and installer versions unchanged until a release is requested.
- Preview development through app.py. Start DayFrame.cmd prefers the existing packaged version when present.
- Pushes, PRs and default manual workflow runs perform Windows/Ubuntu source tests only.
- The Native desktop checks workflow has a boolean Build and verify portable packages input, off by default. Enable it only after the owner requests a release or validation build. It builds portable bundles and runs packaged smoke checks; it does not build an NSIS installer or publish a GitHub Release.
- Packaging/resource changes need packaged verification before shipping. If no build has been authorized, run available source checks and record packaged verification as pending. Do not create a bundle automatically to satisfy this check.

An explicitly requested validation build stays in dist/build output and does not replace release/, change the version, create a tag or publish assets. Preserve the current daily-use package.

## Requested release checklist

1. Confirm the requested version, target platforms and whether the request covers local packaging, tagging or GitHub publication. Complete all preparation and checks within the existing authorization before asking for any remaining publication approval.
2. Review the diff since the last packaged source commit. Select a coherent wave and summarize user-visible changes, compatibility concerns and known limitations.
3. Align pyproject.toml, dayframe/__init__.py, scripts/installer.nsi and Start DayFrame.cmd. Move the included Unreleased notes into a dated version entry. Commit the release preparation separately from feature work.
4. Run the functional suite. Build on each requested target OS and run packaged smoke checks with a fresh isolated profile. Check affected themes/window sizes and account/data continuity. Ubuntu CI does not verify the owner's specific Mint installation.
5. Follow [the packaging commands](../CONTRIBUTING.md#version-and-release). Verify the complete portable folder and any requested installer before replacing the local stable package. Preserve user profiles and runtime data.
6. Record the version, build date, exact source commit, artifacts and validation below only after the requested package exists and checks pass. Keep binaries, runtime data and credentials out of Git.
7. Tag or publish only if the owner requested it. A request for a local package alone does not authorize GitHub publication. When requested, upload binaries as GitHub Release assets and keep release notes concrete.

## Last packaged baseline

| Item | Value |
|---|---|
| Version | 0.5.2 |
| Packaged date | 2026-11-05 |
| Source commit | 277bb2b2e8ad80732bca5ef1f5d36a3999f01394 |
| Windows artifacts | release/native-0.5.2/DayFrame/ and DayFrame-Setup-0.5.2.exe on the development machine |
| Verification | 77 Windows source tests; 61 portable and 61 extracted-installer UI smoke screens; all 881 installer payload files matched the bundle |
| Build tools | Python 3.14.3, PyInstaller 6.22.3, portable NSIS toolset nsis@2.0.4 |
| Installer SHA-256 | 353ff66fc8468c454117468d509544052a8fcc0b09325e4647e247b9855714fd |
| Source review and CI | [Release pull request #1](https://github.com/TylerFreemont0712/DayFrame/pull/1) |
| Linux Mint | The owner's exact installation has not been verified |
| GitHub publication | No GitHub Release or release tag created for this package |

The build commit identifies the packaged source. Binaries and test profiles are excluded from Git. verification.json and SHA256SUMS.txt accompany the local release. Current packaged UI references are in docs/screenshots/current/.

The installer payload was extracted and launched against an isolated profile; this check does not install into the owner's application directory or alter the live profile. The installer remains unsigned.
