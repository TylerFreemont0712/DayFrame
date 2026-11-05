import unittest
import uuid
import time
from unittest.mock import patch
from pathlib import Path
from PySide6.QtCore import Qt,QMimeData,QPoint,QPointF,QTimer,QTime
from PySide6.QtGui import QDragEnterEvent,QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton,QComboBox,QGraphicsView,QTimeEdit,QTabBar,QTableWidget
from PySide6.QtWidgets import QMessageBox
from dayframe.store import Store
from dayframe import domain as D
from dayframe.ui import DayFrame,TicketList
from dayframe.project_map import TicketNode
from dayframe.theme import apply_theme,icon
APP=QApplication.instance() or QApplication([])
class NativeUiTests(unittest.TestCase):
    def setUp(self):
        self.s=Store(Path("build/test-data")/uuid.uuid4().hex);self.s.register("ui","tyler");self.s.load_examples()
        self.w=DayFrame(self.s);self.w.show();APP.processEvents()
    def tearDown(self):self.w.close();APP.processEvents();self.s.close()
    def click(self,text,parent=None):
        b=next(b for b in (parent or self.w).findChildren(QPushButton) if b.text()==text)
        QTest.mouseClick(b,Qt.LeftButton);APP.processEvents()
    def test_native_navigation_editor_timer_and_map(self):
        self.assertFalse(icon("home").isNull())
        self.assertFalse(self.w.context.isVisible())
        QTest.mouseClick(self.w.nav["Projects"],Qt.LeftButton);APP.processEvents()
        self.assertEqual(len(self.w.findChildren(TicketList)),5)
        t=next(t for t in self.w.data["ticket"] if t["status"]=="doing")
        target=next(lane for lane in self.w.findChildren(TicketList) if lane.status=="review")
        mime=QMimeData();mime.setData("application/x-timemanager-ticket",t["id"].encode())
        enter=QDragEnterEvent(QPoint(20,20),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
        APP.sendEvent(target.viewport(),enter)
        drop=QDropEvent(QPointF(20,20),Qt.MoveAction,mime,Qt.LeftButton,Qt.NoModifier)
        APP.sendEvent(target.viewport(),drop);APP.processEvents()
        self.assertEqual(self.s.read("ticket",t["id"])["status"],"review")
        self.w.undo();self.assertEqual(self.s.read("ticket",t["id"])["status"],"doing")
        self.w.select_ticket(t["id"]);APP.processEvents()
        title=next(e for e in self.w.inspector.findChildren(QLineEdit) if e.accessibleName()=="Ticket title")
        title.setText("Native editor saved this")
        self.click("Save ticket",self.w.inspector)
        self.assertEqual(self.s.read("ticket",t["id"])["title"],"Native editor saved this")
        self.click("Track",self.w.inspector)
        self.assertEqual(self.s.read("timer","active")["ticket_id"],t["id"])
        self.w.choose_project(t["project_id"]);APP.processEvents()
        self.assertIsInstance(self.w.map,QGraphicsView)
        self.assertEqual(len(self.w.map.nodes)+len(self.w.map.unsorted),len([x for x in self.s.list("ticket") if x["project_id"]==t["project_id"]]))
        self.w.map.fit();APP.processEvents()
        self.w.navigate("Calendar");self.w.navigate("Time");self.w.navigate("Settings");APP.processEvents()
        self.w.settings_panel.navigation.setCurrentRow(1);APP.processEvents()
        themes=next(c for c in self.w.workspace.findChildren(QComboBox) if c.findData("light")>=0)
        themes.setCurrentIndex(themes.findData("light"));self.click("Apply theme")
        self.assertEqual(self.s.settings()["theme"],"light")
        self.assertFalse(any("WebEngine" in type(x).__name__ for x in self.w.findChildren(object) if hasattr(x,"metaObject")))
    def test_project_tabs_and_calendar_deadline_open_details(self):
        self.w.navigate("Projects")
        def tabs():
            bar=self.w.page_header.findChild(QTabBar)
            return [bar.tabText(i) for i in range(bar.count())]
        self.assertEqual(tabs(),["Kanban","Details"])
        ticket=self.w.data["ticket"][0]
        self.w.choose_project(ticket["project_id"])
        self.assertEqual(tabs(),["Map","Kanban","Details"])
        self.w.navigate("Calendar")
        self.w.open_calendar_item({"kind":"deadline","record":ticket,"ticket_id":ticket["id"]})
        APP.processEvents()
        self.assertEqual(self.w.page,"Projects")
        self.assertEqual(self.w.project_view,"Details")
        self.assertEqual(self.w.selected,ticket["id"])
        self.assertTrue(self.w.inspector.isVisible())
        table=self.w.workspace.findChild(QTableWidget)
        self.assertEqual(table.columnCount(),9)
        self.assertEqual(tabs(),["Map","Kanban","Details"])
    def test_draft_survives_refresh_and_saves_only_changed_fields(self):
        self.w.navigate("Projects")
        t=next(t for t in self.w.data["ticket"] if t["status"]=="doing")
        self.w.select_ticket(t["id"]);APP.processEvents()
        title=next(e for e in self.w.inspector.findChildren(QLineEdit) if e.accessibleName()=="Ticket title")
        title.setText("Unsaved native draft")
        self.s.command("ticket.save",{"id":t["id"],"component":"Another device changed this"})
        self.w.refresh()
        self.assertEqual(title.text(),"Unsaved native draft")
        with patch.object(QMessageBox,"question",return_value=QMessageBox.Cancel):self.w.navigate("Settings")
        self.assertEqual(self.w.page,"Projects")
        self.click("Save ticket",self.w.inspector)
        saved=self.s.read("ticket",t["id"])
        self.assertEqual(saved["title"],"Unsaved native draft")
        self.assertEqual(saved["component"],"Another device changed this")
    def test_compact_window_quick_capture_filter_and_daily_total(self):
        self.assertLessEqual(self.w.width(),1280);self.assertLessEqual(self.w.height(),800)
        self.assertFalse(self.w.isMaximized())
        self.w.quick_type.setCurrentIndex(self.w.quick_type.findData("event"));self.w.quick_input.setText("Captured from the footer")
        QTest.keyClick(self.w.quick_input,Qt.Key_Return);APP.processEvents()
        self.assertTrue(any(n["title"]=="Captured from the footer" for n in self.s.list("event")))
        today=D.day_key(self.s.settings()["timezone"]);start,end=D.day_bounds(today,self.s.settings()["timezone"])
        self.s.command("time.add",{"start_at":start-1800000,"end_at":start+3600000});self.w.refresh()
        self.assertEqual(self.w.today_total.text(),"Today 1h 0m")
        self.w.navigate("Projects");self.w.change_filter("filter_status","review")
        self.assertTrue(all(t["status"]=="review" for t in self.w.filtered_tickets()))
        self.assertEqual(len(self.w.filtered_tickets()),1)
        self.w.navigate("Today");self.w.resize(980,640);APP.processEvents()
        self.w.select_ticket(next(t["id"] for t in self.w.data["ticket"] if t["status"]=="doing"));APP.processEvents()
        self.assertLessEqual(self.w.width(),980);self.assertTrue(self.w.inspector.isVisible())
        self.assertTrue(self.w._today_narrow)
    def test_options_logout_then_login_and_reopen(self):
        root=self.s.root
        action=next(a for a in self.w.options_menu.actions() if a.text()=="Log out");action.trigger();APP.processEvents()
        self.assertIsNone(self.w.data);self.assertFalse(self.s.restore_session())
        self.w.username.setText("ui");self.w.password.setText("tyler");self.w.submit_auth()
        deadline=time.monotonic()+5
        while self.w.jobs and time.monotonic()<deadline:QTest.qWait(20)
        self.assertIsNotNone(self.w.data)
        self.w.close();self.s.close();self.s=Store(root);self.w=DayFrame(self.s);self.w.show();APP.processEvents()
        self.assertIsNotNone(self.w.data);self.assertEqual(self.w.data["account"]["username"],"ui")
    def test_schedule_dialog_adds_real_ticket_block_without_moving_deadline(self):
        ticket=next(t for t in self.w.data["ticket"] if t["status"]=="doing")
        previous=len(self.s.list("block"));deadline=ticket["due_date"]
        def fill_schedule():
            dialog=APP.activeModalWidget();times=dialog.findChildren(QTimeEdit)
            times[0].setTime(QTime(13,0));times[1].setTime(QTime(14,0));dialog.accept()
        QTimer.singleShot(0,fill_schedule);self.w.schedule_ticket(ticket);APP.processEvents()
        self.assertEqual(len(self.s.list("block")),previous+1)
        self.assertEqual(self.s.list("block")[-1]["ticket_id"],ticket["id"])
        self.assertEqual(self.s.read("ticket",ticket["id"])["due_date"],deadline)
        self.w.complete_ticket(ticket);self.assertEqual(self.s.read("ticket",ticket["id"])["status"],"done")
        self.w.undo();self.assertEqual(self.s.read("ticket",ticket["id"])["status"],"doing")

if __name__=="__main__":unittest.main()
