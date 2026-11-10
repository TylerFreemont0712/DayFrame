"""Home: figures, the week strip of day cards, the day timeline, countdown tiles and layouts."""

import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTabWidget

from dayframe.core import domain as D, planning as P
from dayframe.data.store import Store
from dayframe.ui.views.agenda import Agenda
from dayframe.ui.views.home import CountdownTiles, StatChip, WeekStrip, event_glyph, when_text
from dayframe.ui.window import DayFrame

APP = QApplication.instance() or QApplication([])
BASE = Path("build/test-data")


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(BASE / uuid.uuid4().hex)
        self.s.register("home", "tyler")
        self.p = self.s.command("project.save", {"name": "App", "project_key": "APP"})
        self.today = D.day_key(self.s.settings()["timezone"])
        self.w = None

    # Delete windows rather than only closing them: unittest keeps finished tests (and their
    # windows) alive, and without an event loop deleteLater() needs an explicit flush.
    def tearDown(self):
        if self.w:
            self.w.close()
            self.w.deleteLater()
            self.w = None
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.s.close()

    def day(self, offset):
        return (date.fromisoformat(self.today) + timedelta(days=offset)).isoformat()

    def ticket(self, **fields):
        return self.s.command("ticket.save", {"project_id": self.p["id"], "title": "Ticket", **fields})

    def event(self, **fields):
        return self.s.command(
            "event.save", {"title": "Event", "date": self.today, "start_time": "", "end_time": "", **fields}
        )

    def window(self, width=1280, height=800):
        self.w = DayFrame(self.s)
        self.w.resize(width, height)
        self.w.show()
        self.settle()
        return self.w

    def settle(self):
        for _ in range(3):
            APP.processEvents()
        # Rebuilt pages leave their old widgets to deleteLater(); remove them before looking.
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def click(self, widget, point, kind=QEvent.MouseButtonRelease):
        point = QPointF(point)
        position = QPointF(widget.mapToGlobal(point.toPoint()))
        event = QMouseEvent(kind, point, position, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(widget, event)
        self.settle()

    def test_relative_dates_and_event_symbols(self):
        self.assertEqual(when_text("2026-11-10", "2026-11-10"), "Today")
        self.assertEqual(when_text("2026-11-11", "2026-11-10"), "Tomorrow")
        self.assertEqual(when_text("2026-11-14", "2026-11-10"), "Saturday")
        self.assertEqual(when_text("2026-11-22", "2026-11-10"), "Nov 22")
        self.assertEqual(when_text("2026-12-05", "2026-11-10"), "Dec 5")
        self.assertEqual(event_glyph({"event_type": "birthday"}), "birthday-cake")
        self.assertEqual(event_glyph({"event_type": "trip"}), "plane")
        self.assertEqual(event_glyph({"event_type": "deadline"}), "flag")
        self.assertEqual(event_glyph({"event_type": "something new"}), "calendar-alt")
        # Every type the app offers has its own symbol.
        glyphs = [event_glyph({"event_type": key}) for key, name, color in P.EVENT_TYPES]
        self.assertEqual(len(set(glyphs)), len(glyphs))

    def test_figures_count_today_and_open_the_matching_ticket_view(self):
        self.ticket(title="Late", due_date=self.day(-2), status="ready")
        self.ticket(title="Due now", due_date=self.today)
        self.ticket(title="Reviewing", status="review")
        finished = self.ticket(title="Finished", status="done")
        self.ticket(title="Finished long ago", status="done", completed_at=1000)
        self.assertGreater(self.s.read("ticket", finished["id"])["completed_at"], 0)
        w = self.window()
        chips = {
            chip.findChildren(QLabel)[1].text(): chip.findChildren(QLabel)[0]
            for chip in w.workspace.findChildren(StatChip)
        }
        self.assertEqual(
            {name: figure.text() for name, figure in chips.items()},
            {"Overdue": "1", "Due today": "1", "In progress": "2", "Done today": "1"},
        )
        self.assertEqual(chips["Overdue"].objectName(), "homeStatWarn")
        self.assertEqual(chips["Due today"].objectName(), "homeStatValue")
        overdue = chips["Overdue"].parentWidget()
        self.click(overdue, overdue.rect().center())
        self.assertEqual((w.page, w.tickets_view, w.tickets_quick), ("Tickets", "Overview", "overdue"))

    def test_week_strip_selects_a_day_for_the_timeline_and_moves_between_weeks(self):
        self.event(title="Dentist", date=self.day(1), start_time="10:00", end_time="11:00")
        w = self.window()
        strip = w.workspace.findChild(WeekStrip)
        self.assertEqual(strip.day, self.today)
        self.assertEqual(strip.days()[0], P.sunday(self.today).isoformat())
        self.assertEqual(len(strip.days()), 7)
        self.assertFalse(strip.grab().isNull())
        self.assertEqual([day for rect, day in strip.regions], strip.days())
        self.assertEqual(w.workspace.findChild(Agenda).day, self.today)
        # Stay inside the shown week whichever weekday the test runs on.
        target = next(day for rect, day in strip.regions if day != self.today)
        rect = next(rect for rect, day in strip.regions if day == target)
        with patch.object(w, "execute") as execute:
            self.click(strip, rect.center())
        execute.assert_not_called()
        self.assertEqual(w.home_day, target)
        self.assertEqual(w.workspace.findChild(WeekStrip).day, target)
        self.assertEqual(w.workspace.findChild(Agenda).day, target)
        w.home_select_day(w.home_shift(7))
        self.settle()
        strip = w.workspace.findChild(WeekStrip)
        self.assertEqual(strip.start, P.sunday(target) + timedelta(days=7))
        self.assertTrue(any(x.text().startswith("Week of") for x in w.workspace.findChildren(QLabel)))
        back = next(b for b in w.workspace.findChildren(QPushButton) if b.text() == "Today")
        self.assertTrue(back.isEnabled())
        back.click()
        self.settle()
        self.assertEqual(w.home_day, self.today)
        self.assertTrue(any(x.text() == "This week" for x in w.workspace.findChildren(QLabel)))
        # Double-clicking a card adds an event on that day; Calendar opens the same week.
        strip = w.workspace.findChild(WeekStrip)
        strip.grab()
        rect = next(rect for rect, day in strip.regions if day == target)
        with patch.object(w, "quick_add") as add:
            self.click(strip, rect.center(), QEvent.MouseButtonDblClick)
        add.assert_called_once_with("event", day=target, all_day=True)
        w.home_open_calendar(target)
        self.assertEqual((w.page, w.calendar_day), ("Calendar", target))

    def test_day_rollover_returns_home_to_today(self):
        w = self.window()
        w.home_select_day(self.day(3))
        self.assertEqual(w.home_day, self.day(3))
        w.home_today = self.day(-1)  # as if the date changed overnight
        w.refresh_page()
        self.assertEqual(w.home_day, self.today)

    def test_countdowns_and_upcoming_show_symbols_without_repeating_events(self):
        for n, title in enumerate(("Launch", "Trip", "Review", "Fourth")):
            self.event(title=title, date=self.day(10 + n), major=1, event_type="trip" if n == 1 else "event")
        pinned = self.event(title="Pinned far away", date=self.day(40), major=1, pinned=1)
        self.event(title="Mum's birthday", date=self.day(2), event_type="birthday")
        self.event(title="Ordinary", date=self.today, start_time="09:00", end_time="10:00")
        w = self.window()
        tiles = w.workspace.findChild(CountdownTiles)
        self.assertEqual(len(tiles.items), 3)
        self.assertEqual(tiles.items[0]["id"], pinned["id"])
        self.assertEqual([x["title"] for x in tiles.items[1:]], ["Launch", "Trip"])
        self.assertFalse(tiles.grab().isNull())
        self.assertEqual(len(tiles.regions), 3)
        with patch.object(w, "open_calendar_item") as opened:
            self.click(tiles, tiles.regions[0][0].center())
        self.assertEqual(opened.call_args.args[0]["id"], pinned["id"])
        titles = [b.text() for b in w.workspace.findChildren(QPushButton)]
        for shown in ("Mum's birthday", "Ordinary", "Review", "Fourth"):
            self.assertIn(shown, titles)
        for in_tiles in ("Launch", "Trip", "Pinned far away"):
            self.assertNotIn(in_tiles, titles)
        birthday = next(b for b in w.workspace.findChildren(QPushButton) if b.text() == "Mum's birthday")
        self.assertFalse(birthday.icon().isNull())
        labels = [x.text() for x in w.workspace.findChildren(QLabel)]
        self.assertIn("Today", labels)
        self.assertIn(when_text(self.day(2), self.today), labels)

    def test_layout_follows_the_width_and_tabs_keep_their_page(self):
        self.ticket(title="Something to do", pinned=1)
        w = self.window()
        self.assertEqual(w.home_mode(), "wide")
        self.assertFalse(w.workspace.findChildren(QTabWidget))
        self.assertTrue(w.workspace.findChild(CountdownTiles) or w.workspace.findChild(WeekStrip))
        w.resize(1040, 760)
        self.settle()
        self.assertEqual(w.home_mode(), "medium")
        tabs = w.workspace.findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())], ["Day Agenda", "Coming up"])
        w.resize(980, 640)
        self.settle()
        w.select_ticket(w.data["ticket"][0]["id"])
        self.settle()
        self.assertEqual(w.home_mode(), "narrow")
        self.assertTrue(w._today_narrow)
        tabs = w.workspace.findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())], ["Tasks", "Week", "Coming up"])
        tabs.setCurrentIndex(1)
        # Picking a day rebuilds the page; the Week tab must still be showing afterwards.
        w.home_select_day(self.day(1))
        self.settle()
        tabs = w.workspace.findChild(QTabWidget)
        self.assertEqual(tabs.tabText(tabs.currentIndex()), "Week")
        strip = w.workspace.findChild(WeekStrip)
        self.assertEqual(strip.height(), 108)
        self.assertGreaterEqual(strip.width(), strip.minimumWidth())

    def test_focus_panel_is_filled_in_before_the_first_tick(self):
        t = self.ticket(title="Deep work")
        self.s.command("timer.action", {"action": "start", "ticket_id": t["id"]})
        w = self.window()
        w.timer.stop()
        w.refresh_page()
        self.assertEqual(w.home_focus_title.text(), "Deep work")
        self.assertRegex(w.home_focus_clock.text(), r"^\d\d:\d\d:\d\d$")
        self.s.command("timer.action", {"action": "stop"})
        w.data = self.s.snapshot()
        w.refresh_page()
        self.assertEqual(w.home_focus_title.text(), "Start a timer")
