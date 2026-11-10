"""Ticket lanes with an immediate, temporary destination preview."""

import hashlib

from PySide6.QtCore import QEasingCurve, QMimeData, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetricsF, QPainter, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QStyledItemDelegate,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QMenu,
)

from ...core import domain as D
from ..labels import paint_label_pills
from ..status import paint_status
from ..dragdrop import TICKET_MIME
from ..theme import CURRENT as C, icon

PREVIEW_ROLE = Qt.UserRole + 2


def project_color(project_id):
    hue = int(hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:8], 16) % 360
    light = QColor(C["raised"]).lightnessF() > 0.6
    return QColor.fromHsl(hue, 150, 55 if light else 180)


def paint_project_key(p, rect, project_id, prefix, suffix):
    p.save()
    metrics = p.fontMetrics()
    tail = " · " + suffix
    width = min(
        metrics.horizontalAdvance(prefix) + 10, max(16, rect.width() - metrics.horizontalAdvance(tail) - 3)
    )
    badge = QRectF(rect.left(), rect.top(), width, min(rect.height(), metrics.height() + 2))
    color = project_color(project_id)
    tint = QColor(color)
    tint.setAlpha(35)
    p.setBrush(tint)
    p.setPen(Qt.NoPen)
    radius = min(C.get("radius", 3), badge.height() / 2)
    p.drawRoundedRect(badge, radius, radius)
    p.setPen(color)
    p.drawText(
        badge.adjusted(5, 0, -5, 0),
        Qt.AlignVCenter | Qt.AlignLeft,
        metrics.elidedText(prefix, Qt.ElideRight, int(width - 10)),
    )
    remaining = QRectF(
        badge.right() + 3, rect.top(), max(0, rect.right() - badge.right() - 3), badge.height()
    )
    p.setPen(QColor(C["muted"]))
    p.drawText(
        remaining,
        Qt.AlignVCenter | Qt.AlignLeft,
        metrics.elidedText(tail, Qt.ElideRight, int(remaining.width())),
    )
    p.restore()


BADGE_HEIGHT = 18


def code_badge_rect(rect, count=0):
    """Clickable Code marker at a card's top right, left of the priority dot.

    Square for the glyph alone, wider when it also shows a changeset count.
    """
    width = BADGE_HEIGHT + (4 + 7 * len(str(min(count, 99))) if count else 0)
    return QRectF(rect.right() - 20 - width, rect.top() + 3, width, BADGE_HEIGHT)


def paint_code_badge(p, rect, count, hover=0.0, press=0.0):
    """The code glyph (and changeset count) centred in a small button.

    hover and press run from 0 to 1. Pressing sinks the button a pixel, deepens its fill
    and draws an accent ring, so it reads like the app's other pressed buttons.
    """
    p.save()
    accent = QColor(C["accent"])
    sink = 1.2 * press
    body = rect.adjusted(sink * 0.5, sink, -sink * 0.5, 0)
    fill = QColor(accent)
    fill.setAlpha(int(30 + 34 * hover + 70 * press))
    p.setBrush(fill)
    ring = QColor(accent)
    ring.setAlpha(int(150 * max(hover, press)))
    p.setPen(QPen(ring, 1) if hover or press else Qt.NoPen)
    radius = min(4.0, body.height() / 2)
    p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    side = 11
    text = str(min(count, 99)) if count else ""
    font = QFont(p.font())
    font.setPointSizeF(max(6.5, font.pointSizeF() - 0.5))
    font.setBold(True)
    metrics = QFontMetricsF(font)
    group = side + (3 + metrics.horizontalAdvance(text) if text else 0)
    left = body.center().x() - group / 2
    top = body.center().y() - side / 2
    glyph = QColor(C["accent_text"]) if press > 0.6 else accent
    icon("code", glyph.name()).paint(p, round(left), round(top), side, side)
    if text:
        p.setFont(font)
        p.setPen(glyph)
        p.drawText(
            QRectF(left + side + 3, body.top(), group, body.height()), Qt.AlignVCenter | Qt.AlignLeft, text
        )
    p.restore()


