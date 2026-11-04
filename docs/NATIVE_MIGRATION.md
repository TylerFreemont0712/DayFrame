# Native migration — 0.1.0 to 0.2.0

The owner requested a Python desktop app instead of HTML. PySide6 / Qt Widgets is now the active implementation. The earlier Electron implementation is preserved locally under legacy/electron-v0.1; these archives are excluded from clean Git clones and the native executable. DayFrame 0.5.0 renames the current native app without moving its existing runtime profile; see BRANDING.md.

## Source and launch

The root now contains app.py, dayframe/, requirements files, native packaging scripts and updated project documents. Start DayFrame.cmd launches the native bundle. The earlier launcher, source, npm files, build output and packages are archived together, so the earlier implementation remains recoverable.

The root concept archive and product requirements remain. Generated concepts are design references, not functional screenshots. Native screenshots are in docs/screenshots/native/.

## Data import preserves the original

Native Windows data uses Local AppData; the earlier app used Roaming AppData. Linux native uses XDG data rather than Electron's config directory. Changing source files does not migrate or overwrite either profile automatically.

Before configuring a native account:

1. In the earlier app, save a database backup, or locate its timemanager.db.
2. Launch the native app and choose Import an existing DayFrame / TimeManager database.
3. Select the source backup/database. The app verifies the schema/integrity and uses SQLite backup from a read-only connection into the fresh native profile.
4. Sign in with the earlier username/password.
5. Check tickets, map placements, events, notes and time before retiring the earlier app.
6. Reconnect the native app to the hub; earlier encrypted device credentials are not copied into a different application credential namespace.

Schema version 1 and scrypt salt/parameters remain compatible. Import preserves account UUID and device identity. Run the imported copy on the same logical device; pair additional machines through the hub instead of cloning one device identity onto multiple machines.

The original database is never opened for writes by this import. A configured native workspace cannot be overwritten by this command. Existing imports with pending changes/cursors need care before connecting to a hub; import is a migration tool, not a fully sync-aware historical rollback.

## Compatibility evidence

Database backup/import, original-byte preservation, login/password verification, field persistence and Python hub/client synchronization have automated tests. Actual live earlier-hub deployment compatibility and Linux Mint runtime validation are still pending.


##0.2→0.3 compact and session update

Existing account/password data is preserved. Opening a schema1 profile migrates it to schema2 by adding linked work_blocks. Source-preserving import accepts both versions and migrates only the imported copy. The old0.2 app cannot read schema2, so the earlier package remains available with its own original data or an earlier backup.

The new layout resets old giant window geometry once. Sign in once after upgrading; subsequent launches remember the account until Options → Log out. New remembered-session data is local to this profile and excluded from backups and sync.

## Native 0.4 compatibility

Update the Python hub/all clients to 0.4 for event/map fields. Versions 1–3 migrate to schema4; imports migrate only the copy. Older apps cannot open the upgraded database; preserve earlier backups. Notes data remains with its UI hidden. No service/firewall/network setup is installed.
