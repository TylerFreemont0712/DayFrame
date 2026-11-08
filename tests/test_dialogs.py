"""Geometry and type-switch coverage for the compact native forms."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QRect,QTime
from PySide6.QtWidgets import QApplication,QDialog,QLineEdit,QDialogButtonBox
from dayframe.ui.dialogs import AddDialog,SectionDialog
from dayframe.ui.widgets import FormDialog,label
from dayframe.ui.theme import apply_theme

APP=QApplication.instance() or QApplication([])
SNAPSHOT={"settings":{"timezone":"Asia/Tokyo"},"project":[{"id":"project-1","name":"Example","archived":0}]}

class CompactDialogTests(unittest.TestCase):
    def setUp(self):
        self.dialogs=[];apply_theme({"theme":"graphite","density":"compact","textScale":100})
    def tearDown(self):
        for d in self.dialogs:d.close();d.deleteLater()
        APP.processEvents()
    def make(self,kind="ticket",existing=None):
        d=AddDialog(None,SNAPSHOT,kind,"project-1",existing);self.dialogs.append(d)
        d.available_rect=lambda:QRect(12,12,1000,696)
        d.show();APP.processEvents();return d
    def assert_fixed_actions(self,d):
        self.assertIs(d.buttons.parentWidget(),d)
        self.assertLess(d.form_scroll.geometry().bottom(),d.buttons.geometry().top())
        self.assertTrue(d.rect().contains(d.buttons.geometry()))
        self.assertLessEqual(d.height(),696);self.assertLessEqual(d.width(),1000)
    def test_type_switch_preserves_input_and_limits_visible_fields(self):
        d=self.make();d.title.setText("One captured idea")
        self.assertTrue(d.project.isVisible());self.assertFalse(d.description.isVisible())
        self.assertFalse(d.estimate.isVisible());self.assertLess(d.height(),500)
        d.more.setChecked(True);APP.processEvents();self.assertTrue(d.estimate.isVisible());self.assert_fixed_actions(d)
        d.kind.setCurrentIndex(d.kind.findData("event"));APP.processEvents()
        self.assertFalse(d.project.isVisible());self.assertTrue(d.start.isVisible())
        self.assertFalse(d.estimate.isVisible());self.assert_fixed_actions(d)
        self.assertEqual(d.kind.findData("note"),-1);self.assertTrue(d.description.isVisible())
        self.assertEqual(d.title.text(),"One captured idea");self.assert_fixed_actions(d)
        kind,payload=d.payload();self.assertEqual(kind,"event");self.assertIn("description",payload)
    def test_scheduled_time_validation_stays_in_same_dialog(self):
        d=self.make("event");d.title.setText("Appointment")
        d.start.setTime(QTime(14,0));d.end.setTime(QTime(13,0));d.accept();APP.processEvents()
        self.assertTrue(d.isVisible());self.assertTrue(d.feedback.isVisible())
        self.assertIn("after",d.feedback.text());self.assert_fixed_actions(d)
        d.timed.setChecked(False);APP.processEvents()
        self.assertEqual(d.payload()[1]["start_time"],"")
        d.accept();self.assertEqual(d.result(),QDialog.Accepted)
    def test_oversized_form_scrolls_with_footer_in_window(self):
        d=FormDialog(None,"Large form");self.dialogs.append(d)
        d.available_rect=lambda:QRect(12,12,1000,696);d.resize(1600,1400)
        for n in range(35):d.layout.addWidget(QLineEdit("Field "+str(n)))
        d.finish_form();d.show();APP.processEvents()
        self.assert_fixed_actions(d)
        self.assertGreater(d.form_scroll.verticalScrollBar().maximum(),0)
        d.form_scroll.verticalScrollBar().setValue(d.form_scroll.verticalScrollBar().maximum())
        self.assert_fixed_actions(d)
    def test_existing_section_and_scaled_text_stay_bounded(self):
        apply_theme({"theme":"light","density":"compact","textScale":125})
        original={"id":"section-1","name":"Frontend","rule_field":"label","rule_value":"ui"}
        d=SectionDialog(None,original);self.dialogs.append(d);d.available_rect=lambda:QRect(12,12,1000,696)
        d.show();APP.processEvents();self.assertEqual(d.payload(),original);self.assert_fixed_actions(d)
        d.field.setCurrentIndex(d.field.findData(""));self.assertFalse(d.value.isEnabled())
        self.assertEqual(d.payload()["rule_value"],"")

if __name__=="__main__":unittest.main()
