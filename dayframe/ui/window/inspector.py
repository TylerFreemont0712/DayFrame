"""Ticket inspector side panel, draft protection and work scheduling."""

from __future__ import annotations
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QToolButton,
    QWidget,
)
from datetime import datetime
from ...core import domain as D
from ..views.kanban import TicketList
from ..labels import label_choices, LabelsEditor
from ..widgets import button, column, combo, ElidingLabel, error, FormDialog, label, row, scroll


class InspectorMixin:
    def select_ticket(self, ticket_id, rebuild=True):
        if ticket_id != self.selected and not self.leave_editor():
            return
        if ticket_id == self.selected and self.has_draft():
            return
        self.selected = ticket_id
        if self.page == "Today":
            self.refresh_page()
            return
        # Avoid destroying a map item during its mouse event.
        self.render_inspector()

    def render_inspector(self):
        self.clear_layout(self.inspect_layout)
        t = self.find_ticket(self.selected) if self.selected else None
        self.inspector.setVisible(bool(t))
        if not t:
            return
        root, l = column(margins=8, spacing=5)
        header = row(
            label(self.ticket_key(t), "section"), None, button("", lambda: self.close_inspector(), "times")
        )
        l.addWidget(header)
        title = QLineEdit(t["title"])
        title.setAccessibleName("Ticket title")
        title.setObjectName("ticketTitle")
        l.addWidget(title)
        status = combo([(s, D.STATUS_NAMES[s]) for s in D.STATUSES], t["status"])
        status.setToolTip("Workflow status")
        l.addWidget(status)
        if self.blocked(t):
            l.addWidget(label("Blocked · unfinished prerequisites", "warning"))
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setDrawBase(False)
        details, dl = column(spacing=5)
        f = QFormLayout()
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(4)
        dl.addLayout(f)
        priority = combo([(s, s.title()) for s in D.PRIORITIES], t["priority"])
        f.addRow("Priority", priority)
        project_badge = ElidingLabel(self.project_name(t["project_id"]), "badge")
        project_badge.setMaximumWidth(170)
        f.addRow("Project", project_badge)
        candidates = [
            other
            for other in self.data["ticket"]
            if other["project_id"] == t["project_id"] and other["id"] != t["id"] and not other["archived"]
        ]
        parent = combo(
            [("", "No parent")] + [(other["id"], other["title"]) for other in candidates],
            t.get("parent_id", ""),
        )
        f.addRow("Parent", parent)
        children = [other for other in candidates if other.get("parent_id") == t["id"]]
        for child in children:
            child_button = button(
                "Child · " + child["title"], lambda checked=False, c=child: self.select_ticket(c["id"])
            )
            child_button.setObjectName("rowTitle")
            dl.addWidget(child_button)
        labels = LabelsEditor(", ".join(t["labels"]), label_choices(self.data))
        labels.setAccessibleName("Ticket labels")
        f.addRow("Labels", labels)
        due = QLineEdit(t["due_date"])
        due.setPlaceholderText("YYYY-MM-DD")
        f.addRow("Due", due)
        estimate = QSpinBox()
        estimate.setRange(0, 100000)
        estimate.setValue(int(t["estimate_min"]))
        estimate.setSuffix(" min")
        f.addRow("Estimate", estimate)
        f.addRow("Tracked", label(D.short_time(self.tracked_ms(t["id"])), "muted"))
        more = QToolButton()
        more.setText("Component / milestone")
        more.setArrowType(Qt.RightArrow)
        more.setCheckable(True)
        more.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        dl.addWidget(more)
        extra, exl = column()
        exf = QFormLayout()
        exf.setContentsMargins(0, 0, 0, 0)
        exf.setSpacing(4)
        exl.addLayout(exf)
        component = QLineEdit(t["component"])
        milestone = QLineEdit(t["milestone"])
        exf.addRow("Component", component)
        exf.addRow("Milestone", milestone)
        extra.setVisible(False)
        more.toggled.connect(
            lambda checked: (
                extra.setVisible(checked),
                more.setArrowType(Qt.DownArrow if checked else Qt.RightArrow),
            )
        )
        dl.addWidget(extra)
        description = QPlainTextEdit(t["description"])
        description.setPlaceholderText("Description")
        description.setMinimumHeight(45)
        description.setMaximumHeight(64)
        dl.addWidget(description)
        pin = QCheckBox("Pin to Today")
        pin.setChecked(bool(t["pinned"]))
        dl.addWidget(pin)
        done = sum(bool(x["done"]) for x in t["checklist"])
        dl.addWidget(label("Checklist  " + str(done) + " / " + str(len(t["checklist"])), "section"))
        checklist = QListWidget()
        checklist.setObjectName("checklist")
        for step in t["checklist"]:
            item = QListWidgetItem(step["text"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            item.setCheckState(Qt.Checked if step["done"] else Qt.Unchecked)
            checklist.addItem(item)
        checklist.setMinimumHeight(28)
        checklist.setMaximumHeight(min(90, max(28, len(t["checklist"]) * 23 + 4)))
        dl.addWidget(checklist)
        step_edit = QLineEdit()
        step_edit.setPlaceholderText("Add a step…")

        def add_step():
            if step_edit.text().strip():
                item = QListWidgetItem(step_edit.text().strip())
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
                item.setCheckState(Qt.Unchecked)
                checklist.addItem(item)
                step_edit.clear()
                checklist.setMaximumHeight(min(90, checklist.count() * 23 + 4))

        step_edit.returnPressed.connect(add_step)
        dl.addWidget(row(step_edit, button("", add_step, "plus")))
        dep_ids = list(t["dependencies"])
        dep_summary = label(
            "Depends on "
            + (
                ", ".join(self.ticket_key(self.find_ticket(x)) for x in dep_ids if self.find_ticket(x)) or "—"
            ),
            "muted",
        )
        dep_summary.setWordWrap(True)

        def edit_dependencies():
            d = FormDialog(self, "Ticket prerequisites")
            d.resize(400, 320)
            options = QListWidget()
            options.setMinimumHeight(150)
            for other in self.data["ticket"]:
                if other["id"] == t["id"] or other["project_id"] != t["project_id"] or other["archived"]:
                    continue
                item = QListWidgetItem(other["title"])
                item.setData(Qt.UserRole, other["id"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if other["id"] in dep_ids else Qt.Unchecked)
                options.addItem(item)
            d.layout.addWidget(options)
            d.finish_form()
            if d.exec() == QDialog.Accepted:
                dep_ids[:] = [
                    options.item(i).data(Qt.UserRole)
                    for i in range(options.count())
                    if options.item(i).checkState() == Qt.Checked
                ]
                dep_summary.setText(
                    "Depends on "
                    + (
                        ", ".join(
                            self.ticket_key(self.find_ticket(x)) for x in dep_ids if self.find_ticket(x)
                        )
                        or "—"
                    )
                )

        dl.addWidget(row(dep_summary, None, button("", edit_dependencies, "link")))
        dl.addStretch()
        tabs.addTab(scroll(details), "Details")
        log, ll = column(margins=6)
        for e in sorted(
            [e for e in self.data["entry"] if e["ticket_id"] == t["id"]],
            key=lambda e: e["start_at"],
            reverse=True,
        ):
            ll.addWidget(
                button(
                    datetime.fromtimestamp(
                        e["start_at"] / 1000, D.ZoneInfo(self.data["settings"]["timezone"])
                    ).strftime("%b %d %H:%M")
                    + " · "
                    + D.short_time(e["end_at"] - e["start_at"]),
                    lambda checked=False, e=e: self.manual_time(e),
                    "clock",
                )
            )
        ll.addStretch()
        tabs.addTab(scroll(log), "Time")
        l.addWidget(tabs, 1)

        def payload():
            result = {
                "title": title.text(),
                "description": description.toPlainText(),
                "status": status.currentData(),
                "priority": priority.currentData(),
                "labels": [s.strip() for s in labels.text().split(",") if s.strip()],
                "component": component.text(),
                "milestone": milestone.text(),
                "due_date": due.text().strip(),
                "estimate_min": estimate.value(),
                "pinned": int(pin.isChecked()),
                "checklist": [
                    {"text": checklist.item(i).text(), "done": checklist.item(i).checkState() == Qt.Checked}
                    for i in range(checklist.count())
                ],
                "dependencies": list(dep_ids),
                "parent_id": parent.currentData(),
            }
            return D.changes(t, result)

        def save():
            try:
                self.store.command("ticket.save", {"id": t["id"], **payload()})
            except Exception as exc:
                error(self, exc)
                return False
            self.draft_reader = None
            self.draft_save = None
            self.refresh()
            return True

        self.draft_reader = payload
        self.draft_save = save
        l.addWidget(
            row(
                button("Save ticket", save, "save", True),
                button(
                    "Track",
                    lambda: self.execute("timer.action", {"action": "start", "ticket_id": t["id"]}),
                    "play",
                ),
            )
        )
        l.addWidget(
            row(
                button("Full details", lambda: self.open_details(t), "external-link-alt"),
                button("Schedule", lambda: self.schedule_ticket(t), "calendar-plus"),
            )
        )
        menu = QMenu(self)
        menu.addAction("Archive ticket", lambda: self.archive_ticket(t))
        placement = next((p for p in self.data["placement"] if p["ticket_id"] == t["id"]), None)
        if placement and placement["manual"]:
            menu.addAction(
                "Return to automatic placement",
                lambda: self.execute(
                    "placement.save",
                    {"ticket_id": t["id"], "section_id": placement["section_id"], "manual": 0},
                ),
            )
        more_actions = button("More actions")
        more_actions.setMenu(menu)
        l.addWidget(more_actions)
        self.inspect_layout.addWidget(root, 1)
        for field in details.findChildren(QWidget):
            if isinstance(field, (QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QListWidget)):
                field.setMinimumWidth(0)
                field.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        for lane in self.findChildren(TicketList):
            lane.viewport().update()

    def open_details(self, t):
        if not self.leave_editor():
            return
        self.page = "Projects"
        self.project_id = t["project_id"]
        self.project_view = "Details"
        self.refresh_page()

    def close_inspector(self):
        if self.leave_editor():
            self.selected = None
            self.render_inspector()

    def archive_ticket(self, t):
        if self.execute("ticket.save", {"id": t["id"], "archived": 1}):
            self.close_inspector()

    def schedule_ticket(self, ticket, existing=None):
        if not self.leave_editor():
            return
        d = FormDialog(self, "Schedule ticket work")
        d.resize(440, 250)
        d.layout.addWidget(label(ticket["title"], "section"))
        f = QFormLayout()
        f.setSpacing(6)
        d.layout.addLayout(f)
        day = QDateEdit(
            QDate.fromString(
                (existing or {}).get("date", D.day_key(self.data["settings"]["timezone"])), "yyyy-MM-dd"
            )
        )
        day.setDisplayFormat("yyyy-MM-dd")
        day.setCalendarPopup(True)
        f.addRow("Date", day)
        start = QTimeEdit(QTime.fromString((existing or {}).get("start_time", "09:00"), "HH:mm"))
        end = QTimeEdit(QTime.fromString((existing or {}).get("end_time", "10:00"), "HH:mm"))
        start.setDisplayFormat("HH:mm")
        end.setDisplayFormat("HH:mm")
        f.addRow("Work session", row(start, label("to", "muted"), end))
        hint = label("Ticket deadline stays " + (ticket["due_date"] or "unset") + ".", "muted")
        hint.setWordWrap(True)
        d.layout.addWidget(hint)
        d.finish_form()
        if d.exec() == QDialog.Accepted:
            payload = {
                "ticket_id": ticket["id"],
                "date": day.date().toString("yyyy-MM-dd"),
                "start_time": start.time().toString("HH:mm"),
                "end_time": end.time().toString("HH:mm"),
            }
            if existing:
                payload["id"] = existing["id"]
            self.execute("block.save", payload)
