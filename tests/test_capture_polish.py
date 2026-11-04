"""Regression checks for clipped rows/native artifacts and rich Quick Add capture."""
import unittest,uuid
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QComboBox,QSpinBox,QTabWidget,QLabel,QFrame
from dayframe.store import Store
from dayframe.ui import DayFrame
from dayframe.widgets import ElidingLabel
from dayframe.dialogs import AddDialog
from dayframe.theme import apply_theme,CURRENT
APP=QApplication.instance() or QApplication([])

class CapturePolishTests(unittest.TestCase):
    def setUp(self):
        self.s=Store(Path("build/test-data")/uuid.uuid4().hex);self.s.register("polish","tyler");self.w=None;self.dialogs=[]
        self.p=self.s.command("project.save",{"name":"DayFrame Workspace","project_key":"DAYFR"})
        self.section=self.s.command("section.save",{"project_id":self.p["id"],"name":"Calendar","rule_field":"label","rule_value":"calendar"})
        self.parent=self.s.command("ticket.save",{"project_id":self.p["id"],"title":"Calendar","component":"Frontend","milestone":"R1","labels":["shared"]})
    def tearDown(self):
        for d in self.dialogs:d.close();d.deleteLater()
        if self.w:self.w.close()
        APP.processEvents();self.s.close()
    def dialog(self):
        d=AddDialog(None,self.s.snapshot(),"ticket",self.p["id"]);self.dialogs.append(d);d.show();APP.processEvents();return d
    def window(self):
        self.w=DayFrame(self.s);self.w.show();APP.processEvents();return self.w
    def test_rounded_controls_and_empty_tab_base_do_not_leak_native_pixels(self):
        apply_theme({"theme":"studio"});root=QWidget();root.setAutoFillBackground(True);layout=QVBoxLayout(root)
        combo=QComboBox();combo.addItems(["Inbox","Ready"]);spin=QSpinBox();spin.setRange(0,50)
        tabs=QTabWidget();tabs.setDocumentMode(True);tabs.addTab(QWidget(),"Details");tabs.addTab(QWidget(),"Time")
        for w in (combo,spin,tabs):layout.addWidget(w)
        root.resize(280,180);root.show();APP.processEvents()
        try:
            bg=tuple(int(CURRENT["bg"][i:i+2],16) for i in (1,3,5))
            for control in (combo,spin):
                color=control.grab().toImage().pixelColor(control.width()-2,2)
                line=tuple(int(CURRENT["line"][i:i+2],16) for i in (1,3,5))
                for value,low,high in zip((color.red(),color.green(),color.blue()),bg,line):self.assertGreaterEqual(value,low-3);self.assertLessEqual(value,high+3)
            bar=tabs.tabBar();image=bar.grab().toImage()
            if image.width()>bar.tabRect(1).right()+8:
                pixel=image.pixelColor(image.width()-5,image.height()-1);self.assertLess(min(pixel.red(),pixel.green(),pixel.blue()),220)
            QTest.mouseClick(spin,Qt.LeftButton,pos=QPoint(spin.width()-12,6));self.assertEqual(spin.value(),1)
            QTest.mouseClick(combo,Qt.LeftButton,pos=QPoint(combo.width()-11,combo.height()//2));QTest.keyClick(combo,Qt.Key_Down);QTest.keyClick(combo,Qt.Key_Return)
            self.assertEqual(combo.currentIndex(),1)
        finally:root.close();root.deleteLater()
    def test_long_project_rows_keep_distinct_bounds_and_full_hover_text(self):
        self.s.command("ticket.save",{"project_id":self.p["id"],"title":"Test","pinned":1})
        w=self.window()
        for theme in ("graphite","amber","light","studio"):
            self.s.settings({"theme":theme,"textScale":125});apply_theme(self.s.settings());w.build_shell();w.navigate("Today");w.resize(980,640);QTest.qWait(70)
            rows=[x for x in w.workspace.findChildren(QFrame) if x.objectName()=="taskRow" and x.findChildren(ElidingLabel)]
            self.assertTrue(rows)
            for row in rows:
                widgets=[row.layout().itemAt(i).widget() for i in range(row.layout().count())]
                for left,right in zip(widgets,widgets[1:]):self.assertLess(left.geometry().right(),right.geometry().left(),(theme,left.geometry(),right.geometry()))
                badge=next(x for x in row.findChildren(ElidingLabel) if x.objectName()=="badge")
                self.assertEqual(badge.toolTip(),"DayFrame Workspace");self.assertTrue(badge.text().startswith("Day"))
                self.assertLessEqual(badge.fontMetrics().horizontalAdvance(badge.text()),badge.width()-12)
    def test_batch_capture_keeps_context_clears_per_item_text_and_retains_failures(self):
        d=self.dialog();calls=[]
        def save(kind,payload,section):
            if payload["title"]=="Fail":raise ValueError("Try a different title")
            calls.append((kind,payload,section));return True
        d.set_submit_handler(save);d.more.setChecked(True);d.labels.setText("frontend");d.status.setCurrentIndex(d.status.findData("ready"))
        d.title.setText("Fail");d.submit(True);self.assertTrue(d.isVisible());self.assertEqual(d.saved_count,0);self.assertEqual(d.title.text(),"Fail")
        d.title.setText("First");d.ticket_description.setPlainText("First context");d.checklist.setPlainText("One\nTwo");d.submit(True)
        self.assertEqual(d.saved_count,1);self.assertTrue(d.isVisible());self.assertEqual(d.title.text(),"");self.assertEqual(d.labels.text(),"frontend")
        self.assertEqual(d.ticket_description.toPlainText(),"");self.assertEqual(d.checklist.toPlainText(),"");self.assertEqual(d.status.currentData(),"ready")
        d.title.setText("Second");d.accept();self.assertEqual(d.saved_count,2);self.assertEqual(len(calls),2);self.assertFalse(d.isVisible())
        self.assertEqual(calls[0][1]["checklist"],[{"text":"One","done":False},{"text":"Two","done":False}])
    def test_quick_add_custom_fields_reach_home_and_map(self):
        w=self.window()
        def fill():
            d=APP.activeModalWidget();d.title.setText("Polished capture");d.more.setChecked(True)
            d.preset.setCurrentIndex(d.preset.findData("bug"));d.status.setCurrentIndex(d.status.findData("ready"))
            d.parent_ticket.setCurrentIndex(d.parent_ticket.findData(self.parent["id"]));d.section.setCurrentIndex(d.section.findData(self.section["id"]))
            d.pin_today.setChecked(True);d.estimate.setValue(45);d.ticket_description.setPlainText("Done when this behavior works")
            d.checklist.setPlainText("Implement\nVerify");d.accept()
        QTimer.singleShot(0,fill);self.assertTrue(w.quick_add("ticket",project_id=self.p["id"]))
        ticket=next(t for t in self.s.list("ticket") if t["title"]=="Polished capture")
        self.assertEqual(ticket["status"],"ready");self.assertEqual(ticket["priority"],"high");self.assertEqual(ticket["estimate_min"],45)
        self.assertEqual(ticket["parent_id"],self.parent["id"]);self.assertEqual(ticket["component"],"Frontend")
        self.assertEqual(set(ticket["labels"]),{"bug","shared","calendar"});self.assertEqual(len(ticket["checklist"]),2)
        self.assertEqual(ticket["description"],"Done when this behavior works");self.assertEqual(ticket["pinned"],1)
        placement=next(p for p in self.s.list("placement") if p["ticket_id"]==ticket["id"]);self.assertEqual(placement["section_id"],self.section["id"]);self.assertEqual(placement["manual"],1)
        self.assertTrue(any(t["id"]==ticket["id"] for t in w.data["ticket"]))
    def test_capture_and_classification_are_atomic_on_failure(self):
        other=self.s.command("project.save",{"name":"Other"});foreign=self.s.command("section.save",{"project_id":other["id"],"name":"Private"})
        before=self.s.snapshot()
        with self.assertRaises(ValueError):
            self.s.command("ticket.capture",{"ticket":{"project_id":self.p["id"],"title":"Must roll back","parent_id":self.parent["id"]},"section_id":foreign["id"]})
        after=self.s.snapshot()
        for key in ("ticket","placement","pending"):self.assertEqual(after[key],before[key])
    def test_project_change_removes_foreign_parent_and_section_choices(self):
        other=self.s.command("project.save",{"name":"Other"});d=self.dialog()
        d.parent_ticket.setCurrentIndex(d.parent_ticket.findData(self.parent["id"]));d.section.setCurrentIndex(d.section.findData(self.section["id"]))
        d.labels.setText("keep");d.project.setCurrentIndex(d.project.findData(other["id"]))
        self.assertEqual(d.parent_ticket.currentData(),"");self.assertEqual(d.section.currentData(),"")
        self.assertEqual(d.labels.text(),"keep");self.assertEqual(d.parent_ticket.count(),1);self.assertEqual(d.section.count(),1)
    def test_ticket_event_switch_preserves_optional_details(self):
        d=self.dialog();d.title.setText("A captured item");d.more.setChecked(True);d.ticket_description.setPlainText("Ticket context")
        d.labels.setText("calendar");d.estimate.setValue(25);d.kind.setCurrentIndex(d.kind.findData("event"));d.description.setPlainText("Event context")
        d.kind.setCurrentIndex(d.kind.findData("ticket"));kind,payload=d.payload()
        self.assertEqual(payload["description"],"Ticket context");self.assertEqual(payload["labels"],["calendar"]);self.assertEqual(payload["estimate_min"],25)
        d.kind.setCurrentIndex(d.kind.findData("event"));self.assertEqual(d.payload()[1]["description"],"Event context")

    def test_manual_labels_commit_on_enter_without_submitting_the_dialog(self):
        from dayframe.labels import label_color
        from PySide6.QtWidgets import QPushButton
        d=self.dialog();d.title.setText("Still a draft")
        QTest.keyClicks(d.labels.input,"backend");QTest.keyClick(d.labels.input,Qt.Key_Return);APP.processEvents()
        self.assertTrue(d.isVisible());self.assertIn("backend",d.labels.values);self.assertEqual(d.saved_count,0)
        next(a for a in d.labels.menu.actions() if a.text()=="bug").trigger();APP.processEvents()
        next(a for a in d.labels.menu.actions() if a.text()=="feature").trigger();APP.processEvents()
        remove=next(b for b in d.labels.findChildren(QPushButton) if b.accessibleName()=="Remove label bug")
        QTest.mouseClick(remove,Qt.LeftButton);self.assertNotIn("bug",d.labels.values);self.assertIn("feature",d.labels.values)
        d.labels.input.setText("unfinished draft");d.labels.toggle("bug");self.assertEqual(d.labels.input.text(),"unfinished draft")
        d.labels.remove("bug");self.assertEqual(d.labels.input.text(),"unfinished draft")
        from PySide6.QtGui import QColor
        bug=QColor(label_color("bug"));feature=QColor(label_color("feature"))
        self.assertGreater(bug.red(),bug.green());self.assertGreater(feature.green(),feature.red())
    def test_inspector_label_editor_saves_custom_labels_and_offers_them_again(self):
        from dayframe.labels import LabelsEditor
        from PySide6.QtWidgets import QPushButton
        w=self.window();w.navigate("Projects");w.select_ticket(self.parent["id"]);APP.processEvents()
        editor=w.inspector.findChild(LabelsEditor)
        QTest.keyClicks(editor.input,"my-custom-label");QTest.keyClick(editor.input,Qt.Key_Return);editor.toggle("feature")
        save=next(b for b in w.inspector.findChildren(QPushButton) if b.text()=="Save ticket")
        QTest.mouseClick(save,Qt.LeftButton);APP.processEvents()
        values=self.s.read("ticket",self.parent["id"])["labels"];self.assertIn("my-custom-label",values);self.assertIn("feature",values)
        d=self.dialog();self.assertIn("my-custom-label",d.labels.known);self.assertIn("bug",d.labels.known)
    def test_many_label_chips_wrap_within_the_form_and_leave_actions_visible(self):
        from PySide6.QtCore import QRect
        d=self.dialog();d.available_rect=lambda:QRect(8,8,800,500)
        d.labels.setText(", ".join(["bug","feature"]+["custom-label-"+str(i) for i in range(15)]));d.fit_to_contents();QTest.qWait(70)
        self.assertLess(d.form_scroll.geometry().bottom(),d.buttons.geometry().top());self.assertLessEqual(d.height(),500)
        chips=d.labels.chips
        for i in range(d.labels.flow.count()):
            item=d.labels.flow.itemAt(i);self.assertLessEqual(item.geometry().right(),chips.width())
        controls=d.labels.input.parentWidget()
        self.assertLess(chips.geometry().bottom(),controls.geometry().top())


if __name__=="__main__":unittest.main()
