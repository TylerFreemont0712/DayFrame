"""Code page: per-project repositories, ticket changesets, git actions and GitHub.

Git and GitHub calls are blocking, so they always run through run_async. Results come
back on the GUI thread, where records are saved with execute() as everywhere else.
Status and GitHub data are cached per repository and reloaded on demand, after every
git action and when they are older than STATUS_TTL seconds.
"""

from __future__ import annotations
import time
import uuid
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSplitter,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
)
from ...code import git as G
from ...code.github import API_URL, GitHub, TokenStore
from ...core import domain as D
from ..code_dialogs import (
    CommitDialog,
    IssueDialog,
    MergeDialog,
    PullRequestDialog,
    RepoDialog,
    SwitchDialog,
    confirm,
)
from ..theme import CURRENT as C, icon
from ..views.diff_view import DiffView
from ..views.kanban import project_color
from ..widgets import ElidingLabel, ask_text, button, column, error, label, panel, row

STATUS_TTL = 20
WORKTREE = "worktree"


def ago(ms):
    if not ms:
        return ""
    minutes = int((time.time() * 1000 - ms) // 60000)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return str(minutes) + "m ago"
    if minutes < 48 * 60:
        return str(minutes // 60) + "h ago"
    return str(minutes // 1440) + "d ago"


class CodePage:
    # State ----------------------------------------------------------------------------------

    def code_state(self):
        if not hasattr(self, "code_status"):
            self.code_project = None
            self.code_ticket = None
            self.code_item = None
            self.code_view = "Changes"
            self.code_show_done = False
            self.code_status = {}
            self.code_diffs = {}
            self.code_github = {}
            self.code_loading = set()
            self.code_busy = None

    def code_path(self, repo):
        return self.data["settings"].get("repoPaths", {}).get(repo["id"], "")

    def applied_changeset(self, repo):
        changeset_id = self.data["settings"].get("activeChangesets", {}).get(repo["id"], "")
        return next(
            (c for c in self.data["changeset"] if c["id"] == changeset_id and not c["archived"]), None
        )

    def github_token(self):
        """The GitHub token for this account, read once per session from the keyring."""
        account = self.data["account"]["id"]
        if getattr(self, "_github_account", None) != account:
            self._github_account = account
            self.github_tokens = TokenStore(account, persist=getattr(self.sync, "persist_tokens", True))
            self._github_token = self.github_tokens.get()
        return self._github_token

    def set_github_token(self, token):
        self.github_token()
        self._github_token = token
        self.code_state()
        self.code_github.clear()

    def github_client(self):
        return GitHub(self.github_token(), self.data["settings"].get("githubApiUrl") or API_URL)

    # Navigation -----------------------------------------------------------------------------

    def open_code(self, ticket_id=None, project_id=None):
        """Show the Code page for a ticket (or project), from any other view."""
        if not self.leave_editor():
            return
        self.code_state()
        ticket = self.find_ticket(ticket_id) if ticket_id else None
        self.code_project = ticket["project_id"] if ticket else project_id or self.code_project
        self.code_ticket = ticket["id"] if ticket else None
        self.code_item = None
        self.code_view = "Changes"
        self.page = "Code"
        self.selected = None
        self.refresh_page()

    def code_context(self):
        self.code_state()
        l = self.context_layout
        l.addWidget(row(label("CODE", "section"), None, button("", self.toggle_context, "angle-double-left")))
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setIndentation(0)
        tree.setObjectName("projectTree")
        tree.setAccessibleName("Projects with code")
        for p in self.data["project"]:
            if p["archived"]:
                continue
            repo = self.code_repo(p["id"])
            item = QTreeWidgetItem([p["name"]])
            glyph = "code-branch" if repo else "folder"
            item.setIcon(0, icon(glyph, project_color(p["id"]).name() if repo else None))
            item.setToolTip(
                0, (repo["name"] + " · " + repo["provider"]) if repo else "No repository connected"
            )
            item.setData(0, Qt.UserRole, p["id"])
            tree.addTopLevelItem(item)
            if p["id"] == self.code_project:
                item.setSelected(True)
        tree.itemClicked.connect(lambda item: self.choose_code_project(item.data(0, Qt.UserRole)))
        l.addWidget(tree, 1)
        user = self.data["settings"].get("githubUser", "")
        status = label("GitHub: " + (user if user and self.github_token() else "not connected"), "muted")
        status.setWordWrap(True)
        l.addWidget(status)
        l.addWidget(button("GitHub settings", self.open_github_settings, "cog"))

    def choose_code_project(self, project_id):
        self.code_project = project_id
        self.code_ticket = None
        self.code_item = None
        self.refresh_page()

    def open_github_settings(self):
        self.settings_section = "sync"
        self.navigate("Settings")

    # Page -----------------------------------------------------------------------------------

    def show_code(self):
        self.code_state()
        projects = [p for p in self.data["project"] if not p["archived"]]
        if not projects:
            empty, l = panel("No projects yet")
            l.addWidget(label("Create a project, then connect its repository here.", "muted"))
            l.addWidget(row(button("Go to Projects", lambda: self.navigate("Projects"), "layer-group"), None))
            self.work_layout.addWidget(empty)
            self.work_layout.addStretch()
            return
        if self.code_project not in [p["id"] for p in projects]:
            self.code_project = (
                self.project_id if self.project_id in [p["id"] for p in projects] else projects[0]["id"]
            )
        project = next(p for p in projects if p["id"] == self.code_project)
        self.page_header.layout().insertWidget(1, label(project["name"], "muted"))
        repo = self.code_repo(project["id"])
        if not repo:
            self.show_code_connect(project)
            return
        views = ["Changes", "GitHub"]
        tabs = QTabBar()
        tabs.setExpanding(False)
        for view in views:
            tabs.addTab(view)
        tabs.setCurrentIndex(views.index(self.code_view) if self.code_view in views else 0)
        tabs.currentChanged.connect(lambda index: self.change_code_view(views[index]))
        self.page_header.layout().addWidget(tabs)
        if repo["provider"] != "git":
            box, l = panel("Subversion · planned")
            l.addWidget(label("Subversion shelves are planned. Git is available today.", "muted"))
            l.addWidget(row(button("Edit connection", lambda: self.edit_repo(project, repo), "cog"), None))
            self.work_layout.addWidget(box)
            self.work_layout.addStretch()
            return
        path = self.code_path(repo)
        entry = self.code_status.get(repo["id"])
        if path and repo["id"] not in self.code_loading:
            if not entry or entry["path"] != path or time.monotonic() - entry["at"] > STATUS_TTL:
                self.load_code_status(repo)
        self.work_layout.addWidget(self.code_toolbar(project, repo, path, entry))
        if self.code_view == "GitHub":
            self.show_code_github(project, repo, entry)
        else:
            self.show_code_changes(project, repo, path, entry)

    def change_code_view(self, view):
        self.code_view = view
        QTimer.singleShot(0, self.refresh_page)

    def show_code_connect(self, project):
        box, l = panel("Connect version control")
        text = label(
            "Choose how " + project["name"] + " is versioned and where its checkout lives on this "
            "device. Tickets in the project can then keep their own shelved changes.",
            "muted",
        )
        text.setWordWrap(True)
        l.addWidget(text)
        l.addWidget(
            row(button("Connect Git repository", lambda: self.edit_repo(project), "code-branch", True), None)
        )
        l.addWidget(label("Subversion support is planned.", "muted"))
        self.work_layout.addWidget(box)
        self.work_layout.addStretch()

    def edit_repo(self, project, repo=None):
        d = RepoDialog(self, project, repo, self.code_path(repo) if repo else "")
        if d.exec() != QDialog.Accepted:
            return
        payload = d.payload()
        saved = self.execute(
            "repo.save",
            {**({"id": repo["id"]} if repo else {"project_id": project["id"]}), **payload},
            refresh=False,
        )
        if not saved:
            return
        paths = dict(self.data["settings"].get("repoPaths", {}))
        folder = d.path.text().strip()
        if folder:
            paths[saved["id"]] = folder
        else:
            paths.pop(saved["id"], None)
        self.execute("settings.save", {"repoPaths": paths}, refresh=False)
        self.code_status.pop(saved["id"], None)
        self.refresh_page()

    def disconnect_repo(self, repo):
        if confirm(
            self,
            "Disconnect repository",
            "Disconnect " + repo["name"] + " from this project? Changesets stay stored and come back if "
            "you reconnect it. Nothing in the checkout folder changes.",
            action="Disconnect",
        ):
            if self.execute("repo.save", {"id": repo["id"], "archived": 1}):
                self.undo_action = lambda: self.execute("repo.save", {"id": repo["id"], "archived": 0})
                self.toast.setText("Repository disconnected · Ctrl+Z to undo")

    # Status and toolbar ---------------------------------------------------------------------

    def load_code_status(self, repo):
        path = self.code_path(repo)
        self.code_loading.add(repo["id"])

        def work():
            try:
                repository = G.GitRepo(path)
                if not repository.is_repository():
                    return {"error": "That folder is not a git checkout: " + path}
                return {
                    "status": repository.status(),
                    "branches": repository.branches(),
                    "default": repository.default_branch(),
                }
            except Exception as exc:
                return {"error": str(exc)}

        def done(result):
            self.code_loading.discard(repo["id"])
            self.code_status[repo["id"]] = {**result, "path": path, "at": time.monotonic()}
            self.code_diffs.pop(repo["id"], None)
            if self.page == "Code" and self.code_project == repo["project_id"]:
                QTimer.singleShot(0, self.refresh_page)

        self.run_async(work, done)

    def code_toolbar(self, project, repo, path, entry):
        box, l = panel()
        status = (entry or {}).get("status")
        title = label(repo["name"], "section")
        info = []
        if status:
            info.append(status["branch"] or "detached HEAD")
            if status["upstream"]:
                info.append(
                    "↑" + str(status["ahead"]) + " ↓" + str(status["behind"]) + " " + status["upstream"]
                )
            else:
                info.append("not pushed yet" if status["branch"] else "")
            info.append(str(len(status["files"])) + " changed" if status["files"] else "clean")
        elif path and repo["id"] in self.code_loading:
            info.append("Reading repository…")
        branch = ElidingLabel(" · ".join(x for x in info if x), "badge")
        branch.setMaximumWidth(420)
        manage = button("", None, "cog")
        manage.setToolTip("Repository settings")
        manage.setAccessibleName("Repository settings")
        menu = QMenu(self)
        menu.addAction(icon("cog"), "Edit connection…", lambda: self.edit_repo(project, repo))
        if path:
            menu.addAction(
                icon("folder-open"),
                "Open checkout folder",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)),
            )
        if repo["github_repo"]:
            menu.addAction(
                icon("external-link-alt"),
                "Open on GitHub",
                lambda: QDesktopServices.openUrl(QUrl("https://github.com/" + repo["github_repo"])),
            )
        menu.addSeparator()
        menu.addAction(icon("unlink"), "Disconnect repository…", lambda: self.disconnect_repo(repo))
        manage.setMenu(menu)
        l.addWidget(row(icon_label("code-branch"), title, branch, None, manage))
        if not path:
            hint = label("Choose this device's checkout folder to see changes and run git.", "warning")
            hint.setWordWrap(True)
            l.addWidget(
                row(
                    hint,
                    None,
                    button("Choose folder", lambda: self.edit_repo(project, repo), "folder-open", True),
                )
            )
            return box
        if entry and entry.get("error"):
            problem = label(entry["error"], "warning")
            problem.setWordWrap(True)
            l.addWidget(problem)
        actions = [
            button("Refresh", lambda: self.refresh_code(repo), "sync-alt"),
            button(
                "Fetch", lambda: self.code_git(repo, "Fetching", lambda g: g.fetch()), "cloud-download-alt"
            ),
            button("Pull…", lambda: self.code_pull(repo), "arrow-down"),
            button("Commit…", lambda: self.code_commit(repo), "check"),
            button("Push…", lambda: self.code_push(repo), "arrow-up"),
        ]
        branches = button("Branch", None, "code-branch")
        branch_menu = QMenu(self)
        ticket = self.find_ticket(self.code_ticket) if self.code_ticket else None
        if ticket:
            suggested = self.ticket_branch(ticket)
            if suggested not in (entry or {}).get("branches", []):
                branch_menu.addAction(
                    "New branch " + suggested + "…", lambda: self.code_new_branch(repo, suggested)
                )
        branch_menu.addAction("New branch…", lambda: self.code_new_branch(repo, ""))
        switch = branch_menu.addMenu("Switch to")
        for name in (entry or {}).get("branches", []):
            action = switch.addAction(name, lambda n=name: self.code_switch_branch(repo, n))
            action.setEnabled(not status or name != status["branch"])
        switch.setEnabled(bool((entry or {}).get("branches")))
        branches.setMenu(branch_menu)
        actions.append(branches)
        for widget in actions[1:]:
            widget.setEnabled(bool(status) and not self.code_busy)
        l.addWidget(row(*actions, None))
        return box

    def refresh_code(self, repo):
        self.code_status.pop(repo["id"], None)
        self.code_diffs.pop(repo["id"], None)
        self.code_github.pop(repo["id"], None)
        self.refresh_page()

    def ticket_branch(self, ticket):
        project = next((p for p in self.data["project"] if p["id"] == ticket["project_id"]), {})
        return G.branch_name(project.get("project_key", "T"), ticket["id"], ticket["title"])

    # Running git ----------------------------------------------------------------------------

    def code_git(self, repo, title, fn, done=None):
        """Run fn(GitRepo) in a worker; report errors, then reload the repository status."""
        path = self.code_path(repo)
        if not path:
            return
        if self.code_busy:
            self.toast.setText(self.code_busy + "… still running")
            return
        self.code_busy = title
        self.toast.setText(title + "…")

        def work():
            try:
                return {"ok": fn(G.GitRepo(path))}
            except Exception as exc:
                return {"error": str(exc)}

        def finished(result):
            self.code_busy = None
            self.code_status.pop(repo["id"], None)
            self.code_diffs.pop(repo["id"], None)
            if "error" in result:
                self.toast.setText(title + " failed")
                error(self, result["error"])
            else:
                self.toast.setText(title + " · done")
                if done:
                    done(result["ok"])
            if self.page == "Code":
                self.refresh_page()

        self.run_async(work, finished)

    def code_pull(self, repo):
        status = self.code_status.get(repo["id"], {}).get("status")
        if not status:
            return
        if not status["upstream"]:
            error(self, "This branch does not track a remote branch yet. Push it first.")
            return
        if confirm(
            self,
            "Pull",
            "Bring " + status["upstream"] + " into " + status["branch"] + ".",
            "git pull --ff-only",
            "Pull",
            ""
            if not status["ahead"]
            else "You also have local commits; if the branches have diverged the pull stops without changing anything.",
        ):
            self.code_git(repo, "Pulling", lambda g: g.pull())

    def code_push(self, repo):
        def check(g):
            return g.status(), g.outgoing()

        def review(result):
            status, commits = result
            if not status["branch"]:
                error(self, "Switch to a branch before pushing.")
                return
            if status["behind"]:
                error(self, "The remote branch has commits you do not have. Pull first.")
                return
            if status["upstream"] and not commits:
                self.toast.setText("Nothing to push")
                return
            target = status["upstream"] or "origin/" + status["branch"] + " (new remote branch)"
            default = repo["default_branch"] or self.code_status.get(repo["id"], {}).get("default", "")
            details = "\n".join(c["sha"] + "  " + c["subject"] for c in commits) or "(no new commits)"
            command = (
                "git push" if status["upstream"] else "git push --set-upstream origin " + status["branch"]
            )
            warning = "This pushes straight to the default branch." if status["branch"] == default else ""
            if confirm(
                self,
                "Push",
                "Push "
                + str(len(commits))
                + " commit(s) from "
                + status["branch"]
                + " to "
                + target
                + "?\n"
                + command,
                details,
                "Push",
                warning,
            ):
                self.code_git(repo, "Pushing", lambda g: g.push())

        self.code_git(repo, "Checking outgoing commits", check, review)

    def code_commit(self, repo):
        entry = self.code_status.get(repo["id"], {})
        status = entry.get("status")
        if not status or not status["files"]:
            self.toast.setText("Nothing to commit")
            return
        ticket = self.find_ticket(self.code_ticket) if self.code_ticket else None
        message = (self.ticket_key(ticket).replace(" · ", "-") + ": " + ticket["title"]) if ticket else ""
        applied = self.applied_changeset(repo)
        d = CommitDialog(self, status, message, repo["default_branch"] or entry.get("default", ""), applied)
        if d.exec() != QDialog.Accepted:
            return
        text, paths = d.message.toPlainText().strip(), d.paths()
        archive, push = d.archive.isChecked() and applied, d.push_after.isChecked()

        def committed(sha):
            if archive:
                self.execute("changeset.save", {"id": applied["id"], "archived": 1}, refresh=False)
                self.set_applied(repo, "")
            self.toast.setText("Committed " + sha)
            if push:
                QTimer.singleShot(0, lambda: self.code_push(repo))

        self.code_git(repo, "Committing", lambda g: g.commit(text, paths), committed)

    def code_new_branch(self, repo, suggested):
        name = ask_text(self, "New branch", "Branch name (starts from the current commit)", suggested)
        if name:
            self.code_git(repo, "Creating branch " + name, lambda g: g.switch(name, create=True))

    def code_switch_branch(self, repo, name):
        status = self.code_status.get(repo["id"], {}).get("status") or {"files": []}
        warning = (
            "Uncommitted changes come along to the other branch; git refuses the switch if they conflict."
            if status["files"]
            else ""
        )
        if confirm(
            self,
            "Switch branch",
            "Switch the checkout to " + name + "?",
            "git switch " + name,
            "Switch",
            warning,
        ):
            self.code_git(repo, "Switching to " + name, lambda g: g.switch(name))

    def set_applied(self, repo, changeset_id):
        active = dict(self.data["settings"].get("activeChangesets", {}))
        if changeset_id:
            active[repo["id"]] = changeset_id
        else:
            active.pop(repo["id"], None)
        self.execute("settings.save", {"activeChangesets": active}, refresh=False)

    # Changes view ---------------------------------------------------------------------------

    def show_code_changes(self, project, repo, path, entry):
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(3)
        split.setChildrenCollapsible(False)
        left, ll = column(spacing=4)
        left.setMinimumWidth(200)
        done_toggle = QCheckBox("Show completed")
        done_toggle.setChecked(self.code_show_done)
        done_toggle.toggled.connect(self.toggle_code_done)
        ll.addWidget(row(label("Tickets", "section"), None, done_toggle))
        tickets = QListWidget()
        tickets.setObjectName("codeTickets")
        tickets.setAccessibleName("Tickets in " + project["name"])
        tickets.setWordWrap(True)
        applied = self.applied_changeset(repo)
        for t in self.data["ticket"]:
            if t["project_id"] != project["id"] or t["archived"]:
                continue
            if t["status"] == "done" and not self.code_show_done and t["id"] != self.code_ticket:
                continue
            count = self.changeset_count(t["id"])
            detail = D.STATUS_NAMES[t["status"]] + (
                " · " + str(count) + " changeset" + ("s" if count != 1 else "") if count else ""
            )
            if applied and applied["ticket_id"] == t["id"]:
                detail += " · applied here"
            item = QListWidgetItem(self.ticket_key(t) + "  " + t["title"] + "\n" + detail)
            item.setData(Qt.UserRole, t["id"])
            item.setToolTip(t["title"])
            if count:
                item.setIcon(icon("layer-group", C["accent"]))
            tickets.addItem(item)
            if t["id"] == self.code_ticket:
                item.setSelected(True)
                tickets.setCurrentItem(item)
        if not tickets.count():
            ll.addWidget(label("No open tickets in this project.", "muted"))
        tickets.itemClicked.connect(lambda item: self.choose_code_ticket(item.data(Qt.UserRole)))
        ll.addWidget(tickets, 1)
        split.addWidget(left)
        right, rl = column(spacing=5)
        ticket = self.find_ticket(self.code_ticket) if self.code_ticket else None
        if ticket and ticket["project_id"] == project["id"]:
            self.show_ticket_changes(rl, repo, ticket, entry)
        else:
            self.code_ticket = None
            empty, el = panel("Choose a ticket")
            text = label(
                "Each ticket keeps its own changesets: shelved working-tree changes with their diff, "
                "stored in DayFrame and synced to your other devices. Switching restores a ticket's "
                "files into the checkout.",
                "muted",
            )
            text.setWordWrap(True)
            el.addWidget(text)
            rl.addWidget(empty)
            rl.addWidget(self.diff_panel(repo, WORKTREE, entry), 1)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 700])
        self.work_layout.addWidget(split, 1)
        hint = label(
            "Push, pull and fetch use git's own credentials (for example Git Credential Manager). "
            "DayFrame never force-pushes and pulls only fast-forward.",
            "muted",
        )
        hint.setWordWrap(True)
        self.work_layout.addWidget(hint)

    def toggle_code_done(self, checked):
        self.code_show_done = checked
        QTimer.singleShot(0, self.refresh_page)

    def choose_code_ticket(self, ticket_id):
        self.code_ticket = ticket_id
        self.code_item = None
        QTimer.singleShot(0, self.refresh_page)

    def ticket_changesets(self, ticket_id):
        return sorted(
            (c for c in self.data["changeset"] if c["ticket_id"] == ticket_id and not c["archived"]),
            key=lambda c: -c["updated_at"],
        )

    def show_ticket_changes(self, rl, repo, ticket, entry):
        status = (entry or {}).get("status")
        branches = (entry or {}).get("branches", [])
        header = row(
            label(self.ticket_key(ticket), "badge"),
            ElidingLabel(ticket["title"], "section"),
            None,
            button("Open ticket", lambda: self.open_ticket(ticket["id"]), "external-link-alt"),
        )
        rl.addWidget(header)
        suggested = self.ticket_branch(ticket)
        if status:
            if status["branch"] == suggested:
                branch_row = row(label("On the ticket branch " + suggested, "muted"), None)
            elif suggested in branches:
                branch_row = row(
                    label("Ticket branch " + suggested, "muted"),
                    None,
                    button("Switch to it", lambda: self.code_switch_branch(repo, suggested), "code-branch"),
                )
            else:
                branch_row = row(
                    label("No ticket branch yet", "muted"),
                    None,
                    button(
                        "Create " + suggested, lambda: self.code_new_branch(repo, suggested), "code-branch"
                    ),
                )
            rl.addWidget(branch_row)
        changesets = self.ticket_changesets(ticket["id"])
        applied = self.applied_changeset(repo)
        ids = [c["id"] for c in changesets]
        if self.code_item not in [WORKTREE, *ids]:
            self.code_item = applied["id"] if applied and applied["id"] in ids else WORKTREE
        items = QListWidget()
        items.setObjectName("changesets")
        items.setAccessibleName("Changesets")
        files = len(status["files"]) if status else 0
        worktree = QListWidgetItem(
            icon("pen", C["accent"] if files else None),
            "Working tree · "
            + (str(files) + " uncommitted file(s)" if files else "clean" if status else "not loaded"),
        )
        worktree.setData(Qt.UserRole, WORKTREE)
        items.addItem(worktree)
        for c in changesets:
            here = applied and applied["id"] == c["id"]
            parts = [c["stat"] or "stored diff", c["branch"], ago(c["updated_at"])]
            item = QListWidgetItem(
                icon("layer-group", C["accent"] if here else None),
                c["title"] + ("  · applied here" if here else "") + "\n" + " · ".join(p for p in parts if p),
            )
            item.setData(Qt.UserRole, c["id"])
            item.setToolTip("Based on " + (c["base_commit"][:10] or "unknown commit"))
            items.addItem(item)
        for i in range(items.count()):
            if items.item(i).data(Qt.UserRole) == self.code_item:
                items.setCurrentRow(i)
        items.setMaximumHeight(min(190, 30 + items.count() * 40))
        items.itemClicked.connect(lambda item: self.choose_code_item(item.data(Qt.UserRole)))
        rl.addWidget(row(label("Changesets", "section"), label(str(len(changesets)), "count"), None))
        rl.addWidget(items)
        selected = next((c for c in changesets if c["id"] == self.code_item), None)
        ready = bool(status) and not self.code_busy
        new = button("New changeset", lambda: self.code_capture(repo, ticket, None, keep=True), "plus")
        new.setToolTip("Save the working tree as a new changeset for this ticket and keep working")
        new.setEnabled(ready and bool(files))
        save = button(
            "Save to selected", lambda: self.code_capture(repo, ticket, selected, keep=True), "save"
        )
        save.setToolTip("Replace the selected changeset's diff with the working tree and keep working")
        save.setEnabled(ready and bool(files) and bool(selected))
        shelve = button("Shelve", lambda: self.code_shelve(repo, ticket), "archive")
        shelve.setToolTip(
            "Save the working tree into the applied changeset (or a new one) and clean the checkout"
        )
        shelve.setEnabled(ready and bool(files))
        switch = button("Switch to", lambda: self.code_switch(repo, ticket, selected), "exchange-alt", True)
        switch.setToolTip("Restore the selected changeset's files into the checkout")
        switch.setEnabled(
            ready
            and bool(selected)
            and not (applied and selected and applied["id"] == selected["id"] and files)
        )
        remove = button("", lambda: self.code_delete(repo, selected), "trash-alt")
        remove.setToolTip("Delete the selected changeset")
        remove.setAccessibleName("Delete changeset")
        remove.setEnabled(bool(selected))
        rl.addWidget(row(new, save, shelve, switch, None, remove))
        rl.addWidget(self.diff_panel(repo, self.code_item, entry, selected), 1)

    def choose_code_item(self, item_id):
        self.code_item = item_id
        QTimer.singleShot(0, self.refresh_page)

    def diff_panel(self, repo, item, entry, changeset=None):
        view = DiffView()
        if item == WORKTREE:
            if repo["id"] in self.code_diffs:
                view.show_diff(self.code_diffs[repo["id"]])
                view.setPlaceholderText("The working tree is clean.")
            elif (entry or {}).get("status"):
                view.setPlaceholderText("Reading the working tree…")
                self.load_worktree_diff(repo)
            else:
                view.setPlaceholderText("Choose a checkout folder to see uncommitted changes.")
        elif changeset:
            record = self.store.read("changeset", changeset["id"])
            if record and record["diff"]:
                view.show_diff(record["diff"])
            else:
                view.setPlaceholderText(
                    "This changeset's diff was too large to store. It can be restored on the device "
                    "that shelved it, from that device's git stash."
                )
        return view

    def load_worktree_diff(self, repo):
        key = ("diff", repo["id"])
        if key in self.code_loading:
            return
        self.code_loading.add(key)
        path = self.code_path(repo)

        def work():
            try:
                return G.GitRepo(path).working_diff()
            except Exception as exc:
                return "Could not read the working tree: " + str(exc)

        def done(text):
            self.code_loading.discard(key)
            self.code_diffs[repo["id"]] = text
            if self.page == "Code" and self.code_view == "Changes":
                QTimer.singleShot(0, self.refresh_page)

        self.run_async(work, done)

    # Changeset actions ----------------------------------------------------------------------

    def changeset_payload(self, repo, ticket, changeset_id, title, captured):
        payload = {
            "id": changeset_id,
            "repo_id": repo["id"],
            "ticket_id": ticket["id"],
            "title": title,
            "branch": captured["branch"],
            "base_commit": captured["base_commit"],
            "diff": captured["diff"],
            "stat": captured["stat"],
            "updated_at": int(time.time() * 1000),
        }
        if D.diff_size(captured["diff"]) > D.MAX_DIFF_BYTES:
            # Keep the record so the ticket shows the work; the local stash still has the files.
            payload["diff"] = ""
            payload["stat"] = (captured["stat"] + " · too large to sync, kept in this device's git stash")[
                :500
            ]
        return payload

    def code_capture(self, repo, ticket, changeset, keep=True):
        """Save the working tree into a changeset (new or existing)."""
        if changeset is None:
            count = len(self.ticket_changesets(ticket["id"]))
            title = ask_text(
                self,
                "New changeset",
                "Changeset name",
                ticket["title"] + (" #" + str(count + 1) if count else ""),
            )
            if not title:
                return
            changeset_id = str(uuid.uuid4())
        else:
            if not confirm(
                self,
                "Save to changeset",
                "Replace the stored diff of “" + changeset["title"] + "” with the current working tree?",
                action="Save",
            ):
                return
            title, changeset_id = changeset["title"], changeset["id"]

        def saved(captured):
            if self.execute(
                "changeset.save",
                self.changeset_payload(repo, ticket, changeset_id, title, captured),
                refresh=False,
            ):
                self.set_applied(repo, changeset_id if keep else "")
                self.code_item = changeset_id

        self.code_git(repo, "Saving changes", lambda g: g.shelve(changeset_id, title, keep=keep), saved)

    def code_shelve(self, repo, ticket):
        applied = self.applied_changeset(repo)
        target = applied if applied else None
        owner = self.find_ticket(applied["ticket_id"]) if applied else ticket
        title = applied["title"] if applied else ticket["title"]
        if not confirm(
            self,
            "Shelve changes",
            "Save the working tree into "
            + (
                "the applied changeset “" + title + "”"
                if applied
                else "a new changeset for " + self.ticket_key(ticket)
            )
            + " and clean the checkout?",
            "git stash push --include-untracked",
            "Shelve",
        ):
            return
        changeset_id = target["id"] if target else str(uuid.uuid4())

        def saved(captured):
            if self.execute(
                "changeset.save",
                self.changeset_payload(repo, owner, changeset_id, title, captured),
                refresh=False,
            ):
                self.set_applied(repo, "")
                self.code_item = changeset_id

        self.code_git(repo, "Shelving", lambda g: g.shelve(changeset_id, title), saved)

    def code_switch(self, repo, ticket, changeset):
        entry = self.code_status.get(repo["id"], {})
        status = entry.get("status")
        if not changeset or not status:
            return
        applied = self.applied_changeset(repo)
        owner = self.find_ticket(applied["ticket_id"]) if applied else ticket
        into = ("“" + applied["title"] + "”") if applied else "a new changeset for " + self.ticket_key(ticket)
        d = SwitchDialog(self, changeset, status, into, entry.get("branches", []))
        if d.exec() != QDialog.Accepted:
            return
        record = self.store.read("changeset", changeset["id"])
        shelve_id = applied["id"] if applied else str(uuid.uuid4())
        shelve_title = applied["title"] if applied else ticket["title"]
        dirty, switch_branch = bool(status["files"]), d.switch_branch.isChecked()

        def work(g):
            result = {"captured": None, "error": None, "outcome": None}
            try:
                if dirty:
                    result["captured"] = g.shelve(shelve_id, shelve_title)
                if switch_branch:
                    g.switch(record["branch"])
                result["outcome"] = g.restore(record)
            except Exception as exc:
                result["error"] = str(exc)
            return result

        def finished(result):
            # Shelved work is saved even when the restore afterwards failed.
            if result["captured"]:
                self.execute(
                    "changeset.save",
                    self.changeset_payload(repo, owner, shelve_id, shelve_title, result["captured"]),
                    refresh=False,
                )
                self.set_applied(repo, "")
            if result["error"]:
                error(self, result["error"])
                return
            self.set_applied(repo, changeset["id"])
            self.code_item = changeset["id"]
            message = {
                "applied": "Switched to " + changeset["title"],
                "merged": "Switched to " + changeset["title"] + " with a three-way merge",
                "conflicts": "Applied "
                + changeset["title"]
                + " with conflicts; resolve them before committing",
            }[result["outcome"]]
            QTimer.singleShot(0, lambda: self.toast.setText(message))

        self.code_git(repo, "Switching changes", work, finished)

    def code_delete(self, repo, changeset):
        if not changeset or not confirm(
            self,
            "Delete changeset",
            "Delete “" + changeset["title"] + "”? Its stored diff is kept with the archived record and "
            "Ctrl+Z restores it. The checkout and git stash do not change.",
            action="Delete",
        ):
            return
        if self.execute("changeset.save", {"id": changeset["id"], "archived": 1}, refresh=False):
            if self.applied_changeset(repo) and self.applied_changeset(repo)["id"] == changeset["id"]:
                self.set_applied(repo, "")
            self.code_item = None
            self.undo_action = lambda: self.execute("changeset.save", {"id": changeset["id"], "archived": 0})
            self.refresh_page()
            self.toast.setText("Changeset deleted · Ctrl+Z to undo")

    # GitHub view ----------------------------------------------------------------------------

    def show_code_github(self, project, repo, entry):
        if not self.github_token():
            box, l = panel("Connect GitHub")
            text = label(
                "Add a GitHub access token in Settings > Sync to see pull requests, issues, checks and "
                "releases, and to open pull requests from here.",
                "muted",
            )
            text.setWordWrap(True)
            l.addWidget(text)
            l.addWidget(row(button("Open GitHub settings", self.open_github_settings, "cog", True), None))
            self.work_layout.addWidget(box)
            self.work_layout.addStretch()
            return
        if not repo["github_repo"]:
            box, l = panel("GitHub repository not set")
            l.addWidget(label("Set the GitHub repository (owner/name) in the connection settings.", "muted"))
            l.addWidget(
                row(button("Edit connection", lambda: self.edit_repo(project, repo), "cog", True), None)
            )
            self.work_layout.addWidget(box)
            self.work_layout.addStretch()
            return
        cached = self.code_github.get(repo["id"])
        key = ("github", repo["id"])
        if (not cached or time.monotonic() - cached["at"] > 120) and key not in self.code_loading:
            self.load_github(repo, (entry or {}).get("status", {}).get("branch", ""))
        if not cached:
            self.work_layout.addWidget(label("Loading " + repo["github_repo"] + " from GitHub…", "muted"))
            self.work_layout.addStretch()
            return
        if cached.get("error"):
            problem = label(cached["error"], "warning")
            problem.setWordWrap(True)
            self.work_layout.addWidget(problem)
            self.work_layout.addWidget(
                row(button("Try again", lambda: self.reload_github(repo), "sync-alt"), None)
            )
            self.work_layout.addStretch()
            return
        data = cached["data"]
        info = data["repo"]
        box, l = panel()
        checks = data["checks"]
        state = (checks or {}).get("state", "none")
        colors = {"passing": "#7fd49b", "failing": C["danger"], "pending": C["warning"]}
        check_text = {
            "passing": "Checks passing",
            "failing": "Checks failing (" + str((checks or {}).get("failed", 0)) + ")",
            "pending": "Checks running",
            "none": "No checks",
        }[state]
        check_label = label(check_text + " on " + data["ref"], "section")
        if state in colors:
            check_label.setStyleSheet("color:" + colors[state] + ";")
        release = data["release"]
        l.addWidget(
            row(
                label(info["full_name"], "section"),
                label("private" if info.get("private") else "public", "count"),
                label("default " + (info.get("default_branch") or ""), "muted"),
                None,
                button(
                    "Open on GitHub",
                    lambda: QDesktopServices.openUrl(QUrl(info["html_url"])),
                    "external-link-alt",
                ),
                button("Reload", lambda: self.reload_github(repo), "sync-alt"),
            )
        )
        if info.get("description"):
            description = label(info["description"], "muted")
            description.setWordWrap(True)
            l.addWidget(description)
        l.addWidget(
            row(
                check_label,
                label("Latest release " + (release["tag"] if release else "none"), "muted"),
                None,
                button("New pull request…", lambda: self.github_new_pull(repo, entry), "code-branch", True),
                button("New issue…", lambda: self.github_new_issue(repo), "plus"),
            )
        )
        self.work_layout.addWidget(box)
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        pulls = self.github_table(
            ["#", "Pull request", "Branches", "Author"],
            [
                [
                    str(p["number"]),
                    p["title"] + (" (draft)" if p["draft"] else ""),
                    p["head"] + " → " + p["base"],
                    p["author"],
                ]
                for p in data["pulls"]
            ],
            data["pulls"],
        )
        pull_box, pl = column(spacing=4)
        merge = button("Merge…", lambda: self.github_merge(repo, pulls), "code-branch")
        pl.addWidget(
            row(
                label("Open pull requests", "section"),
                label(str(len(data["pulls"])), "count"),
                None,
                button("Open", lambda: self.github_open_row(pulls), "external-link-alt"),
                merge,
            )
        )
        pl.addWidget(pulls, 1)
        issues = self.github_table(
            ["#", "Issue", "Labels", "Author"],
            [[str(i["number"]), i["title"], ", ".join(i["labels"]), i["author"]] for i in data["issues"]],
            data["issues"],
        )
        issue_box, il = column(spacing=4)
        il.addWidget(
            row(
                label("Open issues", "section"),
                label(str(len(data["issues"])), "count"),
                None,
                button("Open", lambda: self.github_open_row(issues), "external-link-alt"),
                button("Create ticket", lambda: self.github_issue_ticket(project, issues), "plus"),
            )
        )
        il.addWidget(issues, 1)
        split.addWidget(pull_box)
        split.addWidget(issue_box)
        self.work_layout.addWidget(split, 1)

    def github_table(self, headers, rows, records):
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(24)
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, records[r])
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.cellDoubleClicked.connect(lambda r, c: QDesktopServices.openUrl(QUrl(records[r]["url"])))
        return table

    def github_selected(self, table):
        rows = table.selectionModel().selectedRows() if table.selectionModel() else []
        if not rows:
            self.toast.setText("Select a row first")
            return None
        return table.item(rows[0].row(), 0).data(Qt.UserRole)

    def github_open_row(self, table):
        record = self.github_selected(table)
        if record:
            QDesktopServices.openUrl(QUrl(record["url"]))

    def load_github(self, repo, branch=""):
        key = ("github", repo["id"])
        self.code_loading.add(key)
        client = self.github_client()

        def work():
            try:
                return {"data": client.overview(repo["github_repo"], branch)}
            except Exception as exc:
                if branch:
                    # The local branch may not exist on GitHub yet; fall back to the default branch.
                    try:
                        return {"data": client.overview(repo["github_repo"])}
                    except Exception:
                        pass
                return {"error": str(exc)}

        def done(result):
            self.code_loading.discard(key)
            self.code_github[repo["id"]] = {**result, "at": time.monotonic()}
            if self.page == "Code" and self.code_view == "GitHub":
                QTimer.singleShot(0, self.refresh_page)

        self.run_async(work, done)

    def reload_github(self, repo):
        self.code_github.pop(repo["id"], None)
        self.refresh_page()

    def github_call(self, title, fn, done):
        """Run a GitHub write in a worker and report the result."""
        client = self.github_client()

        def work():
            try:
                return {"ok": fn(client)}
            except Exception as exc:
                return {"error": str(exc)}

        def finished(result):
            if "error" in result:
                error(self, result["error"])
            else:
                done(result["ok"])

        self.toast.setText(title + "…")
        self.run_async(work, finished)

    def github_new_pull(self, repo, entry):
        status = (entry or {}).get("status") or {}
        ticket = self.find_ticket(self.code_ticket) if self.code_ticket else None
        base = repo["default_branch"] or self.code_github.get(repo["id"], {}).get("data", {}).get(
            "repo", {}
        ).get("default_branch", "main")
        title = (self.ticket_key(ticket).replace(" · ", "-") + ": " + ticket["title"]) if ticket else ""
        body = (ticket["description"] if ticket else "") or ""
        d = PullRequestDialog(
            self, status.get("branch", ""), base, (entry or {}).get("branches", []), title, body
        )
        if d.exec() != QDialog.Accepted:
            return
        p = d.payload()

        def created(result):
            self.toast.setText("Opened pull request #" + str(result["number"]))
            QDesktopServices.openUrl(QUrl(result["url"]))
            self.reload_github(repo)

        self.github_call(
            "Creating pull request",
            lambda c: c.create_pull(
                repo["github_repo"], p["title"], p["head"], p["base"], p["body"], p["draft"]
            ),
            created,
        )

    def github_new_issue(self, repo):
        ticket = self.find_ticket(self.code_ticket) if self.code_ticket else None
        d = IssueDialog(self, ticket["title"] if ticket else "", ticket["description"] if ticket else "")
        if d.exec() != QDialog.Accepted:
            return
        title, body = d.title.text().strip(), d.body.toPlainText()

        def created(result):
            self.toast.setText("Created issue #" + str(result["number"]))
            self.reload_github(repo)

        self.github_call(
            "Creating issue", lambda c: c.create_issue(repo["github_repo"], title, body), created
        )

    def github_merge(self, repo, table):
        pull = self.github_selected(table)
        if not pull:
            return
        d = MergeDialog(self, pull)
        if d.exec() != QDialog.Accepted:
            return
        method = d.method.currentData()

        def merged(result):
            if result["merged"]:
                self.toast.setText("Merged #" + str(pull["number"]))
            else:
                error(self, result["message"] or "GitHub did not merge the pull request.")
            self.reload_github(repo)

        self.github_call(
            "Merging", lambda c: c.merge_pull(repo["github_repo"], pull["number"], method), merged
        )

    def github_issue_ticket(self, project, table):
        issue = self.github_selected(table)
        if issue:
            self.quick_add(
                "ticket",
                project_id=project["id"],
                title="#" + str(issue["number"]) + " " + issue["title"],
                description=issue["url"],
                labels=issue["labels"],
            )


def icon_label(glyph):
    w = label("")
    w.setPixmap(icon(glyph).pixmap(14, 14))
    return w
