"""Compatible, encrypted LAN synchronization without a browser runtime."""

from __future__ import annotations
import hashlib
import hmac
import http.client
import json
import ssl
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from cryptography import x509
from ..core import domain as D


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, fingerprint, timeout=12):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        super().__init__(host, port, timeout=timeout, context=context)
        self.expected = fingerprint

    def connect(self):
        super().connect()
        raw = self.sock.getpeercert(binary_form=True)
        if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), self.expected):
            self.close()
            raise ValueError("Hub certificate does not match the trusted fingerprint.")
        certificate = x509.load_der_x509_certificate(raw)
        now = datetime.now(timezone.utc)
        if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
            self.close()
            raise ValueError("Hub certificate is expired or not yet valid.")


def request(base, route, body, token="", fingerprint="", setup_token=""):
    url = urlsplit(base)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("Enter a valid HTTPS hub address.")
    if url.scheme == "http" and url.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("LAN sync requires HTTPS.")
    if url.scheme == "https" and fingerprint:
        expected = fingerprint.replace(":", "").replace(" ", "").lower()
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("Enter the SHA-256 certificate fingerprint.")
        connection = PinnedHTTPSConnection(url.hostname, url.port or 443, expected)
    elif url.scheme == "https":
        connection = http.client.HTTPSConnection(
            url.hostname, url.port or 443, timeout=12, context=ssl.create_default_context()
        )
    else:
        connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=12)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if setup_token:
        headers["X-Setup-Token"] = setup_token
    try:
        connection.request("POST", route, json.dumps(body).encode(), headers)
        response = connection.getresponse()
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Hub response is too large.")
        result = json.loads(raw)
        if response.status >= 400:
            raise ValueError(result.get("error", "Hub request failed."))
        return result
    finally:
        connection.close()


