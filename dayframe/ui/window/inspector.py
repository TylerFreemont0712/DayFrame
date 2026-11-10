"""Compact read-only ticket inspector, the Edit dialog and work scheduling."""

from __future__ import annotations
from PySide6.QtCore import QDate, Qt, QTime, QTimer
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QGridLayout,
    QMenu,
    QTimeEdit,
)
from ...core import domain as D
from ..status import status_icon
from ..ticket_editor import TicketEditDialog
from ..views.kanban import TicketList
from ..widgets import button, column, ElidingLabel, FormDialog, label, row, scroll


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
        """Compact, read-only ticket summary with the everyday actions; Edit opens the full form."""
        self.clear_layout(self.inspect_layout)
        t = self.find_ticket(self.selected) if self.selected else None
        self.inspector.setVisible(bool(t))
        if not t:
            return
        root, l = column(margins=8, spacing=6)
        edit = button("", lambda: self.edit_ticket(t["id"]), "pen")
        edit.setToolTip("Edit ticket")
        edit.setAccessibleName("Edit ticket")
        close = button("", lambda: self.close_inspector(), "times")
        close.setToolTip("Close")
        close.setAccessibleName("Close inspector")
        for small in (edit, close):
            small.setFixedWidth(30)
        l.addWidget(row(label(self.ticket_key(t), "section"), None, edit, close))
        title = label(t["title"], "inspectorTitle")
        title.setWordWrap(True)
        title.setAccessibleName("Ticket title")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.addWidget(title)
        status = button(D.STATUS_NAMES[t["status"]])
        status.setIcon(status_icon(t["status"]))
        status.setObjectName("statusButton")
        status.setAccessibleName("Ticket status")
        status.setToolTip("Change status")
        menu = QMenu(self)
        for value in D.STATUSES:
            action = menu.addAction(
                status_icon(value), D.STATUS_NAMES[value], lambda v=value: self.set_ticket_status(t, v)
            )
            action.setCheckable(True)
            action.setChecked(value == t["status"])
        status.setMenu(menu)
        priority = label(t["priority"].title(), "count")
        priority.setToolTip("Priority")
        project = ElidingLabel(self.project_name(t["project_id"]), "badge")
        project.setMaximumWidth(130)
        l.addWidget(row(status, priority, project, None))
        if self.blocked(t):
            l.addWidget(label("Blocked · unfinished prerequisites", "warning"))
        facts = QGridLayout()
        facts.setHorizontalSpacing(8)
        facts.setVerticalSpacing(3)
        done = sum(bool(x["done"]) for x in t["checklist"])
        children = [o for o in self.data["ticket"] if o.get("parent_id") == t["id"] and not o["archived"]]
        parent = self.find_ticket(t.get("parent_id")) if t.get("parent_id") else None
        today = D.day_key(self.data["settings"]["timezone"])
        blocks = sorted(
            (b for b in self.data["block"] if b["ticket_id"] == t["id"] and b["date"] >= today),
            key=lambda b: (b["date"], b["start_time"]),
        )
        comments = sum(p["ticket_id"] == t["id"] and not p["archived"] for p in self.data.get("post", []))
        rows = [
            (
                "Due",
                (t["due_date"] or "—")
                + (" · overdue" if t["due_date"] and t["due_date"] < today and t["status"] != "done" else ""),
            ),
            ("Estimate", D.short_time(t["estimate_min"] * 60000)),
            ("Tracked", D.short_time(self.tracked_ms(t["id"]))),
            ("Checklist", str(done) + " / " + str(len(t["checklist"])) if t["checklist"] else "—"),
            ("Parent", self.ticket_key(parent) if parent else "—"),
            ("Children", str(len(children)) if children else "—"),
            (
                "Depends on",
                ", ".join(
                    self.ticket_key(self.find_ticket(x)) for x in t["dependencies"] if self.find_ticket(x)
                )
                or "—",
            ),
            ("Next work", (blocks[0]["date"][5:] + " " + blocks[0]["start_time"]) if blocks else "—"),
            ("Comments", str(comments) if comments else "—"),
        ]
        if self.code_repo(t["project_id"]):
            rows.append(("Changesets", str(self.changeset_count(t["id"])) or "—"))
        for index, (name, value) in enumerate(rows):
            facts.addWidget(label(name, "muted"), index, 0)
            shown = ElidingLabel(value)
            shown.setMinimumWidth(0)
            facts.addWidget(shown, index, 1)
        facts.setColumnStretch(1, 1)
        l.addLayout(facts)
        if t["labels"]:
            l.addWidget(row(*[label(name, "badge") for name in t["labels"][:4]], None))
        summary = t["description"].strip()
        text = label(
            (summary[:260].rstrip() + "…") if len(summary) > 260 else (summary or "No description yet."),
            "muted",
        )
        text.setWordWrap(True)
        text.setAccessibleName("Description")
        l.addWidget(text)
        if t["checklist"]:
            steps = [("✓ " if s["done"] else "○ ") + s["text"] for s in t["checklist"][:5]]
            if len(t["checklist"]) > 5:
                steps.append("+ " + str(len(t["checklist"]) - 5) + " more")
            checklist = label("\n".join(steps), "muted")
            checklist.setWordWrap(True)
            l.addWidget(checklist)
        l.addStretch()
        actions = QGridLayout()
        actions.setSpacing(5)
        more = QMenu(self)
        more.addAction("Archive ticket", lambda: self.archive_ticket(t))
        placement = next((p for p in self.data["placement"] if p["ticket_id"] == t["id"]), None)
        if placement and placement["manual"]:
            more.addAction(
                "Return to automatic placement",
                lambda: self.execute(
                    "placement.save",
                    {"ticket_id": t["id"], "section_id": placement["section_id"], "manual": 0},
                ),
            )
        more_actions = button("More", None, "ellipsis-h")
        more_actions.setMenu(more)
        buttons = [
            button("Edit", lambda: self.edit_ticket(t["id"]), "pen", True),
            button(
                "Track",
                lambda: self.execute("timer.action", {"action": "start", "ticket_id": t["id"]}),
                "play",
            ),
            button("Details", lambda: self.open_ticket_details(t["id"]), "external-link-alt"),
            button("Schedule", lambda: self.schedule_ticket(t), "calendar-plus"),
            button("Code", lambda: self.open_code(t["id"]), "code"),
            more_actions,
        ]
        buttons[4].setToolTip(
            "Open this ticket's changesets on the Code page"
            + (" · " + str(self.changeset_count(t["id"])) + " saved" if self.changeset_count(t["id"]) else "")
        )
        buttons[2].setToolTip("Open the full ticket page with comments and screenshots")
        for index, widget in enumerate(buttons):
            actions.addWidget(widget, index // 2, index % 2)
        l.addLayout(actions)
        self.inspect_layout.addWidget(scroll(root), 1)
        for lane in self.findChildren(TicketList):
            lane.viewport().update()

    def set_ticket_status(self, ticket, status):
        previous = ticket["status"]
        if previous == status:
            return
        if self.execute("ticket.save", {"id": ticket["id"], "status": status}):
            self.undo_action = lambda: self.execute("ticket.save", {"id": ticket["id"], "status": previous})
            self.toast.setText("Moved to " + D.STATUS_NAMES[status] + " · Ctrl+Z to undo")

    def edit_ticket(self, ticket_id):
        ticket = self.find_ticket(ticket_id)
        if not ticket or not self.leave_editor():
            return
        if TicketEditDialog(self, ticket).exec() == QDialog.Accepted:
            self.refresh()
            self.toast.setText("Saved locally")

    def open_ticket(self, ticket_id):
        """Show a ticket in its project with the inspector open, from any page."""
        ticket = self.find_ticket(ticket_id)
        if not ticket or not self.leave_editor():
            return
        self.page = "Projects"
        self.project_id = ticket["project_id"]
        if self.project_view not in ("Map", "Kanban", "Details"):
            self.project_view = "Map"
        self.selected = ticket_id
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
        if existing:
            # Calendar and agenda blocks open here, so this is where they link back to the ticket.
            def jump(target):
                d.reject()
                QTimer.singleShot(0, target)

            links = [
                button(
                    "Open ticket", lambda: jump(lambda: self.open_ticket(ticket["id"])), "external-link-alt"
                )
            ]
            if self.code_repo(ticket["project_id"]):
                links.append(
                    button("Open in Code", lambda: jump(lambda: self.open_code(ticket["id"])), "code")
                )
            d.layout.addWidget(row(*links, None))
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
