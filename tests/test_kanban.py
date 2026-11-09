"""Kanban interactions keep previews separate from persisted ticket changes."""

import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt, QMimeData, QPoint, QPointF, QRect
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDragLeaveEvent,
    QDropEvent,
    QImage,
    QPainter,
    QColor,
)
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QStyleOptionViewItem

from dayframe.core import domain as D, planning as P
from dayframe.ui.dialogs import AddDialog
from dayframe.data.store import Store
from dayframe.ui.window import DayFrame
from dayframe.ui.views.kanban import TicketList
from dayframe.ui.dragdrop import TICKET_MIME
from dayframe.ui.views.kanban import project_color
from dayframe.ui.theme import apply_theme, CURRENT

APP = QApplication.instance() or QApplication([])


class KanbanTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path("build/test-data") / uuid.uuid4().hex)
        self.store.register("kanban", "tyler")
        self.project = self.store.command(
            "project.save", {"id": "kanban-project", "name": "Calendar", "project_key": "CAL"}
        )
        self.window = None

    # Delete windows rather than only closing them: unittest keeps finished tests (and their
    # windows) alive, and without an event loop deleteLater() needs an explicit flush.
    def tearDown(self):
        if self.window:
            self.window.close()
            self.window.deleteLater()
            self.window = None
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.store.close()

    def ticket(self, **fields):
        return self.store.command(
            "ticket.save", {"project_id": self.project["id"], "title": "Calendar ticket", **fields}
        )

    def board(self):
        self.window = DayFrame(self.store)
        self.window.show()
        self.window.navigate("Projects")
        APP.processEvents()
        return {lane.status: lane for lane in self.window.findChildren(TicketList)}

    def test_existing_stages_keep_their_ids_and_use_new_names_in_each_view(self):
        tickets = [self.ticket(status=status) for status in D.STATUSES]
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.assertTrue(self.store.restore_session())
        lanes = self.board()
        names = ["Not Started", "In Progress", "Processed", "Review", "Complete"]
        for status, name, ticket in zip(D.STATUSES, names, tickets):
            self.assertEqual(self.store.read("ticket", ticket["id"])["status"], status)
            self.assertEqual(lanes[status].item(0).data(Qt.UserRole), ticket["id"])
            self.assertTrue(any(label.text() == name for label in self.window.workspace.findChildren(QLabel)))
        dialog = AddDialog(self.window, self.store.snapshot(), "ticket", self.project["id"])
        try:
            self.assertEqual([dialog.status.itemText(i) for i in range(dialog.status.count())], names)
        finally:
            dialog.close()
        self.window.select_ticket(tickets[1]["id"])
        status = next(
            b for b in self.window.inspector.findChildren(QPushButton) if b.objectName() == "statusButton"
        )
        self.assertEqual(status.text(), "In Progress")
        self.assertEqual([a.text() for a in status.menu().actions()], names)
        self.window.complete_ticket(tickets[1])
        self.assertEqual(self.store.read("ticket", tickets[1]["id"])["status"], "done")
        self.window.undo()
        self.assertEqual(self.store.read("ticket", tickets[1]["id"])["status"], "ready")

    def test_home_in_progress_group_follows_the_renamed_stage_and_active_timer(self):
        working = self.ticket(title="Working", status="ready")
        processed = self.ticket(title="Processed work", status="doing")
        self.ticket(title="Finished", status="done")
        day = D.day_key(self.store.settings()["timezone"])
        groups = dict(P.home_groups(self.store.snapshot(), day))
        self.assertEqual([t["id"] for t in groups["In Progress"]], [working["id"]])
        self.store.command("timer.action", {"action": "start", "ticket_id": processed["id"]})
        groups = dict(P.home_groups(self.store.snapshot(), day))
        self.assertEqual([t["id"] for t in groups["In Progress"]], [processed["id"], working["id"]])
        self.assertFalse(any(t["status"] == "done" for group in groups.values() for t in group))

    def mime(self, ticket_id):
        mime = QMimeData()
        mime.setData(TICKET_MIME, ticket_id.encode())
        return mime

    def enter(self, lane, mime):
        event = QDragEnterEvent(QPoint(20, 20), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(lane.viewport(), event)
        return event

    def drop(self, lane, mime):
        event = QDropEvent(QPointF(20, 20), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(lane.viewport(), event)
        APP.processEvents()
        return event

    def test_preview_is_immediate_follows_the_destination_and_only_drop_changes_data(self):
        first = self.ticket(title="Already in progress", status="ready")
        ticket = self.ticket(title="Move this", due_date="2026-12-05", labels=["bug"])
        last = self.ticket(title="Also in progress", status="ready")
        lanes = self.board()
        before = self.store.snapshot()["pending"]
        mime = self.mime(ticket["id"])
        self.assertTrue(self.enter(lanes["ready"], mime).isAccepted())
        preview = lanes["ready"].preview_item
        self.assertIsNotNone(preview)
        self.assertEqual(lanes["ready"].row(preview), 1)
        self.assertIn("In Progress", preview.text())
        move = QDragMoveEvent(QPoint(24, 55), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(lanes["ready"].viewport(), move)
        self.assertIs(lanes["ready"].preview_item, preview)
        self.assertEqual(self.store.snapshot()["pending"], before)
        self.assertEqual(self.store.read("ticket", ticket["id"])["status"], "inbox")
        self.enter(lanes["review"], mime)
        self.assertIsNone(lanes["ready"].preview_item)
        self.assertIsNotNone(lanes["review"].preview_item)
        self.assertTrue(self.drop(lanes["review"], mime).isAccepted())
        saved = self.store.read("ticket", ticket["id"])
        self.assertEqual(saved["status"], "review")
        self.assertEqual(saved["due_date"], ticket["due_date"])
        self.assertEqual(saved["labels"], ["bug"])
        self.assertFalse(any(lane.preview_item for lane in self.window.findChildren(TicketList)))
        self.window.undo()
        self.assertEqual(self.store.read("ticket", ticket["id"])["status"], "inbox")
        self.assertEqual(self.store.read("ticket", first["id"])["status"], "ready")
        self.assertEqual(self.store.read("ticket", last["id"])["status"], "ready")

    def test_leaving_or_cancelling_a_drag_removes_the_preview_without_writes(self):
        ticket = self.ticket()
        lanes = self.board()
        before = self.store.snapshot()["pending"]
        mime = self.mime(ticket["id"])
        self.enter(lanes["ready"], mime)
        APP.sendEvent(lanes["ready"].viewport(), QDragLeaveEvent())
        self.assertIsNone(lanes["ready"].preview_item)
        self.assertEqual(lanes["ready"].count(), 0)
        lanes["inbox"].setCurrentRow(0)
        with patch("dayframe.ui.views.kanban.QDrag") as drag:
            drag.return_value.exec.side_effect = lambda action: self.enter(lanes["review"], mime)
            lanes["inbox"].startDrag(Qt.MoveAction)
        self.assertIsNone(lanes["review"].preview_item)
        self.assertEqual(self.store.snapshot()["pending"], before)

    def test_same_column_drop_preserves_the_previous_undo_and_does_not_save(self):
        ticket = self.ticket()
        lanes = self.board()
        previous_undo = lambda: None
        self.window.undo_action = previous_undo
        before = self.store.snapshot()["pending"]
        mime = self.mime(ticket["id"])
        self.enter(lanes["inbox"], mime)
        self.assertIsNone(lanes["inbox"].preview_item)
        self.assertTrue(self.drop(lanes["inbox"], mime).isAccepted())
        self.assertIs(self.window.undo_action, previous_undo)
        self.assertEqual(self.store.snapshot()["pending"], before)

    def test_invalid_or_archived_ticket_drags_are_ignored(self):
        archived = self.ticket(archived=1)
        lanes = self.board()
        invalid = [self.mime("unknown-ticket"), self.mime(archived["id"]), QMimeData(), QMimeData()]
        invalid[-2].setText("Unrelated text")
        invalid[-1].setData(TICKET_MIME, b"\xff")
        before = self.store.snapshot()["pending"]
        for mime in invalid:
            self.assertFalse(self.enter(lanes["ready"], mime).isAccepted())
            self.assertIsNone(lanes["ready"].preview_item)
        self.assertEqual(self.store.snapshot()["pending"], before)

    def test_failed_drop_clears_preview_and_preserves_the_previous_undo(self):
        ticket = self.ticket()
        lanes = self.board()
        previous_undo = lambda: None
        self.window.undo_action = previous_undo
        mime = self.mime(ticket["id"])
        self.enter(lanes["ready"], mime)
        with patch.object(self.window, "execute", return_value=None):
            self.assertFalse(self.drop(lanes["ready"], mime).isAccepted())
        self.assertIsNone(lanes["ready"].preview_item)
        self.assertIs(self.window.undo_action, previous_undo)
        self.assertEqual(self.store.read("ticket", ticket["id"])["status"], "inbox")

    def test_project_color_only_changes_the_prefix_and_has_contrast_in_each_theme(self):
        ticket = self.ticket()
        other = self.store.command(
            "project.save", {"id": "other-project", "name": "Calendar", "project_key": "CAL"}
        )
        lanes = self.board()
        lane = lanes["inbox"]
        item = lane.item(0)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 240, 105)

        def render(project_id):
            item.setData(Qt.UserRole + 1, {**ticket, "project_id": project_id})
            image = QImage(240, 105, QImage.Format_ARGB32)
            image.fill(QColor(CURRENT["panel"]))
            painter = QPainter(image)
            lane.itemDelegate().paint(painter, option, lane.model().index(0, 0))
            painter.end()
            return image

        def luminance(rgb):
            values = [v / 255 for v in rgb]
            linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
            return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))

        for theme in ("graphite", "terminal", "light", "studio"):
            apply_theme({"theme": theme})
            first, second = render(self.project["id"]), render(other["id"])
            self.assertNotEqual(first, second, theme)
            changed = [
                (x, y) for y in range(105) for x in range(240) if first.pixel(x, y) != second.pixel(x, y)
            ]
            self.assertTrue(all(9 <= x < 65 and 6 <= y < 26 for x, y in changed), theme)
            for project_id in (self.project["id"], other["id"]):
                color = project_color(project_id)
                foreground = (color.red(), color.green(), color.blue())
                base = QColor(CURRENT["raised"])
                background = tuple(
                    f * 35 / 255 + b * 220 / 255
                    for f, b in zip(foreground, (base.red(), base.green(), base.blue()))
                )
                a, b = sorted((luminance(foreground), luminance(background)))
                self.assertGreaterEqual((b + 0.05) / (a + 0.05), 4.5, (theme, project_id))
        item.setData(Qt.UserRole + 1, ticket)

    def test_project_hue_survives_rename_and_restart(self):
        before = project_color(self.project["id"]).hue()
        self.store.command(
            "project.save", {"id": self.project["id"], "name": "Renamed project", "project_key": "NEWPRO"}
        )
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.assertTrue(self.store.restore_session())
        saved = self.store.read("project", self.project["id"])
        self.assertEqual(project_color(saved["id"]).hue(), before)
        self.assertEqual(saved["project_key"], "NEWPRO")

    def test_column_headers_fit_at_small_window_size_with_larger_text(self):
        self.ticket()
        self.board()
        for theme in ("graphite", "terminal", "light", "studio"):
            apply_theme({"theme": theme, "textScale": 125})
            self.window.build_shell()
            self.window.navigate("Projects")
            self.window.resize(980, 640)
            APP.processEvents()
            headers = [
                label
                for label in self.window.workspace.findChildren(QLabel)
                if label.text() in D.STATUS_NAMES.values()
            ]
            self.assertEqual(len(headers), 5)
            for header in headers:
                self.assertGreaterEqual(
                    header.width(),
                    header.fontMetrics().horizontalAdvance(header.text()),
                    (theme, header.text()),
                )

    def test_long_titles_do_not_paint_over_the_project_badge_or_metadata(self):
        ticket = self.ticket(title="Calendar 🗓️ work with a long description that needs more than two lines")
        lanes = self.board()
        lane, option = lanes["inbox"], QStyleOptionViewItem()
        item = lane.item(0)
        option.rect = QRect(0, 0, 180, 105)
        for theme in ("graphite", "terminal", "light", "studio"):
            apply_theme({"theme": theme, "textScale": 125})
            images = []
            for title in ("", ticket["title"]):
                item.setData(Qt.UserRole + 1, {**ticket, "title": title})
                image = QImage(180, 105, QImage.Format_ARGB32)
                image.fill(QColor(CURRENT["panel"]))
                painter = QPainter(image)
                lane.itemDelegate().paint(painter, option, lane.model().index(0, 0))
                painter.end()
                images.append(image)
            self.assertNotEqual(images[0], images[1], theme)
            self.assertEqual(images[0].copy(0, 60, 180, 45), images[1].copy(0, 60, 180, 45), theme)
        item.setData(Qt.UserRole + 1, ticket)
