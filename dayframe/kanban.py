"""Ticket lanes with an immediate, temporary destination preview."""
from PySide6.QtCore import Qt, QMimeData, QSize, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QDrag, QFont
from PySide6.QtWidgets import (
    QApplication, QStyledItemDelegate, QListWidget, QListWidgetItem,
    QAbstractItemView,
)

from . import domain as D
from .labels import paint_label_pills
from .theme import CURRENT as C

TICKET_MIME = 'application/x-timemanager-ticket'
PREVIEW_ROLE = Qt.UserRole + 2


def card_size(ticket):
    return QSize(140, (120 if ticket['due_date'] else 105) + (20 if ticket['labels'] else 0))


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
            p.setOpacity(.52)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = not ghost and ticket['id'] == self.window.selected
        pen = QPen(QColor(C['accent'] if selected or ghost else C['line']), 1.4 if selected or ghost else .8)
        if ghost:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(C['raised']))
        p.drawRoundedRect(rect, C.get('radius', 4), C.get('radius', 4))
        font = QFont(QApplication.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - .5))
        p.setFont(font)
        p.setPen(QColor(C['muted']))
        p.drawText(rect.adjusted(8, 6, -9, -6), Qt.AlignTop, self.window.ticket_key(ticket))
        color = {'urgent': '#ee797e', 'high': '#e1b65d', 'medium': '#83c98d', 'low': '#8da4b3'}[ticket['priority']]
        p.setBrush(QColor(color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(rect.right() - 10, rect.top() + 12), 3, 3)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(C['text']))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 25, rect.width() - 15, 32), Qt.TextWordWrap | Qt.AlignTop, ticket['title'])
        font.setBold(False)
        p.setFont(font)
        project = self.window.project_name(ticket['project_id'])
        badge = QRectF(rect.left() + 8, rect.top() + 60, min(rect.width() - 16, p.fontMetrics().horizontalAdvance(project) + 12), 16)
        tint = QColor(C['accent'])
        tint.setAlpha(30)
        p.setBrush(tint)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(badge, 3, 3)
        p.setPen(QColor(C['text']))
        p.drawText(badge, Qt.AlignCenter, p.fontMetrics().elidedText(project, Qt.ElideRight, int(badge.width() - 6)))
        tracked = self.window.tracked_ms(ticket['id'])
        text = D.short_time(ticket['estimate_min'] * 60000) + ((' · ' + D.short_time(tracked)) if tracked else '')
        if self.window.blocked(ticket):
            text = 'Blocked · ' + text
        p.setPen(QColor('#e1b65d' if self.window.blocked(ticket) else C['muted']))
        extra = 20 if ticket['labels'] else 0
        if extra:
            paint_label_pills(p, QRectF(rect.left() + 8, rect.top() + 82, rect.width() - 16, 16), ticket['labels'])
        p.drawText(rect.adjusted(8, 82 + extra, -6, -6), Qt.AlignTop, text)
        if ticket['due_date']:
            p.setPen(QColor(C['muted']))
            p.drawText(rect.adjusted(8, 99 + extra, -6, -3), Qt.AlignTop, 'Due ' + ticket['due_date'][5:])
        p.restore()


class TicketList(QListWidget):
    def __init__(self, window, status):
        super().__init__()
        self.window = window
        self.status = status
        self.preview_item = None
        self.setObjectName('ticketLane')
        self.setAccessibleName(D.STATUS_NAMES[status] + ' tickets')
        self.setItemDelegate(BoardDelegate(window, self))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setSpacing(3)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.itemClicked.connect(lambda item: window.select_ticket(item.data(Qt.UserRole)) if item.data(Qt.UserRole) else None)

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
            ticket_id = bytes(event.mimeData().data(TICKET_MIME)).decode('utf-8')
        except UnicodeDecodeError:
            return None
        ticket = self.window.find_ticket(ticket_id)
        if ticket and not ticket['archived']:
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
        if ticket['status'] == self.status:
            self.clear_preview()
            return
        if self.preview_item is not None and self.preview_item.data(Qt.UserRole + 1)['id'] == ticket['id']:
            return
        self.clear_preview()
        item = QListWidgetItem('Move ' + ticket['title'] + ' to ' + D.STATUS_NAMES[self.status])
        item.setData(Qt.UserRole + 1, {**ticket, 'status': self.status})
        item.setData(PREVIEW_ROLE, True)
        item.setFlags(Qt.NoItemFlags)
        item.setSizeHint(card_size(ticket))
        # Match the board's saved ticket order, including when filters hide cards.
        order = {t['id']: i for i, t in enumerate(self.window.data['ticket'])}
        position = sum(order.get(self.item(i).data(Qt.UserRole), -1) < order[ticket['id']] for i in range(self.count()))
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
        if ticket['status'] != self.status:
            window, previous, ticket_id = self.window, ticket['status'], ticket['id']
            if not window.execute('ticket.save', {'id': ticket_id, 'status': self.status}):
                event.ignore()
                return
            window.undo_action = lambda: window.execute('ticket.save', {'id': ticket_id, 'status': previous})
        event.setDropAction(Qt.MoveAction)
        event.accept()
