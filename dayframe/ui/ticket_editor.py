"""Full ticket editing form, used by the inspector's Edit dialog and the Tickets details page.

TicketEditor holds every editable ticket field and reports only the fields that changed,
so saving never overwrites values another device changed in the meantime.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from ..core import domain as D
from .labels import LabelsEditor, label_choices
from .widgets import FormDialog, button, combo, error, label, row


class TicketEditor(QWidget):
    def __init__(self, window, ticket, wide=False):
        super().__init__()
        self.window = window
        self.ticket = ticket
        data = window.data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.title = QLineEdit(ticket["title"])
        self.title.setAccessibleName("Ticket title")
        self.title.setObjectName("ticketTitle")
        layout.addWidget(self.title)
        candidates = [
            other
            for other in data["ticket"]
            if other["project_id"] == ticket["project_id"]
            and other["id"] != ticket["id"]
            and not other["archived"]
        ]
        self.status = combo([(s, D.STATUS_NAMES[s]) for s in D.STATUSES], ticket["status"])
        self.status.setAccessibleName("Status")
        self.priority = combo([(p, p.title()) for p in D.PRIORITIES], ticket["priority"])
        self.priority.setAccessibleName("Priority")
        self.parent = combo(
            [("", "No parent")] + [(o["id"], o["title"]) for o in candidates], ticket.get("parent_id", "")
        )
        self.parent.setAccessibleName("Parent ticket")
        self.labels = LabelsEditor(", ".join(ticket["labels"]), label_choices(data))
        self.labels.setAccessibleName("Ticket labels")
        self.due = QLineEdit(ticket["due_date"])
        self.due.setPlaceholderText("YYYY-MM-DD")
        self.due.setAccessibleName("Due date")
        self.estimate = QSpinBox()
        self.estimate.setRange(0, 100000)
        self.estimate.setSingleStep(15)
        self.estimate.setValue(int(ticket["estimate_min"]))
        self.estimate.setSuffix(" min")
        self.estimate.setAccessibleName("Estimate")
        self.component = QLineEdit(ticket["component"])
        self.component.setAccessibleName("Component")
        self.milestone = QLineEdit(ticket["milestone"])
        self.milestone.setAccessibleName("Milestone")
        self.pin = QCheckBox("Pin to Today")
        self.pin.setChecked(bool(ticket["pinned"]))
        fields = [
            ("Status", self.status),
            ("Priority", self.priority),
            ("Parent", self.parent),
            ("Due", self.due),
            ("Estimate", self.estimate),
            ("Component", self.component),
            ("Milestone", self.milestone),
            ("", self.pin),
        ]
        if wide:
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            for index, (title, widget) in enumerate(fields):
                grid.addWidget(label(title, "muted"), index // 2, (index % 2) * 2)
                grid.addWidget(widget, index // 2, (index % 2) * 2 + 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
            layout.addLayout(grid)
            labels_form = QFormLayout()
            labels_form.addRow("Labels", self.labels)
            layout.addLayout(labels_form)
        else:
            form = QFormLayout()
            form.setSpacing(6)
            for title, widget in fields[:3]:
                form.addRow(title, widget)
            form.addRow("Labels", self.labels)
            for title, widget in fields[3:]:
                form.addRow(title, widget)
            layout.addLayout(form)
        layout.addWidget(label("Description · Markdown", "section"))
        self.description = QPlainTextEdit(ticket["description"])
        self.description.setPlaceholderText(
            "Describe the work. Markdown is supported: **bold**, lists, `code`, ## headings."
        )
        self.description.setAccessibleName("Description")
        self.description.setMinimumHeight(140 if wide else 90)
        layout.addWidget(self.description, 1)
        layout.addWidget(label("Checklist", "section"))
        self.checklist = QListWidget()
        self.checklist.setObjectName("checklist")
        self.checklist.setAccessibleName("Checklist")
        for step in ticket["checklist"]:
            self.add_step(step["text"], step["done"])
        self.checklist.setMinimumHeight(60)
        self.checklist.setMaximumHeight(150)
        layout.addWidget(self.checklist)
        self.step = QLineEdit()
        self.step.setPlaceholderText("Add a step and press Enter")
        self.step.setAccessibleName("New checklist step")
        self.step.returnPressed.connect(self.add_typed_step)
        remove = button("", self.remove_step, "minus")
        remove.setToolTip("Remove the selected step")
        layout.addWidget(row(self.step, button("", self.add_typed_step, "plus"), remove))
        layout.addWidget(label("Depends on", "section"))
        self.dependencies = QListWidget()
        self.dependencies.setAccessibleName("Prerequisites")
        for other in candidates:
            item = QListWidgetItem(window.ticket_key(other) + "  " + other["title"])
            item.setData(Qt.UserRole, other["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if other["id"] in ticket["dependencies"] else Qt.Unchecked)
            self.dependencies.addItem(item)
        self.dependencies.setMaximumHeight(130)
        layout.addWidget(self.dependencies)

    def add_step(self, text, done=False):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        item.setCheckState(Qt.Checked if done else Qt.Unchecked)
        self.checklist.addItem(item)

    def add_typed_step(self):
        if self.step.text().strip():
            self.add_step(self.step.text().strip())
            self.step.clear()

    def remove_step(self):
        row_index = self.checklist.currentRow()
        if row_index >= 0:
            self.checklist.takeItem(row_index)

    def values(self):
        return {
            "title": self.title.text(),
            "description": self.description.toPlainText(),
            "status": self.status.currentData(),
            "priority": self.priority.currentData(),
            "labels": [s.strip() for s in self.labels.text().split(",") if s.strip()],
            "component": self.component.text(),
            "milestone": self.milestone.text(),
            "due_date": self.due.text().strip(),
            "estimate_min": self.estimate.value(),
            "pinned": int(self.pin.isChecked()),
            "checklist": [
                {
                    "text": self.checklist.item(i).text(),
                    "done": self.checklist.item(i).checkState() == Qt.Checked,
                }
                for i in range(self.checklist.count())
            ],
            "dependencies": [
                self.dependencies.item(i).data(Qt.UserRole)
                for i in range(self.dependencies.count())
                if self.dependencies.item(i).checkState() == Qt.Checked
            ],
            "parent_id": self.parent.currentData(),
        }

    def payload(self):
        """Only the fields that differ from the ticket as it was opened."""
        return D.changes(self.ticket, self.values())


class TicketEditDialog(FormDialog):
    """Modal editor opened from the compact inspector; keeps the board visible behind it."""

    def __init__(self, window, ticket):
        super().__init__(window, "Edit " + window.ticket_key(ticket))
        self.window = window
        self.ticket = ticket
        self.resize(540, 640)
        self.editor = TicketEditor(window, ticket)
        self.layout.addWidget(self.editor)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Save ticket")

    def accept(self):
        changes = self.editor.payload()
        if changes:
            try:
                self.window.store.command("ticket.save", {"id": self.ticket["id"], **changes})
            except Exception as exc:
                error(self, exc)
                return
        super().accept()
