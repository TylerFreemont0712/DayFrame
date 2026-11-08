import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QCheckBox, QLineEdit

from dayframe.data.store import Store
from dayframe.ui.window import DayFrame
from dayframe.core.palettes import THEMES, schemes
from dayframe.ui.theme import apply_theme, CURRENT

APP = QApplication.instance() or QApplication([])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path("build/test-data") / uuid.uuid4().hex)
        self.store.register("settings", "tyler")
        self.window = DayFrame(self.store)
        self.window.show()
        self.window.navigate("Settings")
        APP.processEvents()

    def tearDown(self):
        self.window.close()
        APP.processEvents()
        self.store.close()

    @property
    def settings(self):
        return self.window.settings_panel

    def section(self, key):
        nav = self.settings.navigation
        index = next(i for i in range(nav.count()) if nav.item(i).data(Qt.UserRole) == key)
        QTest.mouseClick(nav.viewport(), Qt.LeftButton, pos=nav.visualItemRect(nav.item(index)).center())
        APP.processEvents()
        self.assertEqual(self.window.settings_section, key)
        self.assertEqual(self.settings.pages.currentWidget().objectName(), "settings-" + key)
        return self.settings.pages.currentWidget()

    def click(self, title):
        page = self.settings.pages.currentWidget()
        control = next(b for b in page.findChildren(QPushButton) if b.text() == title)
        page.ensureWidgetVisible(control)
        APP.processEvents()
        QTest.mouseClick(control, Qt.LeftButton)
        APP.processEvents()

    def test_categories_show_one_page_keep_entries_and_support_keyboard(self):
        nav = self.settings.navigation
        self.assertEqual([nav.item(i).text() for i in range(nav.count())],
                         ["View", "Theme", "Local data", "Sync", "Account"])
        for i in range(nav.count() - 1):
            self.assertLess(nav.visualItemRect(nav.item(i)).bottom(),
                            nav.visualItemRect(nav.item(i + 1)).top())
        self.settings.fields["timezone"].setText("Europe/London")
        self.section("sync")
        self.settings.fields["syncUrl"].setText("https://private-hub:47831")
        self.settings.fields["password"].setText("draft password")
        self.section("view")
        self.assertEqual(self.settings.fields["timezone"].text(), "Europe/London")
        nav.setFocus()
        QTest.keyClick(nav, Qt.Key_Down)
        self.assertEqual(self.window.settings_section, "theme")
        self.assertEqual(sum(self.settings.pages.widget(i).isVisible()
                             for i in range(self.settings.pages.count())), 1)
        self.section("sync")
        self.assertEqual(self.settings.fields["syncUrl"].text(), "https://private-hub:47831")
        self.assertEqual(self.settings.fields["password"].text(), "draft password")
        self.assertEqual(self.store.settings()["timezone"], "Asia/Tokyo")
        self.assertNotIn("syncUrl", self.store.settings())
        self.window.navigate("Today")
        self.window.navigate("Settings")
        self.assertEqual(self.window.settings_section, "sync")
        self.assertEqual(self.settings.navigation.currentItem().data(Qt.UserRole), "sync")

    def test_theme_and_view_save_independently_and_keep_other_entries(self):
        self.settings.fields["density"].setCurrentIndex(0)
        self.settings.fields["textScale"].setValue(125)
        self.settings.fields["timezone"].setText("Europe/London")
        self.settings.fields["syncUrl"].setText("https://private-hub:47831")
        self.settings.fields["password"].setText("unsent")
        self.section("theme")
        self.settings.fields["theme"].setCurrentIndex(self.settings.fields["theme"].findData("light"))
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual(saved["theme"], "light")
        self.assertEqual((saved["density"], saved["textScale"], saved["timezone"]),
                         ("compact", 100, "Asia/Tokyo"))
        self.assertEqual(self.window.settings_section, "theme")
        self.assertEqual(self.settings.fields["password"].text(), "unsent")
        self.section("view")
        self.assertEqual(self.settings.fields["timezone"].text(), "Europe/London")
        self.assertEqual(self.settings.fields["textScale"].value(), 125)
        self.settings.fields["theme"].setCurrentIndex(self.settings.fields["theme"].findData("terminal"))
        self.click("Apply view settings")
        saved = self.store.settings()
        self.assertEqual((saved["density"], saved["textScale"], saved["timezone"]),
                         ("comfortable", 125, "Europe/London"))
        self.assertEqual(saved["theme"], "light")
        self.assertNotIn("syncUrl", saved)
        self.assertEqual(self.window.settings_section, "view")
        self.assertEqual(self.settings.fields["theme"].currentData(), "terminal")

    def choose(self, box, key):
        box.setCurrentIndex(box.findData(key))
        APP.processEvents()

    def test_color_schemes_follow_the_chosen_theme_and_are_remembered(self):
        self.section("theme")
        fields = self.settings.fields
        theme, scheme = fields["theme"], fields["themeColor"]
        self.assertEqual([scheme.itemData(i) for i in range(scheme.count())],
                         ["cyan", "azure", "mint", "orange", "rose"])
        self.choose(scheme, "mint")
        self.choose(theme, "terminal")
        self.assertEqual([scheme.itemData(i) for i in range(scheme.count())],
                         ["amber", "green", "ice", "magenta", "mono"])
        self.assertEqual(scheme.currentData(), "amber")
        self.assertEqual(self.settings.color_title.text(), "Terminal colors")
        self.choose(scheme, "green")
        self.choose(theme, "graphite")
        self.assertEqual(scheme.currentData(), "mint")
        self.assertEqual(self.store.settings()["themeColors"], {})
        self.choose(theme, "terminal")
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual(saved["theme"], "terminal")
        self.assertEqual(saved["themeColors"], {"graphite": "mint", "terminal": "green"})
        self.assertEqual((CURRENT["theme"], CURRENT["scheme"], CURRENT["accent"]),
                         ("terminal", "green", "#5df07a"))
        self.assertEqual(self.settings.fields["themeColor"].currentData(), "green")
        self.choose(self.settings.fields["theme"], "graphite")
        self.assertEqual(self.settings.fields["themeColor"].currentData(), "mint")

    def test_system_theme_has_no_color_choices_and_keeps_saved_schemes(self):
        self.section("theme")
        page = self.settings.pages.currentWidget()
        self.choose(self.settings.fields["theme"], "light")
        self.choose(self.settings.fields["themeColor"], "clay")
        self.assertTrue(self.settings.fields["themeColor"].isVisibleTo(page))
        self.choose(self.settings.fields["theme"], "system")
        self.assertFalse(self.settings.fields["themeColor"].isVisibleTo(page))
        self.assertEqual(self.settings.fields["themeColor"].count(), 0)
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual((saved["theme"], saved["themeColors"]), ("system", {"light": "clay"}))
        self.assertIn(CURRENT["theme"], ("light", "graphite"))

    def test_view_apply_keeps_unsaved_theme_and_color_drafts(self):
        self.section("theme")
        self.choose(self.settings.fields["theme"], "studio")
        self.choose(self.settings.fields["themeColor"], "wine")
        self.section("view")
        self.click("Apply view settings")
        self.assertEqual(self.store.settings()["theme"], "graphite")
        self.assertEqual(self.store.settings()["themeColors"], {})
        self.assertEqual(self.settings.fields["theme"].currentData(), "studio")
        self.assertEqual(self.settings.fields["themeColor"].currentData(), "wine")

    def test_saved_amber_theme_opens_as_terminal_and_bad_colors_are_ignored(self):
        with self.store.lock:
            self.store.db.execute("UPDATE settings SET data=?",
                                  ('{"theme": "amber", "themeColors": {"terminal": "purple"}}',))
        saved = self.store.settings()
        self.assertEqual((saved["theme"], saved["themeColors"]), ("terminal", {}))
        apply_theme({"theme": "amber"})
        self.assertEqual((CURRENT["theme"], CURRENT["scheme"]), ("terminal", "amber"))
        apply_theme({"theme": "terminal", "themeColors": {"terminal": "nonsense"}})
        self.assertEqual(CURRENT["scheme"], "amber")
        for bad in ({"theme": "amber"}, {"themeColors": {"terminal": "purple"}},
                    {"themeColors": {"system": "cyan"}}):
            with self.assertRaises(ValueError):
                self.store.settings(bad)

    def test_every_scheme_applies_with_matching_chevrons(self):
        for theme in THEMES:
            for key, _ in schemes(theme):
                with self.subTest(theme=theme, scheme=key):
                    apply_theme({"theme": theme, "themeColors": {theme: key}})
                    self.assertEqual((CURRENT["theme"], CURRENT["scheme"]), (theme, key))
                    for arrow in ("down", "up"):
                        text = Path(CURRENT[arrow]).read_text(encoding="utf-8")
                        self.assertIn(CURRENT["muted"], text)

    def test_invalid_view_settings_keep_values_and_leave_saved_preferences_intact(self):
        self.settings.fields["timezone"].setText("Invalid/TimeZone")
        self.settings.fields["textScale"].setValue(110)
        with patch("dayframe.ui.window.main.error") as error:
            self.click("Apply view settings")
        error.assert_called_once()
        self.assertEqual(self.store.settings()["timezone"], "Asia/Tokyo")
        self.assertEqual(self.store.settings()["textScale"], 100)
        self.assertEqual(self.settings.fields["timezone"].text(), "Invalid/TimeZone")
        self.assertEqual(self.settings.fields["textScale"].value(), 110)

    def test_backup_examples_password_and_logout_actions_still_work(self):
        with patch.object(self.window, "backup") as backup, \
             patch.object(self.window, "change_local_password") as password, \
             patch.object(self.window, "logout") as logout:
            self.window.refresh_page()
            self.section("data")
            self.click("Back up database")
            backup.assert_called_once()
            self.click("Load example workspace")
            self.assertTrue(self.store.list("project"))
            self.assertEqual(self.window.settings_section, "data")
            self.section("account")
            self.click("Change local password")
            password.assert_called_once()
            self.click("Log out")
            logout.assert_called_once()

    def test_sync_connection_publish_auto_sync_and_conflict_actions(self):
        conflict = {"id": "review", "kind": "ticket", "entity_id": "12345678-1234",
                    "fields": ["title"]}
        self.window.data["conflicts"] = [conflict]
        with patch.object(self.window, "sync_now") as sync_now, \
             patch.object(self.window, "review_conflict") as review:
            self.window.refresh_page()
            page = self.section("sync")
            self.assertEqual(self.settings.navigation.currentItem().text(), "Sync (1)")
            enabled = page.findChild(QCheckBox)
            enabled.setChecked(True)
            self.assertTrue(self.store.settings()["syncEnabled"])
            self.window.sync_timer.stop()
            for publish, title in ((False, "Connect"), (True, "Publish account to hub")):
                self.settings.fields["syncUrl"].setText(" https://private-hub:47831 ")
                self.settings.fields["syncFingerprint"].setText(" fingerprint ")
                self.settings.fields["password"].setText("local password")
                self.settings.fields["setupToken"].setText("private token")
                self.assertEqual(self.settings.fields["password"].echoMode(), QLineEdit.Password)
                self.assertEqual(self.settings.fields["setupToken"].echoMode(), QLineEdit.Password)
                with patch.object(self.window, "run_async", side_effect=lambda fn, done: fn()), \
                     patch.object(self.window.sync, "connect") as connect, \
                     patch.object(self.window.sync, "publish") as publish_account:
                    self.click(title)
                    expected = publish_account if publish else connect
                    expected.assert_called_once_with({"url": "https://private-hub:47831",
                        "fingerprint": "fingerprint", "password": "local password", "setupToken": "private token"})
                    (connect if publish else publish_account).assert_not_called()
                self.assertEqual(self.settings.fields["password"].text(), "")
                self.assertEqual(self.settings.fields["setupToken"].text(), "")
            self.click("Sync now")
            sync_now.assert_called_once()
            self.click("Review conflict")
            review.assert_called_once_with(conflict)

    def test_conflict_count_refreshes_when_sync_only_changes_conflicts(self):
        self.section("sync")
        snapshot = self.store.snapshot()
        conflict = {"id": "review", "kind": "ticket", "entity_id": "12345678-1234",
                    "fields": ["title"]}
        with patch.object(self.store, "snapshot", return_value={**snapshot, "conflicts": [conflict]}):
            self.window.sync_finished({}, quiet=True)
        self.assertEqual(self.settings.navigation.currentItem().text(), "Sync (1)")
        self.assertEqual(self.window.settings_section, "sync")
        self.window.sync_finished({}, quiet=True)
        self.assertEqual(self.settings.navigation.currentItem().text(), "Sync")

    def test_pages_fit_themes_sizes_and_larger_text(self):
        for theme in ("graphite", "terminal", "light", "studio"):
            for scale in (100, 125):
                self.store.settings({"theme": theme, "textScale": scale, "density": "comfortable"})
                apply_theme(self.store.settings())
                self.window.build_shell()
                self.window.data = self.store.snapshot()
                self.window.data["conflicts"] = [{"id": "long-conflict", "kind": "ticket",
                    "entity_id": "12345678-1234", "fields": ["title", "description", "component",
                    "milestone", "labels", "dependencies", "due_date", "estimate_min"]}]
                self.window.refresh_page()
                for width, height in ((1280, 800), (980, 640)):
                    self.window.resize(width, height)
                    for section, *_ in self.settings.SECTIONS:
                        with self.subTest(theme=theme, scale=scale, width=width, section=section):
                            page = self.section(section)
                            self.assertEqual(self.window.size().width(), width)
                            self.assertEqual(page.horizontalScrollBar().maximum(), 0)
                            for control in page.findChildren(QPushButton) + page.findChildren(QLineEdit):
                                point = control.mapTo(page.widget(), control.rect().topLeft())
                                self.assertGreaterEqual(point.x(), 0)
                                self.assertLessEqual(point.x() + control.width(), page.viewport().width())
                            for control in page.findChildren(QPushButton):
                                page.ensureWidgetVisible(control)
                                APP.processEvents()
                                point = control.mapTo(page.viewport(), control.rect().center())
                                self.assertTrue(page.viewport().rect().contains(point), control.text())


if __name__ == "__main__":
    unittest.main()
