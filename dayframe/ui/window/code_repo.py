"""Code page developer views: working tree, commit history graph and branches.

Each view reads git through CodePage.code_load (cached, loaded in a worker) and changes
the checkout only through CodePage.code_git after a confirmation.
"""

from __future__ import annotations
from datetime import datetime
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..code_dialogs import confirm
from ..theme import CURRENT as C, icon
from ..views.commit_graph import CommitGraph, ref_badges
from ..views.diff_view import ChangeBrowser
from ..widgets import ElidingLabel, ask_text, button, error, label, row

HISTORY_LIMIT = 400
DETAIL_WIDTH = 300


def when(seconds):
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M") if seconds else ""


class CodeRepoViews:
    # Working tree ---------------------------------------------------------------------------

    def show_code_working(self, project, repo, path, entry):
        status = (entry or {}).get("status")
        if not status:
            self.work_layout.addWidget(label("Reading repository…", "muted"))
            self.work_layout.addStretch()
            return
        files = status["files"]
        staged = [f for f in files if f["code"][0] not in ".?"]
        unstaged = [f for f in files if f["code"][1:2] not in (".", "?", "")]
        untracked = [f for f in files if f["code"] == "??"]
        conflicts = [f for f in files if f["code"] == "UU"]
        browser = self.worktree_browser(repo, entry, ("working", repo["id"]), detailed=True)
        self.code_working_browser = browser
        ready = not self.code_busy
        actions = [
            button("Stage", lambda: self.code_index(repo, "stage"), "plus-square"),
            button("Unstage", lambda: self.code_index(repo, "unstage"), "minus-square"),
            button("Discard…", lambda: self.code_index(repo, "discard"), "undo"),
            button(
                "Stage all",
                lambda: self.code_index(repo, "stage", [f["path"] for f in files]),
                "check-double",
            ),
        ]
        actions[0].setToolTip("Stage the selected files or folders (git add)")
        actions[1].setToolTip("Unstage the selected files (git restore --staged)")
        actions[2].setToolTip("Throw away changes to the selected tracked files")
        for widget in actions:
            widget.setEnabled(ready and bool(files))
        commit = button("Commit…", lambda: self.code_commit(repo), "check", True)
        commit.setEnabled(ready and bool(files))
        chips = [
            label(str(len(staged)) + " staged", "count"),
            label(str(len(unstaged)) + " unstaged", "count"),
            label(str(len(untracked)) + " untracked", "count"),
        ]
        if conflicts:
            chips.append(label(str(len(conflicts)) + " conflicts", "warning"))
        self.work_layout.addWidget(row(*chips, None, *actions, commit))
        legend = label(
            "Status shows index then working tree: M· staged, ·M not staged, MM both, ? untracked. "
            "Select files or folders in the tree, then stage, unstage or discard them.",
            "muted",
        )
        legend.setWordWrap(True)
        self.work_layout.addWidget(legend)
        self.work_layout.addWidget(browser, 1)

    def code_index(self, repo, action, paths=None):
        browser = getattr(self, "code_working_browser", None)
        paths = paths if paths is not None else (browser.selected_paths() if browser else [])
        if not paths:
            self.toast.setText("Select files in the tree first")
            return
        if action == "discard":
            entry = self.code_status.get(repo["id"], {})
            codes = {f["path"]: f["code"] for f in (entry.get("status") or {}).get("files", [])}
            tracked = [p for p in paths if codes.get(p) != "??"]
            if not tracked:
                self.toast.setText("Untracked files are left alone; delete them yourself if you mean to.")
                return
            if not confirm(
                self,
                "Discard changes",
                "Throw away all changes to " + str(len(tracked)) + " file(s), staged and unstaged? "
                "This cannot be undone. Save a changeset first if you might want them back.",
                "\n".join(tracked),
                "Discard",
                "Untracked files in the selection are not touched." if len(tracked) < len(paths) else "",
            ):
                return
            self.code_git(repo, "Discarding changes", lambda g: g.discard(tracked))
            return
        title = {"stage": "Staging", "unstage": "Unstaging"}[action]
        self.code_git(repo, title + " " + str(len(paths)) + " file(s)", lambda g: getattr(g, action)(paths))

    # History --------------------------------------------------------------------------------

    def show_code_history(self, project, repo, path, entry):
        loaded = self.code_load(repo, "history", lambda g: g.graph_log(HISTORY_LIMIT), ttl=60)
        if not loaded:
            self.work_layout.addWidget(label("Reading history…", "muted"))
            self.work_layout.addStretch()
            return
        if loaded.get("error"):
            problem = label(loaded["error"], "warning")
            problem.setWordWrap(True)
            self.work_layout.addWidget(problem)
            self.work_layout.addStretch()
            return
        commits = loaded["data"]
        graph = CommitGraph(commits)
        search = QLineEdit()
        search.setPlaceholderText("Filter by message, author, commit or branch…")
        search.setAccessibleName("Filter history")
        search.setClearButtonEnabled(True)
        search.setMaximumWidth(320)

        def apply_filter(text):
            needle = text.casefold().strip()
            for i in range(graph.topLevelItemCount()):
                item = graph.topLevelItem(i)
                commit = item.data(0, Qt.UserRole)
                haystack = " ".join(
                    [commit["subject"], commit["author"], commit["sha"], *commit["refs"]]
                ).casefold()
                item.setHidden(bool(needle) and needle not in haystack)

        search.textChanged.connect(apply_filter)
        merges = sum(len(c["parents"]) > 1 for c in commits)
        authors = len({c["email"] for c in commits})
        more = " (latest %d)" % HISTORY_LIMIT if len(commits) >= HISTORY_LIMIT else ""
        self.work_layout.addWidget(
            row(
                label("History", "section"),
                label(str(len(commits)) + " commits" + more, "count"),
                label(str(merges) + " merges", "count"),
                label(str(authors) + " authors", "count"),
                None,
                search,
                button("Reload", lambda: self.reload_history(repo), "sync-alt"),
            )
        )
        self.work_layout.addWidget(graph, 5)
        detail = QWidget()
        dl = QHBoxLayout(detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        meta = CommitMeta(self, repo)
        browser = ChangeBrowser(self.code_ui.setdefault(("commit", repo["id"]), {}), "Select a commit.")
        dl.addWidget(meta)
        dl.addWidget(browser, 1)
        self.work_layout.addWidget(detail, 6)
        self.code_history_widgets = (meta, browser)

        def selected(item, previous=None):
            if item:
                self.show_commit(repo, item.data(0, Qt.UserRole)["sha"])

        graph.currentItemChanged.connect(selected)
        target = (
            self.code_sha
            if self.code_sha in {c["sha"] for c in commits}
            else (commits[0]["sha"] if commits else None)
        )
        if target:
            graph.select_sha(target)
        meta.jump = lambda sha: graph.select_sha(sha) or self.toast.setText(
            "That commit is outside the loaded history"
        )

    def reload_history(self, repo):
        self.code_cache.pop((repo["id"], "history"), None)
        self.refresh_page()

    def show_commit(self, repo, sha):
        """Fill the commit details in place; load them in the background the first time."""
        self.code_sha = sha
        meta, browser = self.code_history_widgets

        def fill(entry):
            if self.code_sha != sha or self.code_view != "History":
                return
            # Use the widgets of the current page; it may have been rebuilt while this loaded.
            meta, browser = self.code_history_widgets
            try:
                if entry.get("error"):
                    meta.show_error(entry["error"])
                    browser.set_files([])
                else:
                    meta.show_info(entry["data"])
                    browser.set_diff(entry["data"]["diff"], placeholder="This commit changes no files.")
            except RuntimeError:
                pass  # The page was rebuilt while the commit loaded.

        cached = self.code_load(repo, ("commit", sha), lambda g: g.commit_details(sha), ttl=3600, done=fill)
        if cached:
            fill(cached)
        else:
            meta.show_loading(sha)
            browser.set_files([])
            browser.canvas.set_file(None, message="Loading commit…")

    # Branches -------------------------------------------------------------------------------

    def show_code_branches(self, project, repo, path, entry):
        loaded = self.code_load(repo, "refs", lambda g: {"refs": g.refs(), "stashes": g.stashes()}, ttl=30)
        if not loaded:
            self.work_layout.addWidget(label("Reading branches…", "muted"))
            self.work_layout.addStretch()
            return
        if loaded.get("error"):
            self.work_layout.addWidget(label(loaded["error"], "warning"))
            self.work_layout.addStretch()
            return
        refs, stashes = loaded["data"]["refs"], loaded["data"]["stashes"]
        tree = QTreeWidget()
        tree.setObjectName("branchTree")
        tree.setAccessibleName("Branches, tags and stashes")
        columns = ["Name", "Commit", "Tracking", "Ahead / behind", "Updated", "Last commit"]
        tree.setColumnCount(len(columns))
        tree.setHeaderLabels(columns)
        tree.setUniformRowHeights(True)
        tree.setSelectionMode(QAbstractItemView.SingleSelection)
        changesets = {c["id"]: c for c in self.data["changeset"]}
        groups = (
            ("local", "Local branches", "code-branch"),
            ("remote", "Remote branches", "cloud"),
            ("tag", "Tags", "tag"),
        )
        for kind, title, glyph in groups:
            members = [r for r in refs if r["kind"] == kind]
            group = QTreeWidgetItem([title + "  (" + str(len(members)) + ")"])
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            tree.addTopLevelItem(group)
            for ref in members:
                track = ""
                if ref["upstream"]:
                    track = ref["upstream"] + (" (gone)" if ref["gone"] else "")
                counts = (
                    ("↑" + str(ref["ahead"]) + " ↓" + str(ref["behind"]))
                    if ref["upstream"] and not ref["gone"]
                    else ""
                )
                item = QTreeWidgetItem(
                    [
                        ref["name"] + ("  · checked out" if ref["head"] else ""),
                        ref["sha"][:8],
                        track,
                        counts,
                        when(ref["time"]),
                        ref["subject"],
                    ]
                )
                item.setData(0, Qt.UserRole, ref)
                item.setToolTip(5, ref["subject"])
                item.setIcon(0, icon(glyph, C["accent"] if ref["head"] else None))
                if ref["head"]:
                    bold = item.font(0)
                    bold.setBold(True)
                    item.setFont(0, bold)
                    item.setForeground(0, QColor(C["accent"]))
                for column in (1, 4):
                    item.setForeground(column, QColor(C["muted"]))
                group.addChild(item)
            group.setExpanded(kind != "tag" or len(members) <= 20)
        stash_group = QTreeWidgetItem(["Stashes  (" + str(len(stashes)) + ")"])
        font = stash_group.font(0)
        font.setBold(True)
        stash_group.setFont(0, font)
        tree.addTopLevelItem(stash_group)
        for stash in stashes:
            owner = changesets.get(stash["changeset"])
            name = ("DayFrame · " + owner["title"]) if owner else stash["subject"]
            item = QTreeWidgetItem(
                [stash["ref"] + "  " + name, stash["sha"][:8], "", "", when(stash["time"]), stash["subject"]]
            )
            item.setData(0, Qt.UserRole + 1, stash)
            item.setToolTip(0, stash["subject"])
            stash_group.addChild(item)
        stash_group.setExpanded(True)
        header = tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        tree.setColumnWidth(0, 300)
        for column, width in ((1, 80), (2, 170), (3, 100), (4, 118)):
            tree.setColumnWidth(column, width)

        def selected_ref():
            item = tree.currentItem()
            return item.data(0, Qt.UserRole) if item else None

        status = (entry or {}).get("status") or {}
        switch = button(
            "Switch to", lambda: self.branch_action(repo, "switch", selected_ref()), "exchange-alt", True
        )
        create = button(
            "New branch from…", lambda: self.branch_action(repo, "create", selected_ref()), "code-branch"
        )
        delete = button("Delete…", lambda: self.branch_action(repo, "delete", selected_ref()), "trash-alt")
        history = button(
            "Show in history", lambda: self.branch_action(repo, "history", selected_ref()), "stream"
        )
        local = sum(r["kind"] == "local" for r in refs)
        self.work_layout.addWidget(
            row(
                label("Branches", "section"),
                label(str(local) + " local", "count"),
                label(str(sum(r["kind"] == "remote" for r in refs)) + " remote", "count"),
                label(str(sum(r["kind"] == "tag" for r in refs)) + " tags", "count"),
                label("on " + (status.get("branch") or "detached HEAD"), "badge"),
                None,
                switch,
                create,
                delete,
                history,
            )
        )
        self.work_layout.addWidget(tree, 1)
        hint = label(
            "Delete removes only merged local branches (git branch -d). Remote branches, tags and stashes "
            "are shown for reference; DayFrame shelves are named after their changeset.",
            "muted",
        )
        hint.setWordWrap(True)
        self.work_layout.addWidget(hint)

    def branch_action(self, repo, action, ref):
        if not ref:
            self.toast.setText("Select a branch or tag first")
            return
        if action == "history":
            self.code_sha = ref["sha"]
            self.code_view = "History"
            QTimer.singleShot(0, self.refresh_page)
        elif action == "switch":
            if ref["kind"] != "local":
                self.toast.setText("Create a local branch from it with New branch from…")
                return
            self.code_switch_branch(repo, ref["name"])
        elif action == "create":
            suggested = ref["name"].split("/", 1)[1] if ref["kind"] == "remote" else ""
            name = ask_text(self, "New branch", "New branch starting at " + ref["name"], suggested)
            if name:
                self.code_git(repo, "Creating branch " + name, lambda g: g.branch_from(name, ref["name"]))
        elif action == "delete":
            if ref["kind"] != "local" or ref["head"]:
                error(self, "Only local branches that are not checked out can be deleted here.")
                return
            if confirm(
                self,
                "Delete branch",
                "Delete the local branch "
                + ref["name"]
                + "? Git refuses if it has commits that are not merged.",
                "git branch -d " + ref["name"],
                "Delete",
            ):
                self.code_git(repo, "Deleting " + ref["name"], lambda g: g.delete_branch(ref["name"]))


class CommitMeta(QFrame):
    """Commit id, parents, author, refs and full message beside the commit's changes."""

    def __init__(self, window, repo):
        super().__init__()
        self.setObjectName("panel")
        self.setFixedWidth(DETAIL_WIDTH)
        self.window = window
        self.repo = repo
        self.jump = lambda sha: None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        self.sha = ElidingLabel("", "section")
        self.sha.setTextInteractionFlags(Qt.TextSelectableByMouse)
        copy = button("", self.copy_sha, "copy")
        copy.setToolTip("Copy the commit id")
        copy.setAccessibleName("Copy commit id")
        web = button("", self.open_web, "external-link-alt")
        web.setToolTip("Open the commit on GitHub")
        web.setVisible(bool(repo["github_repo"]))
        for small in (copy, web):
            small.setFixedWidth(30)
        sha_row = row(self.sha, copy, web)
        sha_row.layout().setStretchFactor(self.sha, 1)
        layout.addWidget(sha_row)
        self.refs = label("", "muted")
        self.refs.setWordWrap(True)
        layout.addWidget(self.refs)
        self.facts = label("", "muted")
        self.facts.setWordWrap(True)
        self.facts.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.facts)
        self.parents = QHBoxLayout()
        self.parents.setSpacing(4)
        layout.addLayout(self.parents)
        self.message = QPlainTextEdit()
        self.message.setReadOnly(True)
        self.message.setAccessibleName("Commit message")
        layout.addWidget(self.message, 1)
        self.current = None

    def copy_sha(self):
        if self.current:
            QGuiApplication.clipboard().setText(self.current["sha"])
            self.window.toast.setText("Copied " + self.current["sha"][:10])

    def open_web(self):
        if self.current and self.repo["github_repo"]:
            QDesktopServices.openUrl(
                QUrl("https://github.com/" + self.repo["github_repo"] + "/commit/" + self.current["sha"])
            )

    def clear_parents(self):
        while self.parents.count():
            widget = self.parents.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    def show_loading(self, sha):
        self.current = None
        self.sha.setText(sha[:12])
        self.refs.setText("")
        self.facts.setText("Loading…")
        self.clear_parents()
        self.message.setPlainText("")

    def show_error(self, message):
        self.facts.setText(message)

    def show_info(self, info):
        self.current = info
        self.sha.setText(info["sha"])
        self.refs.setText(" · ".join(text for text, _ in ref_badges(info["refs"])))
        self.refs.setVisible(bool(info["refs"]))
        lines = ["Author: " + info["author"] + " <" + info["email"] + ">", "Date: " + when(info["time"])]
        if info["committer"] != info["author"] or abs(info["commit_time"] - info["time"]) > 60:
            lines.append("Committed: " + info["committer"] + ", " + when(info["commit_time"]))
        lines.append(
            "Merge commit" if len(info["parents"]) > 1 else "Root commit" if not info["parents"] else ""
        )
        self.facts.setText("\n".join(line for line in lines if line))
        self.clear_parents()
        if info["parents"]:
            self.parents.addWidget(label("Parents", "muted"))
            for parent in info["parents"]:
                link = button(parent[:8], lambda checked=False, sha=parent: self.jump(sha))
                link.setObjectName("rowTitle")
                link.setToolTip("Show parent " + parent)
                self.parents.addWidget(link)
            self.parents.addStretch()
        self.message.setPlainText(info["message"])
