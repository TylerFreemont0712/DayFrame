"""Applies a theme to the running QApplication: palette, fonts, sizes and the shared style sheet.

Colors come from core/palettes.py (theme, preset scheme or custom colors). Preferences
from core/preferences.py add text and heading scale, density, corner style and font
overrides. CURRENT holds the resolved values so painted widgets can read them.
"""

import os
import sys
import tempfile
from importlib.resources import files
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication
import qtawesome as qta
from ..core.palettes import (
    CUSTOM,
    LEGACY_THEMES,
    THEMES,
    default_scheme,
    is_dark,
    palette,
    schemes,
)

CURRENT = palette("graphite")
# Values apply_theme() also sets, so painted widgets can read them before the first call.
CURRENT.update(
    theme="graphite",
    scheme="cyan",
    dark=True,
    scale=0.9,
    font="Segoe UI",
    heading="Segoe UI",
    mono="Consolas",
)
DESIGN_POINT_SIZE = 8.5
DENSITY_PADDING = {"compact": 3, "comfortable": 5, "spacious": 7}
# Fallbacks tried after a theme's own fonts; the first installed family wins.
UI_FALLBACKS = ("Segoe UI", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans")
MONO_FALLBACKS = (
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "JetBrains Mono",
    "Fira Code",
    "Ubuntu Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
)
# Suggested choices shown first in the font pickers when they are installed.
SUGGESTED_UI_FONTS = (
    "Segoe UI",
    "Segoe UI Variable Text",
    "Inter",
    "Aptos",
    "Atkinson Hyperlegible",
    "Lexend",
    "IBM Plex Sans",
    "Source Sans 3",
    "Roboto",
    "Noto Sans",
    "Ubuntu",
    "Cantarell",
    "Verdana",
    "Trebuchet MS",
    "Bahnschrift",
    "Georgia",
    "Calibri",
)
SUGGESTED_MONO_FONTS = MONO_FALLBACKS + ("IBM Plex Mono", "Source Code Pro", "Iosevka", "Lucida Console")


def installed_families():
    return {name.casefold(): name for name in QFontDatabase.families()}


def pick_font(*candidates):
    """First installed family among candidates.

    When none is installed (for example under Qt's offscreen platform, which lists no
    fonts) the first candidate is returned and Qt substitutes its own match.
    """
    names = [c for c in candidates if c]
    installed = installed_families()
    for name in names:
        if name.casefold() in installed:
            return installed[name.casefold()]
    return names[0] if names else QApplication.font().family()


def resolve_theme(settings):
    """Theme id and color scheme id for saved preferences; System follows the OS."""
    name = settings.get("theme", "graphite")
    name = LEGACY_THEMES.get(name, name)
    if name == "system":
        name = "light" if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else "graphite"
    if name not in THEMES:
        name = "graphite"
    colors = settings.get("themeColors")
    scheme = colors.get(name) if isinstance(colors, dict) else None
    if scheme != CUSTOM and scheme not in dict(schemes(name)):
        scheme = default_scheme(name)
    return name, scheme


def resolve_palette(settings):
    """Complete color palette (advanced roles included) for saved preferences."""
    name, scheme = resolve_theme(settings)
    custom = settings.get("customColors")
    return palette(name, scheme, custom.get(name) if isinstance(custom, dict) else None)


def chevron(direction, color):
    """Path of a chevron SVG in the given color, written on first use outside the checkout."""
    path = (
        Path(tempfile.gettempdir())
        / "dayframe-theme"
        / ("chevron-%s-%s.svg" % (direction, color.lstrip("#")))
    )
    if not path.exists():
        points = "M2 3 L6 7 L10 3" if direction == "down" else "M2 7 L6 3 L10 7"
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="10" viewBox="0 0 12 10"><path d="%s" fill="none" '
            'stroke="%s" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ) % (points, color)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Another instance may be writing the same file, so publish it with an atomic rename.
            partial = path.with_name(path.name + ".%d.tmp" % os.getpid())
            partial.write_text(svg, encoding="utf-8")
            os.replace(partial, path)
        except OSError:
            return ""
    return str(path).replace("\\", "/")


def _fonts(c, settings):
    windows = sys.platform == "win32"
    own = (c["font_win"], c["font_linux"]) if windows else (c["font_linux"], c["font_win"])
    ui = pick_font(settings.get("fontFamily"), *own, *UI_FALLBACKS)
    if c["mode"] == "paper" and not windows:
        heading_own = ("DejaVu Serif", c["heading"])
    elif c["mode"] in ("terminal", "editor"):
        heading_own = (c["heading"],) + MONO_FALLBACKS
    else:
        heading_own = (c["heading"],) + own
    heading = pick_font(settings.get("headingFamily"), *heading_own, *UI_FALLBACKS)
    mono_own = own if c["mode"] == "terminal" else ()
    mono = pick_font(settings.get("monoFamily"), *mono_own, *MONO_FALLBACKS)
    return ui, heading, mono


def apply_theme(settings):
    name, scheme = resolve_theme(settings)
    CURRENT.clear()
    CURRENT.update(resolve_palette(settings))
    c = CURRENT
    c["theme"] = name
    c["scheme"] = scheme
    c["dark"] = is_dark(c)
    scale = settings.get("textScale", 90) / 100
    heading_scale = settings.get("headingScale", 100) / 100
    c["scale"] = scale
    corner = settings.get("cornerRadius", -1)
    if isinstance(corner, int) and corner >= 0:
        c["radius"] = corner
    app = QApplication.instance()
    app.setStyle("Fusion")
    colors = QPalette()
    for role, color in [
        (QPalette.Window, c["bg"]),
        (QPalette.WindowText, c["text"]),
        (QPalette.Base, c["input"]),
        (QPalette.AlternateBase, c["raised"]),
        (QPalette.Text, c["text"]),
        (QPalette.Button, c["button"]),
        (QPalette.ButtonText, c["button_text"]),
        (QPalette.Highlight, c["selection"]),
        (QPalette.HighlightedText, c["accent_text"]),
        (QPalette.ToolTipBase, c["panel"]),
        (QPalette.ToolTipText, c["text"]),
        (QPalette.PlaceholderText, c["muted"]),
        (QPalette.Light, c["raised"]),
        (QPalette.Midlight, c["line"]),
        (QPalette.Mid, c["line"]),
        (QPalette.Dark, c["bg"]),
        (QPalette.Shadow, c["bg"]),
    ]:
        colors.setColor(role, QColor(color))
    app.setPalette(colors)
    ui_font, heading_font, mono_font = _fonts(c, settings)
    c["font"], c["heading"], c["mono"] = ui_font, heading_font, mono_font
    font = QFont(ui_font)
    font.setPointSizeF(DESIGN_POINT_SIZE * scale)
    app.setFont(font)
    c["down"] = chevron("down", c["muted"])
    c["up"] = chevron("up", c["muted"])
    pad = DENSITY_PADDING.get(settings.get("density", "compact"), 3)

    def px(size, factor=1.0):
        return max(6, round(size * scale * factor))

    values = {
        **c,
        "pad": pad,
        "item_pad": pad + 1,
        "heading_px": px(23 if c["mode"] == "paper" else 20, heading_scale),
        "capture_px": px(15, heading_scale),
        "title_px": px(13),
        "clock_px": px(13),
        "status_px": px(10),
    }
    sheet = [
        """
    QWidget { color:%(text)s; }
    QMainWindow,QDialog { background:%(bg)s; }
    QWidget#navigationRail { background:%(rail)s; border-right:1px solid %(line)s; }
    QFrame#masthead,QFrame#utilityBar { background:%(panel)s; border-bottom:1px solid %(line)s; }
    QFrame#utilityBar { border-top:1px solid %(line)s; border-bottom:0; }
    QWidget#contextPane { background:%(rail)s; border-right:1px solid %(line)s; }
    QWidget#ticketInspector,QWidget#agendaPane { border-left:1px solid %(line)s; }
    QFrame#panel { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QFrame#focusPanel { background:%(raised)s; border:1px solid %(accent)s; border-radius:%(radius)spx; }
    QFrame#taskRow { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QFrame#overdueRow { background:%(raised)s; border:1px solid %(warning)s; border-radius:%(radius)spx; }
    QLabel#captureError { color:%(danger)s; }
    QLabel#muted { color:%(muted)s; }
    QLabel#warning { color:%(warning)s; }
    QLabel#captureHeading { font-size:%(capture_px)spx; font-weight:650; color:%(heading_text)s; font-family:"%(heading)s"; }
    QLineEdit#captureTitle { font-size:%(title_px)spx; padding:7px 8px; }
    QLabel#heading { font-size:%(heading_px)spx; font-weight:700; font-family:"%(heading)s"; color:%(heading_text)s; }
    QLabel#section { font-weight:%(weight)s; font-family:"%(heading)s"; color:%(heading_text)s; }
    QLabel#badge { background:%(raised)s; color:%(accent)s; padding:1px 5px; border-radius:%(radius)spx; }
    QLabel#count { background:%(raised)s; color:%(muted)s; padding:1px 4px; border-radius:%(radius)spx; }
    QLabel#clock { font-family:"%(mono)s",monospace; font-size:%(clock_px)spx; font-weight:650; color:%(clock)s; }
    QLabel#worldClock { font-family:"%(mono)s",monospace; color:%(muted)s; }
    QPushButton,QToolButton { background:%(button)s; color:%(button_text)s; border:1px solid transparent; border-radius:%(radius)spx; padding:%(pad)spx 7px; }
    QPushButton:hover,QToolButton:hover { border-color:%(button_hover)s; }
    QPushButton:checked,QToolButton:checked { color:%(accent)s; border-color:%(accent)s; }
    QPushButton#accent { background:%(accent)s; color:%(accent_text)s; font-weight:650; }
    QPushButton#rowTitle { background:transparent; color:%(text)s; border:0; text-align:left; padding:1px 2px; }
    QPushButton#rowTitle:hover { color:%(accent)s; }
    QPushButton#iconOnly { background:transparent; padding:1px; border:0; }
    QPushButton#colorSwatch { border:1px solid %(line)s; padding:0; }
    QPushButton:disabled { color:%(muted)s; }
    QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDateEdit,QTimeEdit,QDateTimeEdit {
      background:%(input)s; border:1px solid %(line)s; border-radius:%(radius)spx; padding:%(pad)spx 5px; selection-background-color:%(selection)s; selection-color:%(accent_text)s; }
    QComboBox { padding-right:24px; }
    QAbstractSpinBox QLineEdit,QComboBox QLineEdit { background:transparent; border:0; padding:0; }
    QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:20px; border:0; background:transparent; }
    QComboBox::down-arrow { image:url("%(down)s"); width:10px; height:8px; }
    QComboBox QAbstractItemView { background:%(panel)s; color:%(text)s; border:1px solid %(line)s; outline:0; selection-background-color:%(raised)s; selection-color:%(accent)s; }
    QToolButton::menu-indicator,QPushButton::menu-indicator { image:url("%(down)s"); width:9px; height:7px; }
    QLineEdit:focus,QPlainTextEdit:focus { border-color:%(accent)s; }
    QLineEdit#ticketTitle { font-size:%(title_px)spx; font-weight:650; }
    QListWidget,QTreeWidget,QTableWidget,QScrollArea { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QScrollArea { border:0; background:transparent; }
    QScrollArea#dialogContent { background:transparent; }
    QListWidget::item,QTreeWidget::item { padding:%(item_pad)spx 4px; }
    QListWidget::item:selected,QTreeWidget::item:selected { background:%(raised)s; color:%(accent)s; }
    QListWidget#settingsNavigation { background:transparent; border:0; }
    QListWidget#settingsNavigation::item { padding:10px 8px; margin-bottom:4px; border:1px solid transparent; border-radius:%(radius)spx; }
    QListWidget#settingsNavigation::item:hover { background:%(panel)s; }
    QListWidget#settingsNavigation::item:selected { background:%(raised)s; color:%(accent)s; border-color:%(line)s; }
    QListWidget#ticketLane { background:%(panel)s; border:1px solid %(line)s; }
    QListWidget#ticketLane::item { padding:0; margin:0; border:0; background:transparent; }
    QTreeWidget#projectTree { border:0; background:transparent; }
    QListWidget#checklist::item { padding:2px; }
    QHeaderView::section { background:%(raised)s; color:%(muted)s; border:0; padding:4px; }
    QTabWidget::pane { border:0; background:transparent; }
    QTabBar { qproperty-drawBase:0; border:0; background:transparent; }
    QTabBar::tear { border:0; background:transparent; }
    QTabBar::tab { background:%(panel)s; padding:5px 10px; border:1px solid %(line)s; }
    QTabBar::tab:selected { color:%(accent)s; border-color:%(accent)s; }
    QSplitter::handle { background:%(line)s; }
    QScrollBar:vertical { background:%(panel)s; width:7px; }
    QScrollBar::handle:vertical { background:%(line)s; min-height:22px; border-radius:2px; }
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
    QSlider::groove:horizontal { height:6px; background:%(raised)s; border:1px solid %(line)s; border-radius:3px; }
    QSlider::handle:horizontal { width:12px; margin:-5px 0; background:%(accent)s; border-radius:6px; }
    QGroupBox { border:1px solid %(line)s; border-radius:%(radius)spx; margin-top:10px; padding-top:10px; }
    QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
    QMenu { background:%(panel)s; border:1px solid %(line)s; }
    QMenu::item { padding:5px 18px; }
    QMenu#optionsMenu::icon { left:6px; }
    QMenu::item:selected { background:%(raised)s; color:%(accent)s; }
    QStatusBar { color:%(muted)s; font-size:%(status_px)spx; border-top:1px solid %(line)s; }
    QToolTip { background:%(panel)s; color:%(text)s; border:1px solid %(line)s; padding:4px; }
    """
    ]
    sheet.append(PROFILE_RULES.get(c["mode"], ""))
    sheet.append(
        """
    QPushButton:pressed,QToolButton:pressed { background:%(line)s; border-color:%(accent)s; }
    QPushButton#accent:pressed { background:%(line)s; color:%(text)s; }
    QPushButton#rowTitle:pressed,QPushButton#iconOnly:pressed { background:%(line)s; color:%(text)s; }
    """
    )
    controls = ("QSpinBox", "QDoubleSpinBox", "QDateEdit", "QTimeEdit", "QDateTimeEdit")
    for control in controls:
        sheet.extend(
            [
                control + " {padding-right:24px;}",
                control
                + "::up-button {subcontrol-origin:border;subcontrol-position:top right;width:18px;height:10px;top:2px;right:3px;border:0;background:transparent;}",
                control
                + "::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:18px;height:10px;bottom:2px;right:3px;border:0;background:transparent;}",
                control + '::up-arrow {image:url("%(up)s");width:8px;height:6px;}',
                control + '::down-arrow {image:url("%(down)s");width:8px;height:6px;}',
                control
                + "::drop-down {subcontrol-origin:padding;subcontrol-position:top right;width:20px;border:0;background:transparent;}",
            ]
        )
    app.setStyleSheet("\n".join(part % values for part in sheet))
    from .window_frame import install_frame_theming

    install_frame_theming()


# Extra rules that give each theme profile its own shape, on top of the shared sheet.
PROFILE_RULES = {
    "terminal": """
    QFrame#taskRow { border:0; border-bottom:1px solid %(line)s; }
    QLabel#heading { letter-spacing:1px; }
    QTabBar::tab:selected { background:%(raised)s; }
    """,
    "paper": """
    QFrame#taskRow { border:0; border-bottom:1px solid %(line)s; }
    QTabBar::tab:selected { background:%(raised)s; }
    QHeaderView::section { font-weight:600; }
    """,
    "studio": """
    QFrame#masthead { background:%(rail)s; }
    QFrame#taskRow { border:1px solid %(line)s; border-left:3px solid %(accent)s; }
    QPushButton:checked { background:%(panel)s; }
    QTabBar::tab { border-radius:7px; }
    """,
    # Nord: flat, quiet surfaces with underlined tabs.
    "arctic": """
    QFrame#masthead { background:%(bg)s; }
    QFrame#taskRow { border:1px solid transparent; background:%(panel)s; }
    QFrame#taskRow:hover { border-color:%(line)s; }
    QTabBar::tab { background:transparent; border:0; border-bottom:2px solid transparent; padding:5px 12px; }
    QTabBar::tab:selected { border-bottom:2px solid %(accent)s; }
    QHeaderView::section { background:%(panel)s; }
    """,
    # Catppuccin: soft pill-shaped controls and roomy rows.
    "pastel": """
    QPushButton,QToolButton { padding:%(pad)spx 10px; }
    QFrame#taskRow { border:1px solid %(line)s; }
    QFrame#focusPanel { border:2px solid %(accent)s; }
    QTabBar::tab { border-radius:9px; margin-right:3px; padding:5px 12px; }
    QLabel#badge,QLabel#count { padding:1px 7px; }
    """,
    # Editor: monospace identifiers, editor-style tabs and a gutter line on rows.
    "editor": """
    QFrame#masthead { background:%(rail)s; }
    QFrame#taskRow { border:0; border-left:2px solid %(line)s; border-bottom:1px solid %(raised)s; border-radius:0; }
    QFrame#taskRow:hover { border-left-color:%(accent)s; }
    QTabBar::tab { background:%(raised)s; border:0; border-top:2px solid transparent; padding:5px 12px; }
    QTabBar::tab:selected { background:%(panel)s; border-top:2px solid %(accent)s; }
    QLabel#badge,QLabel#count { font-family:"%(mono)s",monospace; }
    """,
}


def icon(name, color=None):
    return qta.icon("fa5s." + name, color=color or CURRENT["muted"])


def app_icon():
    return QIcon(str(files("dayframe").joinpath("resources/dayframe-icon.png")))
