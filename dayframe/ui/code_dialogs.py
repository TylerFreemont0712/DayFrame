"""Dialogs for the Code page: repository connection, commits, confirmations and GitHub forms."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
)
from ..code import git as G
from .widgets import FormDialog, button, combo, label, row

FILE_CODES = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed", "C": "copied", "?": "new"}


def describe_change(entry):
    """'modified', 'new', 'deleted'… for a porcelain status code."""
    if entry["code"] == "UU":
        return "conflict"
    letters = [c for c in entry["code"] if c not in ". "]
    return FILE_CODES.get(letters[-1] if letters else "M", "changed")


def confirm(parent, title, text, details="", action="Continue", warning=""):
    """A bounded confirmation with the exact operation spelled out; True when accepted."""
    d = FormDialog(parent, title)
    d.resize(480, 240)
    message = label(text)
    message.setWordWrap(True)
    d.layout.addWidget(message)
    if warning:
        caution = label(warning, "warning")
        caution.setWordWrap(True)
        d.layout.addWidget(caution)
    if details:
        box = QPlainTextEdit(details)
        box.setObjectName("diffView")
        box.setReadOnly(True)
        box.setMaximumHeight(150)
        d.layout.addWidget(box)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    ok = buttons.button(QDialogButtonBox.Ok)
    ok.setText(action)
    ok.setObjectName("accent")
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    d.set_footer(buttons)
    d.buttons = buttons
    return d.exec() == FormDialog.Accepted


class RepoDialog(FormDialog):
    """Connect a project to version control and choose this device's checkout folder."""

    def __init__(self, parent, project, repo=None, path=""):
        super().__init__(parent, ("Edit" if repo else "Connect") + " version control · " + project["name"])
        self.resize(500, 340)
        repo = repo or {}
        form = QFormLayout()
        form.setSpacing(6)
        self.layout.addLayout(form)
        self.provider = combo([("git", "Git"), ("svn", "Subversion (planned)")], repo.get("provider", "git"))
        model = self.provider.model()
        if isinstance(model, QStandardItemModel):
            model.item(1).setEnabled(False)
        form.addRow("Version control", self.provider)
        self.path = QLineEdit(path)
        self.path.setPlaceholderText("Local checkout on this device")
        self.path.setAccessibleName("Checkout folder")
        form.addRow("Checkout folder", row(self.path, button("Browse…", self.browse, "folder-open")))
        self.name = QLineEdit(repo.get("name", ""))
        self.name.setAccessibleName("Repository name")
        form.addRow("Name", self.name)
        self.github = QLineEdit(repo.get("github_repo", ""))
        self.github.setPlaceholderText("owner/name (optional)")
        self.github.setAccessibleName("GitHub repository")
        form.addRow("GitHub repository", self.github)
        self.default_branch = QLineEdit(repo.get("default_branch", ""))
        self.default_branch.setPlaceholderText("main")
        form.addRow("Default branch", self.default_branch)
        self.remote_url = repo.get("remote_url", "")
        hint = label(
            "The repository connection syncs to your other devices. Each device chooses its own "
            "checkout folder, which stays on this device. Choosing a folder fills in the remote "
            "and GitHub name from its origin.",
            "muted",
        )
        hint.setWordWrap(True)
        self.layout.addWidget(hint)
        self.finish_form()

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose the checkout folder", self.path.text())
        if folder:
            self.path.setText(folder)
            self.detect()

    def detect(self):
        """Fill empty fields from the chosen checkout."""
        folder = self.path.text().strip()
        if not folder:
            return
        repo = G.GitRepo(folder)
        if not repo.is_repository():
            return
        self.remote_url = repo.remote_url() or self.remote_url
        if not self.name.text().strip():
            self.name.setText(Path(folder).name)
        if not self.github.text().strip():
            self.github.setText(G.github_repo_from_url(self.remote_url))
        if not self.default_branch.text().strip():
            self.default_branch.setText(repo.default_branch() or repo.status()["branch"])

    def accept(self):
        folder = self.path.text().strip()
        if folder and not G.GitRepo(folder).is_repository():
            self.path.setFocus()
            self.path.setToolTip("That folder is not a git checkout.")
            self.path.setStyleSheet("border-color:#e06c75;")
            return
        self.detect()
        if not self.name.text().strip():
            self.name.setText(Path(folder).name if folder else "Repository")
        super().accept()

    def payload(self):
        return {
            "provider": self.provider.currentData(),
            "name": self.name.text().strip(),
            "github_repo": self.github.text().strip(),
            "default_branch": self.default_branch.text().strip(),
            "remote_url": self.remote_url,
        }


