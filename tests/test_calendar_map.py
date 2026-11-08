"""Shared calendar records, editing/dragging, map hierarchy and guarded gestures."""

import sqlite3
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTime, QTimer, QPointF, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from dayframe.core import domain as D, planning as P
from dayframe.data.store import Store
from dayframe.ui.window import DayFrame
from dayframe.ui.dialogs import AddDialog
from dayframe.ui.theme import apply_theme, CURRENT

APP = QApplication.instance() or QApplication([])
BASE = Path("build/test-data")


class CalendarAndMapTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("planner", "tyler")
        self.p = self.s.command("project.save", {"name": "App"})
        self.w = None

    def tearDown(self):
        if self.w:
            self.w.close()
            APP.processEvents()
        self.s.close()

    def ticket(self, **fields):
        return self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Ticket", **fields})

    def event(self, **fields):
        return self.s.command("event.save", {"title": "Event", "date": "2026-11-04", **fields})

    def window(self):
        self.w = DayFrame(self.s)
        self.w.resize(1280, 800)
        self.w.show()
        APP.processEvents()
        return self.w

    def test_sunday_multiday_midnight_yearly_and_overlap(self):
        self.assertEqual(P.sunday("2026-11-04"), date(2026, 11, 1))
        self.assertEqual(P.sunday("2026-11-01"), date(2026, 11, 1))
        trip = self.event(
            title="Trip",
            date="2026-11-02",
            end_date="2026-11-05",
            start_time="",
            end_time="",
            event_type="trip",
        )
        overnight = self.event(
            title="Overnight", date="2026-11-03", end_date="2026-11-04", start_time="23:00", end_time="00:00"
        )
        birthday = self.event(
            title="Leap birthday", date="2024-02-29", start_time="", end_time="", recurrence="yearly"
        )
        snapshot = self.s.snapshot()
        on_day = P.day_items(snapshot, "2026-11-04")
        self.assertIn(trip["id"], [i["id"] for i in on_day])
        self.assertNotIn(overnight["id"], [i["id"] for i in on_day])
        self.assertEqual(P.day_items(snapshot, "2027-02-28")[0]["id"], birthday["id"])
        lanes = P.overlap_lanes(
            [
                {"key": "a", "start_min": 60, "end_min": 120},
                {"key": "b", "start_min": 90, "end_min": 150},
                {"key": "c", "start_min": 120, "end_min": 180},
                {"key": "d", "start_min": 180, "end_min": 210},
            ]
        )
        self.assertEqual([i["lanes"] for i in lanes], [2, 2, 2, 1])
        self.assertEqual(lanes[0]["lane"], lanes[2]["lane"])

    def test_invalid_event_changes_roll_back_and_preserve_metadata(self):
        e = self.event(description="Meeting agenda", location="Office", color="#123456")
        before = self.s.snapshot()["pending"]
        for fields in (
            {"end_time": "08:00"},
            {"start_time": ""},
            {"end_date": "2026-11-03"},
            {"color": "red"},
            {"recurrence": "daily"},
        ):
            with self.assertRaises(ValueError):
                self.s.command("event.save", {"id": e["id"], **fields})
        self.assertEqual(self.s.snapshot()["pending"], before)
        self.assertEqual(self.s.read("event", e["id"])["location"], "Office")

    def test_v2_migration_preserves_event_and_notes(self):
        e = self.event(title="Old event")
        n = self.s.command("note.save", {"title": "Preserved note", "body": "Old content"})
        root = self.s.root
        self.s.close()
        with sqlite3.connect(root / "timemanager.db") as db:
            for field in ("end_date", "description", "location", "color", "recurrence", "archived"):
                db.execute("ALTER TABLE events DROP COLUMN " + field)
            db.execute("ALTER TABLE tickets DROP COLUMN parent_id")
            db.execute("ALTER TABLE map_sections DROP COLUMN parent_id")
            db.execute("ALTER TABLE map_sections DROP COLUMN predecessor_ids")
            db.execute("DELETE FROM schema_migrations WHERE version>2")
        self.s = Store(root)
        self.assertTrue(self.s.restore_session())
        self.assertEqual(self.s.read("event", e["id"])["title"], "Old event")
        self.assertEqual(self.s.read("event", e["id"])["recurrence"], "")
        self.assertEqual(self.s.read("note", n["id"])["body"], "Old content")
        self.assertEqual(self.s.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], 4)

    def test_nested_rules_ticket_parent_sequence_and_cycle_rollback(self):
        front = self.s.command(
            "section.save",
            {"project_id": self.p["id"], "name": "Frontend", "rule_field": "component", "rule_value": "UI"},
        )
        calendar = self.s.command(
            "section.save",
            {
                "project_id": self.p["id"],
                "name": "Calendar",
                "parent_id": front["id"],
                "rule_field": "label",
                "rule_value": "calendar",
            },
        )
        later = self.s.command(
            "section.save", {"project_id": self.p["id"], "name": "Release", "predecessor_ids": [front["id"]]}
        )
        t = self.ticket(component="UI", labels=["calendar"])
        parent = self.ticket(title="Parent", labels=["shared"], milestone="R1")
        placed = next(p for p in self.s.list("placement") if p["ticket_id"] == t["id"])
        self.assertEqual(placed["section_id"], calendar["id"])
        child = self.ticket(title="Child")
        self.s.command("ticket.relate", {"parent_id": parent["id"], "child_id": child["id"]})
        saved = self.s.read("ticket", child["id"])
        self.assertEqual(saved["parent_id"], parent["id"])
        self.assertEqual(saved["labels"], ["shared"])
        self.assertEqual(saved["milestone"], "R1")
        self.assertEqual(saved["dependencies"], [])
        before = self.s.snapshot()["pending"]
        for command, payload in (
            ("ticket.relate", {"parent_id": child["id"], "child_id": parent["id"]}),
            ("section.save", {"id": front["id"], "parent_id": calendar["id"]}),
            ("section.save", {"id": front["id"], "predecessor_ids": [later["id"]]}),
        ):
            with self.assertRaises(ValueError):
                self.s.command(command, payload)
        self.assertEqual(self.s.snapshot()["pending"], before)
        other = self.s.command("project.save", {"name": "Other"})
        outsider = self.s.command("ticket.save", {"project_id": other["id"], "title": "Private"})
        with self.assertRaises(ValueError):
            self.s.command("ticket.relate", {"parent_id": outsider["id"], "child_id": child["id"]})

    def test_event_edit_and_week_drag_resize_update_same_record_and_undo(self):
        e = self.event(location="Before")
        w = self.window()
        w.calendar_day = "2026-11-04"
        w.navigate("Calendar")
        APP.processEvents()
        item = next(x for x in w.week_calendar.items if x["id"] == e["id"])

        def edit():
            d = APP.activeModalWidget()
            self.assertIsInstance(d, AddDialog)
            d.start.setTime(QTime(10, 0))
            d.end.setTime(QTime(11, 30))
            d.location.setText("After")
            d.accept()

        QTimer.singleShot(0, edit)
        w.open_calendar_item(item)
        self.assertEqual(self.s.read("event", e["id"])["start_time"], "10:00")
        self.assertEqual(self.s.read("event", e["id"])["location"], "After")
        APP.processEvents()
        canvas = w.week_calendar.canvas
        canvas.repaint()
        APP.processEvents()
        rect, entry = next((r, x) for r, x in canvas.regions if x["id"] == e["id"])
        start = rect.center().toPoint()
        end = start + QPointF(0, 48).toPoint()
        QTest.mousePress(canvas, Qt.LeftButton, pos=start)
        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(end),
            QPointF(canvas.mapToGlobal(end)),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(canvas, move)
        QTest.mouseRelease(canvas, Qt.LeftButton, pos=end)
        APP.processEvents()
        self.assertEqual(self.s.read("event", e["id"])["start_time"], "11:00")
        self.assertEqual(len(self.s.list("event")), 1)
        w.undo()
        self.assertEqual(self.s.read("event", e["id"])["start_time"], "10:00")
        APP.processEvents()
        canvas = w.week_calendar.canvas
        canvas.repaint()
        rect, entry = next((r, x) for r, x in canvas.regions if x["id"] == e["id"])
        start = QPointF(rect.center().x(), rect.bottom() - 2).toPoint()
        end = start + QPointF(0, 24).toPoint()
        QTest.mousePress(canvas, Qt.LeftButton, pos=start)
        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(end),
            QPointF(canvas.mapToGlobal(end)),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(canvas, move)
        QTest.mouseRelease(canvas, Qt.LeftButton, pos=end)
        APP.processEvents()
        self.assertEqual(self.s.read("event", e["id"])["end_time"], "12:00")

    def test_home_timer_new_ticket_event_and_calendar_geometry_across_themes(self):
        day = D.day_key(self.s.settings()["timezone"])
        t = self.ticket(title="Unscheduled new ticket")
        self.event(title="Ordinary event", date=day)
        w = self.window()
        self.assertNotIn("Notes", w.nav)
        self.assertEqual(w.quick_type.findData("note"), -1)
        self.assertTrue(any(b.text() == t["title"] for b in w.workspace.findChildren(QPushButton)))
        self.assertTrue(any("Ordinary event" in b.text() for b in w.workspace.findChildren(QPushButton)))
        w.execute("timer.action", {"action": "start", "ticket_id": t["id"]})
        self.assertEqual(w.home_focus_title.text(), t["title"])
        w.execute("timer.action", {"action": "pause"})
        self.assertEqual(w.home_focus_clock.text(), w.timer_clock.text())
        faces = set()
        radii = set()
        for theme in ("graphite", "terminal", "light", "studio"):
            self.s.settings({"theme": theme})
            apply_theme(self.s.settings())
            faces.add(APP.font().family())
            radii.add(CURRENT["radius"])
            w.build_shell()
            w.navigate("Calendar")
            w.resize(980, 640)
            QTest.qWait(100)
            mini = w.mini_month
            upcoming = w.upcoming_panel
            week = w.week_calendar
            self.assertLessEqual(mini.geometry().bottom(), upcoming.geometry().top())
            self.assertLessEqual(mini.grid.geometry().bottom(), mini.height())
            self.assertGreaterEqual(week.width(), 490)
            self.assertEqual(week.start.weekday(), 6)
            header = week.header
            self.assertGreaterEqual(header.row_height, header.fontMetrics().height() + 4)
            self.assertLessEqual(header.band, header.MAX_LANES * header.row_height + 8)
        self.assertGreaterEqual(len(faces), 3)
        self.assertEqual(len(radii), 4)

    def test_all_day_chips_fit_their_row_and_overflow_shows_more(self):
        day = D.day_key(self.s.settings()["timezone"])
        for n in range(6):
            self.event(title="All day %d" % n, date=day, start_time="", end_time="")
        w = self.window()
        for scale in (75, 90, 140):
            self.s.settings({"textScale": scale})
            apply_theme(self.s.settings())
            w.build_shell()
            w.navigate("Calendar")
            QTest.qWait(50)
            header = w.week_calendar.header
            header.repaint()
            line = header.fontMetrics().height()
            self.assertEqual(header.lanes, 6)
            self.assertEqual(len(header.regions), header.MAX_LANES - 1)
            for rect, _ in header.regions:
                self.assertGreaterEqual(rect.height(), line + 2)
                self.assertLessEqual(rect.bottom(), header.height())
            self.assertEqual(len(header.more_regions), 1)
            rect, _, hidden = header.more_regions[0]
            self.assertEqual(len(hidden), 3)
            self.assertLessEqual(rect.bottom(), header.height())

    def test_map_hold_preview_cancel_confirm_and_undo(self):
        a = self.s.command(
            "section.save",
            {"project_id": self.p["id"], "name": "Frontend", "rule_field": "component", "rule_value": "UI"},
        )
        b = self.s.command(
            "section.save",
            {"project_id": self.p["id"], "name": "Calendar", "rule_field": "label", "rule_value": "calendar"},
        )
        t = self.ticket(component="UI")
        w = self.window()
        w.page = "Projects"
        w.choose_project(self.p["id"])
        APP.processEvents()
        view = w.map
        node = view.nodes[t["id"]]
        target = next(r for sec, r in view.regions if sec["id"] == b["id"])
        point = target.center()
        before = self.s.snapshot()["pending"]
        view.begin_hover("ticket", t["id"])
        view.consider_hover("ticket", t["id"], point)
        self.assertTrue(view.ghost_items)
        self.assertFalse(view.hover_armed)
        with patch.object(QMessageBox, "question") as confirmation:
            view.finish_hover("ticket", t["id"], point, node)
        confirmation.assert_not_called()
        self.assertEqual(self.s.snapshot()["pending"], before)
        view.begin_hover("ticket", t["id"])
        view.consider_hover("ticket", t["id"], point)
        QTest.qWait(1600)
        self.assertTrue(view.hover_armed)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
            view.finish_hover("ticket", t["id"], point, node)
        self.assertEqual(self.s.snapshot()["pending"], before)
        view.begin_hover("ticket", t["id"])
        view.consider_hover("ticket", t["id"], point)
        QTest.qWait(1600)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            view.finish_hover("ticket", t["id"], point, node)
        APP.processEvents()
        self.assertIn("calendar", self.s.read("ticket", t["id"])["labels"])
        w.undo()
        self.assertEqual(self.s.read("ticket", t["id"])["labels"], [])
        self.assertEqual(
            next(p for p in self.s.list("placement") if p["ticket_id"] == t["id"])["section_id"], a["id"]
        )

    def test_section_center_and_edge_gestures_update_hierarchy_and_sequence(self):
        front = self.s.command(
            "section.save",
            {"project_id": self.p["id"], "name": "Frontend", "rule_field": "component", "rule_value": "UI"},
        )
        section = self.s.command("section.save", {"project_id": self.p["id"], "name": "Calendar"})
        t = self.ticket()
        self.s.command("placement.save", {"ticket_id": t["id"], "section_id": section["id"], "manual": 1})
        w = self.window()
        w.page = "Projects"
        w.choose_project(self.p["id"])
        APP.processEvents()
        view = w.map
        target = next(r for sec, r in view.regions if sec["id"] == front["id"])
        view.begin_hover("section", section["id"])
        view.consider_hover("section", section["id"], target.center())
        QTest.qWait(1600)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            view.finish_hover("section", section["id"], target.center())
        APP.processEvents()
        self.assertEqual(self.s.read("section", section["id"])["parent_id"], front["id"])
        self.assertEqual(self.s.read("ticket", t["id"])["component"], "UI")
        outer = next(r for sec, r in w.map.regions if sec["id"] == front["id"])
        inner = next(r for sec, r in w.map.regions if sec["id"] == section["id"])
        self.assertTrue(outer.contains(inner))
        w.undo()
        APP.processEvents()
        self.assertEqual(self.s.read("section", section["id"])["parent_id"], "")
        self.assertEqual(self.s.read("ticket", t["id"])["component"], "")
        view = w.map
        target = next(r for sec, r in view.regions if sec["id"] == front["id"])
        at = QPointF(target.right() - 4, target.center().y())
        view.begin_hover("section", section["id"])
        view.consider_hover("section", section["id"], at)
        QTest.qWait(1600)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            view.finish_hover("section", section["id"], at)
        APP.processEvents()
        self.assertEqual(self.s.read("section", section["id"])["predecessor_ids"], [front["id"]])
        self.assertTrue(w.map.edges)

    def test_ticket_edge_gesture_links_without_blocking_and_can_be_undone(self):
        self.s.command(
            "section.save",
            {
                "project_id": self.p["id"],
                "name": "All tickets",
                "rule_field": "component",
                "rule_value": "UI",
            },
        )
        parent = self.ticket(title="Parent", component="UI", labels=["shared"])
        child = self.ticket(title="Child", component="UI")
        w = self.window()
        w.page = "Projects"
        w.choose_project(self.p["id"])
        APP.processEvents()
        view = w.map
        target = view.nodes[parent["id"]].sceneBoundingRect()
        at = QPointF(target.right() + 5, target.center().y())
        view.begin_hover("ticket", child["id"])
        view.consider_hover("ticket", child["id"], at)
        QTest.qWait(1600)
        self.assertEqual(view.hover_target[:3], ("ticket", parent["id"], "right"))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            view.finish_hover("ticket", child["id"], at)
        APP.processEvents()
        saved = self.s.read("ticket", child["id"])
        self.assertEqual(saved["parent_id"], parent["id"])
        self.assertEqual(saved["dependencies"], [])
        self.assertIn("shared", saved["labels"])
        self.assertTrue(w.map.edges)
        w.undo()
        self.assertEqual(self.s.read("ticket", child["id"])["parent_id"], "")
        self.assertEqual(self.s.read("ticket", child["id"])["labels"], [])


if __name__ == "__main__":
    unittest.main()
