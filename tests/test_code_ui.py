import shutil
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QRectF, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QTableWidget

from dayframe.code import git as G
from dayframe.data.store import Store
from dayframe.ui import code_dialogs
from dayframe.ui.views.diff_view import DiffView
from dayframe.ui.views.kanban import TicketList, code_badge_rect
from dayframe.ui.views.project_map import ProjectMap, TicketNode
from dayframe.ui.widgets import FormDialog
from dayframe.ui.window import DayFrame
from dayframe.ui.window import code as code_page
from tests.test_code import FakeGitHub, make_repo

APP = QApplication.instance() or QApplication([])


class CodeUiTests(unittest.TestCase):
    def setUp(self):
        self.root = (Path("build/test-data") / uuid.uuid4().hex).resolve()
        self.s = Store(self.root / "profile")
        self.s.register("coder", "pw")
        self.s.load_examples()
        self.w = DayFrame(self.s)
        # Tests must never write to the real OS credential store.
        self.w.sync.persist_tokens = False
        self.w.show()
        APP.processEvents()
        self.project = next(p for p in self.s.list("project") if p["project_key"] == "WEB")
        self.ticket = next(
            t
            for t in self.s.list("ticket")
            if t["project_id"] == self.project["id"] and t["status"] == "doing"
        )

    def tearDown(self):
        self.wait()
        self.w.close()
        self.w.deleteLater()
        self.w = None
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.s.close()
        shutil.rmtree(self.root / "repo", ignore_errors=True)

    def wait(self, timeout=30):
        """Let background jobs and the refreshes they schedule finish."""
        end = time.time() + timeout
        quiet = 0
        while time.time() < end:
            QThreadPool.globalInstance().waitForDone(50)
            APP.processEvents()
            quiet = quiet + 1 if not self.w or not self.w.jobs else 0
            if quiet >= 3:
                return
        self.fail("background jobs did not finish")

    def connect(self, github_repo=""):
        if not G.git_executable():
            self.skipTest("git is not installed")
        _, self.work = make_repo(self.root / "repo")
        repo = self.w.execute(
            "repo.save",
            {
                "project_id": self.project["id"],
                "name": "web",
                "github_repo": github_repo,
                "default_branch": "main",
            },
            refresh=False,
        )
        self.w.execute("settings.save", {"repoPaths": {repo["id"]: str(self.work)}}, refresh=False)
        return repo

    def repo(self):
        return self.w.code_repo(self.project["id"])

    def test_connect_panel_and_project_tree(self):
        self.w.navigate("Code")
        APP.processEvents()
        self.assertTrue(self.w.context.isVisible())
        self.w.choose_code_project(self.project["id"])
        APP.processEvents()
        texts = [b.text() for b in self.w.workspace.findChildren(QPushButton)]
        self.assertIn("Connect Git repository", texts)
        with patch.object(code_page.RepoDialog, "exec", return_value=QDialog.Rejected):
            self.w.edit_repo(self.project)
        self.assertIsNone(self.repo())

    def test_changesets_shelve_switch_and_commit(self):
        repo = self.connect()
        self.w.open_code(self.ticket["id"])
        self.wait()
        self.assertEqual(self.w.page, "Code")
        self.assertEqual(self.w.code_status[repo["id"]]["status"]["branch"], "main")
        app_py = self.work / "app.py"
        app_py.write_text("print('ticket work')\n", encoding="utf-8")
        self.w.refresh_code(repo)
        self.wait()
        self.assertIn("ticket work", self.w.code_diffs[repo["id"]])
        diff_view = next(v for v in self.w.workspace.findChildren(DiffView) if v.isVisible())
        self.assertIn("ticket work", diff_view.toPlainText())

        with patch.object(code_page, "ask_text", return_value="First try"):
            self.w.code_capture(repo, self.ticket, None, keep=True)
            self.wait()
        change = next(c for c in self.s.list("changeset") if c["title"] == "First try")
        self.assertIn("ticket work", change["diff"])
        self.assertEqual(app_py.read_text(encoding="utf-8"), "print('ticket work')\n")
        self.assertEqual(self.w.applied_changeset(repo)["id"], change["id"])

        with patch.object(code_page, "confirm", return_value=True):
            self.w.code_shelve(repo, self.ticket)
            self.wait()
        self.assertEqual(app_py.read_text(encoding="utf-8"), "print('one')\n")
        self.assertIsNone(self.w.applied_changeset(repo))
        self.assertEqual(len([c for c in self.s.list("changeset") if not c["archived"]]), 1)

        with patch.object(code_page.SwitchDialog, "exec", return_value=QDialog.Accepted):
            self.w.code_switch(repo, self.ticket, self.w.data["changeset"][0])
            self.wait()
        self.assertEqual(app_py.read_text(encoding="utf-8"), "print('ticket work')\n")
        self.assertEqual(self.w.applied_changeset(repo)["id"], change["id"])

        def fill(dialog):
            dialog.message.setPlainText("Ticket work")
            return QDialog.Accepted

        with patch.object(code_page.CommitDialog, "exec", new=fill):
            self.w.code_commit(repo)
            self.wait()
        self.assertEqual(G.GitRepo(self.work).log(1)[0]["subject"], "Ticket work")
        self.assertEqual(self.s.read("changeset", change["id"])["archived"], 1)
        self.assertIsNone(self.w.applied_changeset(repo))

        asked = []
        with patch.object(code_page, "confirm", side_effect=lambda *args: asked.append(args) or True):
            self.w.code_push(repo)
            self.wait()
        _, title, text, details, _, warning = asked[0]
        self.assertEqual(title, "Push")
        self.assertIn("1 commit(s) from main", text)
        self.assertIn("Ticket work", details)
        self.assertIn("default branch", warning)
        self.assertEqual(self.w.code_status[repo["id"]]["status"]["ahead"], 0)

    def test_switch_shelves_dirty_work_before_restoring(self):
        repo = self.connect()
        self.w.open_code(self.ticket["id"])
        self.wait()
        app_py = self.work / "app.py"
        app_py.write_text("print('saved')\n", encoding="utf-8")
        self.w.refresh_code(repo)
        self.wait()
        with (
            patch.object(code_page, "ask_text", return_value="Saved"),
            patch.object(code_page, "confirm", return_value=True),
        ):
            self.w.code_capture(repo, self.ticket, None, keep=False)
            self.wait()
        saved = next(c for c in self.s.list("changeset") if c["title"] == "Saved")
        app_py.write_text("print('in progress')\n", encoding="utf-8")
        self.w.refresh_code(repo)
        self.wait()
        with patch.object(code_page.SwitchDialog, "exec", return_value=QDialog.Accepted):
            self.w.code_switch(repo, self.ticket, saved)
            self.wait()
        self.assertEqual(app_py.read_text(encoding="utf-8"), "print('saved')\n")
        shelved = [c for c in self.s.list("changeset") if c["id"] != saved["id"]]
        self.assertEqual(len(shelved), 1)
        self.assertIn("in progress", shelved[0]["diff"])
        # Deleting is recoverable.
        with patch.object(code_page, "confirm", return_value=True):
            self.w.code_delete(repo, shelved[0])
        self.assertEqual(self.s.read("changeset", shelved[0]["id"])["archived"], 1)
        self.w.undo()
        self.assertEqual(self.s.read("changeset", shelved[0]["id"])["archived"], 0)

    def test_links_from_kanban_map_inspector_and_calendar(self):
        self.w.execute("repo.save", {"project_id": self.project["id"], "name": "web"}, refresh=False)
        self.w.navigate("Projects")
        APP.processEvents()
        lane = next(lane for lane in self.w.findChildren(TicketList) if lane.status == "doing")
        item = next(
            lane.item(i) for i in range(lane.count()) if lane.item(i).data(Qt.UserRole) == self.ticket["id"]
        )
        badge = code_badge_rect(QRectF(lane.visualItemRect(item)).adjusted(2, 2, -2, -2))
        QTest.mouseClick(lane.viewport(), Qt.LeftButton, Qt.NoModifier, badge.center().toPoint())
        APP.processEvents()
        self.assertEqual((self.w.page, self.w.code_ticket), ("Code", self.ticket["id"]))

        self.w.choose_project(self.project["id"])
        self.w.page = "Projects"
        self.w.project_view = "Map"
        self.w.refresh_page()
        APP.processEvents()
        node = next(
            n
            for n in self.w.findChild(ProjectMap).scene().items()
            if isinstance(n, TicketNode) and n.ticket["id"] == self.ticket["id"]
        )
        self.assertTrue(node.code)
        view = self.w.findChild(ProjectMap)
        point = view.mapFromScene(node.mapToScene(node.code_rect.center()))
        QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, point)
        APP.processEvents()
        self.assertEqual((self.w.page, self.w.code_ticket), ("Code", self.ticket["id"]))

        self.w.open_ticket(self.ticket["id"])
        APP.processEvents()
        self.assertEqual((self.w.page, self.w.selected), ("Projects", self.ticket["id"]))
        code_button = next(b for b in self.w.inspector.findChildren(QPushButton) if b.text() == "Code")
        QTest.mouseClick(code_button, Qt.LeftButton)
        APP.processEvents()
        self.assertEqual(self.w.page, "Code")

        block = next(b for b in self.s.list("block") if b["ticket_id"] == self.ticket["id"])

        def click_open_in_code(dialog):
            target = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Open in Code")
            target.click()
            return QDialog.Rejected

        self.w.navigate("Calendar")
        with patch.object(FormDialog, "exec", new=click_open_in_code):
            self.w.open_calendar_item({"kind": "block", "id": block["id"], "ticket_id": self.ticket["id"]})
        APP.processEvents()
        self.assertEqual((self.w.page, self.w.code_ticket), ("Code", self.ticket["id"]))

    def test_github_settings_and_overview(self):
        FakeGitHub.calls = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d" % server.server_address[1]
            self.w.settings_section = "sync"
            self.w.navigate("Settings")
            APP.processEvents()
            panel = self.w.settings_panel
            panel.fields["githubToken"].setText("good-token")
            panel.fields["githubApiUrl"].setText(url)
            panel.save_github_token()
            self.wait()
            self.assertEqual(self.w.data["settings"]["githubUser"], "octo")
            self.assertEqual(self.w.github_token(), "good-token")
            self.assertEqual(panel.fields["githubToken"].text(), "")
            self.assertNotIn("good-token", str(self.s.settings()))

            repo = self.connect("owner/web")
            self.w.open_code(self.ticket["id"])
            self.wait()
            self.w.change_code_view("GitHub")
            self.wait()
            tables = {
                t.horizontalHeaderItem(1).text(): t
                for t in self.w.workspace.findChildren(QTableWidget)
                if t.isVisible()
            }
            self.assertEqual({k: t.rowCount() for k, t in tables.items()}, {"Pull request": 1, "Issue": 1})
            self.assertEqual(tables["Pull request"].item(0, 2).text(), "feat → main")

            def accept_pull(dialog):
                self.assertEqual(dialog.head.text(), "main")
                return QDialog.Accepted

            with (
                patch.object(code_dialogs.PullRequestDialog, "exec", new=accept_pull),
                patch.object(code_page.QDesktopServices, "openUrl"),
            ):
                self.w.github_new_pull(repo, self.w.code_status[repo["id"]])
                self.wait()
            post = next(call for call in FakeGitHub.calls if call[0] == "POST")
            self.assertEqual(post[2]["base"], "main")
            self.assertTrue(post[2]["title"].endswith(self.ticket["title"]))

            with (
                patch.object(code_page, "confirm", return_value=True),
                patch("dayframe.ui.views.settings_panel.confirm", return_value=True),
            ):
                self.w.settings_section = "sync"
                self.w.navigate("Settings")
                APP.processEvents()
                self.w.settings_panel.remove_github_token()
            self.assertIsNone(self.w.github_token())
            self.assertEqual(self.w.data["settings"]["githubUser"], "")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
