"""Compact native palettes and typography based on the Graphite/Cyan concept."""
import sys
from importlib.resources import files
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QFont,QIcon,QPalette
from PySide6.QtWidgets import QApplication
import qtawesome as qta

PALETTES={
 "graphite":{"bg":"#151c22","panel":"#1b252d","raised":"#25313a","line":"#394750","text":"#e4edf1","muted":"#91a3ae","accent":"#54e1e9","danger":"#ee858a",
             "rail":"#11191f","radius":3,"mode":"technical","font_win":"Segoe UI","font_linux":"Noto Sans","heading":"Segoe UI","weight":650},
 "amber":{"bg":"#11120e","panel":"#191b13","raised":"#26291b","line":"#586040","text":"#f2e5bc","muted":"#b7af88","accent":"#ffc65e","danger":"#f29275",
          "rail":"#080b06","radius":0,"mode":"terminal","font_win":"Consolas","font_linux":"DejaVu Sans Mono","heading":"Consolas","weight":700},
 "light":{"bg":"#eee7d9","panel":"#fffcf4","raised":"#e6dcc8","line":"#c9bca2","text":"#392f27","muted":"#7b6b56","accent":"#537260","danger":"#a3473e",
          "rail":"#ddd1ba","radius":8,"mode":"paper","font_win":"Trebuchet MS","font_linux":"Noto Sans","heading":"Georgia","weight":600},
 "studio":{"bg":"#17142a","panel":"#231d3c","raised":"#33294f","line":"#54446f","text":"#f1eafa","muted":"#b3a4cd","accent":"#c4a1ff","danger":"#f99fc2",
           "rail":"#100e20","radius":11,"mode":"studio","font_win":"Bahnschrift","font_linux":"DejaVu Sans","heading":"Bahnschrift","weight":600}}
CURRENT=PALETTES["graphite"].copy()

