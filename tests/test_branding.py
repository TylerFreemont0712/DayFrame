"""The visible rename must not strand an existing device profile."""
import os
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

from dayframe.app import data_directory
from dayframe.data.store import Store


class BrandingCompatibilityTests(unittest.TestCase):
    def test_existing_windows_profile_path(self):
        with patch('dayframe.app.sys.platform','win32'), patch.dict(os.environ,{'LOCALAPPDATA':'C:/example-local'}):
            self.assertEqual(data_directory(),Path('C:/example-local/TimeManager'))

    def test_existing_linux_profile_path(self):
        with patch('dayframe.app.sys.platform','linux'), patch.dict(os.environ,{'XDG_DATA_HOME':'/example-data'}):
            self.assertEqual(data_directory(),Path('/example-data/TimeManager'))

    def test_rename_retains_database_and_remembered_session(self):
        root=Path('build/test-data')/uuid.uuid4().hex
        store=Store(root)
        try:
            store.register('compatibility','tyler')
            project=store.command('project.save',{'name':'Existing project','project_key':'OLD'})
            store.command('ticket.save',{'title':'Retain existing work','project_id':project['id']})
            identity=store.auth()['id']
        finally:
            store.close()
        self.assertTrue((root/'timemanager.db').is_file())
        reopened=Store(root)
        try:
            self.assertTrue(reopened.restore_session())
            self.assertEqual(reopened.auth()['id'],identity)
            self.assertEqual(reopened.list('ticket')[0]['title'],'Retain existing work')
        finally:
            reopened.close()
