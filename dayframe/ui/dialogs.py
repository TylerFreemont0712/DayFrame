"""Compact native modal forms with type-specific layouts and fixed actions."""

import json
from PySide6.QtCore import QDate, QTime, Qt, QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QCheckBox,
    QSpinBox,
    QDateEdit,
    QTimeEdit,
    QToolButton,
    QWidget,
    QDialogButtonBox,
    QButtonGroup,
    QTabWidget,
    QVBoxLayout,
    QComboBox,
)
from ..core import domain as D, planning as P
from .widgets import FormDialog, label, combo, row, button, column
from PySide6.QtGui import QShortcut, QKeySequence
from .theme import CURRENT as C
from .labels import LabelsEditor, label_choices
from .status import add_status_icons


def form_layout():
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(10)
    form.setVerticalSpacing(7)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    return form


class AddDialog(FormDialog):
    """Title-first capture with optional organization and repeat-entry workflow."""

    def __init__(self, parent, snapshot, kind="ticket", project_id=None, existing=None, defaults=None):
        super().__init__(parent, "Event details" if existing else "Quick add")
        self.resize(520, 350)
        self.snapshot = snapshot
        self.existing = existing or {}
        self.archive_requested = False
        self.submit_handler = None
        self.saved_count = 0
        self.preset_label = ""
        self.projects = snapshot["project"]
        values = {**(defaults or {}), **self.existing}
        self.values = values
        self.kind = combo([(k, k.title()) for k in ("ticket", "event")], kind)
        self.kind.hide()
        self.kind.setParent(self.content)
        self.kind.setAccessibleName("Item type")
        self.heading = label("", "captureHeading")
        self.type_buttons = {}
        group = QButtonGroup(self)
        choices = []
        for name, glyph in (("ticket", "ticket-alt"), ("event", "calendar-alt")):
            choice = button(
                name.title(),
                lambda checked=False, n=name: self.kind.setCurrentIndex(self.kind.findData(n)),
                glyph,
            )
            choice.setCheckable(True)
            choice.setObjectName("captureChoice")
            choice.setEnabled(not bool(existing))
            group.addButton(choice)
            self.type_buttons[name] = choice
            choices.append(choice)
        self.layout.addWidget(row(self.heading, None, *choices))
        self.title = QLineEdit(values.get("title", ""))
        self.title.setObjectName("captureTitle")
        self.title.setAccessibleName("Title")
        self.layout.addWidget(self.title)
        self.form = form_layout()
        self.layout.addLayout(self.form)
        self.project = combo(
            [(p["id"], p["name"]) for p in self.projects if not p["archived"]],
            values.get("project_id", project_id),
        )
        self.project.setAccessibleName("Project")
        self.form.addRow("Project", self.project)
        self.preset = combo(
            [
                ("", "Blank ticket"),
                ("task", "Task"),
                ("bug", "Bug"),
                ("feature", "Feature"),
                ("maintenance", "Maintenance"),
            ]
        )
        self.preset.setAccessibleName("Ticket preset")
        self.form.addRow("Preset", self.preset)
        self.status = add_status_icons(
            combo([(k, D.STATUS_NAMES[k]) for k in D.STATUSES], values.get("status", "inbox"))
        )
        self.status.setAccessibleName("Initial status")
        self.priority = combo([(x, x.title()) for x in D.PRIORITIES], values.get("priority", "medium"))
        self.priority.setAccessibleName("Priority")
        self.workflow_row = row(self.status, label("Priority", "muted"), self.priority)
        self.form.addRow("Status", self.workflow_row)
        self.dated = QCheckBox("Deadline")
        self.dated.setChecked(bool(values.get("due_date")))
        day = values.get("date") or values.get("due_date") or D.day_key(snapshot["settings"]["timezone"])
        self.date = QDateEdit(QDate.fromString(day, "yyyy-MM-dd"))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setAccessibleName("Start date")
        today = button("Today", lambda: self.set_date_offset(0))
        tomorrow = button("Tomorrow", lambda: self.set_date_offset(1))
        today.setToolTip("Use today's date")
        tomorrow.setToolTip("Use tomorrow's date")
        self.date_row = row(self.dated, self.date, None, today, tomorrow)
        self.date_label = label("Date")
        self.form.addRow(self.date_label, self.date_row)
        self.pin_today = QCheckBox("Pin to Today")
        self.pin_today.setChecked(bool(values.get("pinned")) if kind == "ticket" else False)
        self.form.addRow("", self.pin_today)
        self.more = QToolButton()
        self.more.setText("More ticket details")
        self.more.setCheckable(True)
        self.more.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.more.setArrowType(Qt.RightArrow)
        self.form.addRow("", self.more)
        self.ticket_details = QWidget()
        advanced = QVBoxLayout(self.ticket_details)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(5)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.tabBar().setDrawBase(False)
        advanced.addWidget(self.detail_tabs)
        details, dl = column(margins=5, spacing=5)
        self.ticket_description = QPlainTextEdit(values.get("description", ""))
        self.ticket_description.setPlaceholderText("Describe the outcome, context, or acceptance criteria…")
        self.ticket_description.setFixedHeight(74)
        dl.addWidget(self.ticket_description)
        self.estimate = QSpinBox()
        self.estimate.setRange(0, 100000)
        self.estimate.setSuffix(" min")
        self.estimate.setValue(int(values.get("estimate_min", 0)))
        self.estimate.setAccessibleName("Estimate")
        dl.addWidget(row(label("Estimate", "muted"), self.estimate, None))
        self.detail_tabs.addTab(details, "Details")
        organization, ol = column(margins=5)
        f = form_layout()
        ol.addLayout(f)
        self.labels = LabelsEditor(", ".join(values.get("labels", [])), label_choices(snapshot))
        self.labels.setAccessibleName("Labels")
        self.form.insertRow(self.form.getWidgetPosition(self.pin_today)[0], "Labels", self.labels)
        self.labels.labelsChanged.connect(
            lambda _: QTimer.singleShot(0, self.fit_to_contents) if self.isVisible() else None
        )
        self.component = QLineEdit(values.get("component", ""))
        self.component.setPlaceholderText("Component")
        self.milestone = QLineEdit(values.get("milestone", ""))
        self.milestone.setPlaceholderText("Milestone")
        f.addRow("Group", row(self.component, self.milestone))
        self.parent_ticket = combo([("", "No parent")])
        self.parent_ticket.setAccessibleName("Parent ticket")
        f.addRow("Parent", self.parent_ticket)
        self.section = combo([("", "Automatic / Unsorted")])
        self.section.setAccessibleName("Map section")
        f.addRow("Map", self.section)
        self.detail_tabs.addTab(organization, "Organization")
        checklist, cl = column(margins=5)
        self.checklist = QPlainTextEdit("\n".join(x["text"] for x in values.get("checklist", [])))
        self.checklist.setPlaceholderText("One checklist step per line")
        self.checklist.setFixedHeight(105)
        cl.addWidget(self.checklist)
        self.detail_tabs.addTab(checklist, "Checklist")
        self.form.addRow("", self.ticket_details)
        self.event_type = combo(
            [(k, n) for k, n, color in P.EVENT_TYPES], values.get("event_type", "appointment")
        )
        self.form.addRow("Event type", self.event_type)
        self.end_date = QDateEdit(QDate.fromString(values.get("end_date") or day, "yyyy-MM-dd"))
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setAccessibleName("End date")
        self.form.addRow("Through", self.end_date)
        self.timed = QCheckBox("Scheduled time")
        self.timed.setChecked(
            bool(values.get("start_time")) if existing else not values.get("all_day", False)
        )
        self.form.addRow("", self.timed)
        self.start = QTimeEdit(QTime.fromString(values.get("start_time") or "09:00", "HH:mm"))
        self.end = QTimeEdit(QTime.fromString(values.get("end_time") or "10:00", "HH:mm"))
        for w, name in ((self.start, "Start time"), (self.end, "End time")):
            w.setDisplayFormat("HH:mm")
            w.setAccessibleName(name)
        self.time_row = row(self.start, label("to", "muted"), self.end, None)
        self.form.addRow("Time", self.time_row)
        self.location = QLineEdit(values.get("location", ""))
        self.location.setPlaceholderText("Place or meeting link")
        self.form.addRow("Location", self.location)
        self.description = QPlainTextEdit(values.get("description", ""))
        self.description.setPlaceholderText("Event details…")
        self.description.setFixedHeight(65)
        self.form.addRow("Details", self.description)
        self.color = combo(
            [("", "Use event type color")] + [(c, n) for k, n, c in P.EVENT_TYPES], values.get("color", "")
        )
        if values.get("color") and self.color.findData(values["color"]) < 0:
            self.color.addItem(values["color"], values["color"])
            self.color.setCurrentIndex(self.color.count() - 1)
        self.form.addRow("Color", self.color)
        self.yearly = QCheckBox("Repeat every year")
        self.yearly.setChecked(
            values.get("recurrence") == "yearly" or (not existing and values.get("event_type") == "birthday")
        )
        self.form.addRow("Repeat", self.yearly)
        self.major = QCheckBox("Major event")
        self.major.setChecked(bool(values.get("major")))
        self.pin = QCheckBox("Pin countdown")
        self.pin.setChecked(bool(values.get("pinned")))
        self.countdown_row = row(self.major, self.pin, None)
        self.form.addRow("Home", self.countdown_row)
        self.series_hint = label(
            "Yearly edits affect the series. All-day end dates include the final day.", "muted"
        )
        self.series_hint.setWordWrap(True)
        self.form.addRow("", self.series_hint)
        self.summary = label("", "muted")
        self.summary.setWordWrap(True)
        self.layout.addWidget(self.summary)
        self.feedback = label("", "captureError")
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        self.layout.addWidget(self.feedback)
        self.finish_form()
        self.create_another = self.buttons.addButton("Add + another", QDialogButtonBox.ActionRole)
        self.create_another.clicked.connect(lambda: self.submit(True))
        self.create_another.hide()
        self.create_another.setToolTip("Save and keep this form open with the same project and options")
        if existing:
            archive = self.buttons.addButton("Archive event", QDialogButtonBox.ActionRole)
            archive.clicked.connect(self.request_archive)
        self.kind.currentIndexChanged.connect(self.visibility)
        self.more.toggled.connect(self.visibility)
        self.dated.toggled.connect(self.visibility)
        self.timed.toggled.connect(self.visibility)
        self.major.toggled.connect(self.countdown_changed)
        self.date.dateChanged.connect(self.start_date_changed)
        self.event_type.currentIndexChanged.connect(self.type_changed)
        self.project.currentIndexChanged.connect(self.project_changed)
        self.parent_ticket.currentIndexChanged.connect(self.update_summary)
        self.section.currentIndexChanged.connect(self.update_summary)
        for w in (self.labels, self.component, self.milestone):
            w.textChanged.connect(self.update_summary)
        self.status.currentIndexChanged.connect(self.update_summary)
        self.priority.currentIndexChanged.connect(self.update_summary)
        self.preset.currentIndexChanged.connect(self.apply_preset)
        self.project_changed(initial=True)
        if values.get("more") or values.get("parent_id") or values.get("section_id"):
            self.more.setChecked(True)
            self.detail_tabs.setCurrentIndex(1)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.accept)
        for w in self.findChildren(QWidget):
            if isinstance(w, (QLineEdit, QComboBox, QSpinBox, QPlainTextEdit)):
                w.setMinimumWidth(0)
        self.visibility()
        self.title.setFocus()

    def set_submit_handler(self, callback):
        self.submit_handler = callback
        self.create_another.setVisible(bool(callback) and not self.existing)

    def request_archive(self):
        self.archive_requested = True
        self.reject()

    def set_date_offset(self, offset):
        today = QDate.fromString(D.day_key(self.snapshot["settings"]["timezone"]), "yyyy-MM-dd")
        self.date.setDate(today.addDays(offset))
        if self.kind.currentData() == "ticket":
            self.dated.setChecked(True)

    def start_date_changed(self, day):
        if self.end_date.date() < day:
            self.end_date.setDate(day)

    def type_changed(self):
        if not self.existing and self.event_type.currentData() == "birthday":
            self.timed.setChecked(False)
            self.yearly.setChecked(True)

    def countdown_changed(self):
        if self.pin.isChecked() and not self.major.isChecked():
            self.pin.setChecked(False)
        self.pin.setEnabled(self.major.isChecked())

    def project_changed(self, *_, initial=False):
        project = self.project.currentData()
        self.labels.set_suggestions(label_choices(self.snapshot))
        parent = self.values.get("parent_id", "") if initial else self.parent_ticket.currentData()
        section = self.values.get("section_id", "") if initial else self.section.currentData()
        self.parent_ticket.blockSignals(True)
        self.parent_ticket.clear()
        self.parent_ticket.addItem("No parent", "")
        for t in self.snapshot.get("ticket", []):
            if t["project_id"] == project and not t["archived"] and t["id"] != self.existing.get("id"):
                self.parent_ticket.addItem(t["title"], t["id"])
        self.parent_ticket.setCurrentIndex(max(0, self.parent_ticket.findData(parent)))
        self.parent_ticket.blockSignals(False)
        self.section.blockSignals(True)
        self.section.clear()
        self.section.addItem("Automatic / Unsorted", "")
        sections = [s for s in self.snapshot.get("section", []) if s["project_id"] == project]
        for s in sections:
            self.section.addItem(" / ".join(x["name"] for x in D.section_path(sections, s["id"])), s["id"])
        self.section.setCurrentIndex(max(0, self.section.findData(section)))
        self.section.blockSignals(False)
        self.update_summary()

    def apply_preset(self):
        preset = self.preset.currentData()
        tags = [
            x.strip() for x in self.labels.text().split(",") if x.strip() and x.strip() != self.preset_label
        ]
        if preset:
            tags.append(preset)
        self.preset_label = preset
        self.labels.setText(", ".join(dict.fromkeys(tags)))
        self.status.setCurrentIndex(self.status.findData("inbox"))
        self.priority.setCurrentIndex(self.priority.findData("high" if preset == "bug" else "medium"))
        self.update_summary()

    def update_summary(self, *_):
        if not hasattr(self, "summary"):
            return
        if self.kind.currentData() == "event":
            self.summary.setText("Choose an event type, dates and optional time. Ctrl+Enter to save.")
            return
        parts = ["Map: " + self.section.currentText()]
        parent = next(
            (t for t in self.snapshot.get("ticket", []) if t["id"] == self.parent_ticket.currentData()), None
        )
        base = {
            "labels": [s.strip() for s in self.labels.text().split(",") if s.strip()],
            "component": self.component.text().strip(),
            "milestone": self.milestone.text().strip(),
        }
        if parent:
            base["labels"] = list(dict.fromkeys(base["labels"] + parent["labels"]))
            for field in ("component", "milestone"):
                if not base[field]:
                    base[field] = parent[field]
            parts.append("Child of " + parent["title"] + "; inherits tags and empty group fields")
        if self.section.currentData():
            patch = D.section_classification(
                self.snapshot.get("section", []), self.section.currentData(), base
            )
            if patch:
                parts.append(
                    "Section sets "
                    + ", ".join(
                        k + "=" + (", ".join(v) if isinstance(v, list) else str(v)) for k, v in patch.items()
                    )
                )
        self.summary.setText(" · ".join(parts))

    def visibility(self, *_):
        event = self.kind.currentData() == "event"
        self.heading.setText("Event details" if self.existing else "New event" if event else "New ticket")
        self.title.setPlaceholderText("Name the event…" if event else "What needs to get done?")
        for k, b in self.type_buttons.items():
            b.setChecked(k == self.kind.currentData())
        for w in (self.project, self.preset, self.workflow_row, self.labels, self.pin_today, self.more):
            self.form.setRowVisible(w, not event)
        self.form.setRowVisible(self.ticket_details, not event and self.more.isChecked())
        self.more.setArrowType(Qt.DownArrow if self.more.isChecked() else Qt.RightArrow)
        self.dated.setVisible(not event)
        self.date.setEnabled(event or self.dated.isChecked())
        self.date_label.setText("From" if event else "Due")
        for w in (
            self.event_type,
            self.end_date,
            self.timed,
            self.location,
            self.description,
            self.color,
            self.yearly,
            self.countdown_row,
            self.series_hint,
        ):
            self.form.setRowVisible(w, event)
        self.form.setRowVisible(self.time_row, event and self.timed.isChecked())
        self.countdown_changed()
        self.buttons.button(QDialogButtonBox.Save).setText(
            "Save changes" if self.existing else "Add event" if event else "Add ticket"
        )
        self.feedback.hide()
        self.update_summary()
        if self.isVisible():
            QTimer.singleShot(0, self.fit_to_contents)

    def payload(self):
        kind = self.kind.currentData()
        p = {"title": self.title.text().strip()}
        if not p["title"]:
            raise ValueError("Enter a title.")
        if kind == "ticket":
            if not self.project.currentData():
                raise ValueError("Create a project before adding a ticket.")
            p.update(
                project_id=self.project.currentData(),
                status=self.status.currentData(),
                priority=self.priority.currentData(),
                estimate_min=self.estimate.value(),
                due_date=self.date.date().toString("yyyy-MM-dd") if self.dated.isChecked() else "",
                pinned=int(self.pin_today.isChecked()),
                description=self.ticket_description.toPlainText(),
                labels=list(dict.fromkeys(s.strip() for s in self.labels.text().split(",") if s.strip())),
                component=self.component.text().strip(),
                milestone=self.milestone.text().strip(),
                parent_id=self.parent_ticket.currentData() or "",
                checklist=[
                    {"text": s.strip(), "done": False}
                    for s in self.checklist.toPlainText().splitlines()
                    if s.strip()
                ],
            )
        else:
            p.update(
                date=self.date.date().toString("yyyy-MM-dd"),
                end_date=self.end_date.date().toString("yyyy-MM-dd"),
                start_time=self.start.time().toString("HH:mm") if self.timed.isChecked() else "",
                end_time=self.end.time().toString("HH:mm") if self.timed.isChecked() else "",
                event_type=self.event_type.currentData(),
                description=self.description.toPlainText(),
                location=self.location.text().strip(),
                color=self.color.currentData(),
                recurrence="yearly" if self.yearly.isChecked() else "",
                major=int(self.major.isChecked()),
                pinned=int(self.pin.isChecked() and self.major.isChecked()),
            )
        if self.existing:
            p["id"] = self.existing["id"]
        D.validate(kind, {k: v for k, v in p.items() if k != "id"})
        return kind, p

    def submit(self, another=False):
        try:
            kind, payload = self.payload()
            if self.submit_handler:
                if not self.submit_handler(
                    kind, payload, self.section.currentData() if kind == "ticket" else ""
                ):
                    raise ValueError("Could not save. Please try again.")
                self.saved_count += 1
        except Exception as exc:
            self.feedback.setStyleSheet("color:" + C["danger"] + ";")
            self.feedback.setText(str(exc))
            self.feedback.show()
            self.fit_to_contents()
            return
        if another and self.submit_handler and not self.existing:
            self.title.clear()
            self.ticket_description.clear()
            self.description.clear()
            self.checklist.clear()
            self.feedback.setStyleSheet("color:" + C["accent"] + ";")
            self.feedback.setText("Saved. Ready for the next item.")
            self.feedback.show()
            self.title.setFocus()
        else:
            super().accept()

    def accept(self):
        self.submit()


