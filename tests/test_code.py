import json
import shutil
import sqlite3
import subprocess
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dayframe.code import diff as DIFF
from dayframe.code import git as G
from dayframe.code import graph as GRAPH
from dayframe.code.github import GitHub, GitHubError, TokenStore
from dayframe.core import domain as D
from dayframe.core import preferences
from dayframe.data.store import Store
from dayframe.sync.client import Sync
from dayframe.sync.hub import Hub

BASE = Path("build/test-data")


def git(path, *args):
    return subprocess.run(
        ["git", "-c", "init.defaultBranch=main", *args], cwd=path, check=True, capture_output=True, text=True
    ).stdout


def make_repo(root):
    """A bare 'origin' and a clone with one commit on main."""
    origin = root / "origin.git"
    origin.mkdir(parents=True)
    git(origin, "init", "--bare", "-b", "main")
    work = root / "work"
    git(root, "clone", str(origin), str(work))
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "config", "user.name", "Test")
    git(work, "config", "commit.gpgsign", "false")
    (work / "app.py").write_text("print('one')\n", encoding="utf-8")
    git(work, "add", "app.py")
    git(work, "commit", "-m", "First")
    git(work, "push", "-u", "origin", "main")
    return origin, work


class CodeStoreTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("coder", "pw")
        self.p = self.s.command("project.save", {"name": "Web", "project_key": "WEB"})
        self.t = self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Build it"})

    def tearDown(self):
        self.s.close()

    def test_repository_and_changeset_rules(self):
        repo = self.s.command(
            "repo.save", {"project_id": self.p["id"], "name": "web", "github_repo": "owner/web"}
        )
        with self.assertRaisesRegex(ValueError, "already has a repository"):
            self.s.command("repo.save", {"project_id": self.p["id"], "name": "second"})
        with self.assertRaisesRegex(ValueError, "owner/name"):
            self.s.command("repo.save", {"id": repo["id"], "github_repo": "not a repo"})
        with self.assertRaisesRegex(ValueError, "Git or Subversion"):
            self.s.command("repo.save", {"id": repo["id"], "provider": "hg"})
        other = self.s.command("project.save", {"name": "Other"})
        foreign = self.s.command("ticket.save", {"project_id": other["id"], "title": "Elsewhere"})
        with self.assertRaisesRegex(ValueError, "repository's project"):
            self.s.command(
                "changeset.save", {"repo_id": repo["id"], "ticket_id": foreign["id"], "title": "x"}
            )
        change = self.s.command(
            "changeset.save",
            {"repo_id": repo["id"], "ticket_id": self.t["id"], "title": "WIP", "diff": "+line\n" * 10},
        )
        snapshot = self.s.snapshot()["changeset"][0]
        self.assertNotIn("diff", snapshot)
        self.assertEqual(snapshot["diff_size"], 60)
        self.assertEqual(self.s.read("changeset", change["id"])["diff"], "+line\n" * 10)
        with self.assertRaisesRegex(ValueError, "too large"):
            self.s.command("changeset.save", {"id": change["id"], "diff": "x" * (D.MAX_DIFF_BYTES + 1)})
        # An archived repository frees the project for a new connection.
        self.s.command("repo.save", {"id": repo["id"], "archived": 1})
        self.s.command("repo.save", {"project_id": self.p["id"], "name": "replacement"})

    def test_version_4_profile_gains_code_tables(self):
        root = self.s.root
        self.s.close()
        with sqlite3.connect(root / "timemanager.db") as db:
            db.execute("DROP TABLE changesets")
            db.execute("DROP TABLE repositories")
            db.execute("DELETE FROM schema_migrations WHERE version>4")
        self.s = Store(root)
        self.assertTrue(self.s.restore_session())
        self.assertEqual(self.s.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], 6)
        self.assertEqual(self.s.read("ticket", self.t["id"])["title"], "Build it")
        self.s.command("repo.save", {"project_id": self.p["id"], "name": "web"})

    def test_device_local_code_preferences(self):
        self.s.settings({"repoPaths": {"r": "C:/src/web"}, "activeChangesets": {"r": "c"}})
        self.assertEqual(self.s.settings()["repoPaths"], {"r": "C:/src/web"})
        for bad in (
            {"repoPaths": {"r": 3}},
            {"activeChangesets": []},
            {"githubApiUrl": "http://github.example"},
        ):
            with self.assertRaises(ValueError):
                preferences.validate(bad)


