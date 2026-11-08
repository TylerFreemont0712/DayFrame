"""Settings page host plus backup, conflict review and sync scheduling."""

from __future__ import annotations
from PySide6.QtWidgets import QDialog, QFileDialog
from ...core import domain as D
from ..views.settings_panel import SettingsPanel
from ..dialogs import ConflictDialog
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
