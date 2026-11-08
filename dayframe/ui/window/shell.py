"""Navigation rail, masthead, utility bar, search and the one-second tick."""

from __future__ import annotations
import time
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QSplitter, QWidget
from ...core import domain as D
from ..views.agenda import Agenda
from ..views.calendar import WeekCalendar
from ..theme import app_icon, icon
from ..widgets import button, column, combo, fit_combo_width, fit_text_width, label


class ShellMixin:
    def build_shell(self):
        outer = QWidget()
        layout = QHBoxLayout(outer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        rail, rl = column(margins=6, spacing=5)
        rail.setObjectName("navigationRail")
        rail.setFixedWidth(48)
        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(30, 30))
        mark.setAlignment(Qt.AlignCenter)
        rl.addWidget(mark)
        self.nav = {}
        for page, glyph in (
            ("Today", "home"),
            ("Projects", "layer-group"),
            ("Calendar", "calendar-alt"),
            ("Time", "clock"),
            ("Code", "code"),
        ):
            b = button("", lambda checked=False, p=page: self.navigate(p), glyph)
            b.setCheckable(True)
            b.setFixedSize(34, 34)
            b.setIconSize(QSize(17, 17))
            b.setToolTip(page)
            b.setAccessibleName(page)
            self.nav[page] = b
            rl.addWidget(b)
        rl.addStretch()
        b = button("", lambda: self.navigate("Settings"), "cog")
        b.setFixedSize(34, 34)
        b.setCheckable(True)
        b.setToolTip("Settings")
        b.setAccessibleName("Settings")
        self.nav["Settings"] = b
        rl.addWidget(b)
        layout.addWidget(rail)
        body, bl = column(spacing=0)
        layout.addWidget(body, 1)
        top = QFrame()
        top.setObjectName("masthead")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(10, 4, 8, 4)
        tl.setSpacing(6)
        personal = button("Personal", None, "user")
        personal.setCheckable(True)
        personal.setChecked(True)
        team = button(
            "Team",
            lambda: QMessageBox.information(
                self,
                "Team",
                "Team workspaces are planned. Your personal workspace and device sync are available.",
            ),
            "users",
        )
        tl.addWidget(personal)
        tl.addWidget(team)
        tl.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tickets…  Ctrl+K")
        self.search.setMinimumWidth(140)
        self.search.setMaximumWidth(300)
        self.search.textChanged.connect(self.search_changed)
        tl.addWidget(self.search)
        self.sync_label = label("Local", "muted")
        self.sync_label.setMaximumWidth(100)
        tl.addWidget(self.sync_label)
        tl.addWidget(button("Add", lambda: self.quick_add(), "plus", True))
        self.options = button("", None, "ellipsis-h")
        self.options.setAccessibleName("Options")
        self.options.setToolTip("Options")
        self.options.setFixedWidth(38)
        self.options_menu = QMenu(self)
        self.options_menu.setObjectName("optionsMenu")
        self.options_menu.addAction(icon("cog"), "Settings", lambda: self.navigate("Settings"))
        self.options_menu.addAction(icon("sync-alt"), "Sync now", lambda: self.sync_now(False))
        self.options_menu.addAction(icon("undo"), "Undo", self.undo)
        self.options_menu.addSeparator()
        self.options_menu.addAction(icon("sign-out-alt"), "Log out", self.logout)
        self.options.setMenu(self.options_menu)
        tl.addWidget(self.options)
        bl.addWidget(top)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.context, self.context_layout = column(margins=8, spacing=5)
        self.context.setObjectName("contextPane")
        self.context.setMinimumWidth(140)
        self.context.setMaximumWidth(280)
        self.workspace, self.work_layout = column(margins=9, spacing=6)
        self.workspace.setMinimumWidth(410)
        self.inspector, self.inspect_layout = column()
        self.inspector.setObjectName("ticketInspector")
        self.inspector.setMinimumWidth(240)
        self.inspector.setMaximumWidth(420)
        self.splitter.addWidget(self.context)
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes(
            [self.data["settings"]["sidebarWidth"], 820, self.data["settings"]["inspectorWidth"]]
        )
        bl.addWidget(self.splitter, 1)
        footer = QFrame()
        footer.setObjectName("utilityBar")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(9, 4, 8, 4)
        fl.setSpacing(6)
        self.timer_title = label("No timer", "section")
        self.timer_title.setMaximumWidth(120)
        self.timer_clock = label("00:00:00", "clock")
        fit_text_width(self.timer_clock, "88:88:88", 8)
        self.timer_toggle = button("", self.toggle_timer, "play")
        self.timer_toggle.setFixedWidth(27)
        self.timer_toggle.setToolTip("Start / pause timer")
        self.timer_toggle.setAccessibleName("Start or pause timer")
        stop = button("", lambda: self.execute("timer.action", {"action": "stop"}), "stop")
        stop.setFixedWidth(27)
        stop.setToolTip("Stop timer")
        stop.setAccessibleName("Stop timer")
        timer_icon = label("")
        timer_icon.setPixmap(icon("stopwatch").pixmap(14, 14))
        for w in (timer_icon, self.timer_title, self.timer_clock, self.timer_toggle, stop):
            fl.addWidget(w)
        self.today_total = label("Today 0m", "section")
        fit_text_width(self.today_total, "Today 10h 59m", 4, fixed=False)
        fl.addWidget(self.today_total)
        fl.addSpacing(8)
        self.quick_input = QLineEdit()
        self.quick_input.setPlaceholderText("Add a ticket or event…")
        self.quick_input.setAccessibleName("Quick capture")
        self.quick_input.setMinimumWidth(140)
        self.quick_input.returnPressed.connect(self.inline_add)
        fl.addWidget(self.quick_input, 1)
        self.quick_type = combo([("ticket", "Ticket"), ("event", "Event")])
        self.quick_type.setAccessibleName("Capture type")
        fit_combo_width(self.quick_type)
        fl.addWidget(self.quick_type)
        add = button("", self.inline_add, "plus")
        add.setFixedWidth(27)
        add.setToolTip("Capture")
        fl.addWidget(add)
        bl.addWidget(footer)
        if hasattr(self, "toast"):
            try:
                self.statusBar().removeWidget(self.toast)
                self.toast.deleteLater()
            except RuntimeError:
                pass
        self.toast = label("Ready", "muted")
        self.statusBar().setSizeGripEnabled(True)
        self.statusBar().addWidget(self.toast, 1)
        self.statusBar().show()
        self.setCentralWidget(outer)

    def scope_changed(self):
        if self.scope.currentData() == "team":
            QMessageBox.information(
                self,
                "Team workspace",
                "Personal accounts and LAN sync are available. Shared team workspaces are planned.",
            )
            self.scope.setCurrentIndex(0)

    def focus_search(self):
        if self.data:
            self.search.setFocus()

    def search_changed(self, text):
        self.search_text = text.casefold()
        if text and self.page != "Projects":
            self.navigate("Projects")
        else:
            self.refresh_page()

    def toggle_timer(self):
        t = next((t for t in self.data["timer"] if t["id"] == "active"), None)
        self.execute("timer.action", {"action": "pause" if t and t["start_at"] else "start"})

    def tick(self):
        if not self.data or not hasattr(self, "timer_title"):
            return
        now = int(time.time() * 1000)
        t = next((t for t in self.data["timer"] if t["id"] == "active"), None)
        ticket = self.find_ticket(t["ticket_id"]) if t else None
        active = bool(t and (t["start_at"] or t["paused"]))
        self.timer_title.setText(
            self.ticket_key(ticket) if ticket else "Unassigned" if active else "No timer"
        )
        self.timer_title.setToolTip(
            ticket["title"] if ticket else "Start unassigned tracking with the play button"
        )
        ms = (
            t["session_ms"] + max(0, now - t["start_at"])
            if t and t["start_at"]
            else t["session_ms"]
            if t
            else 0
        )
        self.timer_clock.setText(D.duration(ms))
        self.timer_toggle.setIcon(icon("pause" if t and t["start_at"] else "play"))
        self.timer_toggle.setToolTip("Pause timer" if t and t["start_at"] else "Resume / start timer")
        today = D.day_key(self.data["settings"]["timezone"])
        start, end = D.day_bounds(today, self.data["settings"]["timezone"])
        total = sum(max(0, min(e["end_at"], end) - max(e["start_at"], start)) for e in self.data["entry"])
        if t and t["start_at"]:
            total += max(0, min(now, end) - max(t["start_at"], start))
        self.today_total.setText("Today " + D.short_time(total))
        self.sync_label.setText(
            "Sync: attention"
            if self.sync.state.get("error")
            else "Synced"
            if self.sync.state["connected"]
            else "Local"
        )
        self.sync_label.setToolTip(
            (self.sync.state.get("error") or "Local workspace")
            + " · "
            + str(self.data["pending"])
            + " queued"
        )
        if self.day != today:
            self.day = today
            self.refresh()
        if self.page == "Today" and hasattr(self, "home_focus_title"):
            self.home_focus_title.setText(
                ticket["title"] if ticket and active else "Unassigned session" if active else "Start a timer"
            )
            self.home_focus_title.setToolTip(ticket["title"] if ticket else "Open time tracking")
            self.home_focus_clock.setText(D.duration(ms))
            self.home_focus_toggle.setIcon(icon("pause" if t and t["start_at"] else "play"))
        for agenda in self.findChildren(Agenda):
            agenda.update()
        for week in self.findChildren(WeekCalendar):
            week.canvas.update()

    def inline_add(self):
        title = self.quick_input.text().strip()
        if not title:
            return
        kind = self.quick_type.currentData()
        projects = [p for p in self.data["project"] if not p["archived"]]
        project_id = self.project_id or self.filter_project
        if kind == "ticket" and (not projects or (not project_id and len(projects) > 1)):
            if self.quick_add(kind, title=title, project_id=project_id):
                self.quick_input.clear()
            return
        p = {"title": title}
        if kind == "ticket":
            p["project_id"] = project_id or projects[0]["id"]
        else:
            p.update(date=D.day_key(self.data["settings"]["timezone"]), start_time="", end_time="")
        if self.execute(kind + ".save", p):
            self.quick_input.clear()