class GitRepoTests(unittest.TestCase):
    def setUp(self):
        if not G.git_executable():
            self.skipTest("git is not installed")
        self.root = (BASE / uuid.uuid4().hex).resolve()
        self.origin, self.work = make_repo(self.root)
        self.repo = G.GitRepo(self.work)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_helpers(self):
        self.assertEqual(
            G.branch_name("WEB", "1A2B3C4D", "Fix the Login page!"), "web-1a2b3c-fix-the-login-page"
        )
        for url in (
            "https://github.com/owner/repo.git",
            "git@github.com:owner/repo.git",
            "ssh://git@github.com/owner/repo",
            "https://token@github.com/owner/repo/",
        ):
            self.assertEqual(G.github_repo_from_url(url), "owner/repo", url)
        self.assertEqual(G.github_repo_from_url("https://gitlab.com/owner/repo"), "")

    def test_status_shelve_and_restore_in_another_checkout(self):
        status = self.repo.status()
        self.assertEqual((status["branch"], status["upstream"], status["files"]), ("main", "origin/main", []))
        (self.work / "app.py").write_text("print('two')\n", encoding="utf-8")
        (self.work / "notes.txt").write_text("new file\n", encoding="utf-8")
        codes = {f["path"]: f["code"] for f in self.repo.status()["files"]}
        self.assertEqual(codes, {"app.py": ".M", "notes.txt": "??"})
        self.assertIn("notes.txt", self.repo.working_diff())
        shelved = self.repo.shelve("change-1", "Try two")
        self.assertEqual(self.repo.status()["files"], [])
        self.assertIn("+print('two')", shelved["diff"])
        self.assertIn("notes.txt", shelved["diff"])
        self.assertEqual(shelved["branch"], "main")
        self.assertTrue(self.repo.find_stash("change-1"))
        # The stored diff alone reproduces the change in a different clone (another device).
        other_path = self.root / "other"
        git(self.root, "clone", str(self.origin), str(other_path))
        other = G.GitRepo(other_path)
        self.assertEqual(other.restore({"id": "change-1", "diff": shelved["diff"]}), "applied")
        self.assertEqual((other_path / "app.py").read_text(encoding="utf-8"), "print('two')\n")
        self.assertTrue((other_path / "notes.txt").exists())
        with self.assertRaisesRegex(G.GitError, "uncommitted"):
            other.restore({"id": "change-1", "diff": shelved["diff"]})
        # Without a stored diff the local stash entry is used.
        self.assertEqual(self.repo.restore({"id": "change-1", "diff": ""}), "applied")
        self.assertEqual((self.work / "app.py").read_text(encoding="utf-8"), "print('two')\n")

    def test_snapshot_keeps_working_tree(self):
        (self.work / "app.py").write_text("print('three')\n", encoding="utf-8")
        snap = self.repo.shelve("change-2", "Snapshot", keep=True)
        self.assertIn("three", snap["diff"])
        self.assertEqual((self.work / "app.py").read_text(encoding="utf-8"), "print('three')\n")
        git(self.work, "checkout", "--", "app.py")
        with self.assertRaisesRegex(G.GitError, "no changes"):
            self.repo.shelve("change-3", "Nothing")

    def test_branch_commit_push_pull(self):
        self.repo.switch("web-feature", create=True)
        self.assertIn("web-feature", self.repo.branches())
        (self.work / "app.py").write_text("print('four')\n", encoding="utf-8")
        (self.work / "skip.txt").write_text("not committed\n", encoding="utf-8")
        with self.assertRaisesRegex(G.GitError, "message"):
            self.repo.commit("  ", ["app.py"])
        sha = self.repo.commit("Print four", ["app.py"])
        self.assertTrue(sha)
        self.assertEqual([f["path"] for f in self.repo.status()["files"]], ["skip.txt"])
        self.assertEqual([c["subject"] for c in self.repo.outgoing()], ["Print four"])
        self.repo.push()
        status = self.repo.status()
        self.assertEqual((status["upstream"], status["ahead"]), ("origin/web-feature", 0))
        self.assertEqual(self.repo.outgoing(), [])
        self.assertEqual(self.repo.log(1)[0]["subject"], "Print four")
        # A second clone pushes; pull fast-forwards, and push refuses while behind.
        other_path = self.root / "other"
        git(self.root, "clone", "-b", "web-feature", str(self.origin), str(other_path))
        git(other_path, "config", "user.email", "o@example.invalid")
        git(other_path, "config", "user.name", "Other")
        (other_path / "app.py").write_text("print('five')\n", encoding="utf-8")
        git(other_path, "commit", "-am", "Five")
        git(other_path, "push")
        self.repo.fetch()
        self.assertEqual(self.repo.status()["behind"], 1)
        with self.assertRaisesRegex(G.GitError, "Pull first"):
            self.repo.push()
        self.repo.pull()
        self.assertEqual((self.work / "app.py").read_text(encoding="utf-8"), "print('five')\n")

    def test_history_refs_stashes_and_index(self):
        self.repo.switch("feature", create=True)
        (self.work / "feature.py").write_text("x = 1\n", encoding="utf-8")
        self.repo.commit("Add feature", ["feature.py"])
        git(self.work, "tag", "v1")
        self.repo.switch("main")
        (self.work / "app.py").write_text("print('main')\n", encoding="utf-8")
        self.repo.commit("Main change", ["app.py"])
        git(self.work, "merge", "--no-ff", "-m", "Merge feature", "feature")
        log = self.repo.graph_log()
        self.assertEqual(log[0]["subject"], "Merge feature")
        self.assertEqual(len(log[0]["parents"]), 2)
        self.assertIn("HEAD -> main", log[0]["refs"])
        self.assertTrue(any("tag: v1" in c["refs"] for c in log))
        details = self.repo.commit_details(log[0]["sha"])
        self.assertEqual(details["message"], "Merge feature")
        self.assertEqual([f["path"] for f in DIFF.parse(details["diff"])], ["feature.py"])
        refs = {(r["kind"], r["name"]): r for r in self.repo.refs()}
        self.assertTrue(refs[("local", "main")]["head"])
        self.assertEqual(refs[("local", "main")]["ahead"], 3)
        self.assertIn(("tag", "v1"), refs)
        self.assertIn(("remote", "origin/main"), refs)
        (self.work / "app.py").write_text("print('wip')\n", encoding="utf-8")
        self.repo.shelve("cs-1", "Keep")
        self.assertEqual(self.repo.stashes()[0]["changeset"], "cs-1")
        (self.work / "app.py").write_text("print('staged')\n", encoding="utf-8")
        self.repo.stage(["app.py"])
        self.assertEqual(self.repo.status()["files"][0]["code"], "M.")
        self.repo.unstage(["app.py"])
        self.assertEqual(self.repo.status()["files"][0]["code"], ".M")
        self.repo.discard(["app.py"])
        self.assertEqual(self.repo.status()["files"], [])
        self.repo.branch_from("from-tag", "v1")
        self.assertEqual(self.repo.status()["branch"], "from-tag")
        self.repo.switch("main")
        self.repo.delete_branch("from-tag")
        self.repo.switch("unmerged", create=True)
        (self.work / "u.txt").write_text("u\n", encoding="utf-8")
        self.repo.commit("Unmerged", ["u.txt"])
        self.repo.switch("main")
        with self.assertRaisesRegex(G.GitError, "not fully merged"):
            self.repo.delete_branch("unmerged")
        for bad in ("-D", "a b", "x..y", ""):
            with self.assertRaises(G.GitError):
                G.check_branch(bad)
        with self.assertRaises(G.GitError):
            self.repo.commit_details("--output=x")

    def test_missing_folder_is_reported(self):
        with self.assertRaisesRegex(G.GitError, "does not exist"):
            G.GitRepo(self.root / "missing").status()
        self.assertFalse(G.GitRepo(self.origin).is_repository())
        self.assertTrue(self.repo.is_repository())


