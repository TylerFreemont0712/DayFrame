"""Color wheel picker and the swatch buttons used by Settings > Theme > Custom colors."""

import math

from PySide6.QtCore import QPointF, QRectF, QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLineEdit, QPushButton, QSlider, QWidget

from .widgets import FormDialog, label, row


class ColorWheel(QWidget):
    """Hue around the circle, saturation from the center outwards; brightness is set separately."""

    colorChanged = Signal(QColor)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setMinimumSize(190, 190)
        self.setAccessibleName("Color wheel")
        self.setCursor(Qt.CrossCursor)
        self._image = None
        color = QColor(color)
        self.hue = max(0, color.hsvHueF())
        self.saturation = color.hsvSaturationF()
        self.value = color.valueF()

    def sizeHint(self):
        return QSize(210, 210)

    def color(self):
        return QColor.fromHsvF(self.hue, self.saturation, self.value)

    def set_color(self, color, emit=False):
        color = QColor(color)
        if color.hsvHueF() >= 0:
            self.hue = color.hsvHueF()
        self.saturation = color.hsvSaturationF()
        self.value = color.valueF()
        self.update()
        if emit:
            self.colorChanged.emit(self.color())

    def set_value(self, value):
        self.value = value
        self.update()
        self.colorChanged.emit(self.color())

    def _geometry(self):
        side = min(self.width(), self.height()) - 8
        return QPointF(self.width() / 2, self.height() / 2), side / 2

    def _wheel(self, radius):
        size = int(radius * 2) + 2
        if self._image is not None and self._image.width() == size:
            return self._image
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPointF(size / 2, size / 2)
        hues = QConicalGradient(center, 0)
        for step in range(13):
            # Conical gradients run counter-clockwise, matching the angle used when picking.
            hues.setColorAt(step / 12, QColor.fromHsvF((step / 12) % 1.0, 1, 1))
        painter.setPen(Qt.NoPen)
        painter.setBrush(hues)
        painter.drawEllipse(center, radius, radius)
        whites = QRadialGradient(center, radius)
        whites.setColorAt(0, QColor(255, 255, 255, 255))
        whites.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(whites)
        painter.drawEllipse(center, radius, radius)
        painter.end()
        self._image = image
        return image

    def paintEvent(self, event):
        center, radius = self._geometry()
        if radius <= 4:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        wheel = self._wheel(radius)
        p.drawImage(QPointF(center.x() - wheel.width() / 2, center.y() - wheel.height() / 2), wheel)
        if self.value < 1:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, int(255 * (1 - self.value))))
            p.drawEllipse(center, radius, radius)
        angle = self.hue * 2 * math.pi
        marker = QPointF(
            center.x() + math.cos(angle) * self.saturation * radius,
            center.y() - math.sin(angle) * self.saturation * radius,
        )
        p.setBrush(self.color())
        p.setPen(QPen(QColor("white" if self.value < 0.6 else "black"), 2))
        p.drawEllipse(marker, 6, 6)
        p.end()

    def _pick(self, position):
        center, radius = self._geometry()
        dx, dy = position.x() - center.x(), center.y() - position.y()
        self.hue = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
        self.saturation = min(1.0, math.hypot(dx, dy) / max(1, radius))
        self.update()
        self.colorChanged.emit(self.color())

    def mousePressEvent(self, event):
        self._pick(event.position())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._pick(event.position())


def color_icon(color, size=QSize(26, 16)):
    pixmap = QPixmap(size)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


class ColorPickerDialog(FormDialog):
    """Wheel, brightness slider, hex entry and quick swatches; .color() holds the choice."""

    def __init__(self, parent, title, color, swatches=()):
        super().__init__(parent, title)
        self.original = QColor(color)
        self.wheel = ColorWheel(color)
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setRange(0, 1000)
        self.brightness.setValue(round(self.original.valueF() * 1000))
        self.brightness.setAccessibleName("Brightness")
        self.hex = QLineEdit(self.original.name())
        self.hex.setAccessibleName("Hex color")
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression("#?[0-9a-fA-F]{0,6}"), self.hex))
        self.hex.setMaximumWidth(110)
        self.preview = QPushButton()
        self.preview.setObjectName("colorSwatch")
        self.preview.setEnabled(False)
        self.preview.setFixedSize(54, 26)
        self.layout.addWidget(self.wheel, 1)
        self.layout.addWidget(row(label("Brightness", "muted"), self.brightness))
        self.layout.addWidget(row(label("Hex", "muted"), self.hex, self.preview, None))
        if swatches:
            quick = QWidget()
            quick_layout = QHBoxLayout(quick)
            quick_layout.setContentsMargins(0, 0, 0, 0)
            quick_layout.setSpacing(4)
            for name, value in swatches:
                swatch = QPushButton()
                swatch.setObjectName("colorSwatch")
                swatch.setFixedSize(22, 18)
                swatch.setToolTip(name + " " + value)
                swatch.setAccessibleName(name)
                swatch.setStyleSheet("background:%s;" % value)
                swatch.clicked.connect(lambda checked=False, v=value: self.set_color(v))
                quick_layout.addWidget(swatch)
            quick_layout.addStretch()
            self.layout.addWidget(label("Current theme colors", "muted"))
            self.layout.addWidget(quick)
        self.wheel.colorChanged.connect(self._wheel_changed)
        self.brightness.valueChanged.connect(lambda v: self.wheel.set_value(v / 1000))
        self.hex.textEdited.connect(self._hex_edited)
        self.finish_form()
        self.buttons.button(QDialogButtonBox.Save).setText("Use color")
        self.resize(330, 420)
        self._show(self.original)

    def color(self):
        return self.wheel.color().name()

    def set_color(self, value):
        color = QColor(value)
        self.wheel.set_color(color)
        self.brightness.blockSignals(True)
        self.brightness.setValue(round(color.valueF() * 1000))
        self.brightness.blockSignals(False)
        self._show(color)

    def _show(self, color):
        self.preview.setStyleSheet("background:%s;" % QColor(color).name())
        if self.hex.text().lstrip("#").lower() != QColor(color).name().lstrip("#"):
            self.hex.setText(QColor(color).name())

    def _wheel_changed(self, color):
        self._show(color)

    def _hex_edited(self, text):
        value = "#" + text.lstrip("#")
        if len(value) == 7 and QColor.isValidColorName(value):
            color = QColor(value)
            self.wheel.set_color(color)
            self.brightness.blockSignals(True)
            self.brightness.setValue(round(color.valueF() * 1000))
            self.brightness.blockSignals(False)
            self.preview.setStyleSheet("background:%s;" % color.name())


