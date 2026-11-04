"""Kanban interactions keep previews separate from persisted ticket changes."""
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt, QMimeData, QPoint, QPointF
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from dayframe import domain as D, planning as P
from dayframe.dialogs import AddDialog
from dayframe.store import Store
from dayframe.ui import DayFrame, TicketList
from dayframe.kanban import TICKET_MIME

APP = QApplication.instance() or QApplication([])


class KanbanTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path('build/test-data') / uuid.uuid4().hex)
        self.store.register('kanban', 'tyler')
        self.project = self.store.command('project.save', {'name': 'Calendar', 'project_key': 'CAL'})
        self.window = None

    def tearDown(self):
        if self.window:
            self.window.close()
            APP.processEvents()
        self.store.close()

    def ticket(self, **fields):
        return self.store.command('ticket.save', {
            'project_id': self.project['id'], 'title': 'Calendar ticket', **fields})

    def board(self):
        self.window = DayFrame(self.store)
        self.window.show()
        self.window.navigate('Projects')
        APP.processEvents()
        return {lane.status: lane for lane in self.window.findChildren(TicketList)}

    def test_existing_stages_keep_their_ids_and_use_new_names_in_each_view(self):
        tickets = [self.ticket(status=status) for status in D.STATUSES]
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.assertTrue(self.store.restore_session())
        lanes = self.board()
        names = ['Not Started', 'In Progress', 'Processed', 'Review', 'Complete']
        for status, name, ticket in zip(D.STATUSES, names, tickets):
            self.assertEqual(self.store.read('ticket', ticket['id'])['status'], status)
            self.assertEqual(lanes[status].item(0).data(Qt.UserRole), ticket['id'])
            self.assertTrue(any(label.text() == name for label in self.window.workspace.findChildren(QLabel)))
        dialog = AddDialog(self.window, self.store.snapshot(), 'ticket', self.project['id'])
        try:
            self.assertEqual([dialog.status.itemText(i) for i in range(dialog.status.count())], names)
        finally:
            dialog.close()
        self.window.select_ticket(tickets[1]['id'])
        choices = next(c for c in self.window.inspector.findChildren(QComboBox) if c.findData('inbox') >= 0)
        self.assertEqual(choices.currentText(), 'In Progress')
        self.window.complete_ticket(tickets[1])
        self.assertEqual(self.store.read('ticket', tickets[1]['id'])['status'], 'done')
        self.window.undo()
        self.assertEqual(self.store.read('ticket', tickets[1]['id'])['status'], 'ready')

    def test_home_in_progress_group_follows_the_renamed_stage_and_active_timer(self):
        working = self.ticket(title='Working', status='ready')
        processed = self.ticket(title='Processed work', status='doing')
        self.ticket(title='Finished', status='done')
        day = D.day_key(self.store.settings()['timezone'])
        groups = dict(P.home_groups(self.store.snapshot(), day))
        self.assertEqual([t['id'] for t in groups['In Progress']], [working['id']])
        self.store.command('timer.action', {'action': 'start', 'ticket_id': processed['id']})
        groups = dict(P.home_groups(self.store.snapshot(), day))
        self.assertEqual([t['id'] for t in groups['In Progress']], [processed['id'], working['id']])
        self.assertFalse(any(t['status'] == 'done' for group in groups.values() for t in group))

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
        first = self.ticket(title='Already in progress', status='ready')
        ticket = self.ticket(title='Move this', due_date='2026-12-05', labels=['bug'])
        last = self.ticket(title='Also in progress', status='ready')
        lanes = self.board()
        before = self.store.snapshot()['pending']
        mime = self.mime(ticket['id'])
        self.assertTrue(self.enter(lanes['ready'], mime).isAccepted())
        preview = lanes['ready'].preview_item
        self.assertIsNotNone(preview)
        self.assertEqual(lanes['ready'].row(preview), 1)
        self.assertIn('In Progress', preview.text())
        move = QDragMoveEvent(QPoint(24, 55), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(lanes['ready'].viewport(), move)
        self.assertIs(lanes['ready'].preview_item, preview)
        self.assertEqual(self.store.snapshot()['pending'], before)
        self.assertEqual(self.store.read('ticket', ticket['id'])['status'], 'inbox')
        self.enter(lanes['review'], mime)
        self.assertIsNone(lanes['ready'].preview_item)
        self.assertIsNotNone(lanes['review'].preview_item)
        self.assertTrue(self.drop(lanes['review'], mime).isAccepted())
        saved = self.store.read('ticket', ticket['id'])
        self.assertEqual(saved['status'], 'review')
        self.assertEqual(saved['due_date'], ticket['due_date'])
        self.assertEqual(saved['labels'], ['bug'])
        self.assertFalse(any(lane.preview_item for lane in self.window.findChildren(TicketList)))
        self.window.undo()
        self.assertEqual(self.store.read('ticket', ticket['id'])['status'], 'inbox')
        self.assertEqual(self.store.read('ticket', first['id'])['status'], 'ready')
        self.assertEqual(self.store.read('ticket', last['id'])['status'], 'ready')

    def test_leaving_or_cancelling_a_drag_removes_the_preview_without_writes(self):
        ticket = self.ticket()
        lanes = self.board()
        before = self.store.snapshot()['pending']
        mime = self.mime(ticket['id'])
        self.enter(lanes['ready'], mime)
        APP.sendEvent(lanes['ready'].viewport(), QDragLeaveEvent())
        self.assertIsNone(lanes['ready'].preview_item)
        self.assertEqual(lanes['ready'].count(), 0)
        lanes['inbox'].setCurrentRow(0)
        with patch('dayframe.kanban.QDrag') as drag:
            drag.return_value.exec.side_effect = lambda action: self.enter(lanes['review'], mime)
            lanes['inbox'].startDrag(Qt.MoveAction)
        self.assertIsNone(lanes['review'].preview_item)
        self.assertEqual(self.store.snapshot()['pending'], before)

    def test_same_column_drop_preserves_the_previous_undo_and_does_not_save(self):
        ticket = self.ticket()
        lanes = self.board()
        previous_undo = lambda: None
        self.window.undo_action = previous_undo
        before = self.store.snapshot()['pending']
        mime = self.mime(ticket['id'])
        self.enter(lanes['inbox'], mime)
        self.assertIsNone(lanes['inbox'].preview_item)
        self.assertTrue(self.drop(lanes['inbox'], mime).isAccepted())
        self.assertIs(self.window.undo_action, previous_undo)
        self.assertEqual(self.store.snapshot()['pending'], before)

    def test_invalid_or_archived_ticket_drags_are_ignored(self):
        archived = self.ticket(archived=1)
        lanes = self.board()
        invalid = [self.mime('unknown-ticket'), self.mime(archived['id']), QMimeData(), QMimeData()]
        invalid[-2].setText('Unrelated text')
        invalid[-1].setData(TICKET_MIME, b'\xff')
        before = self.store.snapshot()['pending']
        for mime in invalid:
            self.assertFalse(self.enter(lanes['ready'], mime).isAccepted())
            self.assertIsNone(lanes['ready'].preview_item)
        self.assertEqual(self.store.snapshot()['pending'], before)

    def test_failed_drop_clears_preview_and_preserves_the_previous_undo(self):
        ticket = self.ticket()
        lanes = self.board()
        previous_undo = lambda: None
        self.window.undo_action = previous_undo
        mime = self.mime(ticket['id'])
        self.enter(lanes['ready'], mime)
        with patch.object(self.window, 'execute', return_value=None):
            self.assertFalse(self.drop(lanes['ready'], mime).isAccepted())
        self.assertIsNone(lanes['ready'].preview_item)
        self.assertIs(self.window.undo_action, previous_undo)
        self.assertEqual(self.store.read('ticket', ticket['id'])['status'], 'inbox')