class CommitDialog(FormDialog):
    def __init__(self, parent, status, message="", default_branch="", applied=None):
        super().__init__(parent, "Commit changes")
        self.resize(520, 440)
        branch = status["branch"] or "a detached HEAD"
        self.layout.addWidget(label("Commit to " + branch, "section"))
        if status["branch"] and status["branch"] == default_branch:
            caution = label(
                "This commits straight to the default branch. Create a ticket branch first if the "
                "change should go through a pull request.",
                "warning",
            )
            caution.setWordWrap(True)
            self.layout.addWidget(caution)
        self.message = QPlainTextEdit(message)
        self.message.setAccessibleName("Commit message")
        self.message.setPlaceholderText("Commit message")
        self.message.setMaximumHeight(90)
        self.layout.addWidget(self.message)
        self.layout.addWidget(label("Files", "section"))
        self.files = QListWidget()
        self.files.setAccessibleName("Files to commit")
        for entry in status["files"]:
            item = QListWidgetItem(entry["path"] + "  ·  " + describe_change(entry))
            item.setData(Qt.UserRole, [entry["path"]] + ([entry["from"]] if entry.get("from") else []))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if entry["code"] == "UU" else Qt.Checked)
            self.files.addItem(item)
        self.layout.addWidget(self.files, 1)
        self.push_after = QCheckBox("Push after committing (you confirm the push next)")
        self.layout.addWidget(self.push_after)
        self.archive = QCheckBox()
        self.archive.setVisible(bool(applied))
        if applied:
            self.archive.setText(
                "Archive changeset “" + applied["title"] + "”; its changes are now committed"
            )
            self.archive.setChecked(True)
        self.layout.addWidget(self.archive)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Commit")

    def paths(self):
        result = []
        for i in range(self.files.count()):
            if self.files.item(i).checkState() == Qt.Checked:
                result.extend(self.files.item(i).data(Qt.UserRole))
        return result

    def accept(self):
        if not self.message.toPlainText().strip():
            self.message.setFocus()
            return
        if not self.paths():
            self.files.setFocus()
            return
        super().accept()


class SwitchDialog(FormDialog):
    """Confirm switching the checkout to a changeset, shelving current work first."""

    def __init__(self, parent, target, status, shelve_into="", branches=()):
        super().__init__(parent, "Switch to changeset")
        self.resize(480, 260)
        text = label("Apply “" + target["title"] + "” (" + (target.get("stat") or "stored diff") + ").")
        text.setWordWrap(True)
        self.layout.addWidget(text)
        if status["files"]:
            note = label(
                str(len(status["files"]))
                + " uncommitted file(s) will be shelved into "
                + shelve_into
                + " first, so nothing is lost.",
                "warning",
            )
            note.setWordWrap(True)
            self.layout.addWidget(note)
        self.switch_branch = QCheckBox()
        branch = target.get("branch", "")
        offer = bool(branch) and branch != status["branch"] and branch in branches
        self.switch_branch.setVisible(offer)
        self.switch_branch.setText("Switch to branch " + branch + " first")
        self.switch_branch.setChecked(offer)
        self.layout.addWidget(self.switch_branch)
        if branch and branch != status["branch"] and branch not in branches:
            missing = label("It was saved on " + branch + ", which does not exist here.", "muted")
            missing.setWordWrap(True)
            self.layout.addWidget(missing)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Switch")


class PullRequestDialog(FormDialog):
    def __init__(self, parent, head, base, branches, title="", body=""):
        super().__init__(parent, "New pull request")
        self.resize(500, 380)
        form = QFormLayout()
        form.setSpacing(6)
        self.layout.addLayout(form)
        self.title = QLineEdit(title)
        self.title.setAccessibleName("Pull request title")
        form.addRow("Title", self.title)
        self.head = QLineEdit(head)
        form.addRow("From branch", self.head)
        self.base = QComboBox()
        self.base.setEditable(True)
        self.base.addItems([b for b in dict.fromkeys([base, *branches]) if b])
        form.addRow("Into", self.base)
        self.body = QPlainTextEdit(body)
        self.body.setPlaceholderText("Description")
        self.layout.addWidget(self.body, 1)
        self.draft = QCheckBox("Open as a draft")
        self.layout.addWidget(self.draft)
        hint = label(
            "Push the branch first; GitHub can only open a pull request for pushed commits.", "muted"
        )
        hint.setWordWrap(True)
        self.layout.addWidget(hint)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Create pull request")

    def accept(self):
        if self.title.text().strip() and self.head.text().strip() and self.base.currentText().strip():
            super().accept()

    def payload(self):
        return {
            "title": self.title.text().strip(),
            "head": self.head.text().strip(),
            "base": self.base.currentText().strip(),
            "body": self.body.toPlainText(),
            "draft": self.draft.isChecked(),
        }


class IssueDialog(FormDialog):
    def __init__(self, parent, title="", body=""):
        super().__init__(parent, "New issue")
        self.resize(480, 320)
        self.title = QLineEdit(title)
        self.title.setAccessibleName("Issue title")
        self.title.setPlaceholderText("Title")
        self.layout.addWidget(self.title)
        self.body = QPlainTextEdit(body)
        self.body.setPlaceholderText("Description")
        self.layout.addWidget(self.body, 1)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Create issue")

    def accept(self):
        if self.title.text().strip():
            super().accept()


class MergeDialog(FormDialog):
    def __init__(self, parent, pull):
        super().__init__(parent, "Merge pull request #" + str(pull["number"]))
        self.resize(460, 220)
        text = label(pull["title"] + "\n" + pull["head"] + " → " + pull["base"])
        text.setWordWrap(True)
        self.layout.addWidget(text)
        self.method = combo(
            [
                ("merge", "Create a merge commit"),
                ("squash", "Squash and merge"),
                ("rebase", "Rebase and merge"),
            ]
        )
        self.layout.addWidget(self.method)
        caution = label(
            "Merging changes " + pull["base"] + " on GitHub and cannot be undone from DayFrame.", "warning"
        )
        caution.setWordWrap(True)
        self.layout.addWidget(caution)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Merge")
