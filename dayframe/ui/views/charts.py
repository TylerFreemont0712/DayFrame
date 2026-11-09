"""Small painted charts and stat tiles for the Tickets overview.

Marks follow one spec: columns at most 24 px wide with 4 px rounded data ends and a
square baseline, 2 px gaps between neighbours, hairline solid gridlines one step off the
surface, round tick values and text in text colours (never the series colour). A single
series uses the accent and needs no legend; two series pair a muted de-emphasis colour
with the accent and always show a legend. Every mark has a hover tooltip, and the table
on the same page carries the underlying values.
"""

import math
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QToolTip, QVBoxLayout, QWidget
from ..theme import CURRENT as C
from ..widgets import label

BAR_MAX = 24


def nice_max(value):
    """A round axis top (1, 2, 2.5, 5 × 10ⁿ) at or above value."""
    if value <= 0:
        return 1
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * power:
            return step * power
    return 10 * power


def rounded_column(rect, radius=4):
    """A column rounded at its data end (top) and square at the baseline."""
    radius = min(radius, rect.width() / 2, rect.height())
    path = QPainterPath()
    path.moveTo(rect.bottomLeft())
    path.lineTo(rect.left(), rect.top() + radius)
    path.quadTo(rect.topLeft(), QPointF(rect.left() + radius, rect.top()))
    path.lineTo(rect.right() - radius, rect.top())
    path.quadTo(rect.topRight(), QPointF(rect.right(), rect.top() + radius))
    path.lineTo(rect.bottomRight())
    path.closeSubpath()
    return path


def rounded_bar(rect, radius=4):
    """A horizontal bar rounded at its data end (right) and square at the baseline."""
    radius = min(radius, rect.height() / 2, rect.width())
    path = QPainterPath()
    path.moveTo(rect.topLeft())
    path.lineTo(rect.right() - radius, rect.top())
    path.quadTo(rect.topRight(), QPointF(rect.right(), rect.top() + radius))
    path.lineTo(rect.right(), rect.bottom() - radius)
    path.quadTo(rect.bottomRight(), QPointF(rect.right() - radius, rect.bottom()))
    path.lineTo(rect.bottomLeft())
    path.closeSubpath()
    return path


def series_colors(count):
    """One series: the accent. Two: muted context first, accent for the series that matters."""
    accent = QColor(C["accent"])
    if count == 1:
        return [accent]
    muted = QColor(C["muted"])
    muted.setAlpha(150)
    return [muted, accent]


