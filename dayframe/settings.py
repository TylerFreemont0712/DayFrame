"""Focused settings pages with a shared category menu."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget,
    QFormLayout, QLineEdit, QSpinBox, QCheckBox, QLabel,
)
from .theme import apply_theme, icon
from .widgets import label, button, column, row, panel, scroll, combo


class SettingsPanel(QWidget):
    SECTIONS = (
        ("view", "View", "desktop", "Adjust spacing, text size and your planning time zone."),
        ("theme", "Theme", "palette", "Choose the colors and visual style of DayFrame."),
        ("data", "Local data", "database", "Back up your workspace or load example projects."),
        ("sync", "Sync", "sync-alt", "Connect this device to your private LAN hub and review conflicts."),
        ("account", "Account", "user", "Manage your local password and sign-in."),
    )

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("settingsPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.navigation = QListWidget()
        self.navigation.setObjectName("settingsNavigation")
        self.navigation.setAccessibleName("Settings sections")
        self.navigation.setFixedWidth(168)
        self.navigation.setIconSize(QSize(16, 16))
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pages = QStackedWidget()
        self.pages.setMinimumWidth(0)
        self.pages.setMaximumWidth(820)
        self.fields = {}
        self.section_items = {}
        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        layout.addStretch()
        for key, title, glyph, description in self.SECTIONS:
            item = QListWidgetItem(icon(glyph), title)
            item.setSizeHint(QSize(0, max(40, self.navigation.fontMetrics().height() + 24)))
            item.setData(Qt.UserRole, key)
            item.setToolTip(description)
            self.navigation.addItem(item)
            self.section_items[key] = item
            content, body = column(margins=1, spacing=12)
            body.addWidget(label(title, "captureHeading"))
            hint = label(description, "muted")
            hint.setWordWrap(True)
            body.addWidget(hint)
            getattr(self, "build_" + key)(body)
            body.addStretch()
            for hint in content.findChildren(QLabel):
                if len(hint.text()) > 60:
                    hint.setWordWrap(True)
            page = scroll(content)
            page.setObjectName("settings-" + key)
            page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.pages.addWidget(page)
        self.navigation.currentRowChanged.connect(self.select_section)
        index = next((i for i, section in enumerate(self.SECTIONS)
                      if section[0] == window.settings_section), 0)
        self.navigation.setCurrentRow(index)

    def select_section(self, index):
        if index < 0:
            return
        self.pages.setCurrentIndex(index)
        self.window.settings_section = self.SECTIONS[index][0]

    def form(self, body, title):
        card, layout = panel(title)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setSpacing(8)
        layout.addLayout(form)
        body.addWidget(card)
        return layout, form

    def field(self, form, title, key, widget):
        widget.setAccessibleName(title)
        self.fields[key] = widget
        form.addRow(title, widget)
        return widget

    def build_view(self, body):
        settings = self.window.data["settings"]
        layout, form = self.form(body, "Layout and text")
        self.field(form, "Density", "density", combo(
            [("comfortable", "Comfortable"), ("compact", "Compact")], settings["density"]))
        scale = self.field(form, "Text size", "textScale", QSpinBox())
        scale.setRange(90, 125)
        scale.setSuffix("%")
        scale.setValue(settings["textScale"])
        layout, form = self.form(body, "Date and time")
        zone = self.field(form, "Time zone", "timezone", QLineEdit(settings["timezone"]))
        zone.setPlaceholderText("Asia/Tokyo")
        layout.addWidget(label("Used for the calendar, deadlines and daily time totals.", "muted"))
        body.addWidget(row(button("Apply view settings", lambda: self.save_preferences({
            "density": self.fields["density"].currentData(),
            "textScale": scale.value(), "timezone": zone.text().strip(),
        }), "check", True), None))

    def build_theme(self, body):
        layout, form = self.form(body, "Visual style")
        theme = self.field(form, "Theme", "theme", combo([
            ("graphite", "Graphite / Cyan"), ("amber", "Terminal / Amber"),
            ("light", "Paper / Linen"), ("studio", "Midnight / Studio"),
            ("system", "System"),
        ], self.window.data["settings"]["theme"]))
        layout.addWidget(label("Each theme has its own colors, fonts and shapes. System follows your OS appearance when applied.", "muted"))
        body.addWidget(row(button("Apply theme", lambda: self.save_preferences({
            "theme": theme.currentData(),
        }), "palette", True), None))

    def save_preferences(self, patch):
        # Rebuilding themed icons must not discard entries on the other settings pages.
        values = {key: widget.currentData() if key in ("theme", "density") else
                  widget.value() if key == "textScale" else widget.text()
                  for key, widget in self.fields.items()}
        if not self.window.execute("settings.save", patch, refresh=False):
            return
        apply_theme(self.window.data["settings"])
        self.window.build_shell()
        self.window.refresh()
        for key, value in {**values, **patch}.items():
            widget = self.window.settings_panel.fields[key]
            if key in ("theme", "density"):
                widget.setCurrentIndex(widget.findData(value))
            elif key == "textScale":
                widget.setValue(value)
            else:
                widget.setText(value)

    def build_data(self, body):
        card, layout = panel("Database backup")
        path = label("SQLite storage: " + str(self.window.store.root / "timemanager.db"), "muted")
        path.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(path)
        layout.addWidget(row(button("Back up database", self.window.backup, "database"), None))
        layout.addWidget(label("Backups contain your project data and password verifier. Protect them with your disk or backup encryption.", "muted"))
        body.addWidget(card)
        card, layout = panel("Example workspace")
        layout.addWidget(label("Add example projects and tickets to explore DayFrame.", "muted"))
        layout.addWidget(row(button("Load example workspace", lambda: self.window.execute("examples.load")), None))
        body.addWidget(card)

    def build_sync(self, body):
        settings = self.window.data["settings"]
        layout, form = self.form(body, "Private LAN connection")
        url = self.field(form, "Hub address", "syncUrl", QLineEdit(settings.get("syncUrl", "")))
        url.setPlaceholderText("https://linux-hub:47831")
        fingerprint = self.field(form, "Certificate fingerprint", "syncFingerprint", QLineEdit(settings.get("syncFingerprint", "")))
        fingerprint.setPlaceholderText("SHA-256 of the trusted hub certificate")
        for key, title in (("password", "Account password"), ("setupToken", "Private setup token")):
            widget = self.field(form, title, key, QLineEdit())
            widget.setEchoMode(QLineEdit.Password)
        layout.addWidget(label("Use Connect for an existing hub account; Publish creates this account on your private hub.", "muted"))
        layout.addWidget(row(button("Connect", lambda: self.connect_hub(False), "link"),
                             button("Publish account to hub", lambda: self.connect_hub(True), "upload"), None))
        card, layout = panel("Synchronization")
        enabled = QCheckBox("Automatically sync while the app is open")
        enabled.setChecked(settings.get("syncEnabled", False))
        enabled.toggled.connect(lambda value: self.window.execute("settings.save", {"syncEnabled": value}, refresh=False))
        layout.addWidget(enabled)
        layout.addWidget(row(button("Sync now", self.window.sync_now, "sync-alt"), None))
        layout.addWidget(label(self.window.sync.state.get("error") or
                               "Credentials use the OS keyring when available; otherwise they last for this session.", "muted"))
        body.addWidget(card)
        conflicts = self.window.data["conflicts"]
        if conflicts:
            self.section_items["sync"].setText(f"Sync ({len(conflicts)})")
            card, layout = panel("Sync conflicts · " + str(len(conflicts)))
            for conflict in conflicts:
                details = label(conflict["kind"] + " · " + conflict["entity_id"][:8] +
                                " · " + ", ".join(conflict["fields"]))
                details.setWordWrap(True)
                review = button("Review conflict", lambda checked=False, c=conflict: self.window.review_conflict(c))
                review.setAccessibleName("Review " + conflict["kind"] + " conflict " + conflict["entity_id"][:8])
                layout.addWidget(row(details, review))
            body.addWidget(card)

    def connect_hub(self, publish):
        params = {"url": self.fields["syncUrl"].text().strip(),
                  "fingerprint": self.fields["syncFingerprint"].text().strip(),
                  "password": self.fields["password"].text(),
                  "setupToken": self.fields["setupToken"].text()}
        self.fields["password"].clear()
        self.fields["setupToken"].clear()
        self.window.run_async(lambda: self.window.sync.publish(params) if publish else
                              self.window.sync.connect(params), self.window.sync_finished)

    def build_account(self, body):
        card, layout = panel("Local account")
        layout.addWidget(label("Signed in as " + self.window.data["account"]["username"], "section"))
        layout.addWidget(row(button("Change local password", self.window.change_local_password, "key"),
                             button("Log out", self.window.logout, "sign-out-alt"), None))
        body.addWidget(card)