def pick_color(parent, title, color, swatches=()):
    """Open the picker; returns "#rrggbb" or None when cancelled."""
    dialog = ColorPickerDialog(parent, title, color, swatches)
    return dialog.color() if dialog.exec() == QDialog.Accepted else None


class ColorSwatchButton(QPushButton):
    """Button showing a color; clicking opens the wheel picker."""

    colorPicked = Signal(str)

    def __init__(self, color, title, swatches=lambda: ()):
        super().__init__()
        self.setObjectName("colorSwatch")
        self.setFixedSize(46, 22)
        self.title = title
        self.swatches = swatches
        self.setAccessibleName(title + " color")
        self.clicked.connect(self.choose)
        self.set_color(color)

    def set_color(self, color):
        self._color = QColor(color).name()
        self.setStyleSheet("background:%s;" % self._color)
        self.setToolTip(self.title + " · " + self._color)

    def color(self):
        return self._color

    def choose(self):
        chosen = pick_color(self.window(), self.title, self._color, self.swatches())
        if chosen:
            self.set_color(chosen)
            self.colorPicked.emit(chosen)


class PalettePreview(QWidget):
    """Miniature window painted with a palette, so color choices can be judged before applying."""

    def __init__(self, colors=None):
        super().__init__()
        self.colors = colors or {}
        self.setMinimumHeight(92)
        self.setAccessibleName("Color preview")

    def set_colors(self, colors):
        self.colors = dict(colors)
        self.update()

    def paintEvent(self, event):
        c = self.colors
        if not c:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(c["bg"]))
        p.fillRect(0, 0, 26, h, QColor(c["rail"]))
        p.setPen(QColor(c["line"]))
        p.drawLine(26, 0, 26, h)
        p.drawRect(0, 0, w - 1, h - 1)
        p.setBrush(QColor(c["accent"]))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(7, 8, 12, 12), 3, 3)
        card = QRectF(36, 8, min(260, w - 46), h - 16)
        p.setBrush(QColor(c["panel"]))
        p.setPen(QColor(c["line"]))
        p.drawRoundedRect(card, 4, 4)
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(c["heading_text"]))
        p.drawText(card.adjusted(10, 6, -8, 0), Qt.AlignLeft | Qt.AlignTop, "Today")
        p.setFont(self.font())
        p.setPen(QColor(c["text"]))
        p.drawText(card.adjusted(10, 24, -8, 0), Qt.AlignLeft | Qt.AlignTop, "Review navigation")
        p.setPen(QColor(c["muted"]))
        p.drawText(card.adjusted(10, 40, -8, 0), Qt.AlignLeft | Qt.AlignTop, "In Progress · 45m")
        p.setPen(QColor(c["danger"]))
        p.drawText(card.adjusted(120, 40, -8, 0), Qt.AlignLeft | Qt.AlignTop, "Overdue")
        if w > 360:
            buttons = QRectF(card.right() + 12, 12, min(150, w - card.right() - 20), 22)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c["accent"]))
            p.drawRoundedRect(buttons, 4, 4)
            p.setPen(QColor(c["accent_text"]))
            p.drawText(buttons, Qt.AlignCenter, "Add")
            second = buttons.translated(0, 28)
            p.setBrush(QColor(c["button"]))
            p.setPen(QColor(c["button_hover"]))
            p.drawRoundedRect(second, 4, 4)
            p.setPen(QColor(c["button_text"]))
            p.drawText(second, Qt.AlignCenter, "Button")
            field = second.translated(0, 28)
            p.setBrush(QColor(c["input"]))
            p.setPen(QColor(c["line"]))
            p.drawRoundedRect(field, 4, 4)
            p.setPen(QColor(c["clock"]))
            p.drawText(field.adjusted(8, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, "00:42:10")
        p.end()