class Sync:
    def __init__(self, store, persist_tokens=True):
        self.store = store
        self.persist_tokens = persist_tokens
        self.token = None
        self.guard = threading.Lock()
        self.state = {"connected": False, "lastSync": None, "error": None}

    def _secret(self, value=None):
        if not self.persist_tokens:
            if value is not None:
                raise ValueError("Session-only credentials.")
            return None
        import keyring

        backend = keyring.get_keyring()
        if backend.priority <= 0 or "plaintext" in type(backend).__name__.lower():
            raise ValueError("A secure operating-system credential store is unavailable.")
        account = self.store.auth()["id"]
        if value is None:
            return keyring.get_password("TimeManager.native.sync", account)
        keyring.set_password("TimeManager.native.sync", account, value)

    def connect(self, p, importing=False):
        s = self.store
        device = s.account["device_id"] if s.account else str(uuid.uuid4())
        result = request(
            p["url"],
            "/login",
            {
                "username": p.get("username") or s.auth()["username"],
                "password": p["password"],
                "device_id": device,
            },
            fingerprint=p.get("fingerprint", ""),
        )
        if importing:
            s.register(result["account"]["username"], p["password"], result["account"]["id"])
            with s.atomic():
                s.db.execute("UPDATE accounts SET device_id=? WHERE id=?", (device, s.account["id"]))
                s.account["device_id"] = device
            s.remember_session()
        elif result["account"]["id"] != s.auth()["id"]:
            raise ValueError(
                "This hub has a different account identity. Import it into an unconfigured installation."
            )
        self.token = result["token"]
        s.settings({"syncUrl": p["url"], "syncFingerprint": p.get("fingerprint", ""), "syncEnabled": True})
        remembered = True
        try:
            self._secret(self.token)
        except Exception:
            remembered = False
        self.run()
        return {**self.state, "remembered": remembered}

    def publish(self, p):
        a = self.store.auth()
        request(
            p["url"],
            "/register",
            {"id": a["id"], "username": a["username"], "password": p["password"]},
            fingerprint=p.get("fingerprint", ""),
            setup_token=p.get("setupToken", ""),
        )
        return self.connect(p)

    def run(self, force=False):
        if not self.store.account or not self.guard.acquire(blocking=False):
            return self.state
        s = self.store
        try:
            config = s.settings()
            if (not force and not config.get("syncEnabled")) or not config.get("syncUrl"):
                return self.state
            actor = s.auth()["id"]
            self.token = self.token or self._secret()
            if not self.token:
                raise ValueError("Sign in to your hub to resume sync.")
            for _ in range(20):
                with s.lock:
                    rows = s.db.execute(
                        "SELECT * FROM outbox WHERE account_id=? AND status='pending' ORDER BY seq LIMIT 100",
                        (actor,),
                    ).fetchall()
                if not rows:
                    break
                operations, selected, size = [], [], 0
                for row in rows:
                    op = {
                        "id": row["operation_id"],
                        "kind": row["kind"],
                        "entity_id": row["entity_id"],
                        "base": json.loads(row["base"]),
                        "patch": json.loads(row["patch"]),
                    }
                    length = len(json.dumps(op).encode())
                    if operations and size + length > 460000:
                        break
                    if length > 500000:
                        raise ValueError("A queued change is too large for synchronization.")
                    size += length
                    operations.append(op)
                    selected.append(row)
                response = request(
                    config["syncUrl"],
                    "/push",
                    {"operations": operations},
                    self.token,
                    config.get("syncFingerprint", ""),
                )
                with s.atomic():
                    if s.auth()["id"] != actor:
                        raise ValueError("Account changed during sync.")
                    by_id = {r["operation_id"]: r for r in selected}
                    for result in response["results"]:
                        op = by_id[result["id"]]
                        if result["status"] == "conflict":
                            s.db.execute(
                                "UPDATE outbox SET status='conflict' WHERE operation_id=?",
                                (op["operation_id"],),
                            )
                            s.db.execute(
                                "INSERT OR REPLACE INTO conflicts VALUES(?,?,?,?,?,?,?)",
                                (
                                    op["operation_id"],
                                    actor,
                                    op["operation_id"],
                                    op["kind"],
                                    op["entity_id"],
                                    json.dumps(result["remote"]),
                                    json.dumps(result["fields"]),
                                ),
                            )
                        else:
                            s.db.execute("DELETE FROM outbox WHERE operation_id=?", (op["operation_id"],))
                            if not s.db.execute(
                                "SELECT seq FROM outbox WHERE account_id=? AND kind=? AND entity_id=?",
                                (actor, op["kind"], op["entity_id"]),
                            ).fetchone():
                                s._save(op["kind"], {"id": op["entity_id"], **result["data"]}, False)
            with s.lock:
                row = s.db.execute("SELECT cursor FROM sync_meta WHERE account_id=?", (actor,)).fetchone()
                cursor = row[0] if row else 0
            for _ in range(50):
                response = request(
                    config["syncUrl"],
                    "/pull",
                    {"cursor": cursor},
                    self.token,
                    config.get("syncFingerprint", ""),
                )
                with s.atomic():
                    if s.auth()["id"] != actor:
                        raise ValueError("Account changed during sync.")
                    for change in response["changes"]:
                        if not s.db.execute(
                            "SELECT seq FROM outbox WHERE account_id=? AND kind=? AND entity_id=?",
                            (actor, change["kind"], change["id"]),
                        ).fetchone():
                            s._save(change["kind"], {"id": change["id"], **change["data"]}, False)
                    s.db.execute(
                        "INSERT INTO sync_meta VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET cursor=excluded.cursor",
                        (actor, response["cursor"]),
                    )
                cursor = response["cursor"]
                if not response["more"]:
                    break
            self.state = {"connected": True, "lastSync": int(time.time() * 1000), "error": None}
        except Exception as error:
            self.state = {**self.state, "connected": False, "error": str(error)}
        finally:
            self.guard.release()
        return self.state

    def resolve(self, conflict_id, choice):
        s = self.store
        with s.atomic():
            a = s.auth()
            row = s.db.execute(
                "SELECT * FROM conflicts WHERE id=? AND account_id=?", (conflict_id, a["id"])
            ).fetchone()
            if not row:
                raise ValueError("Conflict not found.")
            remote = json.loads(row["remote"])
            current = s.read(row["kind"], row["entity_id"])
            queued = s.db.execute(
                "SELECT base FROM outbox WHERE account_id=? AND kind=? AND entity_id=? ORDER BY seq LIMIT 1",
                (a["id"], row["kind"], row["entity_id"]),
            ).fetchone()
            original = json.loads(queued["base"]) if queued else remote
            s.db.execute(
                "DELETE FROM outbox WHERE account_id=? AND kind=? AND entity_id=?",
                (a["id"], row["kind"], row["entity_id"]),
            )
            if choice == "remote":
                s._save(row["kind"], {"id": row["entity_id"], **remote}, False)
            elif choice == "local":
                clean = {k: current[k] for k in D.DEFINITIONS[row["kind"]]["fields"]}
                patch = D.changes(original, clean)
                s._save(row["kind"], {"id": row["entity_id"], **remote, **patch}, False)
                s.db.execute(
                    "INSERT INTO outbox(account_id,operation_id,kind,entity_id,base,patch) VALUES(?,?,?,?,?,?)",
                    (
                        a["id"],
                        str(uuid.uuid4()),
                        row["kind"],
                        row["entity_id"],
                        json.dumps(remote),
                        json.dumps(patch),
                    ),
                )
            else:
                raise ValueError("Choose the local or hub version.")
            s.db.execute(
                "DELETE FROM conflicts WHERE account_id=? AND kind=? AND entity_id=?",
                (a["id"], row["kind"], row["entity_id"]),
            )
