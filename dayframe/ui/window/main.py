"""DayFrame main window: state, async jobs, page refresh and editor guards.

The window is assembled from page mixins (see this package's __init__)
so each page lives in its own module but shares one ``self``.
"""

from __future__ import annotations
from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox
from datetime import datetime
from ...sync.client import Sync
from ...core import domain as D
from ..theme import app_icon, apply_theme
from ..widgets import button, error, label, row
from ..workers import Worker
from .records import RecordLookups
from .account import AccountMixin
from .shell import ShellMixin
from .today import TodayPage
from .projects import ProjectsPage
from .inspector import InspectorMixin
from .schedule import CalendarPage
from .tracking import TimePage
from .settings import SettingsPage
from .capture import CaptureMixin
from .code import CodePage
from .code_repo import CodeRepoViews
from .tickets import TicketsPage


class DayFrame(
    RecordLookups,
    AccountMixin,
    ShellMixin,
    TodayPage,
    ProjectsPage,
    TicketsPage,
    InspectorMixin,
    CalendarPage,
    TimePage,
    SettingsPage,
    CodePage,
    CodeRepoViews,
    CaptureMixin,
    QMainWindow,
):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.sync = Sync(store)
        self.setWindowTitle("DayFrame")
        self.setWindowIcon(app_icon())
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)
        self.page = "Today"
        self.project_id = None
        self.project_view = "Kanban"
        self.selected = None
        self.settings_section = "view"
        self.filter_project = None
        self.filter_status = "all"
        self.filter_label = ""
        self.context_collapsed = False
        self.search_text = ""
        self.data = None
        self.undo_action = None
        self.busy = False
        self.jobs = set()
        self.rebuilding = False
        self.draft_reader = None
        self.draft_save = None
        self.day = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.auto_sync)
        self.sync_timer.start(5000)
        apply_theme({"theme": "graphite", "density": "compact"})
        if self.store.account or self.store.restore_session():
            self.signed_in()
        else:
            self.show_auth()
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.quick_add() if self.data else None)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)

    def run_async(self, fn, done, owner=None):
        job = Worker(fn)
        self.jobs.add(job)
        job.signals.done.connect(lambda result: self._job_done(job, done, result))
        job.signals.failed.connect(lambda message: self._job_error(job, message))
        QThreadPool.globalInstance().start(job)

    def _job_done(self, job, done, result):
        self.jobs.discard(job)
        try:
            done(result)
        except Exception as exc:
            error(self, exc)

    def _job_error(self, job, message):
        self.jobs.discard(job)
        self.busy = False
        if hasattr(self, "auth_submit"):
            self.auth_submit.setEnabled(True)
        error(self, message)

    def navigate(self, page):
        if page not in self.nav:
            return
        if not self.leave_editor():
            return
        self.page = page
        if page != "Projects":
            self.selected = None
        self.refresh()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def refresh(self):
        self.data = self.store.snapshot()
        self.refresh_page()
        self.tick()

    def refresh_page(self):
        if not self.data or not hasattr(self, "work_layout"):
            return
        if self.has_draft():
            self.toast.setText("Your editor draft stays open.")
            return
        self.draft_reader = None
        self.draft_save = None
        self.rebuilding = True
        self.clear_layout(self.work_layout)
        self.clear_layout(self.context_layout)
        self.context.setVisible(self.page in ("Projects", "Tickets", "Code") and not self.context_collapsed)
        for name, w in self.nav.items():
            w.setChecked(name == self.page)
        if self.page == "Projects":
            self.projects_context()
        elif self.page == "Code":
            self.code_context()
        elif self.page == "Tickets":
            self.tickets_context()
        title = self.page
        if self.page == "Projects":
            title = self.project_name(self.project_id) if self.project_id else "All tickets"
        self.page_header = row(label(title, "heading"))
        self.page_header.layout().setSpacing(12)
        if self.page == "Today":
            dt = datetime.strptime(D.day_key(self.data["settings"]["timezone"]), "%Y-%m-%d")
            self.page_header.layout().addWidget(label(dt.strftime("%A, %b %d").replace(" 0", " "), "muted"))
        self.page_header.layout().addStretch()
        if self.page in ("Projects", "Tickets", "Code") and self.context_collapsed:
            self.page_header.layout().addWidget(button("", self.toggle_context, "bars"))
        self.work_layout.addWidget(self.page_header)
        getattr(self, "show_" + self.page.lower())()
        self.render_inspector()
        self.rebuilding = False

    def execute(self, method, payload=None, refresh=True):
        try:
            result = self.store.command(method, payload)
            self.data = self.store.snapshot()
            if refresh:
                self.refresh_page()
            self.tick()
            self.toast.setText("Saved locally")
            return result or True
        except Exception as exc:
            error(self, exc)
            return None

    def undo(self):
        action = self.undo_action
        self.undo_action = None
        if action:
            action()

    def has_draft(self):
        return bool(self.draft_reader and self.draft_reader())

    def leave_editor(self):
        if not self.has_draft():
            self.draft_reader = None
            self.draft_save = None
            return True
        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save your editor changes before leaving?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save and self.draft_save and not self.draft_save():
            return False
        self.draft_reader = None
        self.draft_save = None
        return True

    def closeEvent(self, event):
        if self.jobs:
            self.toast.setText("Finishing a database or sync operation. Close again once it completes.")
            event.ignore()
            return
        if not self.leave_editor():
            event.ignore()
            return
        if self.data:
            try:
                sizes = self.splitter.sizes()
                patch = {"windowGeometry": bytes(self.saveGeometry().toBase64()).decode()}
                # A hidden pane reports a meaningless size; keep the saved width instead.
                if self.context.isVisible() and 140 <= sizes[0] <= 280:
                    patch["sidebarWidth"] = sizes[0]
                if self.inspector.isVisible() and 240 <= sizes[2] <= 420:
                    patch["inspectorWidth"] = sizes[2]
                self.store.settings(patch)
            except Exception:
                pass
        self.timer.stop()
        self.sync_timer.stop()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "data") and self.data and self.page == "Today" and not self.rebuilding:
            narrow = self.width() - 48 - (280 if self.selected else 0) < 840
            if narrow != getattr(self, "_today_narrow", narrow):
                QTimer.singleShot(0, self.refresh_page)
            self._today_narrow = narrow
