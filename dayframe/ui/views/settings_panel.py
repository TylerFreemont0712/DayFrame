"""Focused settings pages with a shared category menu."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QLabel,
    QComboBox,
    QGridLayout,
    QMenu,
    QToolButton,
)
from ...core import preferences as PREFS
from ...core import timezones as TZ
from ...core.palettes import (
    ADVANCED_ROLES,
    CORE_ROLES,
    CUSTOM,
    THEME_IDS,
    THEMES,
    default_scheme,
    palette,
    scheme_colors,
    schemes,
    theme_label,
)
from ..color_picker import ColorSwatchButton, PalettePreview
from ..theme import SUGGESTED_MONO_FONTS, SUGGESTED_UI_FONTS, apply_theme, icon, installed_families
from ..widgets import label, button, column, row, panel, scroll, combo
from ..zone_picker import ZonePicker

WINDOW_SIZES = ((1280, 800), (1440, 900), (1600, 1000))


def swatch(colors, size=16):
    """Small icon showing a scheme's background beside its accent."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, size // 2, size, QColor(colors["bg"]))
    painter.fillRect(size // 2, 0, size - size // 2, size, QColor(colors["accent"]))
    painter.setPen(QColor(colors["line"]))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return QIcon(pixmap)


def font_choices(suggested):
    """("", "Theme default") first, then installed suggestions, then every other installed family."""
    installed = installed_families()
    first = [installed[name.casefold()] for name in suggested if name.casefold() in installed]
    rest = sorted((name for name in installed.values() if name not in first), key=str.casefold)
    return [("", "Theme default")] + [(name, name) for name in dict.fromkeys(first + rest)]


def font_combo(suggested, current):
    box = combo(font_choices(suggested))
    for index in range(1, box.count()):
        if box.itemData(index) in suggested:
            box.setItemData(index, QFont(box.itemData(index)), Qt.FontRole)
    if current and box.findData(current) < 0:
        box.addItem(current + " (not installed)", current)
    box.setCurrentIndex(max(0, box.findData(current or "")))
    box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(16)
    box.setMaxVisibleItems(18)
    return box


def read_field(widget):
    if isinstance(widget, ZonePicker):
        return widget.zone()
    if isinstance(widget, QComboBox):
        return widget.currentData()
    if isinstance(widget, QSpinBox):
        return widget.value()
    return widget.text()


def write_field(widget, value):
    if value is None:
        return
    if isinstance(widget, ZonePicker):
        widget.set_zone(value)
    elif isinstance(widget, QComboBox):
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)
    elif isinstance(widget, QSpinBox):
        widget.setValue(value)
    else:
        widget.setText(value)


