"""Ticket lifecycle times, discussion records, screenshots and the demo workspace."""

import base64
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from dayframe.core import domain as D
from dayframe.data import demo
from dayframe.data.store import Store
from dayframe.sync.client import Sync
from dayframe.sync.hub import Hub

BASE = Path("build/test-data")
PIXEL = base64.b64encode(demo.png(2, 2, [], (10, 20, 30))).decode()


class TicketRecordTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("writer", "pw")
        self.p = self.s.command("project.save", {"name": "Web", "project_key": "WEB"})

    def tearDown(self):
        self.s.close()

    def test_created_and_completed_times_follow_status(self):
        with patch("dayframe.data.store.time.time", return_value=1000.0):
            t = self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Work"})
        self.assertEqual((t["created_at"], t["completed_at"]), (1_000_000, 0))
        with patch("dayframe.data.store.time.time", return_value=2000.0):
            done = self.s.command("ticket.save", {"id": t["id"], "status": "done"})
        self.assertEqual(done["completed_at"], 2_000_000)
        self.assertEqual(done["created_at"], 1_000_000)
        with patch("dayframe.data.store.time.time", return_value=3000.0):
            edited = self.s.command("ticket.save", {"id": t["id"], "title": "Renamed"})
        self.assertEqual(edited["completed_at"], 2_000_000)
        reopened = self.s.command("ticket.save", {"id": t["id"], "status": "ready"})
        self.assertEqual(reopened["completed_at"], 0)
        # Explicit values (imports, demo data) are kept.
        old = self.s.command(
            "ticket.save",
            {
                "project_id": self.p["id"],
                "title": "Old",
                "status": "done",
                "created_at": 5,
                "completed_at": 9,
            },
        )
        self.assertEqual((old["created_at"], old["completed_at"]), (5, 9))

    def test_posts_and_attachments_belong_to_a_ticket(self):
        t = self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Work"})
        other = self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Other"})
        post = self.s.command(
            "post.save", {"ticket_id": t["id"], "body": "First comment", "author": "writer"}
        )
        with self.assertRaises(ValueError):
            self.s.command("post.save", {"ticket_id": t["id"], "body": "   "})
        with self.assertRaisesRegex(ValueError, "Ticket not found"):
            self.s.command("post.save", {"ticket_id": "missing", "body": "x"})
        image = {"ticket_id": t["id"], "post_id": post["id"], "name": "shot.png", "data": PIXEL, "size": 70}
        saved = self.s.command("attachment.save", image)
        with self.assertRaisesRegex(ValueError, "same ticket"):
            self.s.command("attachment.save", {**image, "ticket_id": other["id"]})
        with self.assertRaisesRegex(ValueError, "PNG or JPEG"):
            self.s.command("attachment.save", {**image, "media_type": "image/gif"})
        with self.assertRaisesRegex(ValueError, "too large"):
            self.s.command("attachment.save", {**image, "data": "A" * (D.MAX_ATTACHMENT_CHARS + 4)})
        with self.assertRaisesRegex(ValueError, "too large"):
            self.s.command("attachment.save", {**image, "data": "not base64!"})
        listed = self.s.snapshot()["attachment"][0]
        self.assertNotIn("data", listed)
        self.assertEqual(listed["data_size"], len(PIXEL))
        self.assertEqual(self.s.read("attachment", saved["id"])["data"], PIXEL)

    def test_version_5_profile_migrates_to_6(self):
        t = self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Kept"})
        root = self.s.root
        self.s.close()
        with sqlite3.connect(root / "timemanager.db") as db:
            db.execute("DROP TABLE posts")
            db.execute("DROP TABLE attachments")
            db.execute("ALTER TABLE tickets DROP COLUMN created_at")
            db.execute("ALTER TABLE tickets DROP COLUMN completed_at")
            db.execute("DELETE FROM schema_migrations WHERE version>5")
        self.s = Store(root)
        self.assertTrue(self.s.restore_session())
        self.assertEqual(self.s.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], 6)
        self.assertEqual(self.s.read("ticket", t["id"])["created_at"], 0)
        self.s.command("post.save", {"ticket_id": t["id"], "body": "After migration"})

    def test_demo_workspace(self):
        self.s.close()
        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("demo", "pw")
        self.s.command("demo.load")
        snap = self.s.snapshot()
        self.assertEqual(len(snap["project"]), len(demo.PROJECTS))
        self.assertGreaterEqual(len(snap["ticket"]), 80)
        self.assertEqual({t["status"] for t in snap["ticket"]}, set(D.STATUSES))
        self.assertTrue(all(t["created_at"] for t in snap["ticket"]))
        self.assertTrue(
            all(t["completed_at"] >= t["created_at"] for t in snap["ticket"] if t["status"] == "done")
        )
        for kind in ("entry", "block", "event", "post", "attachment", "section", "placement"):
            self.assertTrue(snap[kind], kind)
        self.assertTrue(any(t["dependencies"] for t in snap["ticket"]))
        image = self.s.read("attachment", snap["attachment"][0]["id"])
        self.assertTrue(base64.b64decode(image["data"]).startswith(b"\x89PNG"))
        with self.assertRaisesRegex(ValueError, "empty workspace"):
            self.s.command("demo.load")


class DiscussionSyncTests(unittest.TestCase):
    def test_comment_and_screenshot_reach_the_other_device(self):
        root = BASE / uuid.uuid4().hex
        hub = Hub(root / "hub", port=0, setup_token="setup").start()
        url = f"http://127.0.0.1:{hub.port}"
        a, b = Store(root / "a"), Store(root / "b")
        try:
            a.register("owner", "pw")
            sa = Sync(a, False)
            sa.publish({"url": url, "password": "pw", "setupToken": "setup"})
            sb = Sync(b, False)
            sb.connect({"url": url, "username": "owner", "password": "pw"}, True)
            p = a.command("project.save", {"name": "P"})
            t = a.command("ticket.save", {"project_id": p["id"], "title": "Work"})
            post = a.command(
                "post.save", {"ticket_id": t["id"], "body": "See the screenshot", "author": "owner"}
            )
            shot = a.command(
                "attachment.save",
                {"ticket_id": t["id"], "post_id": post["id"], "name": "s.png", "data": PIXEL},
            )
            for sync in (sa, sb):
                result = sync.run(force=True)
                self.assertTrue(result["connected"], result["error"])
            self.assertEqual(b.read("post", post["id"])["body"], "See the screenshot")
            self.assertEqual(b.read("attachment", shot["id"])["data"], PIXEL)
            self.assertGreater(b.read("ticket", t["id"])["created_at"], 0)
        finally:
            a.close()
            b.close()
            hub.close()


if __name__ == "__main__":
    unittest.main()
