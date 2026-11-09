"""Change browser for the Code page: changed-file tree, stats and a painted line-numbered diff.

ChangeBrowser takes patch text (a changeset, the working tree or a commit), shows the
files as a folder tree with status letters and +/− counts, and paints the selected
file's diff with old/new line numbers, in-line edit highlighting and visible line-ending
and tab changes, in a unified or split layout.
"""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ...code import diff as DIFF
from ..theme import CURRENT as C, icon
from ..widgets import ElidingLabel, label

STATUS_NAMES = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "?": "untracked",
    "U": "conflict",
}
TREE_WIDTH = 300
TAB = "    "


def added_color():
    return QColor("#7fd49b" if C.get("dark", True) else "#2f8a4c")


def removed_color():
    return QColor(C["danger"])


def status_color(code):
    letter = (code or "M").strip(".")[:1] or "M"
    return {
        "A": added_color(),
        "?": added_color(),
        "D": removed_color(),
        "U": removed_color(),
        "R": QColor(C["accent"]),
        "C": QColor(C["accent"]),
    }.get(letter, QColor(C["warning"]))


def mono_font(scale=1.0):
    font = QFont(C.get("mono", "Consolas"))
    font.setStyleHint(QFont.Monospace)
    font.setPointSizeF(max(7.0, 8.5 * C.get("scale", 0.9) * scale))
    return font


def visible(text):
    """Tabs as spaces and a carriage return as a visible mark, so whitespace edits show."""
    text = text.replace("\t", TAB)
    return text[:-1] + "␍" if text.endswith("\r") else text


class StatBar(QWidget):
    """'+12 −3' with five blocks showing the share of additions and deletions."""

    def __init__(self, added=0, removed=0):
        super().__init__()
        self.added, self.removed = added, removed
        self.setFixedHeight(18)
        self.setMinimumWidth(130)
        self.setAccessibleName("%d lines added, %d removed" % (added, removed))

    def sizeHint(self):
        return QSize(150, 18)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(mono_font())
        metrics = p.fontMetrics()
        x = 0
        for text, color in (
            ("+" + str(self.added), added_color()),
            ("−" + str(self.removed), removed_color()),
        ):
            p.setPen(color)
            p.drawText(QRectF(x, 0, 80, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
            x += metrics.horizontalAdvance(text) + 8
        total = self.added + self.removed
        green = round(5 * self.added / total) if total else 0
        red = (5 - green) if total and self.removed else 0
        for block in range(5):
            color = (
                added_color()
                if block < green
                else removed_color()
                if block < green + red
                else QColor(C["line"])
            )
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x + block * 11, 4, 9, 9), 2, 2)
        p.end()


