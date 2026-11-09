"""Painted cards for the Code page: ticket cards and changeset cards.

TicketCards is a fixed-width list of outlined ticket cards with project key, status,
priority, labels and changeset count. ChangesetStrip is a horizontal row of changeset
cards led by the working tree.
"""

import re
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QApplication, QListView, QListWidget, QStyledItemDelegate
from ...core import domain as D
from ..labels import paint_label_pills
from ..theme import CURRENT as C, icon
from .kanban import paint_project_key, paint_title, project_color

TICKET_ROLE = Qt.UserRole + 1
INFO_ROLE = Qt.UserRole + 2
CARD_LIST_WIDTH = 304
PRIORITY_COLORS = {"urgent": "#ee797e", "high": "#e1b65d", "medium": "#83c98d", "low": "#8da4b3"}


def short_stat(stat):
    """'3 files changed, 10 insertions(+), 2 deletions(-)' → '3 files · +10 −2'."""
    files = re.search(r"(\d+) files? changed", stat or "")
    added = re.search(r"(\d+) insertions?", stat or "")
    removed = re.search(r"(\d+) deletions?", stat or "")
    if not files:
        return stat or ""
    return "%s file%s · +%s −%s" % (
        files.group(1),
        "" if files.group(1) == "1" else "s",
        added.group(1) if added else "0",
        removed.group(1) if removed else "0",
    ) + (" · " + stat.split(" · ", 1)[1] if " · " in stat else "")


def small_font(delta=-0.5, bold=False):
    font = QFont(QApplication.font())
    font.setPointSizeF(max(7.0, font.pointSizeF() + delta))
    font.setBold(bold)
    return font


def card_frame(p, rect, selected, accent=None, dashed=False):
    pen = QPen(QColor(C["accent"] if selected else C["line"]), 1.6 if selected else 1.0)
    if dashed:
        pen.setStyle(Qt.DashLine)
    p.setPen(pen)
    p.setBrush(QColor(C["raised"]))
    radius = C.get("radius", 4)
    p.drawRoundedRect(rect, radius, radius)
    if accent is not None:
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(rect.left() + 1, rect.top() + 6, 3, rect.height() - 12), 1.5, 1.5)


def pill(p, rect_right, y, text, color, filled=False):
    """A small rounded tag ending at rect_right; returns its left edge."""
    width = p.fontMetrics().horizontalAdvance(text) + 12
    box = QRectF(rect_right - width, y, width, 16)
    fill = QColor(color)
    fill.setAlpha(210 if filled else 34)
    p.setBrush(fill)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(box, 8, 8)
    p.setPen(QColor(C["accent_text"]) if filled else QColor(color))
    p.drawText(box, Qt.AlignCenter, text)
    return box.left()


