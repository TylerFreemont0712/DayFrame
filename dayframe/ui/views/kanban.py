"""Ticket lanes with an immediate, temporary destination preview."""

import hashlib

from PySide6.QtCore import Qt, QMimeData, QSize, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QDrag, QFont, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QStyledItemDelegate,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
)

from ...core import domain as D
from ..labels import paint_label_pills
from ..dragdrop import TICKET_MIME
from ..theme import CURRENT as C

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
        paint_project_key(
            p,
            QRectF(rect.left() + 8, rect.top() + 5, rect.width() - 27, 18),
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