class DiffCanvas(QAbstractScrollArea):
    """Painted diff of one file. Scrolls by rows vertically and by pixels horizontally."""

    def __init__(self):
        super().__init__()
        self.setObjectName("diffCanvas")
        self.setAccessibleName("File diff")
        self.setFocusPolicy(Qt.StrongFocus)
        self.rows = []
        self.mode = "unified"
        self.message = "Select a file to see its changes."
        self.file = None
        self.setFont(mono_font())
        self.viewport().setAutoFillBackground(False)

    # Content ----------------------------------------------------------------------------------

    def set_file(self, file, mode=None, message=""):
        self.file = file
        self.mode = mode or self.mode
        self.message = message
        self.rows = []
        if file is None:
            self.message = message or "Select a file to see its changes."
        elif file["binary"]:
            self.message = "Binary file " + STATUS_NAMES.get(file["status"], "changed") + "; no text diff."
        elif not file["hunks"]:
            self.message = "No content changes (" + (STATUS_NAMES.get(file["status"], "mode change")) + ")."
        else:
            self.build_rows()
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)
        self.update_scrollbars()
        self.viewport().update()

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            if self.file and self.file["hunks"]:
                self.build_rows()
                self.update_scrollbars()
            self.viewport().update()

    def build_rows(self):
        rows = []
        for hunk in self.file["hunks"]:
            rows.append(("hunk", hunk["header"]))
            pairs = DIFF.pair_rows(hunk["lines"])
            spans = {}
            for left, right in pairs:
                if left and right and left[0] == "del" and right[0] == "add":
                    start, old_end, new_end = DIFF.changed_span(left[3], right[3])
                    spans[id(left)] = (start, old_end)
                    spans[id(right)] = (start, new_end)
            if self.mode == "split":
                for left, right in pairs:
                    rows.append(
                        (
                            "pair",
                            left,
                            right,
                            spans.get(id(left)) if left else None,
                            spans.get(id(right)) if right else None,
                        )
                    )
            else:
                for line in hunk["lines"]:
                    rows.append(("line", line, spans.get(id(line))))
        self.rows = rows
        metrics = QFontMetricsF(self.font())
        longest = max(
            (len(visible(r[1][3])) for r in rows if r[0] == "line"),
            default=max(
                (len(visible((r[1] or r[2])[3])) for r in rows if r[0] == "pair"),
                default=0,
            ),
        )
        self.text_width = metrics.horizontalAdvance("M") * (longest + 2)

    # Geometry ---------------------------------------------------------------------------------

    def row_height(self):
        return int(QFontMetricsF(self.font()).height() + 3)

    def number_width(self):
        biggest = 1
        for hunk in (self.file or {}).get("hunks", []):
            for line in hunk["lines"]:
                biggest = max(biggest, line[1] or 0, line[2] or 0)
        return QFontMetricsF(self.font()).horizontalAdvance(str(biggest)) + 12

    def update_scrollbars(self):
        visible_rows = max(1, self.viewport().height() // self.row_height())
        bar = self.verticalScrollBar()
        bar.setRange(0, max(0, len(self.rows) - visible_rows + 1))
        bar.setPageStep(visible_rows)
        gutter = self.number_width() * (2 if self.mode == "unified" else 1) + 16
        content = gutter + getattr(self, "text_width", 0)
        width = self.viewport().width() if self.mode == "unified" else self.viewport().width() / 2
        horizontal = self.horizontalScrollBar()
        horizontal.setRange(0, max(0, int(content - width)))
        horizontal.setPageStep(int(width))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scrollbars()

    def scrollContentsBy(self, dx, dy):
        self.viewport().update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y())
        else:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - event.angleDelta().y() // 40)
        event.accept()

    # Painting ---------------------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self.viewport())
        p.fillRect(self.viewport().rect(), QColor(C["input"]))
        p.setFont(self.font())
        if not self.rows:
            p.setPen(QColor(C["muted"]))
            p.drawText(
                self.viewport().rect().adjusted(12, 10, -12, -10), Qt.AlignTop | Qt.TextWordWrap, self.message
            )
            p.end()
            return
        height = self.row_height()
        first = self.verticalScrollBar().value()
        count = self.viewport().height() // height + 2
        width = self.viewport().width()
        for index, row in enumerate(self.rows[first : first + count]):
            y = index * height
            if row[0] == "hunk":
                p.fillRect(QRectF(0, y, width, height), QColor(C["raised"]))
                p.setPen(QColor(C["accent"]))
                p.drawText(QRectF(8, y, width - 16, height), Qt.AlignVCenter, row[1])
            elif row[0] == "line":
                self.paint_line(p, QRectF(0, y, width, height), row[1], row[2], both_numbers=True)
            else:
                half = width / 2
                self.paint_line(p, QRectF(0, y, half, height), row[1], row[3], side="old")
                self.paint_line(p, QRectF(half, y, width - half, height), row[2], row[4], side="new")
                p.setPen(QColor(C["line"]))
                p.drawLine(int(half), y, int(half), y + height)
        p.end()

    def paint_line(self, p, rect, line, span, both_numbers=False, side=""):
        p.save()
        p.setClipRect(rect)
        numbers = self.number_width()
        if line is None:
            p.fillRect(rect, QColor(C["panel"]))
            p.restore()
            return
        kind, old_no, new_no, text = line
        tint = {"add": added_color(), "del": removed_color()}.get(kind)
        if tint:
            soft = QColor(tint)
            soft.setAlpha(34)
            p.fillRect(rect, soft)
        gutter = numbers * (2 if both_numbers else 1)
        p.fillRect(QRectF(rect.left(), rect.top(), gutter, rect.height()), QColor(C["panel"]))
        p.setPen(QColor(C["muted"]))
        if both_numbers:
            for column, number in enumerate((old_no, new_no)):
                if number:
                    p.drawText(
                        QRectF(rect.left() + column * numbers, rect.top(), numbers - 6, rect.height()),
                        Qt.AlignVCenter | Qt.AlignRight,
                        str(number),
                    )
        else:
            number = old_no if side == "old" else new_no
            if number:
                p.drawText(
                    QRectF(rect.left(), rect.top(), numbers - 6, rect.height()),
                    Qt.AlignVCenter | Qt.AlignRight,
                    str(number),
                )
        sign = {"add": "+", "del": "−", "note": "\\"}.get(kind, " ")
        x = rect.left() + gutter + 4
        p.setPen(tint or QColor(C["muted"]))
        p.drawText(QRectF(x, rect.top(), 12, rect.height()), Qt.AlignVCenter, sign)
        x += 14 - self.horizontalScrollBar().value()
        metrics = QFontMetricsF(p.font())
        shown = visible(text)
        if span and tint and span[1] > span[0]:
            start = metrics.horizontalAdvance(visible(text[: span[0]]))
            end = metrics.horizontalAdvance(visible(text[: span[1]]))
            strong = QColor(tint)
            strong.setAlpha(95)
            p.fillRect(QRectF(x + start, rect.top() + 1, max(3, end - start), rect.height() - 2), strong)
        p.setPen(QColor(C["muted"] if kind == "note" else C["text"]))
        p.drawText(
            QRectF(x, rect.top(), metrics.horizontalAdvance(shown) + 8, rect.height()), Qt.AlignVCenter, shown
        )
        p.restore()