class TicketCardDelegate(QStyledItemDelegate):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window

    def sizeHint(self, option, index):
        info = index.data(INFO_ROLE) or {}
        return QSize(CARD_LIST_WIDTH - 24, 96 if info.get("footer") else 74)

    def paint(self, p, option, index):
        ticket = index.data(TICKET_ROLE)
        info = index.data(INFO_ROLE) or {}
        if not ticket:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(3, 3, -3, -3)
        selected = index.data(Qt.UserRole) == getattr(self.window, "code_ticket", None)
        card_frame(p, rect, selected, project_color(ticket["project_id"]))
        p.setFont(small_font())
        project = next((x for x in self.window.data["project"] if x["id"] == ticket["project_id"]), {})
        right = rect.right() - 8
        status = D.STATUS_NAMES[ticket["status"]]
        status_color = C["accent"] if ticket["status"] in ("ready", "doing", "review") else C["muted"]
        left = pill(
            p, right, rect.top() + 6, status, QColor(status_color), filled=ticket["status"] == "doing"
        )
        p.setBrush(QColor(PRIORITY_COLORS.get(ticket["priority"], C["muted"])))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(left - 11, rect.top() + 10, 7, 7))
        paint_project_key(
            p,
            QRectF(rect.left() + 10, rect.top() + 6, max(40, left - rect.left() - 26), 17),
            ticket["project_id"],
            project.get("project_key", "T"),
            ticket["id"][:6].upper(),
        )
        p.setFont(small_font(0.3, True))
        p.setPen(QColor(C["text"]))
        paint_title(p, QRectF(rect.left() + 10, rect.top() + 28, rect.width() - 20, 34), ticket["title"])
        if info.get("footer"):
            p.setFont(small_font(-0.8))
            y = rect.bottom() - 22
            x_right = rect.right() - 8
            if info.get("applied"):
                x_right = pill(p, x_right, y, "applied here", QColor(C["accent"]), filled=True) - 4
            if info.get("changesets"):
                text = str(info["changesets"])
                width = p.fontMetrics().horizontalAdvance(text) + 22
                box = QRectF(x_right - width, y, width, 16)
                icon("layer-group", C["accent"]).paint(p, int(box.left() + 2), int(y + 2), 12, 12)
                p.setPen(QColor(C["accent"]))
                p.drawText(box.adjusted(16, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
                x_right = box.left() - 6
            if info.get("blocked"):
                x_right = pill(p, x_right, y, "blocked", QColor(C["warning"])) - 4
            if ticket["labels"]:
                paint_label_pills(
                    p,
                    QRectF(rect.left() + 10, y, max(0, x_right - rect.left() - 14), 16),
                    ticket["labels"],
                    3,
                )
        p.restore()


class TicketCards(QListWidget):
    """Fixed-width column of ticket cards (the divider beside it does not move)."""

    def __init__(self, window):
        super().__init__()
        self.setObjectName("ticketCards")
        self.setAccessibleName("Tickets")
        self.setItemDelegate(TicketCardDelegate(window, self))
        self.setFixedWidth(CARD_LIST_WIDTH)
        self.setSpacing(2)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SingleSelection)


class ChangesetDelegate(QStyledItemDelegate):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window

    def sizeHint(self, option, index):
        return QSize(236, 70)

    def paint(self, p, option, index):
        info = index.data(INFO_ROLE)
        if not info:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(3, 3, -3, -3)
        selected = index.data(Qt.UserRole) == getattr(self.window, "code_item", None)
        working = info["kind"] == "worktree"
        card_frame(p, rect, selected, QColor(C["accent"]) if info.get("applied") else None, dashed=working)
        inner = rect.adjusted(10, 6, -8, -6)
        p.setFont(small_font(0.2, True))
        p.setPen(QColor(C["text"]))
        glyph = "pen" if working else "layer-group"
        icon(glyph, C["accent"] if working and info.get("files") or info.get("applied") else None).paint(
            p, int(inner.left()), int(inner.top() + 2), 12, 12
        )
        title_right = inner.right()
        p.setFont(small_font(-0.8))
        if info.get("applied"):
            title_right = pill(p, inner.right(), inner.top(), "applied", QColor(C["accent"]), filled=True) - 4
        p.setFont(small_font(0.2, True))
        p.setPen(QColor(C["text"]))
        p.drawText(
            QRectF(inner.left() + 17, inner.top(), title_right - inner.left() - 17, 16),
            Qt.AlignVCenter,
            p.fontMetrics().elidedText(info["title"], Qt.ElideRight, int(title_right - inner.left() - 17)),
        )
        p.setFont(small_font(-0.6))
        p.setPen(QColor(C["muted"]))
        for line, text in enumerate((info.get("line1", ""), info.get("line2", ""))):
            p.drawText(
                QRectF(inner.left(), inner.top() + 19 + line * 15, inner.width(), 15),
                Qt.AlignVCenter,
                p.fontMetrics().elidedText(text, Qt.ElideRight, int(inner.width())),
            )
        p.restore()


class ChangesetStrip(QListWidget):
    """One horizontal row of changeset cards, scrolled sideways when there are many."""

    def __init__(self, window):
        super().__init__()
        self.setObjectName("changesetStrip")
        self.setAccessibleName("Changesets")
        self.setItemDelegate(ChangesetDelegate(window, self))
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        self.setSpacing(2)
        self.setFixedHeight(84)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
