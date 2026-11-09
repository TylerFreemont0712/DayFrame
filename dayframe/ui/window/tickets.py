"""Tickets page: an overview of numbers, charts and the full ticket table, and a ticket page
with the description, comments, screenshots and every detail.

The ticket page reads like a forum thread: the description is the opening post, comments
follow with tracked time and status changes in between, and a composer at the bottom takes
text and pasted screenshots. Editing is explicit (Edit), protected by the unsaved-draft guard.
"""

from __future__ import annotations
import time
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ...core import domain as D
from ...core import ticket_stats as S
from ..code_dialogs import confirm
from ..theme import CURRENT as C, icon
from ..ticket_editor import TicketEditor
from ..views.charts import BarList, ColumnChart, stat_tile
from ..views.kanban import project_color
from ..views.ticket_thread import MarkdownView, PasteEdit, Thumb, avatar, pending_thumb, prepare_image
from ..widgets import ElidingLabel, button, column, combo, error, label, panel, row, scroll

TICKET_COLUMNS = (
    "Ticket",
    "Title",
    "Project",
    "Status",
    "Priority",
    "Assignee",
    "Labels",
    "Due",
    "Estimate",
    "Tracked",
    "Checklist",
    "Comments",
    "Code",
    "Created",
    "Completed",
)
PRIORITY_ORDER = {p: i for i, p in enumerate(D.PRIORITIES)}
SIDEBAR = 300


