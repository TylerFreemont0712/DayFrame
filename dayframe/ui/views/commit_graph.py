"""Commit history with a painted branch graph, ref badges, author, date and commit id."""

from datetime import datetime
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
)
from ...code import graph as GRAPH
from ..theme import CURRENT as C

LANE = 12
ROW = 24
COMMIT_ROLE = Qt.UserRole
LAYOUT_ROLE = Qt.UserRole + 1
LANE_HUES = (190, 35, 280, 130, 345, 60, 220, 0)


def lane_color(index):
    light = QColor(C["raised"]).lightnessF() > 0.6
    return QColor.fromHsl(LANE_HUES[index % len(LANE_HUES)], 150, 105 if light else 165)


def ref_badges(refs):
    """(text, kind) badges from git's decoration list: head, branch, remote, tag."""
    badges = []
    for ref in refs:
        if ref.startswith("HEAD -> "):
            badges.append((ref[8:], "head"))
        elif ref == "HEAD":
            badges.append(("HEAD", "head"))
        elif ref.startswith("tag: "):
            badges.append((ref[5:], "tag"))
        elif "/" in ref and not ref.startswith("refs/"):
            badges.append((ref, "remote"))
        else:
            badges.append((ref, "branch"))
    return badges


def paint_badges(p, rect, badges):
    """Paint ref badges from the left of rect; returns the x where text may continue."""
    metrics = p.fontMetrics()
    x = rect.left()
    for text, kind in badges:
        width = metrics.horizontalAdvance(text) + 10
        if x + width > rect.right() - 40:
            break
        box = QRectF(x, rect.center().y() - 8, width, 16)
        color = QColor(
            {"head": C["accent"], "branch": C["accent"], "remote": C["muted"], "tag": C["warning"]}[kind]
        )
        fill = QColor(color)
        fill.setAlpha(200 if kind == "head" else 40)
        p.setBrush(fill)
        p.setPen(QPen(color, 1))
        p.drawRoundedRect(box, 3, 3)
        p.setPen(QColor(C["accent_text"]) if kind == "head" else color)
        p.drawText(box, Qt.AlignCenter, text)
        x += width + 4
    return x


class GraphDelegate(QStyledItemDelegate):
    def paint(self, p, option, index):
        super().paint(p, option, index)
        layout = index.data(LAYOUT_ROLE)
        commit = index.data(COMMIT_ROLE)
        if not layout or not commit:
            return
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect)
        if index.column() == 0:
            top, mid, bottom = rect.top(), rect.center().y(), rect.bottom() + 1

            def x(lane):
                return rect.left() + 8 + lane * LANE

            for (a, b), start, end in [((a, b), top, mid) for a, b in layout["top"]] + [
                ((a, b), mid, bottom) for a, b in layout["bottom"]
            ]:
                pen = QPen(lane_color(b if start == mid else a), 1.6)
                p.setPen(pen)
                path = QPainterPath(QPointF(x(a), start))
                if a == b:
                    path.lineTo(QPointF(x(b), end))
                else:
                    half = (end - start) / 2
                    path.cubicTo(QPointF(x(a), start + half), QPointF(x(b), end - half), QPointF(x(b), end))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            for lane in layout["dangling"]:
                p.setPen(QPen(lane_color(lane), 1.2, Qt.DotLine))
                p.drawLine(QPointF(x(lane), bottom - 3), QPointF(x(lane), bottom))
            color = lane_color(layout["col"])
            center = QPointF(x(layout["col"]), mid)
            if layout["merge"]:
                p.setPen(QPen(color, 2))
                p.setBrush(QColor(C["panel"]))
                p.drawEllipse(center, 4.5, 4.5)
            else:
                p.setPen(QPen(QColor(C["panel"]), 1.5))
                p.setBrush(color)
                p.drawEllipse(center, 4.5, 4.5)
        elif index.column() == 1:
            p.setClipRect(rect)
            x = paint_badges(p, rect.adjusted(4, 0, 0, 0), ref_badges(commit["refs"]))
            p.setPen(QColor(C["text"]))
            text = p.fontMetrics().elidedText(commit["subject"], Qt.ElideRight, int(rect.right() - x - 4))
            p.drawText(QRectF(x + 2, rect.top(), rect.right() - x, rect.height()), Qt.AlignVCenter, text)
        p.restore()


class CommitGraph(QTreeWidget):
    COLUMNS = ["Graph", "Description", "Author", "Date", "Commit"]

    def __init__(self, commits):
        super().__init__()
        self.setObjectName("commitGraph")
        self.setAccessibleName("Commit history")
        self.setColumnCount(len(self.COLUMNS))
        self.setHeaderLabels(self.COLUMNS)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setItemDelegate(GraphDelegate(self))
        self.commits = commits
        rows = GRAPH.layout(commits)
        widest = max((r["width"] for r in rows), default=1)
        for commit, row in zip(commits, rows):
            item = QTreeWidgetItem(
                [
                    "",
                    "",
                    commit["author"],
                    datetime.fromtimestamp(commit["time"]).strftime("%Y-%m-%d %H:%M")
                    if commit["time"]
                    else "",
                    commit["sha"][:8],
                ]
            )
            item.setData(0, COMMIT_ROLE, commit)
            item.setData(0, LAYOUT_ROLE, row)
            item.setData(1, COMMIT_ROLE, commit)
            item.setData(1, LAYOUT_ROLE, row)
            item.setToolTip(
                1, commit["subject"] + ("\n" + ", ".join(commit["refs"]) if commit["refs"] else "")
            )
            item.setToolTip(2, commit["author"] + " <" + commit["email"] + ">")
            item.setSizeHint(0, QSize(10, ROW))
            item.setForeground(4, QColor(C["muted"]))
            item.setForeground(3, QColor(C["muted"]))
            self.addTopLevelItem(item)
        header = self.header()
        header.setStretchLastSection(False)
        self.setColumnWidth(0, min(220, 16 + widest * LANE))
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column, width in ((2, 140), (3, 118), (4, 76)):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
            self.setColumnWidth(column, width)

    def select_sha(self, sha):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, COMMIT_ROLE)["sha"] == sha:
                self.setCurrentItem(item)
                self.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                return True
        return False

    def selected_commit(self):
        item = self.currentItem()
        return item.data(0, COMMIT_ROLE) if item else None