class ColumnChart(QWidget):
    """Columns over labelled slots, one or two series sharing one axis."""

    def __init__(self, slots, series, value_text=str, slot_text=None, axis_text=None):
        super().__init__()
        self.slots = slots
        self.series = series  # [(name, [values])]
        self.value_text = value_text
        self.axis_text = axis_text or value_text
        self.slot_text = slot_text or (lambda s: s)
        self.hover = None
        self.setMouseTracking(True)
        self.setMinimumHeight(150)
        names = ", ".join(name for name, _ in series)
        self.setAccessibleName(names + " over " + str(len(slots)) + " periods")

    def sizeHint(self):
        return QSize(320, 170)

    def geometry_(self):
        metrics = QFontMetricsF(self.font())
        top = 22 if len(self.series) > 1 else 8
        bottom = metrics.height() + 6
        peak = nice_max(max([max(values or [0]) for _, values in self.series] + [0]))
        left = max(metrics.horizontalAdvance(self.axis_text(peak)), 16) + 8
        return QRectF(left, top, self.width() - left - 6, self.height() - top - bottom), peak

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot, peak = self.geometry_()
        metrics = QFontMetricsF(self.font())
        grid = QColor(C["line"])
        for step in range(5):
            y = plot.bottom() - plot.height() * step / 4
            p.setPen(grid)
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            if step % 2 == 0:
                p.setPen(QColor(C["muted"]))
                p.drawText(
                    QRectF(0, y - 8, plot.left() - 5, 16),
                    Qt.AlignRight | Qt.AlignVCenter,
                    self.axis_text(peak * step / 4),
                )
        slot = plot.width() / max(1, len(self.slots))
        colors = series_colors(len(self.series))
        count = len(self.series)
        bar = min(BAR_MAX, (slot * 0.7 - 2 * (count - 1)) / count)
        group = bar * count + 2 * (count - 1)
        every = max(
            1, math.ceil(len(self.slots) * (metrics.horizontalAdvance("00/00") + 8) / max(1, plot.width()))
        )
        for index, key in enumerate(self.slots):
            x0 = plot.left() + slot * index
            if index == self.hover:
                tint = QColor(C["accent"])
                tint.setAlpha(22)
                p.fillRect(QRectF(x0, plot.top(), slot, plot.height()), tint)
            start = x0 + (slot - group) / 2
            for number, (name, values) in enumerate(self.series):
                value = values[index] if index < len(values) else 0
                height = plot.height() * value / peak if peak else 0
                if height <= 0:
                    continue
                rect = QRectF(start + number * (bar + 2), plot.bottom() - height, bar, height)
                p.setPen(Qt.NoPen)
                p.setBrush(colors[number])
                p.drawPath(rounded_column(rect))
            # Count from the newest slot so the latest label always shows without colliding.
            if (len(self.slots) - 1 - index) % every == 0:
                p.setPen(QColor(C["muted"]))
                p.drawText(
                    QRectF(x0 - 10, plot.bottom() + 3, slot + 20, metrics.height()),
                    Qt.AlignHCenter | Qt.AlignTop,
                    self.slot_text(key),
                )
        if count > 1:
            x = plot.left()
            for number, (name, _) in enumerate(self.series):
                p.setBrush(colors[number])
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x, 5, 10, 10), 2, 2)
                p.setPen(QColor(C["text"]))
                p.drawText(QRectF(x + 14, 0, 200, 20), Qt.AlignVCenter, name)
                x += 14 + metrics.horizontalAdvance(name) + 14
        p.end()

    def mouseMoveEvent(self, event):
        plot, _ = self.geometry_()
        slot = plot.width() / max(1, len(self.slots))
        index = int((event.position().x() - plot.left()) // slot) if slot else -1
        if not 0 <= index < len(self.slots) or not plot.adjusted(0, -10, 0, 20).contains(event.position()):
            index = None
        if index != self.hover:
            self.hover = index
            self.update()
        if index is None:
            QToolTip.hideText()
            return
        lines = [self.slot_text(self.slots[index])]
        for name, values in self.series:
            lines.append(name + ": " + self.value_text(values[index] if index < len(values) else 0))
        QToolTip.showText(event.globalPosition().toPoint(), "\n".join(lines), self)

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        super().leaveEvent(event)


class BarList(QWidget):
    """Horizontal bars: name, bar and value per row, one series or two (with a legend)."""

    ROW = 22

    def __init__(self, rows, value_text=str, series=("Value",)):
        super().__init__()
        self.rows = rows  # [(name, value) | (name, (value1, value2))]
        self.series = series
        self.value_text = value_text
        self.hover = None
        self.setMouseTracking(True)
        top = 22 if len(series) > 1 else 0
        self.setMinimumHeight(top + max(1, len(rows)) * self.ROW + 4)
        self.setAccessibleName(", ".join(series) + " for " + str(len(rows)) + " rows")

    def sizeHint(self):
        return QSize(320, self.minimumHeight())

    def values(self, row):
        value = row[1]
        return value if isinstance(value, tuple) else (value,)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        metrics = QFontMetricsF(self.font())
        top = 22 if len(self.series) > 1 else 0
        names = max([metrics.horizontalAdvance(r[0]) for r in self.rows] + [40])
        name_width = min(names + 8, self.width() * 0.38)
        value_width = (
            max(
                [
                    metrics.horizontalAdvance(" / ".join(self.value_text(v) for v in self.values(r)))
                    for r in self.rows
                ]
                + [20]
            )
            + 8
        )
        track = QRectF(name_width, 0, max(10, self.width() - name_width - value_width), 0)
        peak = max([max(self.values(r)) for r in self.rows] + [0]) or 1
        colors = series_colors(len(self.series))
        if len(self.series) > 1:
            x = name_width
            for number, name in enumerate(self.series):
                p.setBrush(colors[number])
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x, 5, 10, 10), 2, 2)
                p.setPen(QColor(C["text"]))
                p.drawText(QRectF(x + 14, 0, 200, 20), Qt.AlignVCenter, name)
                x += 14 + metrics.horizontalAdvance(name) + 14
        if not self.rows:
            p.setPen(QColor(C["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Nothing to show yet")
        for index, row in enumerate(self.rows):
            y = top + index * self.ROW
            if index == self.hover:
                tint = QColor(C["accent"])
                tint.setAlpha(22)
                p.fillRect(QRectF(0, y, self.width(), self.ROW), tint)
            p.setPen(QColor(C["text"]))
            p.drawText(
                QRectF(0, y, name_width - 8, self.ROW),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(row[0], Qt.ElideRight, name_width - 8),
            )
            values = self.values(row)
            height = min(10.0, (self.ROW - 8 - 2 * (len(values) - 1)) / len(values))
            block = height * len(values) + 2 * (len(values) - 1)
            for number, value in enumerate(values):
                width = track.width() * value / peak
                if width > 0:
                    rect = QRectF(
                        track.left(), y + (self.ROW - block) / 2 + number * (height + 2), width, height
                    )
                    p.setPen(Qt.NoPen)
                    p.setBrush(colors[number])
                    p.drawPath(rounded_bar(rect))
            p.setPen(QColor(C["muted"]))
            p.drawText(
                QRectF(track.right() + 6, y, value_width, self.ROW),
                Qt.AlignVCenter | Qt.AlignLeft,
                " / ".join(self.value_text(v) for v in values),
            )
        p.end()

    def mouseMoveEvent(self, event):
        top = 22 if len(self.series) > 1 else 0
        index = int((event.position().y() - top) // self.ROW)
        if not 0 <= index < len(self.rows):
            index = None
        if index != self.hover:
            self.hover = index
            self.update()
        if index is None:
            QToolTip.hideText()
            return
        row = self.rows[index]
        values = self.values(row)
        lines = [row[0]] + [name + ": " + self.value_text(v) for name, v in zip(self.series, values)]
        QToolTip.showText(event.globalPosition().toPoint(), "\n".join(lines), self)

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        super().leaveEvent(event)


def stat_tile(title, value, delta="", good=None, hint=""):
    """A figure: label, value and an optional signed change against a named period.

    The change carries an arrow and words as well as colour, so it never relies on colour alone.
    """
    tile = QFrame()
    tile.setObjectName("statTile")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(10, 7, 10, 7)
    layout.setSpacing(1)
    layout.addWidget(label(title, "muted"))
    figure = label(value, "statValue")
    figure.setAccessibleName(title + ": " + value)
    layout.addWidget(figure)
    note = label(delta or hint or " ", "muted")
    if delta and good is not None:
        note.setStyleSheet("color:" + (C["accent"] if good else C["warning"]) + ";")
    layout.addWidget(note)
    tile.setToolTip(hint or title)
    return tile