class PressAnimation(QVariantAnimation):
    """Animated 0 to 1 press level for a painted button; repaint() runs on every frame."""

    def __init__(self, repaint):
        super().__init__()
        self.level = 0.0
        self.after = None
        self.valueChanged.connect(lambda value: (setattr(self, "level", float(value)), repaint()))
        self.finished.connect(self._done)

    def run(self, target, duration, after=None):
        self.stop()
        self.after = after
        self.setStartValue(self.level)
        self.setEndValue(float(target))
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.OutCubic)
        self.start()

    def press(self):
        self.run(1.0, 70)

    def release(self, after=None):
        self.run(0.0, 150, after)

    def _done(self):
        after, self.after = self.after, None
        if after:
            after()


def card_size(ticket):
    return QSize(140, (120 if ticket["due_date"] else 105) + (20 if ticket["labels"] else 0))


def paint_title(p, rect, title):
    metrics = p.fontMetrics()
    line_spacing = metrics.height() + 3
    layout = QTextLayout(title, p.font())
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    lines = []
    layout.beginLayout()
    for _ in range(max(1, int((rect.height() + 3) // line_spacing))):
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(rect.width())
        lines.append(line)
    layout.endLayout()
    p.save()
    p.setClipRect(rect, Qt.IntersectClip)
    for i, line in enumerate(lines):
        origin = QPointF(rect.left(), rect.top() + i * line_spacing)
        if i == len(lines) - 1:
            # Qt positions count UTF-16 units, including emoji surrogate pairs.
            remaining = title.encode("utf-16-le")[line.textStart() * 2 :].decode("utf-16-le")
            p.drawText(
                origin + QPointF(0, metrics.ascent()),
                metrics.elidedText(remaining, Qt.ElideRight, int(rect.width())),
            )
        else:
            line.draw(p, origin)
    p.restore()


class BoardDelegate(QStyledItemDelegate):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window

    def paint(self, p, option, index):
        ticket = index.data(Qt.UserRole + 1)
        if not ticket:
            return
        ghost = bool(index.data(PREVIEW_ROLE))
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if ghost:
            p.setOpacity(0.52)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = not ghost and ticket["id"] == self.window.selected
        pen = QPen(QColor(C["accent"] if selected or ghost else C["line"]), 1.4 if selected or ghost else 0.8)
        if ghost:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(C["raised"]))
        p.drawRoundedRect(rect, C.get("radius", 4), C.get("radius", 4))
        font = QFont(QApplication.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5))
        p.setFont(font)
        project = next((x for x in self.window.data["project"] if x["id"] == ticket["project_id"]), {})
        code = bool(self.window.code_repo(ticket["project_id"])) and not ghost
        count = self.window.changeset_count(ticket["id"]) if code else 0
        badge = code_badge_rect(rect, count)
        key_right = badge.left() - 6 if code else rect.right() - 19
        paint_project_key(
            p,
            QRectF(rect.left() + 8, rect.top() + 5, key_right - rect.left() - 8, 18),
            ticket["project_id"],
            project.get("project_key", "T"),
            ticket["id"][:6].upper(),
        )
        color = {"urgent": "#ee797e", "high": "#e1b65d", "medium": "#83c98d", "low": "#8da4b3"}[
            ticket["priority"]
        ]
        p.setBrush(QColor(color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(rect.right() - 10, rect.top() + 12), 3, 3)
        if code:
            lane = self.parent()
            mine = getattr(lane, "badge_ticket", None) == ticket["id"]
            paint_code_badge(
                p,
                badge,
                count,
                1.0 if mine and lane.badge_hover else 0.0,
                lane.badge_press.level if mine else 0.0,
            )
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(C["text"]))
        paint_title(p, QRectF(rect.left() + 8, rect.top() + 25, rect.width() - 16, 32), ticket["title"])
        font.setBold(False)
        p.setFont(font)
        project = self.window.project_name(ticket["project_id"])
        badge = QRectF(
            rect.left() + 8,
            rect.top() + 60,
            min(rect.width() - 16, p.fontMetrics().horizontalAdvance(project) + 12),
            16,
        )
        p.setBrush(QColor(C["panel"]))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(badge, 3, 3)
        p.setPen(QColor(C["text"]))
        p.drawText(
            badge, Qt.AlignCenter, p.fontMetrics().elidedText(project, Qt.ElideRight, int(badge.width() - 6))
        )
        tracked = self.window.tracked_ms(ticket["id"])
        text = D.short_time(ticket["estimate_min"] * 60000) + (
            (" · " + D.short_time(tracked)) if tracked else ""
        )
        if self.window.blocked(ticket):
            text = "Blocked · " + text
        p.setPen(QColor("#e1b65d" if self.window.blocked(ticket) else C["muted"]))
        extra = 20 if ticket["labels"] else 0
        if extra:
            paint_label_pills(
                p, QRectF(rect.left() + 8, rect.top() + 82, rect.width() - 16, 16), ticket["labels"]
            )
        p.drawText(rect.adjusted(8, 82 + extra, -6, -6), Qt.AlignTop, text)
        if ticket["due_date"]:
            p.setPen(QColor(C["muted"]))
            p.drawText(rect.adjusted(8, 99 + extra, -6, -3), Qt.AlignTop, "Due " + ticket["due_date"][5:])
        paint_status(p, QRectF(rect.right() - 20, rect.bottom() - 20, 14, 14), ticket["status"])
        p.restore()


class TicketList(QListWidget):
    def __init__(self, window, status):
        super().__init__()
        self.window = window
        self.status = status
        self.preview_item = None
        self.setObjectName("ticketLane")
        self.setAccessibleName(D.STATUS_NAMES[status] + " tickets")
        self.setItemDelegate(BoardDelegate(window, self))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setSpacing(3)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.itemClicked.connect(
            lambda item: window.select_ticket(item.data(Qt.UserRole)) if item.data(Qt.UserRole) else None
        )
        # The Code badge behaves like a small button: hover ring, animated press, open on release.
        self.badge_ticket = None
        self.badge_hover = False
        self.badge_pressed = False
        self.badge_press = PressAnimation(self.viewport().update)
        self.setMouseTracking(True)

    def code_hit(self, pos):
        """The ticket whose Code badge is under a viewport position, if any."""
        item = self.itemAt(pos)
        ticket = self.window.find_ticket(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None
        if not ticket or not self.window.code_repo(ticket["project_id"]):
            return None
        rect = QRectF(self.visualItemRect(item)).adjusted(2, 2, -2, -2)
        badge = code_badge_rect(rect, self.window.changeset_count(ticket["id"]))
        return ticket["id"] if badge.adjusted(-2, -2, 2, 2).contains(QPointF(pos)) else None

    def mousePressEvent(self, event):
        ticket_id = self.code_hit(event.position().toPoint()) if event.button() == Qt.LeftButton else None
        if ticket_id:
            self.badge_ticket, self.badge_hover, self.badge_pressed = ticket_id, True, True
            self.badge_press.press()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.badge_pressed:
            self.badge_hover = self.code_hit(event.position().toPoint()) == self.badge_ticket
            self.viewport().update()
            event.accept()
            return
        hit = self.code_hit(event.position().toPoint())
        if bool(hit) != self.badge_hover or (hit and hit != self.badge_ticket):
            self.badge_hover = bool(hit)
            if hit:
                self.badge_ticket = hit
            self.viewport().setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
            self.viewport().setToolTip("Open in Code" if hit else "")
            self.viewport().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.badge_pressed:
            self.badge_pressed = False
            ticket_id = self.badge_ticket
            inside = self.code_hit(event.position().toPoint()) == ticket_id
            # Let the button spring back before the page changes, like a real button.
            self.badge_press.release(
                (lambda: QTimer.singleShot(0, lambda: self.window.open_code(ticket_id))) if inside else None
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self.badge_pressed and self.badge_hover:
            self.badge_hover = False
            self.viewport().update()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        ticket = self.window.find_ticket(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None
        if not ticket:
            return
        w, ticket_id = self.window, ticket["id"]
        menu = QMenu(self)
        menu.addAction(icon("external-link-alt"), "Open ticket", lambda: w.select_ticket(ticket_id))
        if w.code_repo(ticket["project_id"]):
            menu.addAction(
                icon("code"), "Open in Code", lambda: QTimer.singleShot(0, lambda: w.open_code(ticket_id))
            )
        menu.addAction(
            icon("play"),
            "Start timer",
            lambda: w.execute("timer.action", {"action": "start", "ticket_id": ticket_id}),
        )
        menu.addAction(icon("calendar-plus"), "Schedule work", lambda: w.schedule_ticket(ticket))
        menu.exec(event.globalPos())

    def startDrag(self, actions):
        item = self.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        mime = QMimeData()
        mime.setData(TICKET_MIME, item.data(Qt.UserRole).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        card = self.visualItemRect(item)
        drag.setPixmap(self.viewport().grab(card))
        drag.setHotSpot(card.center() - card.topLeft())
        try:
            drag.exec(Qt.MoveAction)
        finally:
            for lane in self.window.findChildren(TicketList):
                lane.clear_preview()

    def dragged_ticket(self, event):
        if not event.mimeData().hasFormat(TICKET_MIME):
            return None
        try:
            ticket_id = bytes(event.mimeData().data(TICKET_MIME)).decode("utf-8")
        except UnicodeDecodeError:
            return None
        ticket = self.window.find_ticket(ticket_id)
        if ticket and not ticket["archived"]:
            return ticket
        return None

    def clear_preview(self):
        if self.preview_item is not None:
            self.takeItem(self.row(self.preview_item))
            self.preview_item = None

    def show_preview(self, ticket):
        for lane in self.window.findChildren(TicketList):
            if lane is not self:
                lane.clear_preview()
        if ticket["status"] == self.status:
            self.clear_preview()
            return
        if self.preview_item is not None and self.preview_item.data(Qt.UserRole + 1)["id"] == ticket["id"]:
            return
        self.clear_preview()
        item = QListWidgetItem("Move " + ticket["title"] + " to " + D.STATUS_NAMES[self.status])
        item.setData(Qt.UserRole + 1, {**ticket, "status": self.status})
        item.setData(PREVIEW_ROLE, True)
        item.setFlags(Qt.NoItemFlags)
        item.setSizeHint(card_size(ticket))
        # Match the board's saved ticket order, including when filters hide cards.
        order = {t["id"]: i for i, t in enumerate(self.window.data["ticket"])}
        position = sum(
            order.get(self.item(i).data(Qt.UserRole), -1) < order[ticket["id"]] for i in range(self.count())
        )
        self.insertItem(position, item)
        self.preview_item = item
        self.scrollToItem(item, QAbstractItemView.EnsureVisible)

    def dragEnterEvent(self, event):
        ticket = self.dragged_ticket(event)
        if ticket:
            self.show_preview(ticket)
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            self.clear_preview()
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.clear_preview()
        event.accept()

    def dropEvent(self, event):
        ticket = self.dragged_ticket(event)
        self.clear_preview()
        if not ticket:
            event.ignore()
            return
        if ticket["status"] != self.status:
            window, previous, ticket_id = self.window, ticket["status"], ticket["id"]
            if not window.execute("ticket.save", {"id": ticket_id, "status": self.status}):
                event.ignore()
                return
            window.undo_action = lambda: window.execute("ticket.save", {"id": ticket_id, "status": previous})
        event.setDropAction(Qt.MoveAction)
        event.accept()
