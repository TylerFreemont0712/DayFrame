"""Kanban interactions keep previews separate from persisted ticket changes."""
import unittest
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from dayframe import domain as D, planning as P
from dayframe.dialogs import AddDialog
from dayframe.store import Store
from dayframe.ui import DayFrame, TicketList

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