class ChangeBrowser(QWidget):
    """Changed-file tree beside the selected file's diff, with totals and a layout toggle.

    state is a dict owned by the caller (kept across page rebuilds) that remembers the
    selected file and the unified/split choice.
    """

    def __init__(self, state=None, placeholder="No changes."):
        super().__init__()
        self.state = state if state is not None else {}
        self.files = []
        self.statuses = {}
        self.placeholder = placeholder
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.summary = label("", "section")
        self.stats = StatBar()
        header.addWidget(self.summary)
        header.addWidget(self.stats)
        header.addStretch()
        self.mode_group = QButtonGroup(self)
        for mode, title, glyph in (("unified", "Unified", "align-justify"), ("split", "Split", "columns")):
            toggle = QPushButton(title)
            toggle.setIcon(icon(glyph))
            toggle.setCheckable(True)
            toggle.setChecked(self.state.get("mode", "unified") == mode)
            toggle.setProperty("mode", mode)
            toggle.setAccessibleName(title + " diff")
            self.mode_group.addButton(toggle)
            header.addWidget(toggle)
        self.mode_group.buttonClicked.connect(lambda b: self.set_mode(b.property("mode")))
        outer.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(6)
        self.tree = QTreeWidget()
        self.tree.setObjectName("changeTree")
        self.tree.setAccessibleName("Changed files")
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Changed files", "", "+", "−"])
        self.tree.setFixedWidth(TREE_WIDTH)
        self.tree.setIndentation(12)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header_view = self.tree.header()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        for column, width in ((1, 28), (2, 44), (3, 44)):
            header_view.setSectionResizeMode(column, QHeaderView.Fixed)
            self.tree.setColumnWidth(column, width)
        self.tree.currentItemChanged.connect(self.show_current)
        body.addWidget(self.tree)
        right = QVBoxLayout()
        right.setSpacing(4)
        file_row = QHBoxLayout()
        self.file_title = ElidingLabel("", "section")
        self.file_detail = label("", "muted")
        file_row.addWidget(self.file_title, 1)
        file_row.addWidget(self.file_detail)
        right.addLayout(file_row)
        self.canvas = DiffCanvas()
        self.canvas.mode = self.state.get("mode", "unified")
        right.addWidget(self.canvas, 1)
        body.addLayout(right, 1)
        outer.addLayout(body, 1)
        self.set_files([])

    def set_mode(self, mode):
        self.state["mode"] = mode
        self.canvas.set_mode(mode)

    def set_diff(self, text, statuses=None, placeholder=None):
        if placeholder:
            self.placeholder = placeholder
        self.set_files(DIFF.parse(text), statuses)

    def set_files(self, files, statuses=None):
        self.files = files
        self.statuses = statuses or {}
        count, added, removed = DIFF.summary(files)
        self.summary.setText(str(count) + " file" + ("" if count == 1 else "s") + " changed")
        self.stats.added, self.stats.removed = added, removed
        self.stats.setAccessibleName("%d lines added, %d removed" % (added, removed))
        self.stats.update()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.add_nodes(self.tree.invisibleRootItem(), DIFF.tree(files))
        self.tree.expandAll()
        self.tree.blockSignals(False)
        remembered = self.state.get("path")
        target = self.find_item(remembered) if remembered else None
        target = target or self.first_file()
        if target:
            self.tree.setCurrentItem(target)
            self.show_current(target)
        else:
            self.file_title.setText("")
            self.file_detail.setText("")
            self.canvas.set_file(None, message=self.placeholder)

    def add_nodes(self, parent, node):
        for child in node["children"].values():
            item = QTreeWidgetItem(parent)
            f = child["file"]
            item.setText(0, child["name"])
            item.setToolTip(0, child["path"] + ("" if f else " · %d files" % child["count"]))
            item.setText(2, "+" + str(child["added"]) if child["added"] else "")
            item.setText(3, "−" + str(child["removed"]) if child["removed"] else "")
            item.setForeground(2, added_color())
            item.setForeground(3, removed_color())
            for column in (2, 3):
                item.setTextAlignment(column, Qt.AlignRight | Qt.AlignVCenter)
            if f:
                code = self.statuses.get(f["path"]) or f["status"]
                item.setText(1, code)
                item.setForeground(1, status_color(code))
                item.setTextAlignment(1, Qt.AlignCenter)
                item.setIcon(0, icon("file-alt"))
                item.setData(0, Qt.UserRole, f["path"])
                if f["status"] == "R" and f["old_path"]:
                    item.setToolTip(0, f["old_path"] + " → " + f["path"])
            else:
                item.setIcon(0, icon("folder"))
                item.setData(0, Qt.UserRole + 1, child["path"])
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
                self.add_nodes(item, child)

    def find_item(self, path):
        for item in self.iter_items():
            if item.data(0, Qt.UserRole) == path:
                return item
        return None

    def first_file(self):
        return next((item for item in self.iter_items() if item.data(0, Qt.UserRole)), None)

    def iter_items(self, parent=None):
        parent = parent or self.tree.invisibleRootItem()
        for i in range(parent.childCount()):
            child = parent.child(i)
            yield child
            yield from self.iter_items(child)

    def show_current(self, item, previous=None):
        path = item.data(0, Qt.UserRole) if item else None
        if not path:
            return
        f = next((f for f in self.files if f["path"] == path), None)
        if not f:
            return
        self.state["path"] = path
        code = self.statuses.get(path) or f["status"]
        self.file_title.setText(
            (f["old_path"] + " → " if f["status"] == "R" and f["old_path"] else "") + path
        )
        detail = STATUS_NAMES.get(code.strip(".")[:1] or "M", "changed")
        self.file_detail.setText(detail + " · +" + str(f["added"]) + " −" + str(f["removed"]))
        self.canvas.set_file(f, self.state.get("mode", "unified"))

    def selected_paths(self):
        """Files of the selected tree rows; a folder selects every file under it."""
        paths = []
        for item in self.tree.selectedItems() or (
            [self.tree.currentItem()] if self.tree.currentItem() else []
        ):
            if item.data(0, Qt.UserRole):
                paths.append(item.data(0, Qt.UserRole))
            else:
                paths.extend(i.data(0, Qt.UserRole) for i in self.iter_items(item) if i.data(0, Qt.UserRole))
        return list(dict.fromkeys(paths))