class SectionDialog(FormDialog):
    def __init__(self, parent, existing=None, sections=None, parent_id=""):
        super().__init__(parent, "Edit map section" if existing else "Add map section")
        self.resize(440, 250)
        self.existing = existing or {}
        f = form_layout()
        self.layout.addLayout(f)
        self.name = QLineEdit(self.existing.get("name", ""))
        self.name.setPlaceholderText("e.g. Frontend")
        f.addRow("Section name", self.name)
        self.field = combo(
            [("", "Manual"), ("component", "Component"), ("milestone", "Milestone"), ("label", "Label")],
            self.existing.get("rule_field", ""),
        )
        f.addRow("Automatic rule", self.field)
        self.value = QLineEdit(self.existing.get("rule_value", ""))
        self.value.setPlaceholderText("Match this field value")
        f.addRow("Match value", self.value)
        self.field.currentIndexChanged.connect(lambda: self.value.setEnabled(bool(self.field.currentData())))
        self.value.setEnabled(bool(self.field.currentData()))
        hint = label("Manual placements stay in place until you release them.", "muted")
        hint.setWordWrap(True)
        self.layout.addWidget(hint)
        self.parent_section = None
        if sections is not None:
            current = self.existing.get("id")
            allowed = [
                s for s in sections if current not in [p["id"] for p in D.section_path(sections, s["id"])]
            ]
            self.parent_section = combo(
                [("", "Project root")]
                + [
                    (s["id"], " / ".join(x["name"] for x in D.section_path(sections, s["id"])))
                    for s in allowed
                ],
                self.existing.get("parent_id", parent_id),
            )
            f.addRow("Inside section", self.parent_section)
        self.feedback = label("", "muted")
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        self.layout.addWidget(self.feedback)
        self.finish_form()

    def payload(self):
        p = {
            "name": self.name.text().strip(),
            "rule_field": self.field.currentData(),
            "rule_value": self.value.text().strip() if self.field.currentData() else "",
        }
        if not p["name"]:
            raise ValueError("Enter a section name.")
        if p["rule_field"] and not p["rule_value"]:
            raise ValueError("Enter the value this section should match.")
        if self.parent_section is not None:
            p["parent_id"] = self.parent_section.currentData()
        if self.existing:
            p["id"] = self.existing["id"]
        return p

    def accept(self):
        try:
            self.payload()
        except Exception as exc:
            self.feedback.setText(str(exc))
            self.feedback.show()
            self.fit_to_contents()
            return
        super().accept()


class ConflictDialog(FormDialog):
    def __init__(self, parent, conflict, local):
        super().__init__(parent, "Review sync conflict")
        self.resize(680, 580)
        self.choice = None
        heading = label("Both versions stay preserved until you choose one.", "section")
        heading.setWordWrap(True)
        self.layout.addWidget(heading)
        fields = label("Competing fields: " + ", ".join(conflict["fields"]), "muted")
        fields.setWordWrap(True)
        self.layout.addWidget(fields)
        for title, value in (("This device", local), ("Hub version", conflict["remote"])):
            self.layout.addWidget(label(title, "section"))
            view = QPlainTextEdit(json.dumps(value, indent=2, ensure_ascii=False))
            view.setReadOnly(True)
            view.setMinimumHeight(130)
            self.layout.addWidget(view)
        self.set_footer(
            row(
                button("Keep this device", lambda: self.choose("local")),
                button("Use hub version", lambda: self.choose("remote")),
                None,
                button("Review later", self.reject),
            )
        )

    def choose(self, value):
        self.choice = value
        self.accept()
