"""Stage symbols: one small painted glyph and color per workflow status.

The shapes fill up as work advances (dashed ring, half, three quarters, ring with a
core, solid disc with a check), so a stage reads at a glance without its name and
without relying on color alone. Painted widgets call paint_status(); buttons, menus,
combo boxes and tables use status_icon().
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from ..core import domain as D
from .theme import CURRENT as C

# Mid-tones that stay readable on both light and dark surfaces. Not Started follows the
# theme's muted color instead.
STATUS_COLORS = {"ready": "#5b9bf0", "doing": "#d9a441", "review": "#a884e0", "done": "#5cb87a"}
_cache = {}


def status_color(status):
    return QColor(STATUS_COLORS.get(status, C["muted"]))


def paint_status(p, rect, status):
    """Draw the stage glyph centred in rect, sized to its shorter side."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(rect)
    size = min(rect.width(), rect.height())
    center = rect.center()
    stroke = max(1.2, size * 0.115)
    radius = size / 2 - stroke / 2 - 0.5
    color = status_color(status)
    ring = QPen(color, stroke)
    p.setBrush(Qt.NoBrush)
    if status == "done":
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(center, radius + stroke / 2, radius + stroke / 2)
        tick = QPen(QColor(C["panel"]), max(1.4, size * 0.14))
        tick.setCapStyle(Qt.RoundCap)
        tick.setJoinStyle(Qt.RoundJoin)
        p.setPen(tick)
        p.setBrush(Qt.NoBrush)
        mark = QPainterPath(center + QPointF(-radius * 0.48, radius * 0.04))
        mark.lineTo(center + QPointF(-radius * 0.12, radius * 0.4))
        mark.lineTo(center + QPointF(radius * 0.5, radius * -0.36))
        p.drawPath(mark)
    elif status in ("ready", "doing", "review"):
        p.setPen(ring)
        p.drawEllipse(center, radius, radius)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        inner = radius - stroke * 1.15
        if status == "review":
            p.drawEllipse(center, inner * 0.62, inner * 0.62)
        else:
            # Angles are sixteenths of a degree, counter-clockwise from three o'clock; a
            # negative span fills clockwise from twelve o'clock like a progress pie.
            span = -180 if status == "ready" else -270
            box = QRectF(center.x() - inner, center.y() - inner, inner * 2, inner * 2)
            p.drawPie(box, 90 * 16, span * 16)
    else:
        ring.setDashPattern([1.7, 1.5])
        ring.setCapStyle(Qt.FlatCap)
        p.setPen(ring)
        p.drawEllipse(center, radius, radius)
    p.restore()


def status_pixmap(status, size=14):
    app = QApplication.instance()
    ratio = app.devicePixelRatio() if app else 1.0
    key = (status, size, ratio, C["muted"], C["panel"])
    if key not in _cache:
        pixmap = QPixmap(round(size * ratio), round(size * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        paint_status(p, QRectF(0, 0, size, size), status)
        p.end()
        _cache[key] = pixmap
    return _cache[key]


def status_icon(status, size=14):
    return QIcon(status_pixmap(status, size))


def status_label(status, size=14):
    """A fixed-size glyph for widget rows; the stage name is its tooltip and accessible name."""
    w = QLabel()
    w.setPixmap(status_pixmap(status, size))
    w.setFixedSize(size + 2, size + 2)
    w.setAlignment(Qt.AlignCenter)
    w.setToolTip(D.STATUS_NAMES.get(status, ""))
    w.setAccessibleName(D.STATUS_NAMES.get(status, ""))
    return w


def add_status_icons(box):
    """Give every stage entry of a combo box its glyph; other entries are left alone."""
    for index in range(box.count()):
        if box.itemData(index) in D.STATUSES:
            box.setItemIcon(index, status_icon(box.itemData(index)))
    return box