class SettingsPanel(QWidget):
    SECTIONS = (
        (
            "view",
            "View",
            "desktop",
            "Adjust text size, spacing, panel sizes, your time zone and world clocks.",
        ),
        ("theme", "Theme", "palette", "Choose the theme, colors, corners and fonts of DayFrame."),
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
        index = next(
            (i for i, section in enumerate(self.SECTIONS) if section[0] == window.settings_section), 0
        )
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

    def spin(self, form, title, key, value, bounds, step, suffix=""):
        box = self.field(form, title, key, QSpinBox())
        box.setRange(*bounds)
        box.setSingleStep(step)
        box.setSuffix(suffix)
        box.setValue(value)
        return box

    # View ---------------------------------------------------------------------------------

    def build_view(self, body):
        settings = self.window.data["settings"]
        layout, form = self.form(body, "Text and spacing")
        self.spin(form, "Text size", "textScale", settings["textScale"], PREFS.TEXT_SCALE, 5, "%")
        self.spin(
            form, "Heading size", "headingScale", settings["headingScale"], PREFS.HEADING_SCALE, 10, "%"
        )
        self.field(form, "Density", "density", combo(PREFS.DENSITIES, settings["density"]))
        layout.addWidget(
            label(
                "90% is the standard text size. Density changes the padding inside controls and lists.",
                "muted",
            )
        )
        layout, form = self.form(body, "Panels and window")
        self.spin(form, "Projects pane", "sidebarWidth", settings["sidebarWidth"], (140, 280), 10, " px")
        self.spin(
            form, "Ticket inspector", "inspectorWidth", settings["inspectorWidth"], (240, 420), 10, " px"
        )
        sizes = [
            button("%d × %d" % size, lambda checked=False, s=size: self.resize_window(*s), "expand")
            for size in WINDOW_SIZES
        ]
        sizes.append(button("Maximize", self.window.showMaximized, "expand-arrows-alt"))
        for widget in sizes:
            widget.setAccessibleName("Window size " + widget.text())
        form.addRow("Window size", row(*sizes[:2], None))
        form.addRow("", row(*sizes[2:], None))
        layout.addWidget(label("Window sizes apply immediately and are limited to your screen.", "muted"))
        layout, form = self.form(body, "Date and time")
        zone = self.field(form, "Time zone", "timezone", ZonePicker(settings["timezone"]))
        self.zone_now = label("", "muted")
        form.addRow("", self.zone_now)
        zone.currentIndexChanged.connect(self.show_zone_time)
        zone.editTextChanged.connect(self.show_zone_time)
        clocks = list(settings.get("worldClocks", [])) + [""] * PREFS.MAX_WORLD_CLOCKS
        for index in range(PREFS.MAX_WORLD_CLOCKS):
            self.field(
                form, "World clock %d" % (index + 1), "worldClock%d" % index, ZonePicker(clocks[index], True)
            )
        layout.addWidget(
            label(
                "The time zone sets the calendar, deadlines and daily totals. World clocks show the "
                "current time in other places in the bottom bar. Type a city or a UTC offset to search.",
                "muted",
            )
        )
        self.show_zone_time()
        body.addWidget(row(button("Apply view settings", self.apply_view, "check", True), None))

    def show_zone_time(self):
        zone = self.fields["timezone"].zone()
        self.zone_now.setText("Now: " + TZ.describe(zone) if PREFS.valid_zone(zone) else "Unknown time zone")

    def resize_window(self, width, height):
        screen = self.window.screen().availableGeometry()
        self.window.showNormal()
        self.window.resize(min(width, screen.width() - 20), min(height, screen.height() - 40))

    def apply_view(self):
        clocks = [self.fields["worldClock%d" % index].zone() for index in range(PREFS.MAX_WORLD_CLOCKS)]
        self.save_preferences(
            {
                "density": self.fields["density"].currentData(),
                "textScale": self.fields["textScale"].value(),
                "headingScale": self.fields["headingScale"].value(),
                "sidebarWidth": self.fields["sidebarWidth"].value(),
                "inspectorWidth": self.fields["inspectorWidth"].value(),
                "timezone": self.fields["timezone"].zone(),
                "worldClocks": list(dict.fromkeys(zone for zone in clocks if zone)),
            }
        )

    # Theme --------------------------------------------------------------------------------

    def build_theme(self, body):
        settings = self.window.data["settings"]
        layout, form = self.form(body, "Visual style")
        theme = self.field(
            form, "Theme", "theme", combo([(key, theme_label(key)) for key in THEME_IDS], settings["theme"])
        )
        self.field(form, "Corners", "cornerRadius", combo(PREFS.CORNER_STYLES, settings["cornerRadius"]))
        layout.addWidget(
            label(
                "Each theme has its own fonts, shapes and surfaces. System follows your OS appearance when applied.",
                "muted",
            )
        )
        # Each theme remembers its own scheme and custom colors, so switching themes never loses a choice.
        self.pending_colors = dict(settings.get("themeColors", {}))
        self.pending_custom = {k: dict(v) for k, v in settings.get("customColors", {}).items()}
        layout, form = self.form(body, "Colors")
        self.color_title = layout.itemAt(0).widget()
        self.color_form = form
        self.color_scheme = self.field(form, "Color scheme", "themeColor", QComboBox())
        self.color_hint = label("", "muted")
        layout.addWidget(self.color_hint)
        self.preview = PalettePreview()
        layout.addWidget(self.preview)
        self.build_custom_editor(layout)
        theme.currentIndexChanged.connect(self.show_color_schemes)
        self.color_scheme.currentIndexChanged.connect(self.remember_color_scheme)
        layout, form = self.form(body, "Fonts")
        self.field(form, "Interface", "fontFamily", font_combo(SUGGESTED_UI_FONTS, settings["fontFamily"]))
        self.field(
            form, "Headings", "headingFamily", font_combo(SUGGESTED_UI_FONTS, settings["headingFamily"])
        )
        self.field(
            form, "Numbers and clocks", "monoFamily", font_combo(SUGGESTED_MONO_FONTS, settings["monoFamily"])
        )
        layout.addWidget(
            label(
                "Theme default uses the theme's own font, falling back to an installed one. "
                "Suggested fonts are listed first when they are installed.",
                "muted",
            )
        )
        self.show_color_schemes()
        body.addWidget(row(button("Apply theme", self.apply_theme_settings, "palette", True), None))

    def build_custom_editor(self, layout):
        self.custom_editor, editor = column(spacing=6)
        editor.addWidget(label("Custom colors", "section"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.role_buttons = {}
        self.role_values = {}
        for index, (role, title) in enumerate(CORE_ROLES):
            self._color_row(grid, index // 2, (index % 2) * 3, role, title)
        grid.setColumnMinimumWidth(2, 24)
        grid.setColumnStretch(5, 1)
        editor.addLayout(grid)
        start = QToolButton()
        start.setText("Start from a scheme")
        start.setPopupMode(QToolButton.InstantPopup)
        start.setIcon(icon("fill-drip"))
        start.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.start_menu = QMenu(start)
        start.setMenu(self.start_menu)
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Advanced colors")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        editor.addWidget(row(start, self.advanced_toggle, None))
        self.advanced, advanced = column(spacing=4)
        advanced.addWidget(
            label("Override individual elements. Automatic follows the matching main color above.", "muted")
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.reset_buttons = {}
        for index, (role, title, _) in enumerate(ADVANCED_ROLES):
            self._color_row(grid, index, 0, role, title, resettable=True)
        advanced.addLayout(grid)
        self.advanced.setVisible(False)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        editor.addWidget(self.advanced)
        layout.addWidget(self.custom_editor)

    def _color_row(self, grid, line, column_, role, title, resettable=False):
        def swatches():
            colors = self.current_palette()
            return [(name, colors[key]) for key, name in CORE_ROLES]

        picker = ColorSwatchButton("#000000", title, swatches)
        picker.colorPicked.connect(lambda color, r=role: self.set_custom_color(r, color))
        self.role_buttons[role] = picker
        grid.addWidget(label(title), line, column_)
        grid.addWidget(picker, line, column_ + 1)
        if resettable:
            # Only advanced rows show their value ("Automatic" or the chosen color).
            value = label("", "muted")
            self.role_values[role] = value
            grid.addWidget(value, line, column_ + 2)
            reset = button("", lambda checked=False, r=role: self.reset_custom_color(r), "undo")
            reset.setObjectName("iconOnly")
            reset.setToolTip("Use automatic color")
            reset.setAccessibleName("Reset " + title)
            self.reset_buttons[role] = reset
            grid.addWidget(reset, line, column_ + 3)
            grid.setColumnMinimumWidth(column_ + 2, 70)
            grid.setColumnStretch(column_ + 4, 1)
        else:
            picker.setToolTip(title)

    def _toggle_advanced(self, checked):
        self.advanced.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def chosen_theme(self):
        return self.fields["theme"].currentData()

    def current_palette(self):
        theme = self.chosen_theme()
        if theme not in THEMES:
            return palette("graphite")
        scheme = self.pending_colors.get(theme) or default_scheme(theme)
        return palette(theme, scheme, self.pending_custom.get(theme))

    def show_color_schemes(self):
        """List the color schemes of the theme currently chosen in the Theme box."""
        theme = self.chosen_theme()
        options = schemes(theme)
        chosen = self.pending_colors.get(theme) or (default_scheme(theme) if options else None)
        scheme = self.color_scheme
        scheme.blockSignals(True)
        scheme.clear()
        for key, name in options:
            scheme.addItem(swatch(scheme_colors(theme, key)), name, key)
        if options:
            scheme.insertSeparator(scheme.count())
            scheme.addItem(swatch(palette(theme, CUSTOM, self.pending_custom.get(theme))), "Custom…", CUSTOM)
        scheme.setCurrentIndex(scheme.findData(chosen))
        scheme.blockSignals(False)
        self.color_form.setRowVisible(scheme, bool(options))
        self.preview.setVisible(bool(options))
        if options:
            self.color_title.setText(theme_label(theme) + " colors")
            self.color_hint.setText(
                "Changes only the colors of the "
                + theme_label(theme)
                + " theme. Each theme remembers its own choice. Choose Custom… to pick every color yourself."
            )
            self.start_menu.clear()
            for key, name in options:
                self.start_menu.addAction(
                    swatch(scheme_colors(theme, key)), name, lambda k=key: self.seed_custom(k, replace=True)
                )
        else:
            self.color_title.setText("Colors")
            self.color_hint.setText(
                "System uses Paper in a light OS appearance and Graphite in a dark one, "
                "each with the color scheme chosen for that theme."
            )
        self.refresh_custom_editor()

    def remember_color_scheme(self):
        key = self.color_scheme.currentData()
        theme = self.chosen_theme()
        if key is None:
            return
        previous = self.pending_colors.get(theme) or default_scheme(theme)
        if key == CUSTOM and theme not in self.pending_custom:
            # A new custom palette starts from the scheme that was selected before.
            self.seed_custom(previous if previous != CUSTOM else default_scheme(theme))
        self.pending_colors[theme] = key
        self.refresh_custom_editor()

    def seed_custom(self, scheme, replace=False):
        theme = self.chosen_theme()
        colors = scheme_colors(theme, scheme)
        # Starting over from a scheme also clears advanced overrides.
        self.pending_custom[theme] = {role: colors[role] for role, _ in CORE_ROLES}
        if replace:
            self.pending_colors[theme] = CUSTOM
            self.color_scheme.blockSignals(True)
            self.color_scheme.setCurrentIndex(self.color_scheme.findData(CUSTOM))
            self.color_scheme.blockSignals(False)
            self.refresh_custom_editor()

    def set_custom_color(self, role, color):
        theme = self.chosen_theme()
        if theme not in self.pending_custom:
            self.seed_custom(default_scheme(theme))
        self.pending_custom[theme][role] = color
        self.refresh_custom_editor()

    def reset_custom_color(self, role):
        self.pending_custom.get(self.chosen_theme(), {}).pop(role, None)
        self.refresh_custom_editor()

    def refresh_custom_editor(self):
        theme = self.chosen_theme()
        custom = theme in THEMES and self.pending_colors.get(theme) == CUSTOM
        self.custom_editor.setVisible(custom)
        colors = self.current_palette()
        self.preview.set_colors(colors)
        saved = self.pending_custom.get(theme, {})
        for role, picker in self.role_buttons.items():
            picker.set_color(colors[role])
            if role in self.reset_buttons:
                self.role_values[role].setText(colors[role] if role in saved else "Automatic")
                self.reset_buttons[role].setEnabled(role in saved)
        index = self.color_scheme.findData(CUSTOM)
        if index >= 0:
            self.color_scheme.setItemIcon(index, swatch(palette(theme, CUSTOM, saved)))

    def apply_theme_settings(self):
        self.save_preferences(
            {
                "theme": self.chosen_theme(),
                "themeColors": dict(self.pending_colors),
                "customColors": {k: dict(v) for k, v in self.pending_custom.items()},
                "cornerRadius": self.fields["cornerRadius"].currentData(),
                "fontFamily": self.fields["fontFamily"].currentData() or "",
                "headingFamily": self.fields["headingFamily"].currentData() or "",
                "monoFamily": self.fields["monoFamily"].currentData() or "",
            }
        )

    # Saving -------------------------------------------------------------------------------

    def save_preferences(self, patch):
        # Rebuilding themed widgets must not discard entries or color drafts on the other pages.
        values = {key: read_field(widget) for key, widget in self.fields.items()}
        drafts = (dict(self.pending_colors), {k: dict(v) for k, v in self.pending_custom.items()})
        advanced_open = self.advanced_toggle.isChecked()
        if not self.window.execute("settings.save", patch, refresh=False):
            return
        apply_theme(self.window.data["settings"])
        self.window.build_shell()
        self.window.refresh()
        panel_ = self.window.settings_panel
        panel_.pending_colors, panel_.pending_custom = drafts
        for key, value in values.items():
            widget = panel_.fields.get(key)
            if widget is not None and key != "themeColor":
                write_field(widget, value)
        panel_.show_color_schemes()
        panel_.advanced_toggle.setChecked(advanced_open)

    # Local data, sync and account ----------------------------------------------------------

    def build_data(self, body):
        card, layout = panel("Database backup")
        path = label("SQLite storage: " + str(self.window.store.root / "timemanager.db"), "muted")
        path.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        layout.addWidget(path)
        layout.addWidget(row(button("Back up database", self.window.backup, "database"), None))
        layout.addWidget(
            label(
                "Backups contain your project data and password verifier. Protect them with your disk or backup encryption.",
                "muted",
            )
        )
        body.addWidget(card)
        card, layout = panel("Example workspace")
        layout.addWidget(label("Add example projects and tickets to explore DayFrame.", "muted"))
        layout.addWidget(
            row(button("Load example workspace", lambda: self.window.execute("examples.load")), None)
        )
        body.addWidget(card)

    def build_sync(self, body):
        settings = self.window.data["settings"]
        layout, form = self.form(body, "Private LAN connection")
        url = self.field(form, "Hub address", "syncUrl", QLineEdit(settings.get("syncUrl", "")))
        url.setPlaceholderText("https://linux-hub:47831")
        fingerprint = self.field(
            form, "Certificate fingerprint", "syncFingerprint", QLineEdit(settings.get("syncFingerprint", ""))
        )
        fingerprint.setPlaceholderText("SHA-256 of the trusted hub certificate")
        for key, title in (("password", "Account password"), ("setupToken", "Private setup token")):
            widget = self.field(form, title, key, QLineEdit())
            widget.setEchoMode(QLineEdit.Password)
        layout.addWidget(
            label(
                "Use Connect for an existing hub account; Publish creates this account on your private hub.",
                "muted",
            )
        )
        layout.addWidget(
            row(
                button("Connect", lambda: self.connect_hub(False), "link"),
                button("Publish account to hub", lambda: self.connect_hub(True), "upload"),
                None,
            )
        )
        card, layout = panel("Synchronization")
        enabled = QCheckBox("Automatically sync while the app is open")
        enabled.setChecked(settings.get("syncEnabled", False))
        enabled.toggled.connect(
            lambda value: self.window.execute("settings.save", {"syncEnabled": value}, refresh=False)
        )
        layout.addWidget(enabled)
        layout.addWidget(row(button("Sync now", self.window.sync_now, "sync-alt"), None))
        layout.addWidget(
            label(
                self.window.sync.state.get("error")
                or "Credentials use the OS keyring when available; otherwise they last for this session.",
                "muted",
            )
        )
        body.addWidget(card)
        conflicts = self.window.data["conflicts"]
        if conflicts:
            self.section_items["sync"].setText(f"Sync ({len(conflicts)})")
            card, layout = panel("Sync conflicts · " + str(len(conflicts)))
            for conflict in conflicts:
                details = label(
                    conflict["kind"]
                    + " · "
                    + conflict["entity_id"][:8]
                    + " · "
                    + ", ".join(conflict["fields"])
                )
                details.setWordWrap(True)
                review = button(
                    "Review conflict", lambda checked=False, c=conflict: self.window.review_conflict(c)
                )
                review.setAccessibleName(
                    "Review " + conflict["kind"] + " conflict " + conflict["entity_id"][:8]
                )
                layout.addWidget(row(details, review))
            body.addWidget(card)

    def connect_hub(self, publish):
        params = {
            "url": self.fields["syncUrl"].text().strip(),
            "fingerprint": self.fields["syncFingerprint"].text().strip(),
            "password": self.fields["password"].text(),
            "setupToken": self.fields["setupToken"].text(),
        }
        self.fields["password"].clear()
        self.fields["setupToken"].clear()
        self.window.run_async(
            lambda: self.window.sync.publish(params) if publish else self.window.sync.connect(params),
            self.window.sync_finished,
        )

    def build_account(self, body):
        card, layout = panel("Local account")
        layout.addWidget(label("Signed in as " + self.window.data["account"]["username"], "section"))
        layout.addWidget(
            row(
                button("Change local password", self.window.change_local_password, "key"),
                button("Log out", self.window.logout, "sign-out-alt"),
                None,
            )
        )
        body.addWidget(card)
