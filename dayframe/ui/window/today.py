"""The Today page: focus and figures, the task list, the week strip, a day timeline and what is coming up."""

from __future__ import annotations
import time
from datetime import date, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QSizePolicy, QSplitter, QTabWidget
from ...core import domain as D, planning as P
from ..status import status_label
from ..theme import CURRENT as C, icon
from ..views.agenda import Agenda
from ..views.home import CountdownTiles, StatChip, WeekStrip, event_icon, time_text, tooltip, when_text
from ..widgets import button, column, ElidingLabel, fit_text_width, label, panel, row, scroll


class TodayPage:
    def ticket_row(self, t, overdue=False):
        """One compact line: complete, stage symbol, title, project, due date, estimate, pin and start."""
        w = QFrame()
        w.setObjectName("overdueRow" if overdue else "taskRow")
        w.setMinimumHeight(28)
        l = QHBoxLayout(w)
        l.setContentsMargins(5, 2, 5, 2)
        l.setSpacing(5)
        check = QCheckBox()
        check.setToolTip("Complete ticket")
        check.setAccessibleName("Complete " + t["title"])
        check.clicked.connect(lambda checked: self.complete_ticket(t, checked))
        l.addWidget(check)
        l.addWidget(status_label(t["status"]))
        title = button(t["title"], lambda: self.select_ticket(t["id"]))
        title.setObjectName("rowTitle")
        title.setMinimumWidth(65)
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setToolTip(
            tooltip(t["title"] + "\n" + self.ticket_key(t) + " · " + D.STATUS_NAMES[t["status"]])
        )
        l.addWidget(title, 1)
        project = ElidingLabel(self.project_name(t["project_id"]), "badge")
        project.setFixedWidth(86)
        project.setAlignment(Qt.AlignCenter)
        l.addWidget(project)
        due = label(("Due " + t["due_date"][5:]) if t["due_date"] else "", "warning" if overdue else "muted")
        fit_text_width(due, "Due 12-30", 2)
        l.addWidget(due)
        estimate = label(D.short_time(t["estimate_min"] * 60000), "muted")
        estimate.setToolTip("Estimate")
        fit_text_width(estimate, "10h 0m", 2)
        l.addWidget(estimate)
        pin = button("", lambda: self.execute("ticket.save", {"id": t["id"], "pinned": int(not t["pinned"])}))
        pin.setIcon(icon("thumbtack", C["accent"] if t["pinned"] else None))
        pin.setObjectName("iconOnly")
        pin.setFixedWidth(20)
        pin.setToolTip("Unpin priority" if t["pinned"] else "Pin priority")
        l.addWidget(pin)
        play = button(
            "", lambda: self.execute("timer.action", {"action": "start", "ticket_id": t["id"]}), "play"
        )
        play.setObjectName("iconOnly")
        play.setFixedWidth(23)
        play.setToolTip("Start tracking")
        l.addWidget(play)
        return w

    def home_mode(self):
        """wide: tasks, plan and coming up side by side. medium: two columns. narrow: tabs."""
        available = self.width() - 48 - (280 if self.selected else 0)
        return "narrow" if available < 840 else "medium" if available < 1090 else "wide"

    def home_select_day(self, day):
        """Show another day in Home's week strip and timeline."""
        self.home_day = day
        self.refresh_page()

    def show_today(self):
        today = D.day_key(self.data["settings"]["timezone"])
        if getattr(self, "home_today", None) != today:
            # First visit, or the date rolled over while the app was open.
            self.home_today = today
            self.home_day = today
        day = self.home_day
        mode = self.home_mode()
        self._home_layout = (mode, self.height() >= 720)
        self._today_narrow = mode == "narrow"
        self.work_layout.addWidget(self.home_hero(today, mode))
        tasks, tl = column(spacing=5)
        tasks.setMinimumWidth(400)
        self.home_tasks(tl, today)
        tl.addStretch()
        coming, cl = column(spacing=5)
        self.home_coming(cl, today)
        cl.addStretch()
        plan, pl = column(spacing=6)
        self.home_week(pl, today, day)
        timeline = self.home_timeline(today, day)
        if mode == "wide":
            lower = QSplitter(Qt.Horizontal)
            lower.setHandleWidth(2)
            lower.addWidget(timeline)
            side = scroll(coming)
            side.setMinimumWidth(250)
            coming.setContentsMargins(8, 0, 0, 0)
            lower.addWidget(side)
            lower.setStretchFactor(0, 3)
            lower.setStretchFactor(1, 2)
            lower.setSizes([400, 320])
            pl.addWidget(lower, 1)
        elif mode == "medium":
            # Not enough width for three columns: the timeline shares its place with Coming up.
            pl.addWidget(
                self.home_tabs("home_plan_tab", (("Day Agenda", timeline), ("Coming up", scroll(coming)))), 1
            )
        else:
            pl.addWidget(timeline, 1)
            pages = (("Tasks", scroll(tasks)), ("Week", plan), ("Coming up", scroll(coming)))
            self.work_layout.addWidget(self.home_tabs("home_page_tab", pages), 1)
            return
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(2)
        split.addWidget(scroll(tasks))
        plan.setContentsMargins(8, 0, 0, 0)
        plan.setMinimumWidth(430)
        split.addWidget(plan)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([470, 740] if mode == "wide" else [430, 480])
        self.work_layout.addWidget(split, 1)

    def home_tabs(self, name, pages):
        """Tabs that stay on the chosen page when Home is rebuilt (picking a day rebuilds it)."""
        tabs = QTabWidget()
        for title, widget in pages:
            tabs.addTab(widget, title)
        tabs.setCurrentIndex(min(getattr(self, name, 0), len(pages) - 1))
        tabs.currentChanged.connect(lambda index: setattr(self, name, index))
        return tabs

    def home_hero(self, today, mode):
        """The focus timer beside the day's figures."""
        focus, fl = panel()
        focus.setObjectName("focusPanel")
        self.home_focus_title = button("", self.open_focus_ticket, "stopwatch")
        self.home_focus_title.setObjectName("rowTitle")
        self.home_focus_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.home_focus_clock = label("", "clock")
        self.home_focus_toggle = button("", self.toggle_timer, "play")
        self.home_focus_toggle.setFixedWidth(26)
        line = row(
            label("Focus", "section"), self.home_focus_title, self.home_focus_clock, self.home_focus_toggle
        )
        line.layout().setStretch(1, 1)
        fl.addWidget(line)
        self.home_focus_update()
        tickets = [t for t in self.data["ticket"] if not t["archived"]]
        open_ = [t for t in tickets if t["status"] != "done"]
        start, end = D.day_bounds(today, self.data["settings"]["timezone"])
        figures = [
            ("Overdue", sum(bool(t["due_date"]) and t["due_date"] < today for t in open_), "overdue", True),
            ("Due today", sum(t["due_date"] == today for t in open_), "week", False),
            ("In progress", sum(t["status"] in ("ready", "doing", "review") for t in open_), "open", False),
            (
                "Done today",
                sum(t["status"] == "done" and start <= t["completed_at"] < end for t in tickets),
                "done_week",
                False,
            ),
        ]
        hero = row(focus)
        hero.layout().setStretch(0, 1)
        for caption, value, view, warn in figures[: 2 if mode == "narrow" else 4]:
            chip = StatChip(
                caption,
                str(value),
                lambda v=view: self.home_open_tickets(v),
                warn and value > 0,
                caption + " · open in Tickets",
            )
            hero.layout().addWidget(chip)
        return hero

    def home_focus_update(self):
        """Show the running, paused or idle timer in the focus panel; tick() calls this every second."""
        timer = next((x for x in self.data["timer"] if x["id"] == "active"), None)
        ticket = self.find_ticket(timer["ticket_id"]) if timer else None
        running = bool(timer and timer["start_at"])
        active = bool(timer and (timer["start_at"] or timer["paused"]))
        ms = timer["session_ms"] if timer else 0
        if running:
            ms += max(0, int(time.time() * 1000) - timer["start_at"])
        self.home_focus_title.setText(
            ticket["title"] if ticket and active else "Unassigned session" if active else "Start a timer"
        )
        self.home_focus_title.setToolTip(ticket["title"] if ticket else "Open time tracking")
        self.home_focus_clock.setText(D.duration(ms))
        self.home_focus_toggle.setIcon(icon("pause" if running else "play"))

    def home_open_tickets(self, view):
        """Open the Tickets overview on one of its quick views."""
        if self.leave_editor():
            self.tickets_state()
            self.tickets_quick = view
            self.tickets_view = "Overview"
            self.navigate("Tickets")

    def home_tasks(self, layout, today):
        for title, group in P.home_groups(self.data, today):
            if not group and title in (D.STATUS_NAMES["ready"], "Recent tickets"):
                continue
            layout.addWidget(row(label(title, "section"), label(str(len(group)), "count"), None))
            for ticket in group:
                layout.addWidget(self.ticket_row(ticket, title == "Overdue"))
            if not group:
                layout.addWidget(
                    label(
                        "Pin a ticket to focus on it." if title == "Top priorities" else "Nothing here.",
                        "muted",
                    )
                )

    def home_week(self, layout, today, day):
        """Week caption, navigation and the strip of day cards."""
        start = P.sunday(day)
        end = start + timedelta(days=6)
        this_week = start == P.sunday(today)
        caption = label("This week" if this_week else "Week of " + start.strftime("%b %d"), "section")
        span = label(
            start.strftime("%b %d").replace(" 0", " ") + " – " + end.strftime("%b %d").replace(" 0", " "),
            "muted",
        )
        back = button("", lambda: self.home_select_day(self.home_shift(-7)), "chevron-left")
        forward = button("", lambda: self.home_select_day(self.home_shift(7)), "chevron-right")
        for b, tip in ((back, "Previous week"), (forward, "Next week")):
            b.setFixedWidth(25)
            b.setToolTip(tip)
            b.setAccessibleName(tip)
        now = button("Today", lambda: self.home_select_day(today))
        now.setEnabled(day != today)
        calendar = button("Calendar", lambda: self.home_open_calendar(day), "calendar-alt")
        calendar.setToolTip("Open this week in the calendar")
        layout.addWidget(row(caption, span, None, back, now, forward, calendar))
        strip = WeekStrip(self, day)
        strip.setFixedHeight(132 if self.height() >= 720 else 108)
        layout.addWidget(strip)

    def home_shift(self, days):
        return (date.fromisoformat(self.home_day) + timedelta(days=days)).isoformat()

    def home_open_calendar(self, day):
        self.calendar_day = day
        self.navigate("Calendar")

    def home_timeline(self, today, day):
        """The selected day's all-day items and hour-by-hour agenda."""
        pane, al = column(margins=0, spacing=4)
        pane.setMinimumWidth(240)
        title = "Today" if day == today else date.fromisoformat(day).strftime("%A, %b %d").replace(" 0", " ")
        add = button("", lambda: self.quick_add("event", day=day), "plus")
        add.setToolTip("Add an event on this day")
        al.addWidget(row(label("Day Agenda", "section"), label(title, "muted"), None, add))
        whole = [x for x in P.day_items(self.data, day) if x["all_day"]]
        # A short window keeps the hours readable by listing fewer all-day items.
        room = 4 if self.height() >= 720 else 2
        shown = whole if len(whole) <= room else whole[: room - 1]
        for item in shown:
            al.addWidget(self.event_button(item, day))
        if len(whole) > len(shown):
            more = label("+%d more all day" % (len(whole) - len(shown)), "muted")
            more.setToolTip(tooltip("\n".join(x["title"] for x in whole[len(shown) :])))
            al.addWidget(more)
        al.addWidget(Agenda(self, day), 1)
        return pane

    def home_coming(self, layout, today):
        """Countdown tiles for major events, then the next events with their type symbols."""
        events = [x for x in P.upcoming(self.data, today, 500, False) if x["kind"] == "event"]
        majors = sorted(
            [x for x in events if x["record"]["major"]], key=lambda x: (not x["record"]["pinned"], x["date"])
        )[:3]
        add = button("", lambda: self.quick_add("event"), "plus")
        add.setToolTip("Add an event")
        layout.addWidget(row(label("Next major events", "section"), None, add))
        if majors:
            layout.addWidget(CountdownTiles(self, majors, today))
        else:
            hint = label("Mark an event as major to count down to it here.", "muted")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        layout.addWidget(
            row(
                label("Upcoming", "section"),
                None,
                button("Calendar", lambda: self.navigate("Calendar"), "calendar-alt"),
            )
        )
        shown = {x["key"] for x in majors}
        upcoming = [x for x in events if x["key"] not in shown][:7]
        for item in upcoming:
            when = label(when_text(item["date"], today), "badge" if item["date"] == today else "muted")
            times = label(time_text(item), "muted")
            line = row(self.event_button(item), when, times)
            line.layout().setStretch(0, 1)
            layout.addWidget(line)
        if not upcoming:
            hint = label("Appointments, birthdays, trips and plans appear here.", "muted")
            hint.setWordWrap(True)
            layout.addWidget(hint)

    def event_button(self, item, day=None):
        """An event as a clickable title with its type symbol; day adds the time for that day's list."""
        text = item["title"]
        if day and item["end_date"] != item["date"]:
            text += " · until " + item["end_date"][5:]
        b = button(text, lambda checked=False, x=item: self.open_calendar_item(x))
        b.setIcon(event_icon(item))
        b.setObjectName("rowTitle")
        b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        b.setMinimumHeight(24)
        b.setMinimumWidth(60)
        details = [item["title"], item["date"] + " · " + time_text(item)]
        details += [item[k] for k in ("location", "description") if item.get(k)]
        b.setToolTip(tooltip("\n".join(details)))
        return b

    def open_focus_ticket(self):
        timer = next((x for x in self.data["timer"] if x["id"] == "active"), {})
        ticket = self.find_ticket(timer.get("ticket_id"))
        if ticket:
            self.select_ticket(ticket["id"])
        else:
            self.navigate("Time")

    def complete_ticket(self, ticket, checked=True):
        self.undo_action = lambda: self.execute(
            "ticket.save", {"id": ticket["id"], "status": ticket["status"]}
        )
        self.execute("ticket.save", {"id": ticket["id"], "status": "done" if checked else "ready"})
