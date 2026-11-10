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


class TicketsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from dayframe.ui.window import DayFrame

        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("demo", "pw")
        self.s.command("demo.load")
        self.w = DayFrame(self.s)
        self.w.sync.persist_tokens = False
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        from PySide6.QtCore import QEvent

        self.w.close()
        self.w.deleteLater()
        self.w = None
        self.app.processEvents()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.s.close()

    def settle(self):
        for _ in range(3):
            self.app.processEvents()

    def test_navigation_order_and_overview(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLineEdit
        from dayframe.ui.views.charts import BarList, ColumnChart

        self.assertEqual(
            list(self.w.nav), ["Today", "Projects", "Tickets", "Code", "Calendar", "Time", "Settings"]
        )
        self.w.navigate("Tickets")
        self.settle()
        self.assertTrue(self.w.context.isVisible())
        self.assertEqual(len(self.w.workspace.findChildren(ColumnChart)), 3)
        self.assertEqual(len(self.w.workspace.findChildren(BarList)), 3)
        table = self.w.ticket_table
        open_count = sum(t["status"] != "done" and not t["archived"] for t in self.s.list("ticket"))
        self.assertEqual(table.rowCount(), open_count)
        search = next(
            e for e in self.w.workspace.findChildren(QLineEdit) if e.accessibleName() == "Search tickets"
        )
        word = max(table.item(0, 1).text().split(), key=len).casefold()
        search.setText(word)
        shown = [r for r in range(table.rowCount()) if not table.isRowHidden(r)]
        self.assertTrue(shown)
        self.assertLess(len(shown), table.rowCount())
        for r in shown:
            ticket = self.w.find_ticket(table.item(r, 0).data(Qt.UserRole))
            self.assertIn(word, self.w.ticket_haystack(ticket))
        search.clear()
        table.sortItems(4, Qt.DescendingOrder)
        self.assertEqual(table.item(0, 4).text(), "Urgent")
        self.w.choose_tickets_view("overdue")
        self.settle()
        today = D.day_key(self.s.settings()["timezone"])
        for r in range(self.w.ticket_table.rowCount()):
            ticket = self.w.find_ticket(self.w.ticket_table.item(r, 0).data(Qt.UserRole))
            self.assertLess(ticket["due_date"], today)
        first = self.w.ticket_table.item(0, 0).data(Qt.UserRole)
        self.w.ticket_table.cellDoubleClicked.emit(0, 0)
        self.settle()
        self.assertEqual((self.w.tickets_view, self.w.tickets_ticket), ("Details", first))

    def test_activity_header_counts_time_sessions(self):
        from PySide6.QtWidgets import QLabel

        entries = self.s.list("entry")
        ticket = next(t for t in self.s.list("ticket") if any(e["ticket_id"] == t["id"] for e in entries))
        sessions = sum(e["ticket_id"] == ticket["id"] for e in entries)
        self.w.open_ticket_details(ticket["id"])
        self.settle()
        labels = [x.text() for x in self.w.workspace.findChildren(QLabel)]
        self.assertIn("%d time sessions" % sessions, labels)

    def test_comment_with_screenshot_edit_and_delete(self):
        from unittest.mock import patch as mock
        from PySide6.QtGui import QColor, QImage
        from dayframe.ui.window import tickets as page
        from dayframe.ui.views.ticket_thread import MarkdownView, Thumb

        ticket = next(t for t in self.s.list("ticket") if t["status"] == "doing")
        self.w.open_ticket_details(ticket["id"])
        self.settle()
        self.w.ticket_composer.setPlainText("Looks **good** on my machine")
        image = QImage(1200, 700, QImage.Format_RGB32)
        image.fill(QColor("#336699"))
        self.w.ticket_composer.imagePasted.emit(image, "pasted.png")
        self.settle()
        self.assertEqual(len(self.w.ticket_pending[ticket["id"]]), 1)
        self.assertEqual(self.w.ticket_composer.toPlainText(), "Looks **good** on my machine")
        self.assertTrue(self.w.post_comment(ticket))
        self.settle()
        post = next(p for p in self.s.list("post") if p["body"] == "Looks **good** on my machine")
        shot = next(a for a in self.s.list("attachment") if a["post_id"] == post["id"])
        self.assertEqual((shot["width"], shot["height"]), (1200, 700))
        self.assertTrue(
            any(
                isinstance(w, Thumb) and w.attachment["id"] == shot["id"]
                for w in self.w.workspace.findChildren(Thumb)
            )
        )
        self.assertTrue(any("good" in v.toPlainText() for v in self.w.workspace.findChildren(MarkdownView)))
        self.assertEqual(self.w.ticket_composer.toPlainText(), "")
        self.w.start_post_edit(post["id"])
        self.settle()
        self.w.save_post_edit(self.s.read("post", post["id"]), "Edited text")
        edited = self.s.read("post", post["id"])
        self.assertEqual(edited["body"], "Edited text")
        self.assertGreater(edited["edited_at"], 0)
        with mock.object(page, "confirm", return_value=True):
            self.w.delete_post(edited)
        self.assertEqual(self.s.read("post", post["id"])["archived"], 1)
        self.w.undo()
        self.assertEqual(self.s.read("post", post["id"])["archived"], 0)

    def test_unsent_comment_is_protected_and_status_menu_works(self):
        from unittest.mock import patch as mock
        from PySide6.QtWidgets import QMessageBox, QPushButton

        ticket = next(t for t in self.s.list("ticket") if t["status"] == "ready")
        self.w.open_ticket_details(ticket["id"])
        self.settle()
        self.w.ticket_composer.setPlainText("Half-written thought")
        with mock.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
            self.w.navigate("Calendar")
        self.assertEqual(self.w.page, "Tickets")
        with mock.object(QMessageBox, "question", return_value=QMessageBox.Save):
            self.w.navigate("Calendar")
        self.assertEqual(self.w.page, "Calendar")
        self.assertTrue(any(p["body"] == "Half-written thought" for p in self.s.list("post")))
        self.w.navigate("Projects")
        self.w.select_ticket(ticket["id"])
        self.settle()
        status = next(
            b for b in self.w.inspector.findChildren(QPushButton) if b.objectName() == "statusButton"
        )
        review = next(a for a in status.menu().actions() if a.text() == "Review")
        review.trigger()
        self.assertEqual(self.s.read("ticket", ticket["id"])["status"], "review")
        self.w.undo()
        self.assertEqual(self.s.read("ticket", ticket["id"])["status"], "ready")
        for text in ("Edit", "Track", "Details", "Schedule", "Code", "More"):
            self.assertTrue(any(b.text() == text for b in self.w.inspector.findChildren(QPushButton)), text)

    def test_large_images_shrink_to_fit(self):
        from PySide6.QtGui import QImage
        from dayframe.ui.views.ticket_thread import prepare_image

        image = QImage(3000, 2000, QImage.Format_RGB32)
        for y in range(0, 2000, 4):
            for x in range(0, 3000, 4):
                image.setPixel(x, y, (x * 7919 + y * 104729) & 0xFFFFFF)
        prepared = prepare_image(image, "noisy.png")
        self.assertLessEqual(len(prepared["data"]), D.MAX_ATTACHMENT_CHARS)
        self.assertLessEqual(max(prepared["width"], prepared["height"]), 1600)
        with self.assertRaises(ValueError):
            prepare_image(QImage())


if __name__ == "__main__":
    unittest.main()
