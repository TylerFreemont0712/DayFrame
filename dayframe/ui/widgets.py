"""Compact native controls and bounded scrolling modal forms."""

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QComboBox,
    QSizePolicy,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QLineEdit,
    QStyle,
    QStyleOptionComboBox,
)
from .theme import icon


def label(text="", kind=None):
    w = QLabel(str(text))
    w.setTextFormat(Qt.PlainText)
    if kind:
        w.setObjectName(kind)
    return w


class ElidingLabel(QLabel):
    """Keep full text accessible while fitting styled badges/identifiers."""

    def __init__(self, text="", kind=None, parent=None):
        super().__init__(parent)
        self._text_padding = 14 if kind == "badge" else 2
        self.full_text = str(text)
        self.setTextFormat(Qt.PlainText)
        if kind:
            self.setObjectName(kind)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(self.full_text)
        self.setAccessibleName(self.full_text)
        self._elide()

    def setText(self, text):
        self.full_text = str(text)
        self.setToolTip(self.full_text)
        self.setAccessibleName(self.full_text)
        self._elide()

    def _elide(self):
        if not hasattr(self, "full_text"):
            return
        QLabel.setText(
            self,
            self.fontMetrics().elidedText(
                self.full_text, Qt.ElideRight, max(0, self.width() - self._text_padding)
            ),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def changeEvent(self, event):
        super().changeEvent(event)
        self._elide()


def button(text, callback=None, glyph=None, accent=False):
    w = QPushButton(text)
    w.setAutoDefault(False)
    if glyph:
        w.setIcon(icon(glyph))
    if accent:
        w.setObjectName("accent")
    if callback:
        w.clicked.connect(callback)
    return w


def column(parent=None, margins=0, spacing=6):
    w = QWidget(parent)
    l = QVBoxLayout(w)
    l.setContentsMargins(*([margins] * 4))
    l.setSpacing(spacing)
    return w, l


def row(*items):
    w = QWidget()
    l = QHBoxLayout(w)
    l.setContentsMargins(0, 0, 0, 0)
    l.setSpacing(6)
    for item in items:
        if item is None:
            l.addStretch()
        elif isinstance(item, str):
            l.addWidget(label(item))
        else:
            l.addWidget(item)
    return w


def panel(title=None):
    w = QFrame()
    w.setObjectName("panel")
    l = QVBoxLayout(w)
    l.setContentsMargins(10, 8, 10, 8)
    l.setSpacing(6)
    if title:
        l.addWidget(label(title, "section"))
    return w, l


def scroll(w):
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setWidget(w)
    s.setFrameShape(QFrame.NoFrame)
    return s


def combo(items, current=None):
    w = QComboBox()
    for value, display in items:
        w.addItem(display, value)
    if current is not None:
        w.setCurrentIndex(max(0, w.findData(current)))
    return w


def fit_text_width(widget, sample, extra=0, fixed=True):
    """Size a label to its style-sheet font so sample text never clips at any text scale."""
    widget.ensurePolished()
    width = widget.fontMetrics().horizontalAdvance(sample) + extra
    if fixed:
        widget.setFixedWidth(width)
    else:
        widget.setMinimumWidth(width)
    return width


def fit_combo_width(box, extra=6):
    """Fixed width that shows the longest item beside the drop-down arrow.

    The space around the text (padding, borders and the arrow) is measured from the
    style, so the result stays right for every theme, density and text size.
    """
    box.ensurePolished()
    metrics = box.fontMetrics()
    longest = max((metrics.horizontalAdvance(box.itemText(i)) for i in range(box.count())), default=0)
    option = QStyleOptionComboBox()
    box.initStyleOption(option)
    option.rect = QRect(0, 0, 400, max(20, box.sizeHint().height()))
    field = box.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, box)
    width = longest + (400 - field.width()) + extra
    box.setFixedWidth(width)
    return width


def error(parent, exc):
    QMessageBox.warning(parent, "DayFrame", str(exc))


class FormDialog(QDialog):
    """Callers add to layout; finish_form keeps actions outside scroll content."""

    def __init__(self, parent, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 280)
        self.setWindowModality(Qt.WindowModal if parent else Qt.ApplicationModal)
        self.setSizeGripEnabled(True)
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(12, 12, 12, 12)
        self.outer_layout.setSpacing(10)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignTop)
        self.form_scroll = QScrollArea()
        self.form_scroll.setObjectName("dialogContent")
        self.form_scroll.setFrameShape(QFrame.NoFrame)
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.form_scroll.setWidget(self.content)
        self.outer_layout.addWidget(self.form_scroll, 1)
        self.buttons = None
        self._footer = None

    def finish_form(self):
        if self.buttons:
            return
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.Save).setDefault(True)
        self.buttons.button(QDialogButtonBox.Save).setObjectName("accent")
        self.set_footer(self.buttons)

    def set_footer(self, widget):
        if self._footer:
            self.outer_layout.removeWidget(self._footer)
            self._footer.hide()
            self._footer.deleteLater()
        self._footer = widget
        self.outer_layout.addWidget(widget)

    def available_rect(self):
        screen = self.screen() or QApplication.primaryScreen()
        return screen.availableGeometry().adjusted(16, 16, -16, -16) if screen else QRect(16, 16, 992, 688)

    def fit_to_contents(self):
        self.layout.activate()
        available = self.available_rect()
        self.setMaximumSize(available.size())
        footer = self._footer.sizeHint().height() + 10 if self._footer else 0
        height = min(max(150, self.content.sizeHint().height() + 24 + footer + 4), available.height(), 620)
        self.resize(min(max(360, self.width()), available.width()), height)
        center = self.parentWidget().frameGeometry().center() if self.parentWidget() else available.center()
        position = center - self.rect().center()
        self.move(
            max(available.left(), min(position.x(), available.right() - self.width() + 1)),
            max(available.top(), min(position.y(), available.bottom() - self.height() + 1)),
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_to_contents()
        QTimer.singleShot(0, self.fit_to_contents)


def ask_text(parent, title, prompt, value=""):
    d = FormDialog(parent, title)
    d.resize(430, 170)
    prompt_label = label(prompt)
    prompt_label.setWordWrap(True)
    d.layout.addWidget(prompt_label)
    edit = QLineEdit(value)
    d.layout.addWidget(edit)
    d.finish_form()
    return edit.text().strip() if d.exec() == QDialog.Accepted else None
