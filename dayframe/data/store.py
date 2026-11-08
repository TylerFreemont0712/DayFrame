"""Transactional, account-scoped SQLite storage shared by native views and sync."""

from __future__ import annotations
import copy
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from importlib.resources import files
from pathlib import Path
from ..core import domain as D
from ..core import preferences


# Schema 5: version-control records. Kept here so the migration and schema.sql agree.
REPOSITORIES_TABLE = (
    "CREATE TABLE IF NOT EXISTS repositories(account_id TEXT NOT NULL,id TEXT NOT NULL,project_id TEXT NOT NULL,"
    "provider TEXT NOT NULL,name TEXT NOT NULL,remote_url TEXT NOT NULL,github_repo TEXT NOT NULL,"
    "default_branch TEXT NOT NULL,archived INTEGER NOT NULL,PRIMARY KEY(account_id,id),"
    "FOREIGN KEY(account_id,project_id) REFERENCES projects(account_id,id))"
)
CHANGESETS_TABLE = (
    "CREATE TABLE IF NOT EXISTS changesets(account_id TEXT NOT NULL,id TEXT NOT NULL,repo_id TEXT NOT NULL,"
    "ticket_id TEXT NOT NULL,title TEXT NOT NULL,branch TEXT NOT NULL,base_commit TEXT NOT NULL,"
    "diff TEXT NOT NULL,stat TEXT NOT NULL,updated_at REAL NOT NULL,archived INTEGER NOT NULL,"
    "PRIMARY KEY(account_id,id),FOREIGN KEY(account_id,repo_id) REFERENCES repositories(account_id,id),"
    "FOREIGN KEY(account_id,ticket_id) REFERENCES tickets(account_id,id))"
)
CHANGESETS_INDEX = "CREATE INDEX IF NOT EXISTS changesets_ticket ON changesets(account_id,ticket_id)"


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "timemanager.db", check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;")
        self.db.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY)")
        self._migrate()
        self.account = None
        self.failed_logins = {}
        self.session_error = None

    def _migrate(self):
        version = self.db.execute("SELECT coalesce(max(version),0) FROM schema_migrations").fetchone()[0]
        if version > 5:
            raise ValueError("This database requires a newer DayFrame version.")
        if not version:
            self.db.executescript(files("dayframe.data").joinpath("schema.sql").read_text(encoding="utf-8"))
            return
        if version == 1:
            with self.atomic():
                self.db.execute(
                    "CREATE TABLE work_blocks(account_id TEXT NOT NULL,ticket_id TEXT NOT NULL,id TEXT NOT NULL,date TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,PRIMARY KEY(account_id,id),FOREIGN KEY(account_id,ticket_id) REFERENCES tickets(account_id,id))"
                )
                self.db.execute("CREATE INDEX work_blocks_day ON work_blocks(account_id,date,start_time)")
                self.db.execute("INSERT INTO schema_migrations VALUES(2)")
        if version < 3:
            with self.atomic():
                columns = {row[1] for row in self.db.execute("PRAGMA table_info(events)")}
                for field in ("end_date", "description", "location", "color", "recurrence"):
                    if field not in columns:
                        self.db.execute(
                            "ALTER TABLE events ADD COLUMN " + field + " TEXT NOT NULL DEFAULT ''"
                        )
                if "archived" not in columns:
                    self.db.execute("ALTER TABLE events ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
                self.db.execute("INSERT INTO schema_migrations VALUES(3)")
        if version < 4:
            with self.atomic():
                for table, field, default in (
                    ("tickets", "parent_id", ""),
                    ("map_sections", "parent_id", ""),
                    ("map_sections", "predecessor_ids", "[]"),
                ):
                    columns = {row[1] for row in self.db.execute("PRAGMA table_info(" + table + ")")}
                    if field not in columns:
                        self.db.execute(
                            "ALTER TABLE "
                            + table
                            + " ADD COLUMN "
                            + field
                            + " TEXT NOT NULL DEFAULT '"
                            + default
                            + "'"
                        )
                self.db.execute("INSERT INTO schema_migrations VALUES(4)")
        if version < 5:
            with self.atomic():
                self.db.execute(REPOSITORIES_TABLE)
                self.db.execute(CHANGESETS_TABLE)
                self.db.execute(CHANGESETS_INDEX)
                self.db.execute("INSERT INTO schema_migrations VALUES(5)")

    def remember_session(self):
        """Remember trusted local access without storing a password or syncing it.

        The marker is deliberately outside SQLite backups and the change outbox.
        It is a convenience setting protected by the user's OS profile, not an
        additional encryption or authorization boundary.
        """
        with self.lock:
            account = self.auth()
            temporary = self.root / (".local-session-" + uuid.uuid4().hex + ".tmp")
            try:
                with temporary.open("x", encoding="utf-8") as stream:
                    json.dump(
                        {"version": 1, "account_id": account["id"], "device_id": account["device_id"]}, stream
                    )
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, self.root / ".local-session.json")
                self.session_error = None
                return True
            except OSError as exc:
                self.session_error = "Sign-in succeeded, but this device could not remember it: " + str(exc)
                return False
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def restore_session(self):
        """Restore this profile's remembered account; return False for first use/logout."""
        with self.lock:
            if self.account:
                return True
            try:
                marker = json.loads((self.root / ".local-session.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            if (
                not isinstance(marker, dict)
                or marker.get("version") != 1
                or not isinstance(marker.get("account_id"), str)
                or not isinstance(marker.get("device_id"), str)
            ):
                return False
            row = self.db.execute(
                "SELECT * FROM accounts WHERE id=? AND device_id=?",
                (marker["account_id"], marker["device_id"]),
            ).fetchone()
            if not row:
                return False
            self.account = dict(row)
            return True

    def _forget_session(self):
        try:
            (self.root / ".local-session.json").unlink(missing_ok=True)
        except OSError as exc:
            raise ValueError("Could not finish logging out on this device. Try again: " + str(exc)) from exc
        self.session_error = None

    @contextmanager
    def atomic(self):
        with self.lock:
            nested = self.db.in_transaction
            name = "sp_" + uuid.uuid4().hex
            self.db.execute("SAVEPOINT " + name if nested else "BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("RELEASE " + name if nested else "COMMIT")
            except Exception:
                if nested:
                    self.db.execute("ROLLBACK TO " + name)
                    self.db.execute("RELEASE " + name)
                else:
                    self.db.execute("ROLLBACK")
                raise

    def auth(self):
        if not self.account:
            raise ValueError("Please sign in.")
        return self.account

    def status(self):
        with self.lock:
            return {
                "configured": bool(self.db.execute("SELECT id FROM accounts LIMIT 1").fetchone()),
                "account": {k: self.account[k] for k in ("id", "username")} if self.account else None,
            }

    def register(self, username, password, account_id=None):
        username = D.text(username, 80, True).lower()
        if account_id:
            uuid.UUID(account_id)
        if self.status()["configured"]:
            raise ValueError("This installation is configured. Sign in to your existing account.")
        salt, digest = D.hash_password(password)
        with self.atomic():
            if self.status()["configured"]:
                raise ValueError("This installation is already configured.")
            self.account = {
                "id": account_id or str(uuid.uuid4()),
                "username": username,
                "password_hash": digest,
                "salt": salt,
                "device_id": str(uuid.uuid4()),
            }
            self.db.execute(
                "INSERT INTO accounts VALUES(?,?,?,?,?)",
                tuple(self.account[k] for k in ("id", "username", "password_hash", "salt", "device_id")),
            )
        self.remember_session()
        return self.status()

    def login(self, username, password):
        username = D.text(username, 80, True).lower()
        now = time.monotonic()
        failure = self.failed_logins.get(username, {"count": 0, "until": 0})
        if failure["until"] > now:
            raise ValueError("Too many attempts. Wait a minute.")
        with self.lock:
            row = self.db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
        if not row or not D.verify_password(password, row):
            failure["count"] += 1
            if failure["count"] >= 5:
                failure["until"] = now + 60
            self.failed_logins[username] = failure
            raise ValueError("Username or password is incorrect.")
        self.failed_logins.pop(username, None)
        self.account = dict(row)
        self.remember_session()
        return self.status()

    def logout(self):
        with self.lock:
            self._forget_session()
            self.account = None

    def change_password(self, new_password):
        """Change only this installation's password; hub credentials are separate."""
        account_id = self.auth()["id"]
        salt, digest = D.hash_password(new_password)
        with self.lock:
            if self.auth()["id"] != account_id:
                raise ValueError("The signed-in account changed. Try again.")
            with self.atomic():
                result = self.db.execute(
                    "UPDATE accounts SET password_hash=?,salt=? WHERE id=?", (digest, salt, account_id)
                )
                if result.rowcount != 1:
                    raise ValueError("This account is no longer available.")
            self.account = {**self.account, "password_hash": digest, "salt": salt}
        return self.status()

    def read(self, kind, record_id):
        with self.lock:
            account = self.auth()
            definition = D.DEFINITIONS[kind]
            row = self.db.execute(
                f"SELECT * FROM {definition['table']} WHERE account_id=? AND id=?", (account["id"], record_id)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            del result["account_id"]
            for key in definition.get("json", []):
                result[key] = json.loads(result[key])
            if kind == "ticket":
                result["labels"] = [
                    x[0]
                    for x in self.db.execute(
                        "SELECT label FROM ticket_labels WHERE account_id=? AND ticket_id=? ORDER BY label",
                        (account["id"], record_id),
                    )
                ]
                result["dependencies"] = [
                    x[0]
                    for x in self.db.execute(
                        "SELECT prerequisite_id FROM ticket_dependencies WHERE account_id=? AND ticket_id=?",
                        (account["id"], record_id),
                    )
                ]
            return result

    def list(self, kind, summary=False):
        """All records of a kind. summary=True replaces large fields (diffs) with their size."""
        with self.lock:
            account = self.auth()
            table = D.DEFINITIONS[kind]["table"]
            ids = self.db.execute(
                f"SELECT id FROM {table} WHERE account_id=? ORDER BY rowid", (account["id"],)
            ).fetchall()
            records = [self.read(kind, row[0]) for row in ids]
            for key in D.DEFINITIONS[kind].get("heavy", []) if summary else ():
                for record in records:
                    record[key + "_size"] = len(record.pop(key))
            return records

    def _save(self, kind, payload, queue=True):
        account = self.auth()
        if kind not in D.DEFINITIONS:
            raise ValueError("Unknown record type.")
        definition = D.DEFINITIONS[kind]
        record_id = payload.get("id") or str(uuid.uuid4())
        D.text(record_id, 120, True)
        old = self.read(kind, record_id)
        patch = {k: v for k, v in payload.items() if k != "id"}
        D.validate(kind, patch)
        next_record = {**copy.deepcopy(definition["defaults"]), **(old or {}), **patch}
        next_record.pop("id", None)
        D.validate(kind, next_record)
        if kind in ("ticket", "section") and not self.read("project", next_record["project_id"]):
            raise ValueError("Choose an existing project.")
        if kind in ("ticket", "section"):
            D.check_map_relations(self.list(kind), record_id, next_record)
        if kind == "ticket":
            for dep in next_record["dependencies"]:
                other = self.read("ticket", dep)
                if not other or other["project_id"] != next_record["project_id"]:
                    raise ValueError("Dependency must belong to the same project.")
            D.assert_acyclic(self.list("ticket"), record_id, next_record["dependencies"])
        if kind == "placement":
            ticket = self.read("ticket", next_record["ticket_id"])
            if not ticket:
                raise ValueError("Ticket not found.")
            if next_record["section_id"]:
                section = self.read("section", next_record["section_id"])
                if not section or section["project_id"] != ticket["project_id"]:
                    raise ValueError("Section belongs to another project.")
        if kind in ("repo", "changeset"):
            D.check_code_relations(kind, next_record, self.read)
            # Only local edits are refused; a duplicate arriving through sync is kept and the
            # Code page uses the first one.
            if kind == "repo" and queue and not next_record["archived"]:
                if any(
                    r["id"] != record_id
                    and r["project_id"] == next_record["project_id"]
                    and not r["archived"]
                    for r in self.list("repo")
                ):
                    raise ValueError("This project already has a repository.")
        if (
            kind in ("entry", "timer", "block")
            and next_record["ticket_id"]
            and not self.read("ticket", next_record["ticket_id"])
        ):
            raise ValueError("Ticket not found.")
        columns = [k for k in definition["fields"] if k not in definition.get("virtual", [])]
        values = [
            json.dumps(next_record[k], ensure_ascii=False)
            if k in definition.get("json", [])
            else next_record[k]
            for k in columns
        ]
        sql = (
            f"INSERT INTO {definition['table']}(account_id,id,{','.join(columns)}) "
            f"VALUES({','.join('?' for _ in range(len(columns) + 2))}) "
            "ON CONFLICT(account_id,id) DO UPDATE SET " + ",".join(f"{k}=excluded.{k}" for k in columns)
        )
        self.db.execute(sql, [account["id"], record_id] + values)
        if kind == "ticket":
            self.db.execute(
                "DELETE FROM ticket_labels WHERE account_id=? AND ticket_id=?", (account["id"], record_id)
            )
            for label in dict.fromkeys(next_record["labels"]):
                self.db.execute("INSERT INTO ticket_labels VALUES(?,?,?)", (account["id"], record_id, label))
            self.db.execute(
                "DELETE FROM ticket_dependencies WHERE account_id=? AND ticket_id=?",
                (account["id"], record_id),
            )
            for dep in dict.fromkeys(next_record["dependencies"]):
                self.db.execute(
                    "INSERT INTO ticket_dependencies VALUES(?,?,?)", (account["id"], record_id, dep)
                )
        delta = D.changes(old, next_record)
        if queue and delta:
            base = {k: old[k] for k in definition["fields"]} if old else {}
            self.db.execute(
                "INSERT INTO outbox(account_id,operation_id,kind,entity_id,base,patch) VALUES(?,?,?,?,?,?)",
                (account["id"], str(uuid.uuid4()), kind, record_id, json.dumps(base), json.dumps(delta)),
            )
        return {"id": record_id, **next_record}

    def save(self, kind, payload, queue=True):
        with self.atomic():
            return self._save(kind, payload, queue)

    def settings(self, patch=None):
        with self.lock:
            account = self.auth()
            row = self.db.execute("SELECT data FROM settings WHERE account_id=?", (account["id"],)).fetchone()
            current = preferences.sanitize(json.loads(row[0]) if row else {})
            if patch is None:
                return {**preferences.DEFAULTS, **current}
            preferences.validate(patch)
            self.db.execute(
                "INSERT INTO settings VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET data=excluded.data",
                (account["id"], json.dumps({**current, **patch})),
            )
            return {**preferences.DEFAULTS, **current, **patch}

    def snapshot(self):
        with self.lock:
            a = self.auth()
            result = {"account": {k: a[k] for k in ("id", "username")}, "settings": self.settings()}
            result.update({kind: self.list(kind, summary=True) for kind in D.DEFINITIONS})
            rows = self.db.execute("SELECT * FROM conflicts WHERE account_id=?", (a["id"],)).fetchall()
            result["conflicts"] = [
                {**dict(r), "remote": json.loads(r["remote"]), "fields": json.loads(r["fields"])}
                for r in rows
            ]
            result["pending"] = self.db.execute(
                "SELECT count(*) FROM outbox WHERE account_id=?", (a["id"],)
            ).fetchone()[0]
            return result

    def auto_placement(self, ticket):
        placement = next((p for p in self.list("placement") if p["ticket_id"] == ticket["id"]), None)
        if placement and placement["manual"]:
            return
        sections = [s for s in self.list("section") if s["project_id"] == ticket["project_id"]]
        hierarchy = list(sections)
        sections.sort(key=lambda s: (-len(D.section_path(hierarchy, s["id"])), s["sort_order"], s["id"]))
        section = next(
            (s for s in sections if s["rule_field"] and D.section_matches(sections, s, ticket)), None
        )
        self._save(
            "placement",
            {
                "id": placement["id"] if placement else ticket["id"],
                "ticket_id": ticket["id"],
                "section_id": section["id"] if section else "",
                "manual": 0,
                "x": 0,
                "y": 0,
            },
        )

    def timer_action(self, action, ticket_id=None, now=None):
        with self.atomic():
            a = self.auth()
            timer = self.read("timer", "active")
            now = int(time.time() * 1000) if now is None else now
            if timer and timer["start_at"]:
                if now < timer["start_at"]:
                    raise ValueError("The clock moved backwards. Review this timer before saving.")
                self._save(
                    "entry",
                    {
                        "ticket_id": timer["ticket_id"],
                        "start_at": timer["start_at"],
                        "end_at": now,
                        "device_id": timer["device_id"],
                    },
                )
                timer = {**timer, "session_ms": timer["session_ms"] + now - timer["start_at"], "start_at": 0}
            if action == "stop":
                return self._save("timer", {"id": "active", **D.DEFINITIONS["timer"]["defaults"]})
            if action == "pause":
                return self._save(
                    "timer", {"id": "active", **(timer or D.DEFINITIONS["timer"]["defaults"]), "paused": 1}
                )
            if action != "start":
                raise ValueError("Unknown timer action.")
            if ticket_id is not None and (not timer or timer["ticket_id"] != ticket_id):
                timer = {**D.DEFINITIONS["timer"]["defaults"], "ticket_id": ticket_id}
            return self._save(
                "timer",
                {
                    **D.DEFINITIONS["timer"]["defaults"],
                    **(timer or {}),
                    "id": "active",
                    "ticket_id": ticket_id if ticket_id is not None else (timer or {}).get("ticket_id", ""),
                    "start_at": now,
                    "paused": 0,
                    "device_id": a["device_id"],
                },
            )

    def command(self, method, payload=None):
        p = payload or {}
        self.auth()
        if method == "data.snapshot":
            return self.snapshot()
        if method == "settings.save":
            return self.settings(p)
        if method == "timer.action":
            return self.timer_action(p["action"], p.get("ticket_id"))
        if method == "examples.load":
            return self.load_examples()
        with self.atomic():
            direct = {
                "project.save": "project",
                "event.save": "event",
                "note.save": "note",
                "block.save": "block",
                "repo.save": "repo",
                "changeset.save": "changeset",
            }
            if method in direct:
                return self._save(direct[method], p)
            if method == "ticket.capture":
                # Capture, inherited fields and explicit map placement form one transaction.
                ticket = self.command("ticket.save", p["ticket"])
                if ticket.get("parent_id"):
                    self.command(
                        "ticket.relate", {"parent_id": ticket["parent_id"], "child_id": ticket["id"]}
                    )
                if p.get("section_id"):
                    self.command(
                        "placement.save",
                        {
                            "ticket_id": ticket["id"],
                            "section_id": p["section_id"],
                            "manual": 1,
                            "x": 0,
                            "y": 0,
                        },
                    )
                return self.read("ticket", ticket["id"])
            if method == "ticket.relate":
                child = self.read("ticket", p["child_id"])
                parent = self.read("ticket", p["parent_id"])
                if not child or not parent or child["project_id"] != parent["project_id"]:
                    raise ValueError("Choose two tickets in the same project.")
                patch = {"parent_id": parent["id"]}
                if p.get("inherit", True):
                    patch["labels"] = list(dict.fromkeys(child["labels"] + parent["labels"]))
                    for field in ("component", "milestone"):
                        if not child[field] and parent[field]:
                            patch[field] = parent[field]
                child = self._save("ticket", {"id": child["id"], **patch})
                self.auto_placement(child)
                placements = {x["ticket_id"]: x for x in self.list("placement")}
                own = placements.get(child["id"])
                anchor = placements.get(parent["id"])
                if own and not own["section_id"] and anchor and anchor["section_id"]:
                    self._save(
                        "placement",
                        {
                            "id": own["id"],
                            "ticket_id": child["id"],
                            "section_id": anchor["section_id"],
                            "manual": 1,
                            "x": anchor["x"] + 210,
                            "y": anchor["y"],
                        },
                    )
                return child
            if method == "map.restore":
                for record in p["records"]:
                    self._save(record["kind"], record["data"])
                return True
            if method == "ticket.save":
                ticket = self._save("ticket", p)
                self.auto_placement(ticket)
                return ticket
            if method == "section.save":
                original = self.read("section", p.get("id", ""))
                section = self._save("section", p)
                if original and "parent_id" in p and original.get("parent_id") != section["parent_id"]:
                    sections = self.list("section")
                    descendants = {
                        s["id"]
                        for s in sections
                        if section["id"] in [x["id"] for x in D.section_path(sections, s["id"])]
                    }
                    for placement in self.list("placement"):
                        if placement["section_id"] in descendants:
                            ticket = self.read("ticket", placement["ticket_id"])
                            patch = D.section_classification(sections, placement["section_id"], ticket)
                            if patch:
                                self._save("ticket", {"id": ticket["id"], **patch})
                for ticket in self.list("ticket"):
                    if ticket["project_id"] == section["project_id"]:
                        self.auto_placement(ticket)
                return section
            if method == "placement.save":
                ticket = self.read("ticket", p["ticket_id"])
                if not ticket:
                    raise ValueError("Ticket not found.")
                if p.get("section_id"):
                    section = self.read("section", p["section_id"])
                    if not section or section["project_id"] != ticket["project_id"]:
                        raise ValueError("Invalid section.")
                    patch = D.section_classification(self.list("section"), section["id"], ticket)
                    if patch:
                        ticket = self._save("ticket", {"id": ticket["id"], **patch})
                placement = self._save("placement", {**p, "id": ticket["id"], "manual": p.get("manual", 1)})
                if not placement["manual"]:
                    self.auto_placement(ticket)
                return placement
            if method == "placement.restore":
                ticket = self._save("ticket", {"id": p["ticket_id"], **p["classification"]})
                return self._save(
                    "placement", {**p["placement"], "id": ticket["id"], "ticket_id": ticket["id"]}
                )
            if method == "time.add":
                return self._save("entry", {**p, "device_id": self.account["device_id"]})
            raise ValueError("Unsupported action.")

    def backup(self, destination):
        destination = Path(destination)
        if destination.resolve() == (self.root / "timemanager.db").resolve():
            raise ValueError("Choose a different file for the backup.")
        with self.lock, sqlite3.connect(destination) as other:
            self.db.backup(other)
        return str(destination)

    def import_database(self, source):
        if self.status()["configured"]:
            raise ValueError("Import is available only before creating an account on this device.")
        source = Path(source).resolve()
        if source == (self.root / "timemanager.db").resolve():
            raise ValueError("Choose a different database.")
        # Importing someone else's account data never imports their local unlock.
        self._forget_session()
        with self.lock, sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            tables = {r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"accounts", "tickets", "schema_migrations"}.issubset(tables):
                raise ValueError("That is not a DayFrame database.")
            if original.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] not in (
                1,
                2,
                3,
                4,
                5,
            ):
                raise ValueError("Unsupported database version.")
            if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("The source database failed its integrity check.")
            original.backup(self.db)
            self._migrate()
        self.db.execute("PRAGMA foreign_keys=ON")
        return self.status()

    def load_examples(self):
        with self.atomic():
            if self.list("project"):
                raise ValueError("Examples can only be loaded into an empty workspace.")
            today = date.fromisoformat(D.day_key(self.settings()["timezone"]))
            day = lambda n: (today + timedelta(days=n)).isoformat()
            website = self._save(
                "project",
                {
                    "name": "Website",
                    "project_key": "WEB",
                    "description": "Example workspace — replace it with your own project.",
                },
            )
            home = self._save("project", {"name": "Home", "project_key": "HOME"})
            learning = self._save("project", {"name": "Learning", "project_key": "LEARN"})
            self._save(
                "section",
                {
                    "project_id": website["id"],
                    "name": "Frontend",
                    "rule_field": "component",
                    "rule_value": "Frontend",
                },
            )
            self._save(
                "section",
                {
                    "project_id": website["id"],
                    "name": "Release 1",
                    "rule_field": "milestone",
                    "rule_value": "R1",
                    "sort_order": 1,
                },
            )
            first = self._save(
                "ticket",
                {
                    "project_id": website["id"],
                    "title": "Sketch project views",
                    "status": "done",
                    "estimate_min": 80,
                    "component": "Frontend",
                },
            )
            active = self._save(
                "ticket",
                {
                    "project_id": website["id"],
                    "title": "Build project dashboard",
                    "status": "doing",
                    "priority": "high",
                    "estimate_min": 120,
                    "component": "Frontend",
                    "due_date": day(2),
                    "pinned": 1,
                    "labels": ["ui", "dashboard"],
                    "dependencies": [first["id"]],
                    "description": "Create a clear overview for projects, tickets, and tracked time.",
                    "checklist": [
                        {"text": "Layout structure", "done": True},
                        {"text": "Ticket summary", "done": False},
                        {"text": "Timer widget", "done": False},
                    ],
                },
            )
            examples = [
                {
                    "project_id": website["id"],
                    "title": "Review navigation",
                    "status": "ready",
                    "estimate_min": 45,
                    "component": "Frontend",
                    "due_date": day(0),
                    "pinned": 1,
                },
                {
                    "project_id": website["id"],
                    "title": "Add timer shortcuts",
                    "status": "review",
                    "estimate_min": 60,
                    "milestone": "R1",
                    "dependencies": [active["id"]],
                },
                {"project_id": website["id"], "title": "Write setup notes", "estimate_min": 30},
                {
                    "project_id": home["id"],
                    "title": "Plan weekend errands",
                    "status": "ready",
                    "estimate_min": 30,
                    "pinned": 1,
                    "due_date": day(0),
                },
                {
                    "project_id": learning["id"],
                    "title": "Read chapter 4",
                    "estimate_min": 30,
                    "due_date": day(0),
                },
                {
                    "project_id": website["id"],
                    "title": "Update project notes",
                    "status": "ready",
                    "due_date": day(-2),
                },
            ]
            for item in examples:
                self._save("ticket", item)
            for ticket in self.list("ticket"):
                self.auto_placement(ticket)
            for event in [
                {"title": "Weekly planning", "start_time": "09:00", "end_time": "10:00"},
                {"title": "Lunch", "start_time": "12:00", "end_time": "13:00"},
                {"title": "Walk", "start_time": "17:00", "end_time": "17:30", "event_type": "routine"},
            ]:
                self._save("event", {"date": day(0), **event})
            self._save(
                "block",
                {"ticket_id": active["id"], "date": day(0), "start_time": "10:00", "end_time": "12:00"},
            )
            for title, n in (("Project launch", 14), ("Weekend trip", 18), ("Annual review", 30)):
                self._save("event", {"title": title, "date": day(n), "major": 1})
            front = next(
                sec
                for sec in self.list("section")
                if sec["project_id"] == website["id"] and sec["name"] == "Frontend"
            )
            self._save(
                "section",
                {
                    "project_id": website["id"],
                    "name": "Calendar",
                    "parent_id": front["id"],
                    "rule_field": "label",
                    "rule_value": "calendar",
                    "sort_order": 2,
                },
            )
            calendar_ticket = self._save(
                "ticket",
                {
                    "project_id": website["id"],
                    "title": "Build week timeline",
                    "component": "Frontend",
                    "labels": ["calendar"],
                    "parent_id": active["id"],
                    "estimate_min": 60,
                },
            )
            self.auto_placement(calendar_ticket)
            for title, n, kind, length in (
                ("Family birthday", 2, "birthday", 0),
                ("Weekend away", 3, "trip", 2),
            ):
                self._save(
                    "event",
                    {
                        "title": title,
                        "date": day(n),
                        "end_date": day(n + length),
                        "start_time": "",
                        "end_time": "",
                        "event_type": kind,
                        "recurrence": "yearly" if kind == "birthday" else "",
                        "description": "Example event details",
                        "location": "Home" if kind == "birthday" else "Kyoto",
                    },
                )
            self._save(
                "note",
                {
                    "title": "Welcome to DayFrame",
                    "body": "This is an example workspace. The same tickets appear on your board, map, and daily plan.",
                    "project_id": website["id"],
                },
            )
        return True

    def close(self):
        with self.lock:
            self.db.close()