def apply_theme(settings):
    name=settings.get("theme","graphite")
    if name=="system":name="light" if QApplication.styleHints().colorScheme()==Qt.ColorScheme.Light else "graphite"
    CURRENT.clear();CURRENT.update(PALETTES.get(name,PALETTES["graphite"]));c=CURRENT;app=QApplication.instance();app.setStyle("Fusion")
    palette=QPalette()
    for role,color in [(QPalette.Window,c["bg"]),(QPalette.WindowText,c["text"]),(QPalette.Base,c["panel"]),
        (QPalette.AlternateBase,c["raised"]),(QPalette.Text,c["text"]),(QPalette.Button,c["raised"]),(QPalette.ButtonText,c["text"]),
        (QPalette.Highlight,c["accent"]),(QPalette.HighlightedText,c["bg"]),(QPalette.ToolTipBase,c["panel"]),
        (QPalette.ToolTipText,c["text"]),(QPalette.PlaceholderText,c["muted"]),(QPalette.Light,c["raised"]),
        (QPalette.Midlight,c["line"]),(QPalette.Mid,c["line"]),(QPalette.Dark,c["bg"]),(QPalette.Shadow,c["bg"])]:
        palette.setColor(role,QColor(color))
    app.setPalette(palette)
    font=QFont(c["font_win"] if sys.platform=="win32" else c["font_linux"]);font.setPointSizeF(8.5*settings.get("textScale",100)/100);app.setFont(font)
    c["heading"]=c["heading"] if sys.platform=="win32" else ("DejaVu Serif" if c["mode"]=="paper" else c["font_linux"])
    assets=files("dayframe").joinpath("resources")
    name=name if name in PALETTES else "graphite"
    c["down"]=str(assets.joinpath(name+"-down.svg")).replace("\\","/")
    c["up"]=str(assets.joinpath(name+"-up.svg")).replace("\\","/")
    pad=3 if settings.get("density","compact")=="compact" else 5
    app.setStyleSheet("""
    QWidget { color:%(text)s; }
    QMainWindow,QDialog { background:%(bg)s; }
    QWidget#navigationRail { background:%(rail)s; border-right:1px solid %(line)s; }
    QFrame#masthead,QFrame#utilityBar { background:%(panel)s; border-bottom:1px solid %(line)s; }
    QFrame#utilityBar { border-top:1px solid %(line)s; border-bottom:0; }
    QWidget#contextPane { background:%(rail)s; border-right:1px solid %(line)s; }
    QWidget#ticketInspector,QWidget#agendaPane { border-left:1px solid %(line)s; }
    QFrame#panel { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QFrame#focusPanel { background:%(raised)s; border:1px solid %(accent)s; border-radius:%(radius)spx; }\n    QFrame#taskRow { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QFrame#overdueRow { background:%(raised)s; border:1px solid #8e7446; border-radius:%(radius)spx; }
    QLabel#captureError { color:%(danger)s; }
    QLabel#muted { color:%(muted)s; }
    QLabel#warning { color:#d4b16c; }
    QLabel#captureHeading { font-size:15px; font-weight:650; }
    QLineEdit#captureTitle { font-size:13px; padding:7px 8px; }
    QLabel#heading { font-size:20px; font-weight:700; font-family:"%(heading)s"; }
    QLabel#section { font-weight:%(weight)s; font-family:"%(heading)s"; }
    QLabel#badge { background:%(raised)s; color:%(accent)s; padding:1px 5px; border-radius:%(radius)spx; }
    QLabel#count { background:%(raised)s; color:%(muted)s; padding:1px 4px; border-radius:%(radius)spx; }
    QLabel#clock { font-family:Consolas,monospace; font-size:13px; font-weight:650; color:%(accent)s; }
    QPushButton,QToolButton { background:%(raised)s; border:1px solid transparent; border-radius:%(radius)spx; padding:%(pad)spx 7px; }
    QPushButton:hover,QToolButton:hover { border-color:%(accent)s; }
    QPushButton:checked,QToolButton:checked { color:%(accent)s; border-color:%(accent)s; }
    QPushButton#accent { background:%(accent)s; color:%(bg)s; font-weight:650; }
    QPushButton#rowTitle { background:transparent; border:0; text-align:left; padding:1px 2px; }
    QPushButton#rowTitle:hover { color:%(accent)s; }
    QPushButton#iconOnly { background:transparent; padding:1px; border:0; }
    QPushButton:disabled { color:%(muted)s; }
    QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDateEdit,QTimeEdit,QDateTimeEdit {
      background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; padding:%(pad)spx 5px; selection-background-color:%(accent)s; }
    QComboBox { padding-right:24px; }
    QAbstractSpinBox QLineEdit,QComboBox QLineEdit { background:transparent; border:0; padding:0; }
    QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; width:20px; border:0; background:transparent; }
    QComboBox::down-arrow { image:url("%(down)s"); width:10px; height:8px; }
    QComboBox QAbstractItemView { background:%(panel)s; color:%(text)s; border:1px solid %(line)s; outline:0; selection-background-color:%(raised)s; selection-color:%(accent)s; }
    QToolButton::menu-indicator,QPushButton::menu-indicator { image:url("%(down)s"); width:9px; height:7px; }
    QLineEdit:focus,QPlainTextEdit:focus { border-color:%(accent)s; }
    QLineEdit#ticketTitle { font-size:13px; font-weight:650; }
    QListWidget,QTreeWidget,QTableWidget,QScrollArea { background:%(panel)s; border:1px solid %(line)s; border-radius:%(radius)spx; }
    QScrollArea { border:0; background:transparent; }
    QScrollArea#dialogContent { background:transparent; }
    QListWidget::item,QTreeWidget::item { padding:3px 4px; }
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
    QGroupBox { border:1px solid %(line)s; border-radius:%(radius)spx; margin-top:10px; padding-top:10px; }
    QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
    QMenu { background:%(panel)s; border:1px solid %(line)s; }
    QMenu::item { padding:5px 18px; }
    QMenu#optionsMenu::icon { left:6px; }
    QMenu::item:selected { background:%(raised)s; color:%(accent)s; }
    QStatusBar { color:%(muted)s; font-size:10px; border-top:1px solid %(line)s; }
    QToolTip { background:%(panel)s; color:%(text)s; border:1px solid %(line)s; padding:4px; }
    """%{**c,"pad":pad})
    if c["mode"]=="terminal":
        app.setStyleSheet(app.styleSheet()+"QFrame#taskRow {border:0;border-bottom:1px solid "+c["line"]+";} QLabel#heading {letter-spacing:1px;} QTabBar::tab:selected {background:"+c["raised"]+";}")
    elif c["mode"]=="paper":
        app.setStyleSheet(app.styleSheet()+"QFrame#taskRow {border:0;border-bottom:1px solid "+c["line"]+";} QLabel#heading {font-size:23px;} QTabBar::tab:selected {background:"+c["raised"]+";} QHeaderView::section {font-weight:600;}")
    elif c["mode"]=="studio":
        app.setStyleSheet(app.styleSheet()+"QFrame#masthead {background:"+c["rail"]+";} QFrame#taskRow {border:1px solid "+c["line"]+";border-left:3px solid "+c["accent"]+";} QPushButton:checked {background:"+c["panel"]+";} QTabBar::tab {border-radius:7px;}")

    controls=("QSpinBox","QDoubleSpinBox","QDateEdit","QTimeEdit","QDateTimeEdit")
    rules=[]
    for control in controls:
        rules.extend([
            control+' {padding-right:24px;}',
            control+'::up-button {subcontrol-origin:border;subcontrol-position:top right;width:18px;height:10px;top:2px;right:3px;border:0;background:transparent;}',
            control+'::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:18px;height:10px;bottom:2px;right:3px;border:0;background:transparent;}',
            control+'::up-arrow {image:url("'+c["up"]+'");width:8px;height:6px;}',
            control+'::down-arrow {image:url("'+c["down"]+'");width:8px;height:6px;}',
            control+'::drop-down {subcontrol-origin:padding;subcontrol-position:top right;width:20px;border:0;background:transparent;}'])
    app.setStyleSheet(app.styleSheet()+"\n"+"\n".join(rules))
    from .window_frame import install_frame_theming
    install_frame_theming()

def icon(name,color=None):return qta.icon("fa5s."+name,color=color or CURRENT["muted"])

def app_icon():
    return QIcon(str(files("dayframe").joinpath("resources/dayframe-icon.png")))
