# Native desktop and Python LAN hub operations

## Windows

The bundled application needs no separate Python installation:

    C:\Apps\TimeManager\Start DayFrame.cmd

On the original development machine its executable is release/native-0.5.1/DayFrame/DayFrame.exe. Keep _internal with it. The native installer is release/native-0.5.1/DayFrame-Setup-0.5.1.exe; it installs under the current user's Programs directory and creates a Start-menu shortcut. It is unsigned. Uninstalling does not remove the runtime database. A clean Git clone contains source only; run the setup script or build locally. The launcher falls back to the source virtual environment.

For source work, install Python 3.12+ (3.14 recommended) and run:

    powershell -ExecutionPolicy Bypass -File scripts/setup-windows.ps1
    .venv\Scripts\python.exe app.py
    .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    .venv\Scripts\python.exe -m unittest discover -s tests -v

Run Preview DayFrame.cmd (or scripts/preview.sh) to preview source changes in a separate TimeManager-preview profile; see [CONTRIBUTING.md](../../CONTRIBUTING.md). The regular launcher prefers the current packaged release. Development commits do not replace it. Build only for an explicitly requested release or validation build; see [release policy](RELEASES.md) and [packaging commands](../../CONTRIBUTING.md#version-and-release).

Source desktop dependencies are pinned in requirements.txt. requirements-windows.lock.txt captures the tested environment; do not use its Windows-only packages as a Linux lock.

## Linux Mint

Copy/extract source to a user-owned directory. Create a fresh Linux virtual environment:

    sudo apt update
    sudo apt install python3-venv libegl1 libxcb-cursor0 libxkbcommon-x11-0
    sh scripts/setup-linux.sh
    sh start-dayframe.sh

These package names apply to contemporary Ubuntu-based Mint; verify availability against the actual release. No sudo action was run here. Older distributions may not meet the bundled Qt wheel's glibc/platform requirements.

For Linux source checks:

    .venv/bin/python -m pip install -r requirements-dev.txt
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v

When a Linux build is explicitly requested, follow [the packaging commands](../../CONTRIBUTING.md#version-and-release). The folder dist/DayFrame is the Linux bundle. Use packaging/dayframe.desktop as a launcher template, replacing its executable/icon paths with absolute installation paths. A tested Mint installer/AppImage is still pending; a Windows executable cannot be used as a native Linux build.

References: [Qt Linux requirements](https://doc.qt.io/qt-6/linux-requirements.html), [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html).

## Runtime directories

Windows native: %LOCALAPPDATA%\TimeManager
Linux native: $XDG_DATA_HOME/TimeManager, default ~/.local/share/TimeManager

app.py --data-dir PATH selects a separate profile. Use separate empty profiles for testing. Only one native app process opens a given profile at a time. Never put a live SQLite file on a shared network drive.

## Database import

Before configuring an account, choose Import an existing DayFrame database to copy a consistent SQLite backup. The source stays intact. Existing installations keep using the configured native profile automatically; no import or data move is required for this cleanup.

## Private hub and TLS

An always-on Linux machine can host the headless Python hub without installing Qt:

    python3 -m venv .venv-hub
    .venv-hub/bin/python -m pip install -r requirements-hub.txt
    mkdir -p ~/.local/share/timemanager-hub ~/.config/timemanager
    chmod 700 ~/.local/share/timemanager-hub ~/.config/timemanager

Generate a private self-signed certificate on the hub if you do not already have a trusted certificate. Replace mint-host with the actual hostname:

    openssl req -x509 -newkey rsa:3072 -nodes -days 365 \
      -keyout ~/.config/dayframe/hub-key.pem \
      -out ~/.config/dayframe/hub-cert.pem \
      -subj "/CN=mint-host" \
      -addext "subjectAltName=DNS:mint-host,DNS:localhost,IP:127.0.0.1"
    chmod 600 ~/.config/dayframe/hub-key.pem
    openssl x509 -in ~/.config/dayframe/hub-cert.pem -noout -fingerprint -sha256

Read the fingerprint from the trusted hub and enter it in each client's settings. The client verifies the pin and certificate dates before sending credentials. Changing a certificate requires checking the new fingerprint.

Start the hub from the source root:

    export TM_HUB_DATA="$HOME/.local/share/timemanager-hub"
    export TM_HUB_HOST="0.0.0.0"
    export TM_HUB_PORT="47831"
    export TM_HUB_CERT="$HOME/.config/dayframe/hub-cert.pem"
    export TM_HUB_KEY="$HOME/.config/dayframe/hub-key.pem"
    export TM_HUB_SETUP_TOKEN="$(.venv-hub/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
    .venv-hub/bin/python -m dayframe.hub

The setup token is private; use it to publish your existing local account. The hub refuses LAN binding without TLS. HTTP is accepted only for loopback development. Keep the hub on your trusted LAN. No firewall/router rule is changed by the app.

For a persistent systemd service, use packaging/dayframe-hub.service as a template and adjust its user/paths. Put credentials in a private environment file, not the repository. Installing/enabling this service remains a machine-specific operation.

## Pairing devices

1. Create a local account on the first device.
2. Configure the hub with TLS and private setup token.
3. Settings → Private LAN synchronization: enter URL, certificate fingerprint, account password and setup token; choose Publish account to hub.
4. On each additional unconfigured device choose Connect to my existing LAN account. Enter the same credentials, URL and fingerprint.
5. Do not create unrelated accounts with the same username first. A shared UUID establishes identity.
6. Automatic sync runs while the app is open; Sync now is also available. Disable automatic sync with the checkbox.

Passwords for local unlock and hub authentication can diverge if someone changes them outside the app. Local password change is in Settings; hub change/recovery remain planned. Linux credentials need a working Secret Service/keyring; otherwise reconnect each session. No plaintext fallback file is written.

## Conflicts, timers and devices

Settings lists real conflicts with local and hub versions. Keep this device preserves local field changes against the received hub version; Use hub version accepts that remote entity. Further concurrent edits can raise another conflict.

The hub exposes POST /devices and /revoke for registered-device management. A full UI is planned. Revocation prevents subsequent hub access; it does not erase offline files. Timer synchronization is advisory through the shared active record, not a strong immediate lease. Time shows saved overlaps.

## Backups and recovery

Settings → Local data → Back up database uses SQLite's consistent backup API. A backup contains a password verifier and personal data; use protected storage.

Settings → Local data → Clear workspace empties the signed-in account's workspace after a typed confirmation and a second prompt. It first writes `backups/before-clear-<date>-<time>.db` inside the profile folder and checks it; if that fails, nothing is deleted. The account, password and appearance preferences stay. A configured hub connection is switched off and the sync cursor and unsent changes are dropped, because the hub has no delete operation: the hub and other devices keep their copy, and connecting again downloads it. To go back, import the backup into a new, unconfigured profile, or close DayFrame and put the backup in place of `timemanager.db`.

Import-copy is supported into an unconfigured native profile. Do not restore an old backup directly into an actively syncing profile without reconciliation: its cursor and outbox can be stale. Sync is not a backup. For the hub, stop the service before a simple filesystem backup or use SQLite's backup API; copying only a live WAL main file is insufficient.

## Troubleshooting

- Missing _internal or Qt plugin: keep the entire portable bundle; reinstall/extract it together.
- Linux xcb plugin failure: check Qt's Linux requirements and the host's X11/Wayland libraries.
- Wrong account identity: import the existing hub account on an unconfigured profile.
- Certificate mismatch/expiry: verify the real hub certificate before changing the trusted pin.
- Keyring unavailable: reconnect to the hub after restart; data remains local and queued.
- Schema newer than app: install a compatible version; do not delete the database.
- Outdated backup: preserve it and reconcile account/cursor/outbox state before reconnecting.
- Diagnostics should omit passwords, tokens, private keys and personal ticket/note content.


## Source interpreter selection

The setup scripts prefer Python 3.14, then 3.13/3.12, and reject older desktop interpreters. On Windows you can pass `-Python C:\path\to\python.exe`; on Linux set `DAYFRAME_PYTHON=/path/to/python`. An existing older .venv is preserved and setup asks you to rename it before creating a new one. Do not copy virtual environments between operating systems. Desktop build/runtime does not change existing profile or hub identities.
