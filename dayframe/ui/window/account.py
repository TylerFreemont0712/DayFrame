"""Sign-in, account import, local password and logout flows."""

from __future__ import annotations
from PySide6.QtWidgets import QDialog, QFileDialog, QFormLayout, QLineEdit, QMessageBox
from pathlib import Path
from ...core import domain as D
from ..theme import apply_theme
from ..widgets import button, column, error, FormDialog, label, panel, row


class AccountMixin:
    def show_auth(self):
        self.data = None
        root, l = column(margins=40)
        l.addStretch()
        card, cl = panel()
        card.setMaximumWidth(540)
        cl.addWidget(label("DayFrame", "heading"))
        cl.addWidget(label("Your projects. Your day. Your space.", "muted"))
        configured = self.store.status()["configured"]
        cl.addWidget(
            label("Sign in to this device" if configured else "Create your private workspace", "section")
        )
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setAccessibleName("Username")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        cl.addWidget(self.username)
        cl.addWidget(self.password)
        self.auth_submit = button(
            "Sign in" if configured else "Create account", self.submit_auth, accent=True
        )
        cl.addWidget(self.auth_submit)
        self.password.returnPressed.connect(self.submit_auth)
        if not configured:
            cl.addWidget(label("Everything stays in your local SQLite database.", "muted"))
            cl.addWidget(button("Import an existing DayFrame database", self.import_database, "database"))
            cl.addWidget(button("Connect to my existing LAN account", self.import_hub, "network-wired"))
        cl.addWidget(label(str(self.store.root), "muted"))
        center = row(None, card, None)
        l.addWidget(center)
        l.addStretch()
        self.setCentralWidget(root)

    def submit_auth(self):
        if self.busy:
            return
        self.busy = True
        self.auth_submit.setEnabled(False)
        name, pw = self.username.text(), self.password.text()
        fn = self.store.login if self.store.status()["configured"] else self.store.register
        self.run_async(lambda: fn(name, pw), lambda result: self.signed_in())

    def signed_in(self):
        self.busy = False
        if hasattr(self, "password"):
            try:
                self.password.clear()
            except RuntimeError:
                pass
        self.data = self.store.snapshot()
        apply_theme(self.data["settings"])
        self.day = D.day_key(self.data["settings"]["timezone"])
        if self.data["settings"].get("layoutRevision", 0) < 3:
            self.store.settings(
                {
                    "layoutRevision": 3,
                    "density": "compact",
                    "sidebarWidth": 164,
                    "inspectorWidth": 280,
                    "windowGeometry": "",
                }
            )
            self.data = self.store.snapshot()
            apply_theme(self.data["settings"])
            self.resize(1280, 800)
        self.build_shell()
        geometry = self.data["settings"].get("windowGeometry")
        if geometry:
            from PySide6.QtCore import QByteArray

            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
        screen = self.screen().availableGeometry()
        if self.width() > screen.width() or self.height() > screen.height():
            self.resize(min(1280, screen.width() - 40), min(800, screen.height() - 60))
        self.refresh()

    def import_database(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Import a copy of an existing database",
            str(Path.home()),
            "SQLite database (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if not file:
            return
        try:
            self.store.import_database(file)
            self.show_auth()
            QMessageBox.information(
                self,
                "Import complete",
                "A copy was imported. Sign in with your existing account. The original database was not changed.",
            )
        except Exception as exc:
            error(self, exc)

    def import_hub(self):
        d = FormDialog(self, "Connect this device to your account")
        f = QFormLayout()
        d.layout.addLayout(f)
        edits = {}
        for key, title in (
            ("url", "HTTPS hub address"),
            ("fingerprint", "Certificate SHA-256"),
            ("username", "Username"),
            ("password", "Password"),
        ):
            edits[key] = QLineEdit()
            f.addRow(title, edits[key])
        edits["password"].setEchoMode(QLineEdit.Password)
        d.finish_form()
        if d.exec() != QDialog.Accepted:
            return
        p = {k: w.text() for k, w in edits.items()}
        self.run_async(lambda: self.sync.connect(p, importing=True), lambda result: self.signed_in())

    def lock_workspace(self):
        self.logout()

    def change_local_password(self):
        d = FormDialog(self, "Change local password")
        d.resize(430, 170)
        hint = label("Choose any password. Your hub password stays unchanged.", "muted")
        hint.setWordWrap(True)
        d.layout.addWidget(hint)
        value = QLineEdit()
        value.setEchoMode(QLineEdit.Password)
        value.setPlaceholderText("New local password")
        d.layout.addWidget(value)
        d.finish_form()
        if d.exec() != QDialog.Accepted:
            return
        password = value.text()
        value.clear()
        self.run_async(
            lambda: self.store.change_password(password),
            lambda result: self.toast.setText("Local password updated."),
        )

    def logout(self):
        if not self.leave_editor():
            return
        if self.jobs:
            self.toast.setText("Wait for the current operation before logging out.")
            return
        try:
            self.store.logout()
        except Exception as exc:
            error(self, exc)
            return
        self.sync.token = None
        self.selected = None
        self.search_text = ""
        self.statusBar().hide()
        self.show_auth()
