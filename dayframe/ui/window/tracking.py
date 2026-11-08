"""Time page: recorded sessions and the manual time entry dialog."""

from __future__ import annotations
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
)
from datetime import datetime
from ...core import domain as D
from ..widgets import button, combo, FormDialog, label, row


class TimePage:
    def show_time(self):
        self.work_layout.addWidget(
            row(
                label("Recorded sessions · editable manual entries", "muted"),
                None,
                button("Add time", self.manual_time, "plus"),
            )
        )
        entries = sorted(self.data["entry"], key=lambda e: e["start_at"], reverse=True)
        table = QTableWidget(len(entries), 5)
        table.setHorizontalHeaderLabels(["Ticket / activity", "Start", "End", "Duration", "Review"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().hide()
        zone = D.ZoneInfo(self.data["settings"]["timezone"])
        for r, e in enumerate(entries):
            ticket = self.find_ticket(e["ticket_id"])
            overlap = any(
                x["id"] != e["id"] and x["start_at"] < e["end_at"] and x["end_at"] > e["start_at"]
                for x in entries
            )
            values = [
                ticket["title"] if ticket else "Unassigned",
                datetime.fromtimestamp(e["start_at"] / 1000, zone).strftime("%Y-%m-%d %H:%M"),
                datetime.fromtimestamp(e["end_at"] / 1000, zone).strftime("%Y-%m-%d %H:%M"),
                D.short_time(e["end_at"] - e["start_at"]),
                "Overlaps another session" if overlap else "",
            ]
            for c, value in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.cellClicked.connect(lambda r, c: self.manual_time(entries[r]))
        self.work_layout.addWidget(table, 1)

    def manual_time(self, existing=None):
        if isinstance(existing, bool):
            existing = None
        e = existing or {}
        d = FormDialog(self, "Edit time entry" if existing else "Add time")
        f = QFormLayout()
        d.layout.addLayout(f)
        ticket = combo(
            [("", "Unassigned")] + [(t["id"], t["title"]) for t in self.data["ticket"] if not t["archived"]],
            e.get("ticket_id", ""),
        )
        f.addRow("Ticket", ticket)
        zone = D.ZoneInfo(self.data["settings"]["timezone"])
        now = datetime.now(zone)
        start = QDateTimeEdit(
            QDateTime.fromString(
                datetime.fromtimestamp(e.get("start_at", int(now.timestamp() * 1000)) / 1000, zone).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "yyyy-MM-dd HH:mm",
            )
        )
        end = QDateTimeEdit(
            QDateTime.fromString(
                datetime.fromtimestamp(
                    e.get("end_at", int(now.timestamp() * 1000) + 1800000) / 1000, zone
                ).strftime("%Y-%m-%d %H:%M"),
                "yyyy-MM-dd HH:mm",
            )
        )
        for title, w in (("Start", start), ("End", end)):
            w.setDisplayFormat("yyyy-MM-dd HH:mm")
            w.setCalendarPopup(True)
            f.addRow(title, w)
        note = QLineEdit(e.get("note", ""))
        f.addRow("Note", note)
        d.finish_form()
        if d.exec() != QDialog.Accepted:
            return

        def stamp(w):
            return int(
                datetime.strptime(w.dateTime().toString("yyyy-MM-dd HH:mm"), "%Y-%m-%d %H:%M")
                .replace(tzinfo=zone)
                .timestamp()
                * 1000
            )

        payload = {
            "ticket_id": ticket.currentData(),
            "start_at": stamp(start),
            "end_at": stamp(end),
            "note": note.text(),
        }
        if existing:
            payload["id"] = e["id"]
        self.execute("time.add", payload)
