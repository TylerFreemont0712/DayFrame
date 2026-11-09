"""Private Python LAN hub. Uses DayFrame sync protocol 1."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ..core import domain as D


class Hub:
    def __init__(self, root, host="127.0.0.1", port=47831, setup_token="", cert=None, key=None):
        if host not in ("127.0.0.1", "localhost", "::1") and not (cert and key):
            raise ValueError("LAN hosting requires a TLS certificate and key.")
        Path(root).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(root) / "hub.db", check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT,salt TEXT);
CREATE TABLE IF NOT EXISTS devices(token_hash TEXT PRIMARY KEY,user_id TEXT,device_id TEXT,revoked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS entities(user_id TEXT,kind TEXT,id TEXT,data TEXT,PRIMARY KEY(user_id,kind,id));
CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,user_id TEXT,result TEXT);
CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,kind TEXT,entity_id TEXT,data TEXT);""")
        self.lock = threading.RLock()
        self.setup_token = setup_token
        self.failures = {}
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/health":
                    self.send_json(200, {"name": "DayFrame Python sync", "protocol": 1})
                else:
                    self.send_json(404, {"error": "Unknown endpoint."})

            def do_POST(self):
                try:
                    self.connection.settimeout(15)
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= length <= 524288:
                        return self.send_json(413, {"error": "Request too large."})
                    body = json.loads(self.rfile.read(length) or b"{}")
                    status, payload = hub.handle(self.path, body, self.headers)
                    self.send_json(status, payload)
                except Exception as error:
                    message = (
                        "That account already exists."
                        if isinstance(error, sqlite3.IntegrityError)
                        else str(error)
                    )
                    self.send_json(400, {"error": message})

            def send_json(self, status, payload):
                content = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        if cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(cert, key)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    @property
    def port(self):
        return self.server.server_address[1]

    def close(self):
        if self.thread:
            self.server.shutdown()
            self.thread.join(timeout=5)
        self.server.server_close()
        self.db.close()

    def handle(self, route, body, headers):
        if route == "/register":
            if not self.setup_token or not secrets.compare_digest(
                headers.get("X-Setup-Token", ""), self.setup_token
            ):
                return 403, {"error": "A private hub setup token is required."}
            username = D.text(body.get("username"), 80, True).lower()
            account_id = D.text(body.get("id"), 120, True)
            salt, digest = D.hash_password(body.get("password"))
            with self.lock:
                self.db.execute("INSERT INTO users VALUES(?,?,?,?)", (account_id, username, digest, salt))
            return 200, {"ok": True}
        if route == "/login":
            username = D.text(body.get("username"), 80, True).lower()
            with self.lock:
                failure = self.failures.get(username, {"count": 0, "until": 0})
                if failure["until"] > time.monotonic():
                    return 429, {"error": "Too many attempts. Try again in one minute."}
                row = self.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row or not D.verify_password(body.get("password"), row):
                with self.lock:
                    failure["count"] += 1
                    if failure["count"] >= 5:
                        failure["until"] = time.monotonic() + 60
                    self.failures[username] = failure
                return 401, {"error": "Username or password is incorrect."}
            token = secrets.token_hex(32)
            with self.lock:
                self.failures.pop(username, None)
                self.db.execute(
                    "INSERT INTO devices(token_hash,user_id,device_id) VALUES(?,?,?)",
                    (
                        hashlib.sha256(token.encode()).hexdigest(),
                        row["id"],
                        D.text(body.get("device_id"), 120, True),
                    ),
                )
            return 200, {"account": {"id": row["id"], "username": row["username"]}, "token": token}
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        with self.lock:
            device = self.db.execute(
                "SELECT * FROM devices WHERE token_hash=? AND revoked=0",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
            if not device:
                return 401, {"error": "Sign in to this hub again."}
            uid = device["user_id"]
            if route == "/push":
                ops = body.get("operations")
                if not isinstance(ops, list) or len(ops) > 100:
                    raise ValueError("Invalid operation batch.")
                results = []
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    for op in ops:
                        D.text(op.get("id"), 120, True)
                        D.text(op.get("entity_id"), 120, True)
                        D.validate(op["kind"], op["patch"])
                        prior = self.db.execute("SELECT * FROM operations WHERE id=?", (op["id"],)).fetchone()
                        if prior:
                            if prior["user_id"] != uid:
                                raise ValueError("Invalid operation identity.")
                            results.append(json.loads(prior["result"]))
                            continue
                        existing = self.db.execute(
                            "SELECT data FROM entities WHERE user_id=? AND kind=? AND id=?",
                            (uid, op["kind"], op["entity_id"]),
                        ).fetchone()
                        remote = json.loads(existing["data"]) if existing else {}
                        merged, conflicts = D.merge_fields(op["base"], op["patch"], remote)
                        if conflicts:
                            results.append(
                                {"id": op["id"], "status": "conflict", "remote": remote, "fields": conflicts}
                            )
                            continue
                        data = {**D.DEFINITIONS[op["kind"]]["defaults"], **merged}
                        D.validate(op["kind"], data)
                        if (
                            op["kind"] in ("ticket", "section")
                            and not self.db.execute(
                                "SELECT id FROM entities WHERE user_id=? AND kind='project' AND id=?",
                                (uid, data["project_id"]),
                            ).fetchone()
                        ):
                            raise ValueError("Project is not available in this account.")
                        if op["kind"] in ("ticket", "section"):
                            related = [
                                {"id": r["id"], **json.loads(r["data"])}
                                for r in self.db.execute(
                                    "SELECT id,data FROM entities WHERE user_id=? AND kind=?",
                                    (uid, op["kind"]),
                                )
                            ]
                            D.check_map_relations(related, op["entity_id"], data)
                        if op["kind"] == "ticket":
                            tickets = [
                                {"id": r["id"], **json.loads(r["data"])}
                                for r in self.db.execute(
                                    "SELECT id,data FROM entities WHERE user_id=? AND kind='ticket'", (uid,)
                                )
                            ]
                            for dependency in data["dependencies"]:
                                if not any(
                                    t["id"] == dependency and t["project_id"] == data["project_id"]
                                    for t in tickets
                                ):
                                    raise ValueError("Invalid dependency.")
                            D.assert_acyclic(tickets, op["entity_id"], data["dependencies"])
                        if op["kind"] in ("repo", "changeset", "post", "attachment"):

                            def find(kind, entity_id):
                                row = self.db.execute(
                                    "SELECT data FROM entities WHERE user_id=? AND kind=? AND id=?",
                                    (uid, kind, entity_id),
                                ).fetchone()
                                return {"id": entity_id, **json.loads(row["data"])} if row else None

                            D.check_code_relations(op["kind"], data, find)
                        if op["kind"] in ("placement", "entry", "timer", "block"):
                            target = self.db.execute(
                                "SELECT data FROM entities WHERE user_id=? AND kind='ticket' AND id=?",
                                (uid, data["ticket_id"]),
                            ).fetchone()
                            if data["ticket_id"] and not target:
                                raise ValueError("Ticket is not available in this account.")
                            if op["kind"] == "placement":
                                if not target:
                                    raise ValueError("A placement needs a ticket.")
                                if data["section_id"]:
                                    section = self.db.execute(
                                        "SELECT data FROM entities WHERE user_id=? AND kind='section' AND id=?",
                                        (uid, data["section_id"]),
                                    ).fetchone()
                                    if (
                                        not section
                                        or json.loads(section["data"])["project_id"]
                                        != json.loads(target["data"])["project_id"]
                                    ):
                                        raise ValueError("Section belongs to another project.")
                        raw = json.dumps(data)
                        self.db.execute(
                            "INSERT INTO entities VALUES(?,?,?,?) ON CONFLICT(user_id,kind,id) DO UPDATE SET data=excluded.data",
                            (uid, op["kind"], op["entity_id"], raw),
                        )
                        self.db.execute(
                            "INSERT INTO changes(user_id,kind,entity_id,data) VALUES(?,?,?,?)",
                            (uid, op["kind"], op["entity_id"], raw),
                        )
                        result = {"id": op["id"], "status": "accepted", "data": data}
                        self.db.execute(
                            "INSERT INTO operations VALUES(?,?,?)", (op["id"], uid, json.dumps(result))
                        )
                        results.append(result)
                    self.db.execute("COMMIT")
                except Exception:
                    self.db.execute("ROLLBACK")
                    raise
                return 200, {"results": results}
            if route == "/pull":
                cursor = body.get("cursor", 0)
                if type(cursor) is not int or cursor < 0:
                    raise ValueError("Invalid cursor.")
                rows = self.db.execute(
                    "SELECT * FROM changes WHERE user_id=? AND seq>? ORDER BY seq LIMIT 200", (uid, cursor)
                ).fetchall()
                return 200, {
                    "changes": [
                        {
                            "seq": r["seq"],
                            "kind": r["kind"],
                            "id": r["entity_id"],
                            "data": json.loads(r["data"]),
                        }
                        for r in rows
                    ],
                    "cursor": rows[-1]["seq"] if rows else cursor,
                    "more": len(rows) == 200,
                }
            if route == "/devices":
                return 200, {
                    "devices": [
                        dict(r)
                        for r in self.db.execute(
                            "SELECT device_id,revoked FROM devices WHERE user_id=?", (uid,)
                        )
                    ]
                }
            if route == "/revoke":
                self.db.execute(
                    "UPDATE devices SET revoked=1 WHERE user_id=? AND device_id=?",
                    (uid, D.text(body.get("device_id"), 120, True)),
                )
                return 200, {"ok": True}
            return 404, {"error": "Unknown endpoint."}


def main():
    parser = argparse.ArgumentParser(description="DayFrame private Python LAN sync hub")
    parser.add_argument("--host", default=os.environ.get("TM_HUB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("TM_HUB_PORT", "47831")))
    parser.add_argument(
        "--data-dir", default=os.environ.get("TM_HUB_DATA", str(Path.home() / ".local/share/timemanager-hub"))
    )
    parser.add_argument("--cert", default=os.environ.get("TM_HUB_CERT"))
    parser.add_argument("--key", default=os.environ.get("TM_HUB_KEY"))
    args = parser.parse_args()
    hub = Hub(
        args.data_dir, args.host, args.port, os.environ.get("TM_HUB_SETUP_TOKEN", ""), args.cert, args.key
    )
    print(f"DayFrame Python hub listening on {args.host}:{args.port}")
    try:
        hub.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        hub.close()


if __name__ == "__main__":
    main()