SAMPLE_DIFF = """diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,4 +1,4 @@
 import os
-value = 1\r
+value = 2
 print(value)
-- not a header
+-- still content
diff --git a/old name.txt b/new name.txt
similarity index 100%
rename from old name.txt
rename to new name.txt
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
index 3333333..0000000
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
\\ No newline at end of file
diff --git a/src/views/new.py b/src/views/new.py
new file mode 100644
index 0000000..4444444
--- /dev/null
+++ b/src/views/new.py
@@ -0,0 +1,2 @@
+a
+b
diff --git a/logo.png b/logo.png
index 5555555..6666666 100644
Binary files a/logo.png and b/logo.png differ
"""


class DiffAndGraphTests(unittest.TestCase):
    def test_parse_statuses_counts_and_line_numbers(self):
        files = {f["path"]: f for f in DIFF.parse(SAMPLE_DIFF)}
        self.assertEqual(
            {p: f["status"] for p, f in files.items()},
            {
                "src/app.py": "M",
                "new name.txt": "R",
                "gone.txt": "D",
                "src/views/new.py": "A",
                "logo.png": "M",
            },
        )
        app = files["src/app.py"]
        self.assertEqual((app["added"], app["removed"]), (2, 2))
        lines = app["hunks"][0]["lines"]
        self.assertEqual(lines[1], ("del", 2, None, "value = 1\r"))
        self.assertEqual(lines[2], ("add", None, 2, "value = 2"))
        self.assertEqual(lines[4][0], "del")
        self.assertEqual(files["new name.txt"]["old_path"], "old name.txt")
        self.assertEqual(files["gone.txt"]["hunks"][0]["lines"][-1][0], "note")
        self.assertTrue(files["logo.png"]["binary"])
        self.assertEqual(DIFF.summary(DIFF.parse(SAMPLE_DIFF)), (5, 4, 3))
        self.assertEqual(DIFF._strip_prefix(r'"a/sp\303\251 \"q\".txt"'), 'spé "q".txt')

    def test_tree_merges_single_folders_and_sums(self):
        root = DIFF.tree(DIFF.parse(SAMPLE_DIFF))
        self.assertEqual(list(root["children"]), ["src", "gone.txt", "logo.png", "new name.txt"])
        src = root["children"]["src"]
        self.assertEqual((src["count"], src["added"], src["removed"]), (2, 4, 2))
        self.assertEqual(list(src["children"]), ["views", "app.py"])
        only = DIFF.tree(
            DIFF.parse(
                SAMPLE_DIFF[
                    SAMPLE_DIFF.index("diff --git a/src/views") : SAMPLE_DIFF.index("diff --git a/logo")
                ]
            )
        )
        self.assertEqual(list(only["children"]), ["src/views"])

    def test_inline_span_and_split_pairs(self):
        self.assertEqual(DIFF.changed_span("value = 1", "value = 22"), (8, 9, 10))
        lines = [("ctx", 1, 1, "a"), ("del", 2, None, "b"), ("del", 3, None, "c"), ("add", None, 2, "B")]
        pairs = DIFF.pair_rows(lines)
        self.assertEqual([(l and l[3], r and r[3]) for l, r in pairs], [("a", "a"), ("b", "B"), ("c", None)])

    def test_graph_lanes_for_branch_and_merge(self):
        commits = [
            {"sha": "m", "parents": ["a", "f"]},
            {"sha": "f", "parents": ["b"]},
            {"sha": "a", "parents": ["b"]},
            {"sha": "b", "parents": ["old"]},
        ]
        rows = GRAPH.layout(commits)
        self.assertEqual([r["col"] for r in rows], [0, 1, 0, 0])
        self.assertTrue(rows[0]["merge"])
        self.assertEqual(sorted(rows[0]["bottom"]), [(0, 0), (0, 1)])
        # a's parent b already waits in lane 1 (from f); it folds back into lane 0 below a.
        self.assertIn((1, 0), rows[2]["bottom"])
        self.assertEqual(rows[3]["top"], [(0, 0)])
        self.assertEqual(rows[3]["dangling"], [0])
        self.assertEqual(max(r["width"] for r in rows), 2)


