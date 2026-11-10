"""Home's painted pieces: event-type symbols, the week strip of day cards and countdown tiles."""

from __future__ import annotations
from datetime import date, datetime, timedelta
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QSizePolicy, QVBoxLayout, QWidget
from ...core import domain as D, planning as P
from ..theme import CURRENT as C, icon
from ..widgets import label
from .calendar import paint_item, readable

# One symbol per event type, so a birthday or a trip is recognisable before its title is read.
EVENT_GLYPHS = {
    "appointment": "calendar-check",
    "meeting": "users",
    "birthday": "birthday-cake",
    "trip": "plane",
    "personal": "user",
    "routine": "redo",
    "holiday": "umbrella-beach",
    "work": "briefcase",
    "event": "calendar-alt",
    "deadline": "flag",
}


def event_glyph(item):
    return EVENT_GLYPHS.get(item.get("event_type"), "calendar-alt")


def event_icon(item):
    """The item's type symbol in its own color."""
    return icon(event_glyph(item), P.event_color(item))


def when_text(day, today):
    """Today, Tomorrow, a weekday within the week, otherwise the date."""
    target = date.fromisoformat(day)
    days = (target - date.fromisoformat(today)).days
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    if 1 < days < 7:
        return target.strftime("%A")
    return target.strftime("%b %d").replace(" 0", " ")


def time_text(item):
    return "All day" if item["all_day"] else item["start_time"] + "–" + item["end_time"]


def small_font(delta=-0.5, bold=False):
    font = QFont(QApplication.font())
    font.setPointSizeF(max(6.5, font.pointSizeF() + delta))
    font.setBold(bold)
    return font


def tooltip(text):
    return text.replace("<", "‹").replace(">", "›")