def when(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M") if ms else ""


def ago(ms):
    if not ms:
        return ""
    minutes = int((time.time() * 1000 - ms) // 60000)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return str(minutes) + " min ago"
    if minutes < 48 * 60:
        return str(minutes // 60) + " h ago"
    if minutes < 60 * 24 * 60:
        return str(minutes // 1440) + " days ago"
    return datetime.fromtimestamp(ms / 1000).strftime("%b %d, %Y")


def hours(ms):
    return D.short_time(ms)


def axis_hours(value):
    """Axis tick for a value already in hours."""
    return ("%g" % round(value, 1)) + "h" if value else "0"


class SortItem(QTableWidgetItem):
    """Table cell that sorts by a hidden key (numbers, dates) rather than its text."""

    def __init__(self, text, key):
        super().__init__(text)
        self.key = key

    def __lt__(self, other):
        if isinstance(other, SortItem):
            return self.key < other.key
        return super().__lt__(other)


class TicketsPage:
    # State and navigation -------------------------------------------------------------------

    def tickets_state(self):
        if not hasattr(self, "tickets_view"):
            self.tickets_view = "Overview"
            self.tickets_ticket = None
            self.tickets_quick = "open"
            self.tickets_project = None
            self.tickets_status = "any"
            self.tickets_priority = "any"
            self.tickets_search = ""
            self.tickets_sort = (-1, Qt.AscendingOrder)
            self.ticket_editing = False
            self.ticket_editor = None
            self.ticket_composer = None
            self.ticket_drafts = {}
            self.ticket_pending = {}
            self.post_editing = None

    def open_ticket_details(self, ticket_id):
        """Show one ticket's full page, from any view."""
        if not self.leave_editor():
            return
        self.tickets_state()
        self.tickets_ticket = ticket_id
        self.tickets_view = "Details"
        self.ticket_editing = False
        self.post_editing = None
        self.page = "Tickets"
        self.selected = None
        self.refresh_page()

    def tickets_context(self):
        self.tickets_state()
        l = self.context_layout
        l.addWidget(
            row(label("TICKETS", "section"), None, button("", self.toggle_context, "angle-double-left"))
        )
        for view, glyph in (("Overview", "chart-bar"), ("Details", "file-alt")):
            b = button(view, lambda checked=False, v=view: self.change_tickets_view(v), glyph)
            b.setCheckable(True)
            b.setChecked(self.tickets_view == view)
            l.addWidget(b)
        l.addWidget(label("VIEWS", "muted"))
        views = QListWidget()
        views.setObjectName("projectTree")
        views.setAccessibleName("Ticket views")
        tickets = [t for t in self.data["ticket"] if not t["archived"]]
        by_id = {t["id"]: t for t in self.data["ticket"]}
        today = D.day_key(self.data["settings"]["timezone"])
        week_start = D.day_bounds(S.P.sunday(today).isoformat(), self.data["settings"]["timezone"])[0]
        for key, title in S.QUICK_VIEWS:
            count = len(S.quick_filter(key, tickets, by_id, today, week_start))
            item = QListWidgetItem(title + "   " + str(count))
            item.setData(Qt.UserRole, key)
            views.addItem(item)
            if key == self.tickets_quick:
                item.setSelected(True)
                views.setCurrentItem(item)
        views.itemClicked.connect(lambda item: self.choose_tickets_view(item.data(Qt.UserRole)))
        views.setMaximumHeight(len(S.QUICK_VIEWS) * 26 + 8)
        l.addWidget(views)
        l.addWidget(label("PROJECTS", "muted"))
        projects = QListWidget()
        projects.setObjectName("projectTree")
        projects.setAccessibleName("Filter by project")
        everything = QListWidgetItem(icon("layer-group"), "All projects")
        everything.setData(Qt.UserRole, None)
        projects.addItem(everything)
        for p in self.data["project"]:
            if p["archived"]:
                continue
            count = sum(t["project_id"] == p["id"] and t["status"] != "done" for t in tickets)
            item = QListWidgetItem(
                icon("folder", project_color(p["id"]).name()), p["name"] + "   " + str(count)
            )
            item.setData(Qt.UserRole, p["id"])
            projects.addItem(item)
        for i in range(projects.count()):
            if projects.item(i).data(Qt.UserRole) == self.tickets_project:
                projects.setCurrentRow(i)
        projects.itemClicked.connect(lambda item: self.choose_tickets_project(item.data(Qt.UserRole)))
        l.addWidget(projects, 1)

    def change_tickets_view(self, view):
        if self.tickets_view != view and self.leave_editor():
            self.tickets_view = view
            self.ticket_editing = False
            QTimer.singleShot(0, self.refresh_page)

    def choose_tickets_view(self, key):
        if self.leave_editor():
            self.tickets_quick = key
            self.tickets_view = "Overview"
            QTimer.singleShot(0, self.refresh_page)

    def choose_tickets_project(self, project_id):
        if self.leave_editor():
            self.tickets_project = project_id
            self.tickets_view = "Overview"
            QTimer.singleShot(0, self.refresh_page)

    def show_tickets(self):
        self.tickets_state()
        views = ["Overview", "Details"]
        tabs = QTabBar()
        tabs.setExpanding(False)
        for view in views:
            tabs.addTab(view)
        tabs.setCurrentIndex(views.index(self.tickets_view))
        tabs.currentChanged.connect(lambda index: self.change_tickets_view(views[index]))
        self.page_header.layout().addWidget(
            button("New ticket", lambda: self.quick_add("ticket"), "plus", True)
        )
        self.page_header.layout().addWidget(tabs)
        if not self.data["project"]:
            empty, l = panel("No tickets yet")
            l.addWidget(
                label("Create a project and its tickets, or load the demo workspace in Settings.", "muted")
            )
            self.work_layout.addWidget(empty)
            self.work_layout.addStretch()
            return
        if self.tickets_view == "Details":
            self.tickets_details()
        else:
            self.tickets_overview()

    # Overview -------------------------------------------------------------------------------

    def visible_tickets(self, include_search=False):
        tickets = [t for t in self.data["ticket"] if not t["archived"]]
        by_id = {t["id"]: t for t in self.data["ticket"]}
        zone = self.data["settings"]["timezone"]
        today = D.day_key(zone)
        week_start = D.day_bounds(S.P.sunday(today).isoformat(), zone)[0]
        result = S.quick_filter(self.tickets_quick, tickets, by_id, today, week_start)
        if self.tickets_project:
            result = [t for t in result if t["project_id"] == self.tickets_project]
        if self.tickets_status != "any":
            result = [t for t in result if t["status"] == self.tickets_status]
        if self.tickets_priority != "any":
            result = [t for t in result if t["priority"] == self.tickets_priority]
        if include_search and self.tickets_search:
            needle = self.tickets_search.casefold()
            result = [t for t in result if needle in self.ticket_haystack(t)]
        return result

    def ticket_haystack(self, t):
        return " ".join(
            [
                self.ticket_key(t),
                t["title"],
                t["description"],
                self.project_name(t["project_id"]),
                *t["labels"],
            ]
        ).casefold()

    def tickets_overview(self):
        zone = self.data["settings"]["timezone"]
        today = D.day_key(zone)
        now = int(time.time() * 1000)
        snapshot = dict(self.data)
        if self.tickets_project:
            snapshot = {
                **self.data,
                "ticket": [t for t in self.data["ticket"] if t["project_id"] == self.tickets_project],
                "entry": [
                    e
                    for e in self.data["entry"]
                    if (self.find_ticket(e["ticket_id"]) or {}).get("project_id") == self.tickets_project
                ],
            }
        stats = S.overview(snapshot, today, zone, now)
        page, pl = column(spacing=10)
        scope = self.project_name(self.tickets_project) if self.tickets_project else "All projects"
        pl.addWidget(
            row(
                label(scope, "section"),
                label("week of " + stats["week_start"], "muted"),
                None,
                label("Personal workspace · everything is assigned to you until Teams arrive", "muted"),
            )
        )
        tiles = QGridLayout()
        tiles.setSpacing(8)

        def change(now_value, before, unit=str, up_is_good=True):
            if now_value == before:
                return "same as last week", None
            arrow = "▲ " if now_value > before else "▼ "
            return arrow + unit(abs(now_value - before)) + " vs last week", (now_value > before) == up_is_good

        done_delta, done_good = change(stats["completed_week"], stats["completed_last_week"])
        time_delta, time_good = change(stats["tracked_week"], stats["tracked_last_week"], hours)
        cycle = "—" if stats["cycle_days"] is None else ("%.1f days" % stats["cycle_days"])
        for index, (title, value, delta, good, hint) in enumerate(
            (
                (
                    "Open tickets",
                    str(stats["open"]),
                    "",
                    None,
                    str(stats["active"]) + " in progress or review",
                ),
                ("Completed this week", str(stats["completed_week"]), done_delta, done_good, ""),
                ("Created this week", str(stats["created_week"]), "", None, "new tickets since Sunday"),
                ("Overdue", str(stats["overdue"]), "", None, "open tickets past their due date"),
                ("Due in 7 days", str(stats["due_soon"]), "", None, "open tickets due soon"),
                ("Blocked", str(stats["blocked"]), "", None, "waiting on unfinished prerequisites"),
                ("Tracked this week", hours(stats["tracked_week"]), time_delta, time_good, ""),
                ("Cycle time", cycle, "", None, "median, created to completed, last 30 days"),
            )
        ):
            tile = stat_tile(title, value, delta, good, hint)
            if title == "Overdue" and stats["overdue"]:
                tile.findChildren(QWidget)[1].setStyleSheet("color:" + C["danger"] + ";")
            tiles.addWidget(tile, index // 4, index % 4)
        pl.addLayout(tiles)
        charts = QGridLayout()
        charts.setSpacing(8)

        def chart_panel(title, subtitle, widget):
            box, bl = panel()
            bl.addWidget(row(label(title, "section"), label(subtitle, "muted"), None))
            bl.addWidget(widget, 1)
            return box

        day_label = lambda d: d[5:].replace("-", "/")  # noqa: E731
        charts.addWidget(
            chart_panel(
                "Completed per day",
                "last 14 days",
                ColumnChart(
                    [d for d, _ in stats["completed_days"]],
                    [("Completed", [n for _, n in stats["completed_days"]])],
                    slot_text=day_label,
                ),
            ),
            0,
            0,
        )
        charts.addWidget(
            chart_panel(
                "Tracked time per day",
                "last 14 days",
                ColumnChart(
                    [d for d, _ in stats["tracked_days"]],
                    # Plotted in hours so the axis gets round ticks (2h, 4h and so on).
                    [("Tracked", [ms / 3_600_000 for _, ms in stats["tracked_days"]])],
                    value_text=lambda h: hours(h * 3_600_000),
                    slot_text=day_label,
                    axis_text=axis_hours,
                ),
            ),
            0,
            1,
        )
        charts.addWidget(
            chart_panel(
                "Created and completed",
                "per week, Sunday start",
                ColumnChart(
                    [w for w, _, _ in stats["weekly"]],
                    [
                        ("Created", [c for _, c, _ in stats["weekly"]]),
                        ("Completed", [d for _, _, d in stats["weekly"]]),
                    ],
                    slot_text=day_label,
                ),
            ),
            0,
            2,
        )
        charts.addWidget(chart_panel("Open by stage", "", BarList(stats["by_status"])), 1, 0)
        charts.addWidget(chart_panel("Open by project", "", BarList(stats["by_project"][:7])), 1, 1)
        charts.addWidget(
            chart_panel(
                "Estimate and tracked",
                "by project",
                BarList(
                    [(name, (estimate, tracked)) for name, (estimate, tracked) in stats["effort"]],
                    value_text=hours,
                    series=("Estimate", "Tracked"),
                ),
            ),
            1,
            2,
        )
        for column_index in range(3):
            charts.setColumnStretch(column_index, 1)
        pl.addLayout(charts)
        pl.addWidget(self.ticket_table_panel())
        self.work_layout.addWidget(scroll(page), 1)

    def ticket_table_panel(self):
        box, bl = panel()
        tickets = self.visible_tickets()
        quick = dict(S.QUICK_VIEWS)[self.tickets_quick]
        search = QLineEdit(self.tickets_search)
        search.setPlaceholderText("Search keys, titles, labels, descriptions…")
        search.setAccessibleName("Search tickets")
        search.setClearButtonEnabled(True)
        search.setMinimumWidth(200)
        status = combo(
            [("any", "Any stage")] + [(s, D.STATUS_NAMES[s]) for s in D.STATUSES], self.tickets_status
        )
        priority = combo(
            [("any", "Any priority")] + [(p, p.title()) for p in D.PRIORITIES], self.tickets_priority
        )
        count = label(str(len(tickets)), "count")
        bl.addWidget(row(label("Tickets · " + quick, "section"), count, None, search, status, priority))
        table = QTableWidget(len(tickets), len(TICKET_COLUMNS))
        table.setObjectName("ticketTable")
        table.setAccessibleName("Tickets")
        table.setHorizontalHeaderLabels(TICKET_COLUMNS)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(25)
        table.setMinimumHeight(420)
        today = D.day_key(self.data["settings"]["timezone"])
        comments = {}
        for post in self.data.get("post", []):
            if not post["archived"]:
                comments[post["ticket_id"]] = comments.get(post["ticket_id"], 0) + 1
        user = self.data["account"]["username"]
        for r, t in enumerate(tickets):
            done = sum(bool(s["done"]) for s in t["checklist"])
            tracked = self.tracked_ms(t["id"])
            overdue = t["due_date"] and t["due_date"] < today and t["status"] != "done"
            cells = [
                (self.ticket_key(t), self.ticket_key(t)),
                (t["title"], t["title"].casefold()),
                (self.project_name(t["project_id"]), self.project_name(t["project_id"]).casefold()),
                (
                    D.STATUS_NAMES[t["status"]] + (" · blocked" if self.blocked(t) else ""),
                    D.STATUSES.index(t["status"]),
                ),
                (t["priority"].title(), PRIORITY_ORDER[t["priority"]]),
                ("You (" + user + ")", user),
                (", ".join(t["labels"]), ", ".join(t["labels"])),
                (
                    (t["due_date"] + (" · overdue" if overdue else "")) if t["due_date"] else "",
                    t["due_date"] or "9999",
                ),
                (hours(t["estimate_min"] * 60000), t["estimate_min"]),
                (hours(tracked) if tracked else "", tracked),
                (
                    "%d/%d" % (done, len(t["checklist"])) if t["checklist"] else "",
                    (done / len(t["checklist"])) if t["checklist"] else -1,
                ),
                (str(comments.get(t["id"], "")), comments.get(t["id"], 0)),
                (str(self.changeset_count(t["id"]) or ""), self.changeset_count(t["id"])),
                (when(t["created_at"])[:10], t["created_at"]),
                (when(t["completed_at"])[:10], t["completed_at"]),
            ]
            for c, (text, key) in enumerate(cells):
                item = SortItem(text, key)
                item.setData(Qt.UserRole, t["id"])
                if c == 1:
                    item.setToolTip(t["title"])
                if c == 7 and overdue:
                    item.setForeground(QColor(C["danger"]))
                table.setItem(r, c, item)
        table.setSortingEnabled(True)
        column_index, order = self.tickets_sort
        if column_index >= 0:
            table.sortItems(column_index, order)
        table.horizontalHeader().sortIndicatorChanged.connect(
            lambda c, o: setattr(self, "tickets_sort", (c, o))
        )
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        table.setColumnWidth(1, max(220, table.columnWidth(1)))
        table.cellDoubleClicked.connect(
            lambda r, c: self.open_ticket_details(table.item(r, 0).data(Qt.UserRole))
        )
        table.cellClicked.connect(
            lambda r, c: setattr(self, "tickets_ticket", table.item(r, 0).data(Qt.UserRole))
        )

        def apply_search(text):
            self.tickets_search = text
            needle = text.casefold().strip()
            shown = 0
            for r in range(table.rowCount()):
                ticket = self.find_ticket(table.item(r, 0).data(Qt.UserRole))
                hidden = bool(needle) and needle not in self.ticket_haystack(ticket)
                table.setRowHidden(r, hidden)
                shown += not hidden
            count.setText(str(shown))

        search.textChanged.connect(apply_search)
        apply_search(self.tickets_search)
        status.currentIndexChanged.connect(
            lambda: self.set_ticket_filter("tickets_status", status.currentData())
        )
        priority.currentIndexChanged.connect(
            lambda: self.set_ticket_filter("tickets_priority", priority.currentData())
        )
        bl.addWidget(table)
        bl.addWidget(
            label("Double-click a ticket to open its page. Click a column heading to sort.", "muted")
        )
        self.ticket_table = table
        return box

    def set_ticket_filter(self, key, value):
        setattr(self, key, value)
        QTimer.singleShot(0, self.refresh_page)

    # Ticket page ----------------------------------------------------------------------------

    def tickets_details(self):
        tickets = sorted(
            [t for t in self.data["ticket"] if not t["archived"]],
            key=lambda t: (t["status"] == "done", self.ticket_key(t)),
        )
        ticket = self.find_ticket(self.tickets_ticket) if self.tickets_ticket else None
        if not ticket or ticket["archived"]:
            ticket = next(
                (t for t in self.visible_tickets() if t["status"] != "done"), tickets[0] if tickets else None
            )
        if not ticket:
            self.work_layout.addWidget(label("No tickets yet.", "muted"))
            self.work_layout.addStretch()
            return
        self.tickets_ticket = ticket["id"]
        order = [t["id"] for t in self.visible_tickets()] or [t["id"] for t in tickets]
        position = order.index(ticket["id"]) if ticket["id"] in order else -1
        picker = QComboBox()
        picker.setEditable(True)
        picker.setInsertPolicy(QComboBox.NoInsert)
        picker.setAccessibleName("Go to ticket")
        for t in tickets:
            picker.addItem(self.ticket_key(t) + "  " + t["title"], t["id"])
        picker.setCurrentIndex(max(0, picker.findData(ticket["id"])))
        picker.completer().setFilterMode(Qt.MatchContains)
        picker.completer().setCompletionMode(QCompleter.PopupCompletion)
        picker.setMinimumWidth(320)
        picker.activated.connect(lambda index: self.open_ticket_details(picker.itemData(index)))
        previous = button("", lambda: self.open_ticket_details(order[position - 1]), "chevron-left")
        following = button(
            "", lambda: self.open_ticket_details(order[(position + 1) % len(order)]), "chevron-right"
        )
        previous.setEnabled(position > 0)
        following.setEnabled(0 <= position < len(order) - 1)
        previous.setToolTip("Previous ticket in the current view")
        following.setToolTip("Next ticket in the current view")
        where = label(
            ("%d of %d in %s" % (position + 1, len(order), dict(S.QUICK_VIEWS)[self.tickets_quick]))
            if position >= 0
            else "",
            "muted",
        )
        self.work_layout.addWidget(row(picker, previous, following, where, None))
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(12)
        main = QVBoxLayout()
        main.setSpacing(10)
        side = QVBoxLayout()
        side.setSpacing(10)
        layout.addLayout(main, 1)
        side_widget = QWidget()
        side_widget.setFixedWidth(SIDEBAR)
        side_widget.setLayout(side)
        layout.addWidget(side_widget, 0, Qt.AlignTop)
        self.ticket_header(main, ticket)
        if self.ticket_editing:
            self.ticket_edit_form(main, ticket)
        else:
            self.ticket_opening_post(main, ticket)
            self.ticket_checklist(main, ticket)
        self.ticket_activity(main, ticket)
        self.ticket_composer_card(main, ticket)
        main.addStretch()
        self.ticket_sidebar(side, ticket)
        side.addStretch()
        self.work_layout.addWidget(scroll(body), 1)
        self.install_ticket_drafts(ticket)

    def ticket_header(self, main, t):
        card = QFrame()
        card.setObjectName("postCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(6)
        project = ElidingLabel(self.project_name(t["project_id"]), "badge")
        project.setMaximumWidth(180)
        actions = [
            button("Edit", self.start_ticket_edit, "pen", not self.ticket_editing),
            button(
                "Track",
                lambda: self.execute("timer.action", {"action": "start", "ticket_id": t["id"]}),
                "play",
            ),
            button("Schedule", lambda: self.schedule_ticket(t), "calendar-plus"),
            button("Code", lambda: self.open_code(t["id"]), "code"),
        ]
        actions[0].setEnabled(not self.ticket_editing)
        if t["status"] == "done":
            actions.append(button("Reopen", lambda: self.set_ticket_status(t, "ready"), "undo"))
        else:
            actions.append(button("Complete", lambda: self.set_ticket_status(t, "done"), "check"))
        more = button("", None, "ellipsis-h")
        more.setToolTip("More actions")
        menu = QMenu(self)
        menu.addAction(icon("columns"), "Show on the board", lambda: self.open_ticket(t["id"]))
        menu.addAction(
            icon("copy"), "Copy ticket key", lambda: QGuiApplication.clipboard().setText(self.ticket_key(t))
        )
        menu.addAction(icon("plus"), "Create child ticket", lambda: self.new_child_ticket(t))
        menu.addSeparator()
        menu.addAction(icon("archive"), "Archive ticket…", lambda: self.archive_from_page(t))
        more.setMenu(menu)
        cl.addWidget(row(label(self.ticket_key(t), "badge"), project, None, *actions, more))
        heading = label(t["title"], "ticketHeading")
        heading.setWordWrap(True)
        heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
        heading.setAccessibleName("Ticket title")
        cl.addWidget(heading)
        status = button(D.STATUS_NAMES[t["status"]], None, "circle")
        status.setObjectName("statusButton")
        status.setToolTip("Change status")
        status_menu = QMenu(self)
        for value in D.STATUSES:
            action = status_menu.addAction(
                D.STATUS_NAMES[value], lambda v=value: self.set_ticket_status(t, v)
            )
            action.setCheckable(True)
            action.setChecked(value == t["status"])
        status.setMenu(status_menu)
        chips = [status, label(t["priority"].title() + " priority", "count")]
        chips += [label(name, "badge") for name in t["labels"][:6]]
        if self.blocked(t):
            chips.append(label("Blocked by prerequisites", "warning"))
        cl.addWidget(row(*chips, None))
        meta = ["Opened by " + self.data["account"]["username"]]
        if t["created_at"]:
            meta.append(when(t["created_at"]) + " (" + ago(t["created_at"]) + ")")
        if t["completed_at"]:
            meta.append("completed " + when(t["completed_at"]))
        cl.addWidget(label(" · ".join(meta), "muted"))
        main.addWidget(card)

    def ticket_opening_post(self, main, t):
        card, cl = self.post_frame(self.data["account"]["username"], "opened this ticket", t["created_at"])
        cl.addWidget(MarkdownView(t["description"], "No description yet. Use Edit to describe the work."))
        images = [
            a
            for a in self.data.get("attachment", [])
            if a["ticket_id"] == t["id"] and not a["post_id"] and not a["archived"]
        ]
        if images:
            cl.addWidget(self.thumb_grid(images))
        main.addWidget(card)

    def post_frame(self, author, action, moment, tools=()):
        card = QFrame()
        card.setObjectName("postCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 9, 12, 10)
        cl.setSpacing(6)
        stamp = label(ago(moment), "muted")
        stamp.setToolTip(when(moment))
        cl.addWidget(
            row(avatar(author), label(author, "section"), label(action, "muted"), stamp, None, *tools)
        )
        return card, cl

    def thumb_grid(self, images):
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for index, image in enumerate(images):
            grid.addWidget(Thumb(self, image), index // 3, index % 3, Qt.AlignLeft)
        grid.setColumnStretch(3, 1)
        return holder

    def ticket_checklist(self, main, t):
        if not t["checklist"]:
            return
        box, bl = panel()
        done = sum(bool(s["done"]) for s in t["checklist"])
        bar = QProgressBar()
        bar.setRange(0, len(t["checklist"]))
        bar.setValue(done)
        bar.setFormat("%v of %m done")
        bar.setMaximumHeight(14)
        bl.addWidget(row(label("Checklist", "section"), bar, None))
        for index, step in enumerate(t["checklist"]):
            check = QCheckBox(step["text"])
            check.setChecked(bool(step["done"]))
            check.toggled.connect(lambda value, i=index: self.toggle_step(t, i, value))
            bl.addWidget(check)
        main.addWidget(box)

    def toggle_step(self, t, index, value):
        steps = [dict(s) for s in t["checklist"]]
        steps[index]["done"] = bool(value)
        QTimer.singleShot(0, lambda: self.execute("ticket.save", {"id": t["id"], "checklist": steps}))

    def ticket_activity(self, main, t):
        posts = [p for p in self.data.get("post", []) if p["ticket_id"] == t["id"] and not p["archived"]]
        images = {}
        for a in self.data.get("attachment", []):
            if a["ticket_id"] == t["id"] and a["post_id"] and not a["archived"]:
                images.setdefault(a["post_id"], []).append(a)
        zone = self.data["settings"]["timezone"]
        days = {}
        for e in self.data["entry"]:
            if e["ticket_id"] == t["id"]:
                key = D.day_key(zone, e["start_at"])
                total, count, first = days.get(key, (0, 0, e["start_at"]))
                days[key] = (total + e["end_at"] - e["start_at"], count + 1, min(first, e["start_at"]))
        items = [("post", p["created_at"], p) for p in posts]
        items += [("time", first, (key, total, count)) for key, (total, count, first) in days.items()]
        if t["completed_at"]:
            items.append(("done", t["completed_at"], None))
        items.sort(key=lambda item: item[1] or 0)
        sessions = sum(count for _, (_, _, count) in [(k, v) for k, v in days.items()])
        main.addWidget(
            row(
                label("Activity", "section"),
                label(str(len(posts)) + " comments", "count"),
                label(str(sessions) + " time sessions", "count"),
                None,
            )
        )
        for kind, moment, value in items:
            if kind == "post":
                main.addWidget(self.post_card(t, value, images.get(value["id"], [])))
            elif kind == "time":
                key, total, count = value
                note = label(
                    "⏱  Tracked "
                    + hours(total)
                    + " on "
                    + key
                    + (" in %d sessions" % count if count > 1 else ""),
                    "muted",
                )
                note.setContentsMargins(14, 0, 0, 0)
                main.addWidget(note)
            else:
                note = label("✔  Marked complete · " + when(moment), "muted")
                note.setContentsMargins(14, 0, 0, 0)
                main.addWidget(note)
        if not posts:
            main.addWidget(label("No comments yet. Start the discussion below.", "muted"))

    def post_card(self, t, post, images):
        edit = button("", lambda: self.start_post_edit(post["id"]), "pen")
        edit.setObjectName("iconOnly")
        edit.setToolTip("Edit comment")
        edit.setAccessibleName("Edit comment")
        delete = button("", lambda: self.delete_post(post), "trash-alt")
        delete.setObjectName("iconOnly")
        delete.setToolTip("Delete comment")
        delete.setAccessibleName("Delete comment")
        action = "commented" + (" · edited " + ago(post["edited_at"]) if post["edited_at"] else "")
        card, cl = self.post_frame(post["author"] or "you", action, post["created_at"], (edit, delete))
        if self.post_editing == post["id"]:
            editor = QPlainTextEdit(post["body"])
            editor.setAccessibleName("Edit comment text")
            editor.setMinimumHeight(90)
            cl.addWidget(editor)
            save = button(
                "Save comment", lambda: self.save_post_edit(post, editor.toPlainText()), "save", True
            )
            cl.addWidget(row(None, button("Cancel", self.cancel_post_edit), save))
            self.post_editor = editor
        else:
            cl.addWidget(MarkdownView(post["body"]))
        if images:
            cl.addWidget(self.thumb_grid(images))
        return card

    def ticket_composer_card(self, main, t):
        card = QFrame()
        card.setObjectName("postCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 9, 12, 10)
        cl.setSpacing(6)
        cl.addWidget(row(avatar(self.data["account"]["username"]), label("Add a comment", "section"), None))
        composer = PasteEdit()
        composer.setObjectName("composer")
        composer.setAccessibleName("Comment")
        composer.setPlaceholderText(
            "Write a comment… Markdown works. Paste or drop a screenshot to attach it. Ctrl+Enter posts."
        )
        composer.setPlainText(self.ticket_drafts.get(t["id"], ""))
        composer.setMinimumHeight(80)
        composer.setMaximumHeight(150)
        composer.textChanged.connect(lambda: self.ticket_drafts.__setitem__(t["id"], composer.toPlainText()))
        composer.imagePasted.connect(lambda image, name: self.attach_image(t, image, name))
        cl.addWidget(composer)
        pending = self.ticket_pending.get(t["id"], [])
        if pending:
            strip = QWidget()
            sl = QHBoxLayout(strip)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(8)
            for index, (attachment, pixmap) in enumerate(pending):
                sl.addWidget(
                    pending_thumb(
                        self, attachment, pixmap, lambda checked=False, i=index: self.drop_pending(t, i)
                    )
                )
            sl.addStretch()
            cl.addWidget(strip)
        post = button("Comment", lambda: self.post_comment(t), "paper-plane", True)
        cl.addWidget(
            row(
                button("Attach image…", lambda: self.pick_image(t), "image"),
                button("Paste screenshot", lambda: self.paste_image(t), "paste"),
                label(str(len(pending)) + " image(s) ready" if pending else "", "muted"),
                None,
                post,
            )
        )
        QShortcut(QKeySequence("Ctrl+Return"), composer, activated=lambda: self.post_comment(t))
        self.ticket_composer = composer
        main.addWidget(card)

    def ticket_sidebar(self, side, t):
        box, bl = panel("Details")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        today = D.day_key(self.data["settings"]["timezone"])
        tracked = self.tracked_ms(t["id"])
        user = self.data["account"]["username"]
        rows = [
            ("Status", D.STATUS_NAMES[t["status"]]),
            ("Priority", t["priority"].title()),
            ("Project", self.project_name(t["project_id"])),
            ("Assignee", "You (" + user + ")"),
            ("Labels", ", ".join(t["labels"]) or "—"),
            ("Component", t["component"] or "—"),
            ("Milestone", t["milestone"] or "—"),
            (
                "Due",
                (t["due_date"] or "—")
                + (" · overdue" if t["due_date"] and t["due_date"] < today and t["status"] != "done" else ""),
            ),
            ("Estimate", hours(t["estimate_min"] * 60000)),
            ("Tracked", hours(tracked)),
            ("Created", when(t["created_at"]) or "—"),
            ("Completed", when(t["completed_at"]) or "—"),
            ("Pinned", "Yes" if t["pinned"] else "No"),
        ]
        for index, (name, value) in enumerate(rows):
            grid.addWidget(label(name, "muted"), index, 0, Qt.AlignTop)
            shown = label(value)
            shown.setWordWrap(True)
            if name == "Assignee":
                shown.setToolTip("Assigning to other people arrives with Team workspaces.")
            grid.addWidget(shown, index, 1)
        grid.setColumnStretch(1, 1)
        bl.addLayout(grid)
        if t["estimate_min"]:
            bar = QProgressBar()
            bar.setRange(0, int(t["estimate_min"]))
            bar.setValue(min(int(t["estimate_min"]), int(tracked / 60000)))
            bar.setFormat("%d%% of estimate used" % round(100 * tracked / (t["estimate_min"] * 60000)))
            bar.setMaximumHeight(14)
            bl.addWidget(bar)
        side.addWidget(box)
        box, bl = panel("Relations")
        parent = self.find_ticket(t.get("parent_id")) if t.get("parent_id") else None
        children = [o for o in self.data["ticket"] if o.get("parent_id") == t["id"] and not o["archived"]]
        prerequisites = [self.find_ticket(x) for x in t["dependencies"] if self.find_ticket(x)]
        dependents = [o for o in self.data["ticket"] if t["id"] in o["dependencies"] and not o["archived"]]
        any_link = False
        for title, records in (
            ("Parent", [parent] if parent else []),
            ("Children", children),
            ("Depends on", prerequisites),
            ("Blocks", dependents),
        ):
            if not records:
                continue
            any_link = True
            bl.addWidget(label(title, "muted"))
            for other in records:
                link = button(
                    ("✓ " if other["status"] == "done" else "")
                    + self.ticket_key(other)
                    + "  "
                    + other["title"],
                    lambda checked=False, i=other["id"]: self.open_ticket_details(i),
                )
                link.setObjectName("rowTitle")
                link.setToolTip(other["title"] + " · " + D.STATUS_NAMES[other["status"]])
                bl.addWidget(link)
        if not any_link:
            bl.addWidget(label("No parent, children or dependencies.", "muted"))
        side.addWidget(box)
        box, bl = panel("Schedule")
        blocks = sorted(
            (b for b in self.data["block"] if b["ticket_id"] == t["id"] and b["date"] >= today),
            key=lambda b: (b["date"], b["start_time"]),
        )
        for b in blocks[:5]:
            entry = button(
                b["date"] + "  " + b["start_time"] + "–" + b["end_time"],
                lambda checked=False, x=b: self.schedule_ticket(t, self.store.read("block", x["id"])),
                "calendar-alt",
            )
            entry.setObjectName("rowTitle")
            bl.addWidget(entry)
        if not blocks:
            bl.addWidget(label("No upcoming work scheduled.", "muted"))
        entries = [e for e in self.data["entry"] if e["ticket_id"] == t["id"]]
        bl.addWidget(label(str(len(entries)) + " time sessions · " + hours(tracked), "muted"))
        bl.addWidget(row(button("Schedule work", lambda: self.schedule_ticket(t), "calendar-plus"), None))
        side.addWidget(box)
        repo = self.code_repo(t["project_id"])
        if repo:
            box, bl = panel("Code")
            changesets = [
                c for c in self.data["changeset"] if c["ticket_id"] == t["id"] and not c["archived"]
            ]
            bl.addWidget(
                label(repo["name"] + (" · " + repo["github_repo"] if repo["github_repo"] else ""), "muted")
            )
            for c in changesets[:5]:
                bl.addWidget(label("▣ " + c["title"] + (" · " + c["branch"] if c["branch"] else ""), "muted"))
            if not changesets:
                bl.addWidget(label("No changesets yet.", "muted"))
            bl.addWidget(row(button("Open in Code", lambda: self.open_code(t["id"]), "code"), None))
            side.addWidget(box)

    # Editing ----------------------------------------------------------------------------------

    def ticket_edit_form(self, main, t):
        box, bl = panel("Edit ticket")
        editor = TicketEditor(self, t, wide=True)
        bl.addWidget(editor)
        bl.addWidget(
            row(
                None,
                button("Cancel", self.cancel_ticket_edit),
                button("Save ticket", self.save_ticket_edit, "save", True),
            )
        )
        self.ticket_editor = editor
        main.addWidget(box)

    def install_ticket_drafts(self, t):
        """Unsaved edits and comment drafts are protected like the other editors."""

        def reader():
            changes = self.ticket_editor.payload() if self.ticket_editing and self.ticket_editor else {}
            text = self.ticket_composer.toPlainText().strip() if self.ticket_composer else ""
            post_text = getattr(self, "post_editor", None)
            return changes or text or self.ticket_pending.get(t["id"]) or (self.post_editing and post_text)

        def save():
            if self.ticket_editing and self.ticket_editor and self.ticket_editor.payload():
                return self.save_ticket_edit()
            if self.ticket_composer and (
                self.ticket_composer.toPlainText().strip() or self.ticket_pending.get(t["id"])
            ):
                return self.post_comment(t)
            return True

        self.draft_reader = reader
        self.draft_save = save

    def start_ticket_edit(self):
        self.ticket_editing = True
        self.release_drafts()
        QTimer.singleShot(0, self.refresh_page)

    def cancel_ticket_edit(self):
        self.ticket_editing = False
        self.ticket_editor = None
        self.release_drafts()
        QTimer.singleShot(0, self.refresh_page)

    def save_ticket_edit(self):
        t = self.ticket_editor.ticket
        try:
            changes = self.ticket_editor.payload()
            if changes:
                self.store.command("ticket.save", {"id": t["id"], **changes})
        except Exception as exc:
            error(self, exc)
            return False
        self.ticket_editing = False
        self.ticket_editor = None
        self.release_drafts()
        self.refresh()
        self.toast.setText("Saved locally")
        return True

    def release_drafts(self):
        self.draft_reader = None
        self.draft_save = None

    # Comments and screenshots -----------------------------------------------------------------

    def attach_image(self, t, image, name="screenshot.png"):
        try:
            prepared = prepare_image(image, name)
        except ValueError as exc:
            error(self, exc)
            return
        pixmap = QPixmap.fromImage(image)
        attachment = {"id": "", **prepared}
        self.ticket_pending.setdefault(t["id"], []).append((attachment, pixmap))
        self.release_drafts()
        QTimer.singleShot(0, self.refresh_page)

    def pick_image(self, t):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Attach images", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        for path in files:
            self.attach_image(t, QImage(path), path.replace("\\", "/").rsplit("/", 1)[-1])

    def paste_image(self, t):
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            self.toast.setText("The clipboard has no image. Take a screenshot first, then paste.")
            return
        self.attach_image(t, image, "pasted-screenshot.png")

    def drop_pending(self, t, index):
        pending = self.ticket_pending.get(t["id"], [])
        if 0 <= index < len(pending):
            pending.pop(index)
        self.release_drafts()
        QTimer.singleShot(0, self.refresh_page)

    def post_comment(self, t):
        text = (self.ticket_composer.toPlainText() if self.ticket_composer else "").strip()
        pending = self.ticket_pending.get(t["id"], [])
        if not text and not pending:
            self.toast.setText("Write a comment or attach a screenshot first")
            return False
        body = text or (
            "Attached a screenshot." if len(pending) == 1 else "Attached %d screenshots." % len(pending)
        )
        now = int(time.time() * 1000)
        attachments = [{k: v for k, v in a.items() if k != "id"} | {"created_at": now} for a, _ in pending]
        payload = {
            "post": {
                "ticket_id": t["id"],
                "body": body,
                "author": self.data["account"]["username"],
                "created_at": now,
            },
            "attachments": attachments,
        }
        try:
            self.store.command("post.capture", payload)
        except Exception as exc:
            error(self, exc)
            return False
        self.ticket_drafts.pop(t["id"], None)
        self.ticket_pending.pop(t["id"], None)
        self.release_drafts()
        self.refresh()
        self.toast.setText("Comment posted")
        return True

    def start_post_edit(self, post_id):
        if self.leave_editor():
            self.post_editing = post_id
            QTimer.singleShot(0, self.refresh_page)

    def cancel_post_edit(self):
        self.post_editing = None
        self.release_drafts()
        QTimer.singleShot(0, self.refresh_page)

    def save_post_edit(self, post, text):
        if not text.strip():
            self.toast.setText("A comment needs some text")
            return
        self.post_editing = None
        self.release_drafts()
        self.execute("post.save", {"id": post["id"], "body": text, "edited_at": int(time.time() * 1000)})

    def delete_post(self, post):
        if confirm(
            self,
            "Delete comment",
            "Delete this comment and its screenshots? Ctrl+Z restores it.",
            action="Delete",
        ):
            self.release_drafts()
            if self.execute("post.save", {"id": post["id"], "archived": 1}):
                self.undo_action = lambda: self.execute("post.save", {"id": post["id"], "archived": 0})
                self.toast.setText("Comment deleted · Ctrl+Z to undo")

    def archive_from_page(self, t):
        if confirm(
            self,
            "Archive ticket",
            "Archive " + self.ticket_key(t) + "? It leaves the boards and lists; its history is kept.",
            action="Archive",
        ):
            self.release_drafts()
            if self.execute("ticket.save", {"id": t["id"], "archived": 1}):
                self.undo_action = lambda: self.execute("ticket.save", {"id": t["id"], "archived": 0})
                self.tickets_ticket = None