class FakeGitHub(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_):
        pass

    def reply(self, status, body, headers=()):
        raw = json.dumps(body).encode()
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.calls.append(("GET", self.path, self.headers.get("Authorization")))
        if self.headers.get("Authorization") != "Bearer good-token":
            return self.reply(401, {"message": "Bad credentials"})
        path = self.path.split("?")[0]
        if path == "/user":
            return self.reply(200, {"login": "octo", "name": "Octo"}, [("X-OAuth-Scopes", "repo, workflow")])
        if path == "/repos/owner/web":
            return self.reply(
                200,
                {
                    "full_name": "owner/web",
                    "html_url": "https://x/owner/web",
                    "default_branch": "main",
                    "private": True,
                },
            )
        if path.endswith("/releases/latest"):
            return self.reply(404, {"message": "Not Found"})
        if path.endswith("/status"):
            return self.reply(200, {"statuses": [{"state": "success"}]})
        if path.endswith("/check-runs"):
            return self.reply(200, {"check_runs": [{"status": "completed", "conclusion": "failure"}]})
        if path.endswith("/pulls"):
            return self.reply(
                200,
                [
                    {
                        "number": 4,
                        "title": "Feature",
                        "html_url": "u",
                        "user": {"login": "octo"},
                        "head": {"ref": "feat"},
                        "base": {"ref": "main"},
                        "draft": False,
                    }
                ],
            )
        if path.endswith("/issues"):
            return self.reply(
                200,
                [
                    {"number": 5, "title": "Bug", "html_url": "u", "labels": [{"name": "bug"}]},
                    {"number": 4, "title": "Feature", "html_url": "u", "pull_request": {}},
                ],
            )
        self.reply(404, {"message": "Not Found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(("POST", self.path, body))
        self.reply(201, {"number": 9, "html_url": "https://x/pull/9"})


class GitHubClientTests(unittest.TestCase):
    def setUp(self):
        FakeGitHub.calls = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_viewer_overview_and_create(self):
        hub = GitHub("good-token", self.url)
        self.assertEqual(hub.viewer(), {"login": "octo", "name": "Octo", "scopes": "repo, workflow"})
        overview = hub.overview("owner/web")
        self.assertEqual(overview["ref"], "main")
        self.assertIsNone(overview["release"])
        self.assertEqual(overview["checks"]["state"], "failing")
        self.assertEqual([p["head"] for p in overview["pulls"]], ["feat"])
        self.assertEqual([i["number"] for i in overview["issues"]], [5])
        self.assertEqual(hub.create_pull("owner/web", "T", "feat", "main")["number"], 9)
        self.assertEqual(FakeGitHub.calls[-1][2]["head"], "feat")
        with self.assertRaisesRegex(GitHubError, "merge, squash or rebase"):
            hub.merge_pull("owner/web", 9, "force")

    def test_errors_never_echo_the_token(self):
        with self.assertRaises(GitHubError) as caught:
            GitHub("secret-token-value", self.url).viewer()
        self.assertIn("rejected the access token", str(caught.exception))
        self.assertNotIn("secret-token-value", str(caught.exception))
        with self.assertRaisesRegex(GitHubError, "HTTPS"):
            GitHub("t", "http://github.example")
        with self.assertRaisesRegex(GitHubError, "Settings"):
            GitHub("", self.url)

    def test_session_token_store(self):
        tokens = TokenStore("account", persist=False)
        self.assertIsNone(tokens.get())
        self.assertFalse(tokens.set("  abc123  "))
        self.assertEqual(tokens.get(), "abc123")
        with self.assertRaises(GitHubError):
            tokens.set("has space")
        tokens.delete()
        self.assertIsNone(tokens.get())


class CodeSyncTests(unittest.TestCase):
    def setUp(self):
        self.root = BASE / uuid.uuid4().hex
        self.hub = Hub(self.root / "hub", port=0, setup_token="setup").start()
        url = f"http://127.0.0.1:{self.hub.port}"
        self.a = Store(self.root / "a")
        self.a.register("owner", "pw")
        self.sa = Sync(self.a, False)
        self.sa.publish({"url": url, "password": "pw", "setupToken": "setup"})
        self.b = Store(self.root / "b")
        self.sb = Sync(self.b, False)
        self.sb.connect({"url": url, "username": "owner", "password": "pw"}, True)

    def tearDown(self):
        self.a.close()
        self.b.close()
        self.hub.close()

    def test_changeset_diff_reaches_the_other_device(self):
        project = self.a.command("project.save", {"name": "Web"})
        ticket = self.a.command("ticket.save", {"project_id": project["id"], "title": "Work"})
        repo = self.a.command("repo.save", {"project_id": project["id"], "name": "web"})
        self.a.settings({"repoPaths": {repo["id"]: "C:/only/on/a"}})
        diff = "diff --git a/x b/x\n" + "+ünïcode line\n" * 4000
        change = self.a.command(
            "changeset.save", {"repo_id": repo["id"], "ticket_id": ticket["id"], "title": "WIP", "diff": diff}
        )
        for sync in (self.sa, self.sb):
            result = sync.run()
            self.assertTrue(result["connected"], result["error"])
        self.assertEqual(self.b.read("changeset", change["id"])["diff"], diff)
        self.assertEqual(self.b.read("repo", repo["id"])["name"], "web")
        # Checkout folders stay on the device that chose them.
        self.assertNotIn("repoPaths", {k for k, v in self.b.settings().items() if v})
        self.b.command("changeset.save", {"id": change["id"], "diff": diff + "+more\n"})
        for sync in (self.sb, self.sa):
            self.assertTrue(sync.run()["connected"])
        self.assertTrue(self.a.read("changeset", change["id"])["diff"].endswith("+more\n"))


if __name__ == "__main__":
    unittest.main()