class StatChip(QFrame):
    """A compact figure with a caption; clicking it opens the matching list."""

    def __init__(self, caption, value, action=None, warn=False, hint=""):
        super().__init__()
        self.setObjectName("homeStat")
        self.action = action
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 4)
        layout.setSpacing(0)
        figure = label(value, "homeStatWarn" if warn else "homeStatValue")
        figure.setAccessibleName(caption + ": " + str(value))
        layout.addWidget(figure)
        layout.addWidget(label(caption, "muted"))
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.setToolTip(hint or caption)
        if action:
            self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if (
            self.action
            and event.button() == Qt.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            QTimer.singleShot(0, self.action)


class WeekStrip(QWidget):
    """Seven day cards, Sunday first, each filled in with a small picture of that day.

    A card shows the day's all-day items as chips with their type symbol and its timed
    events and work blocks on a miniature timeline shared by the whole week. Clicking a
    card selects the day for Home's timeline; double-clicking adds an event on it.
    """

    def __init__(self, window, day):
        super().__init__()
        self.window = window
        self.day = day
        self.start = P.sunday(day)
        self.regions = []
        self.hover = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Week overview")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(7 * 46)

    def sizeHint(self):
        return QSize(560, 132)

    def days(self):
        return [(self.start + timedelta(days=n)).isoformat() for n in range(7)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.regions = []
        data = self.window.data
        today = D.day_key(data["settings"]["timezone"])
        items = P.items_between(data, self.start, self.start + timedelta(days=6))
        timed = [x for x in items if not x["all_day"]]
        # One scale for all seven cards, so a morning block sits at the same height everywhere.
        first = min([8] + [P.minutes(x["start_time"]) // 60 for x in timed if x["date"] == x["end_date"]])
        last = max(
            [19] + [(P.minutes(x["end_time"]) + 59) // 60 for x in timed if x["date"] == x["end_date"]]
        )
        if any(x["date"] != x["end_date"] for x in timed):
            first, last = 0, 24
        gap = 5
        width = (self.width() - gap * 6) / 7
        base = small_font()
        bold = small_font(bold=True)
        metrics = QFontMetricsF(base)
        head = metrics.height() + 7
        chip = metrics.height() + 3
        radius = min(7, C.get("radius", 4))
        now = datetime.now(D.ZoneInfo(data["settings"]["timezone"]))
        for n, day in enumerate(self.days()):
            card = QRectF(n * (width + gap) + 0.5, 0.5, width - 1, self.height() - 1)
            self.regions.append((card, day))
            selected = day == self.day
            fill = QColor(C["raised"] if selected else C["panel"])
            edge = QColor(C["accent"] if selected else C["button_hover"] if day == self.hover else C["line"])
            p.setPen(QPen(edge, 1.5 if selected else 1))
            p.setBrush(fill)
            p.drawRoundedRect(card, radius, radius)
            p.save()
            p.setClipRect(card.adjusted(1, 1, -1, -1))
            if day < today:
                p.setOpacity(0.62)
            current = date.fromisoformat(day)
            p.setFont(base)
            p.setPen(QColor(C["accent"] if day == today else C["muted"]))
            p.drawText(
                QRectF(card.left() + 7, card.top() + 3, width - 14, head - 3),
                Qt.AlignVCenter | Qt.AlignLeft,
                current.strftime("%a").upper(),
            )
            p.setFont(bold)
            number = str(current.day)
            number_width = QFontMetricsF(bold).horizontalAdvance(number) + 10
            badge = QRectF(card.right() - number_width - 5, card.top() + 4, number_width, head - 5)
            if day == today:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(C["accent"]))
                p.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
                p.setPen(QColor(C["accent_text"]))
            else:
                p.setPen(QColor(C["text"]))
            p.drawText(badge, Qt.AlignCenter, number)
            p.setFont(base)
            segments = P.segments_for_day(items, day)
            y = card.top() + head + 1
            whole = [x for x in segments if x["all_day"]]
            shown = whole if len(whole) <= 2 else whole[:1]
            for item in shown:
                self.paint_chip(p, QRectF(card.left() + 4, y, width - 9, chip), item, metrics)
                y += chip + 2
            if len(whole) > len(shown):
                p.setPen(QColor(C["accent"]))
                p.drawText(
                    QRectF(card.left() + 7, y, width - 12, chip),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    "+%d more" % (len(whole) - len(shown)),
                )
                y += chip + 2
            area = QRectF(card.left() + 4, y + 2, width - 9, card.bottom() - y - 6)
            if area.height() >= 14:
                self.paint_timeline(p, area, segments, first, last, day == today and now, bold, metrics)
            p.restore()
        p.end()

    def paint_chip(self, p, rect, item, metrics):
        color = QColor(P.event_color(item))
        fill = QColor(color)
        fill.setAlpha(60 if C.get("dark", True) else 46)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(rect, 3, 3)
        side = min(11.0, rect.height() - 3)
        icon(event_glyph(item), color.name()).paint(
            p, round(rect.left() + 3), round(rect.center().y() - side / 2), round(side), round(side)
        )
        room = rect.width() - side - 9
        if room > metrics.horizontalAdvance("Mm"):
            title = item["title"].removeprefix("Due · ")
            p.setPen(QColor(C["text"]))
            p.drawText(
                QRectF(rect.left() + side + 6, rect.top(), room, rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                metrics.elidedText(title, Qt.ElideRight, room),
            )

    def paint_timeline(self, p, area, segments, first, last, now, bold, metrics):
        span = max(1, last - first) * 60
        scale = area.height() / span
        tick = QColor(C["line"])
        tick.setAlpha(150)
        p.setPen(QPen(tick, 0.6))
        for hour in range(first, last + 1):
            if hour % 3 == 0:
                y = area.top() + (hour - first) * 60 * scale
                p.drawLine(area.left(), y, area.right(), y)
        for item in P.overlap_lanes(x for x in segments if not x["all_day"]):
            top = area.top() + (max(item["start_min"], first * 60) - first * 60) * scale
            bottom = area.top() + (min(item["end_min"], last * 60) - first * 60) * scale
            lane = area.width() / item["lanes"]
            rect = QRectF(area.left() + item["lane"] * lane, top, lane - 1, max(4.0, bottom - top - 1))
            if rect.height() >= metrics.height() + 1 and rect.width() >= 34:
                p.setFont(bold)
                paint_item(p, rect, item, True)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(P.event_color(item)))
                p.drawRoundedRect(rect, 2, 2)
        if now and first * 60 <= now.hour * 60 + now.minute <= last * 60:
            y = area.top() + (now.hour * 60 + now.minute - first * 60) * scale
            p.setPen(QPen(QColor(C["accent"]), 1.3))
            p.drawLine(area.left(), y, area.right(), y)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(QRectF(area.left() - 1.5, y - 2.5, 5, 5))

    def day_at(self, pos):
        return next((day for rect, day in self.regions if rect.contains(pos)), None)

    def mouseMoveEvent(self, event):
        day = self.day_at(event.position())
        if day != self.hover:
            self.hover = day
            self.setCursor(Qt.PointingHandCursor if day else Qt.ArrowCursor)
            lines = []
            if day:
                lines = [date.fromisoformat(day).strftime("%A, %b %d").replace(" 0", " ")]
                lines += [time_text(x) + "  " + x["title"] for x in P.day_items(self.window.data, day)]
                lines.append("Click to show this day · double-click to add an event")
            self.setToolTip(tooltip("\n".join(lines)))
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        day = self.day_at(event.position())
        if day and event.button() == Qt.LeftButton and day != self.day:
            QTimer.singleShot(0, lambda: self.window.home_select_day(day))

    def mouseDoubleClickEvent(self, event):
        day = self.day_at(event.position())
        if day:
            QTimer.singleShot(0, lambda: self.window.quick_add("event", day=day, all_day=True))

    def keyPressEvent(self, event):
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1}.get(event.key())
        if step:
            target = (date.fromisoformat(self.day) + timedelta(days=step)).isoformat()
            QTimer.singleShot(0, lambda: self.window.home_select_day(target))
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            QTimer.singleShot(0, lambda: self.window.quick_add("event", day=self.day, all_day=True))
        else:
            super().keyPressEvent(event)


class CountdownTiles(QWidget):
    """Up to three major events as countdown tiles: days left, title, date and type symbol."""

    def __init__(self, window, items, today):
        super().__init__()
        self.window = window
        self.items = items
        self.today = today
        self.regions = []
        self.hover = None
        self.setMouseTracking(True)
        self.setAccessibleName("Next major events")
        self.number = QFont(C.get("mono") or QApplication.font().family())
        self.number.setPointSizeF(QApplication.font().pointSizeF() * 2.1)
        self.number.setBold(True)
        self.text = small_font()
        self.title = small_font(0, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(
            round(
                QFontMetricsF(self.number).height()
                + QFontMetricsF(self.title).height()
                + 2 * QFontMetricsF(self.text).height()
                + 17
            )
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.regions = []
        gap = 6
        width = (self.width() - gap * 2) / 3
        radius = min(8, C.get("radius", 4))
        small = QFontMetricsF(self.text)
        for n, item in enumerate(self.items[:3]):
            tile = QRectF(n * (width + gap) + 0.5, 0.5, width - 1, self.height() - 1)
            self.regions.append((tile, item))
            color = QColor(P.event_color(item))
            p.setPen(QPen(QColor(C["button_hover"] if n == self.hover else C["line"]), 1))
            p.setBrush(QColor(C["panel"]))
            p.drawRoundedRect(tile, radius, radius)
            p.save()
            p.setClipRect(tile.adjusted(1, 1, -1, -1))
            wash = QColor(color)
            wash.setAlpha(34 if C.get("dark", True) else 26)
            p.fillRect(QRectF(tile.left(), tile.top(), tile.width(), 4 + small.height() + 5), wash)
            p.fillRect(QRectF(tile.left(), tile.top(), tile.width(), 2.5), color)
            icon(event_glyph(item), color.name()).paint(
                p, round(tile.left() + 7), round(tile.top() + 6), 12, 12
            )
            p.setFont(self.text)
            p.setPen(QColor(C["muted"]))
            kind = P.TYPE_NAMES.get(item["event_type"], "Event")
            p.drawText(
                QRectF(tile.left() + 24, tile.top() + 4, width - 46, small.height() + 2),
                Qt.AlignVCenter | Qt.AlignLeft,
                small.elidedText(kind, Qt.ElideRight, width - 46),
            )
            if item["record"].get("pinned"):
                icon("thumbtack", C["muted"]).paint(
                    p, round(tile.right() - 17), round(tile.top() + 7), 10, 10
                )
            days = max(0, D.days_until(item["date"], self.today))
            y = tile.top() + 4 + small.height() + 6
            numbers = QFontMetricsF(self.number)
            p.setFont(self.number)
            p.setPen(QColor(C["clock"] if days else C["accent"]))
            figure = str(days) if days else "Today"
            if not days:
                p.setFont(small_font(4, True))
            p.drawText(
                QRectF(tile.left() + 8, y, width - 16, numbers.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                figure,
            )
            if days:
                p.setFont(self.text)
                p.setPen(QColor(C["muted"]))
                p.drawText(
                    QRectF(
                        tile.left() + 12 + numbers.horizontalAdvance(figure), y, width, numbers.height() - 3
                    ),
                    Qt.AlignBottom | Qt.AlignLeft,
                    "day" if days == 1 else "days",
                )
            y += numbers.height()
            titles = QFontMetricsF(self.title)
            p.setFont(self.title)
            p.setPen(QColor(C["text"]))
            p.drawText(
                QRectF(tile.left() + 8, y, width - 16, titles.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                titles.elidedText(item["title"], Qt.ElideRight, width - 16),
            )
            y += titles.height()
            p.setFont(self.text)
            p.setPen(QColor(C["muted"]))
            when = date.fromisoformat(item["date"]).strftime("%a, %b %d").replace(" 0", " ")
            if not item["all_day"]:
                when += " · " + item["start_time"]
            p.drawText(
                QRectF(tile.left() + 8, y, width - 16, small.height() + 2),
                Qt.AlignVCenter | Qt.AlignLeft,
                small.elidedText(when, Qt.ElideRight, width - 16),
            )
            p.restore()
        p.end()

    def index_at(self, pos):
        return next((n for n, (rect, item) in enumerate(self.regions) if rect.contains(pos)), None)

    def mouseMoveEvent(self, event):
        index = self.index_at(event.position())
        if index != self.hover:
            self.hover = index
            self.setCursor(Qt.PointingHandCursor if index is not None else Qt.ArrowCursor)
            item = self.regions[index][1] if index is not None else None
            self.setToolTip(tooltip(item["title"] + "\n" + readable(item)) if item else "")
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        index = self.index_at(event.position())
        if index is not None and event.button() == Qt.LeftButton:
            item = self.regions[index][1]
            QTimer.singleShot(0, lambda: self.window.open_calendar_item(item))
