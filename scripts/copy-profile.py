"""Copy a DayFrame profile's database into an empty preview profile.

Usage: python scripts/copy-profile.py SOURCE_DIR PREVIEW_DIR

The source is opened read-only and copied with SQLite's backup API, so the live
profile is never modified, even while DayFrame has it open. The copy has automatic
sync turned off, so preview edits cannot reach the hub, and no remembered sign-in
is copied: sign in with your usual password. The preview app migrates only the copy.
"""

import json
import sqlite3
import sys
from pathlib import Path


def main(source, preview):
    source_db = Path(source) / "timemanager.db"
    preview_db = Path(preview) / "timemanager.db"
    if not source_db.is_file():
        raise SystemExit("No DayFrame database found at " + str(source_db))
    if preview_db.exists():
        raise SystemExit("The preview profile already has a database: " + str(preview_db))
    if source_db.resolve() == preview_db.resolve():
        raise SystemExit("Choose a preview folder different from the source profile.")
    preview_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True) as original:
        if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SystemExit("The source database failed its integrity check; nothing was copied.")
        with sqlite3.connect(preview_db) as copy:
            original.backup(copy)
    with sqlite3.connect(preview_db) as copy:
        for account_id, data in copy.execute("SELECT account_id, data FROM settings").fetchall():
            settings = json.loads(data)
            settings["syncEnabled"] = False
            copy.execute("UPDATE settings SET data=? WHERE account_id=?", (json.dumps(settings), account_id))
    print("Copied " + str(source_db) + " to " + str(preview_db) + " with automatic sync off.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
