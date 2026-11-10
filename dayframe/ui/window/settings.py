"""Settings page host plus backup, conflict review and sync scheduling."""

from __future__ import annotations
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox
from ...core import domain as D
from ..views.settings_panel import SettingsPanel
from ..dialogs import ClearWorkspaceDialog, ConflictDialog
from ..widgets import error


class SettingsPage:
    def show_settings(self):
        self.settings_panel = SettingsPanel(self)
        self.work_layout.addWidget(self.settings_panel, 1)

    def backup(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "Back up DayFrame", "DayFrame-backup-" + D.day_key() + ".db", "SQLite database (*.db)"
        )
        if file:
            try:
                self.store.backup(file)
                self.toast.setText("Backup saved: " + file)
            except Exception as exc:
                error(self, exc)

    def clear_workspace(self):
        """Empty the workspace after a typed confirmation and a second question; a backup is saved first."""
        if self.jobs:
            self.toast.setText("Wait for the running sync or database job to finish, then try again.")
            return
        if not self.leave_editor():
            return
        counts = self.store.workspace_counts()
        summary = ClearWorkspaceDialog.summary(counts)
        if not summary:
            QMessageBox.information(self, "Clear workspace", "This workspace is already empty.")
            return
        hub = self.data["settings"].get("syncUrl", "")
        dialog = ClearWorkspaceDialog(self, counts, self.store.root / "backups", hub)
        if dialog.exec() != QDialog.Accepted:
            return
        if (
            QMessageBox.warning(
                self,
                "Clear workspace",
                "Delete " + summary + " now?\n\nA backup is saved first.",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            != QMessageBox.Yes
        ):
            return
        # Selections, filters, Undo and cached repository state all point at deleted records.
        self.selected = None
        self.project_id = None
        self.filter_project = None
        self.filter_status = "all"
        self.filter_label = ""
        self.undo_action = None
        for name in ("tickets_ticket", "tickets_project", "code_project", "code_ticket", "code_item"):
            if hasattr(self, name):
                setattr(self, name, None)
        for name in ("code_status", "code_cache", "code_github"):
            if hasattr(self, name):
                setattr(self, name, {})
        result = self.execute("workspace.clear")
        if result:
            self.toast.setText("Workspace cleared · backup: " + result["backup"])
            QMessageBox.information(
                self,
                "Workspace cleared",
                "The workspace is empty.\n\nBackup saved to:\n" + result["backup"],
            )

    def review_conflict(self, c):
        d = ConflictDialog(self, c, self.store.read(c["kind"], c["entity_id"]))
        if d.exec() == QDialog.Accepted:
            try:
                self.sync.resolve(c["id"], d.choice)
                self.refresh()
            except Exception as exc:
                error(self, exc)

    def auto_sync(self):
        if self.data and self.data["settings"].get("syncEnabled") and not self.jobs:
            self.sync_now(quiet=True)

    def sync_now(self, quiet=False):
        if isinstance(quiet, bool) and not self.data:
            return
        self.run_async(
            lambda: self.sync.run(force=not quiet), lambda result: self.sync_finished(result, quiet)
        )

    def sync_finished(self, result, quiet=False):
        latest = self.store.snapshot()
        changed = any(latest[k] != self.data[k] for k in (*D.DEFINITIONS, "conflicts")) if self.data else True
        self.data = latest
        if changed:
            self.refresh_page()
        self.tick()
        if not quiet:
            self.toast.setText(
                result.get("error")
                or ("Synced · credentials remembered" if result.get("remembered") else "Sync complete")
            )
