import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton, QCheckBox, QLineEdit

from dayframe.data.store import Store
from dayframe.ui.window import DayFrame
from dayframe.core.palettes import THEME_ORDER, THEMES, palette, schemes
from dayframe.ui.theme import _fonts, apply_theme, CURRENT

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
        self.assertEqual(
            [nav.item(i).text() for i in range(nav.count())],
            ["View", "Theme", "Local data", "Sync", "Account"],
        )
        for i in range(nav.count() - 1):
            self.assertLess(
                nav.visualItemRect(nav.item(i)).bottom(), nav.visualItemRect(nav.item(i + 1)).top()
            )
        self.settings.fields["timezone"].set_zone("Europe/London")
        self.section("sync")
        self.settings.fields["syncUrl"].setText("https://private-hub:47831")
        self.settings.fields["password"].setText("draft password")
        self.section("view")
        self.assertEqual(self.settings.fields["timezone"].zone(), "Europe/London")
        nav.setFocus()
        QTest.keyClick(nav, Qt.Key_Down)
        self.assertEqual(self.window.settings_section, "theme")
        self.assertEqual(
            sum(self.settings.pages.widget(i).isVisible() for i in range(self.settings.pages.count())), 1
        )
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
        self.settings.fields["density"].setCurrentIndex(
            self.settings.fields["density"].findData("comfortable")
        )
        self.settings.fields["textScale"].setValue(125)
        self.settings.fields["timezone"].set_zone("Europe/London")
        self.settings.fields["syncUrl"].setText("https://private-hub:47831")
        self.settings.fields["password"].setText("unsent")
        self.section("theme")
        self.settings.fields["theme"].setCurrentIndex(self.settings.fields["theme"].findData("light"))
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual(saved["theme"], "light")
        self.assertEqual(
            (saved["density"], saved["textScale"], saved["timezone"]), ("compact", 90, "Asia/Tokyo")
        )
        self.assertEqual(self.window.settings_section, "theme")
        self.assertEqual(self.settings.fields["password"].text(), "unsent")
        self.section("view")
        self.assertEqual(self.settings.fields["timezone"].zone(), "Europe/London")
        self.assertEqual(self.settings.fields["textScale"].value(), 125)
        self.settings.fields["theme"].setCurrentIndex(self.settings.fields["theme"].findData("terminal"))
        self.click("Apply view settings")
        saved = self.store.settings()
        self.assertEqual(
            (saved["density"], saved["textScale"], saved["timezone"]), ("comfortable", 125, "Europe/London")
        )
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
        self.assertEqual(
            [scheme.itemData(i) for i in range(scheme.count())],
            ["cyan", "azure", "mint", "orange", "rose", None, "custom"],
        )
        self.choose(scheme, "mint")
        self.choose(theme, "terminal")
        self.assertEqual(
            [scheme.itemData(i) for i in range(scheme.count())],
            ["amber", "green", "ice", "magenta", "mono", None, "custom"],
        )
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
        self.assertEqual(
            (CURRENT["theme"], CURRENT["scheme"], CURRENT["accent"]), ("terminal", "green", "#5df07a")
        )
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
            self.store.db.execute(
                "UPDATE settings SET data=?", ('{"theme": "amber", "themeColors": {"terminal": "purple"}}',)
            )
        saved = self.store.settings()
        self.assertEqual((saved["theme"], saved["themeColors"]), ("terminal", {}))
        apply_theme({"theme": "amber"})
        self.assertEqual((CURRENT["theme"], CURRENT["scheme"]), ("terminal", "amber"))
        apply_theme({"theme": "terminal", "themeColors": {"terminal": "nonsense"}})
        self.assertEqual(CURRENT["scheme"], "amber")
        for bad in (
            {"theme": "amber"},
            {"themeColors": {"terminal": "purple"}},
            {"themeColors": {"system": "cyan"}},
        ):
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
        self.settings.fields["timezone"].set_zone("Invalid/TimeZone")
        self.settings.fields["textScale"].setValue(110)
        with patch("dayframe.ui.window.main.error") as error:
            self.click("Apply view settings")
        error.assert_called_once()
        self.assertEqual(self.store.settings()["timezone"], "Asia/Tokyo")
        self.assertEqual(self.store.settings()["textScale"], 90)
        self.assertEqual(self.settings.fields["timezone"].zone(), "Invalid/TimeZone")
        self.assertEqual(self.settings.fields["textScale"].value(), 110)

    def test_backup_examples_password_and_logout_actions_still_work(self):
        with (
            patch.object(self.window, "backup") as backup,
            patch.object(self.window, "change_local_password") as password,
            patch.object(self.window, "logout") as logout,
        ):
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
        conflict = {"id": "review", "kind": "ticket", "entity_id": "12345678-1234", "fields": ["title"]}
        self.window.data["conflicts"] = [conflict]
        with (
            patch.object(self.window, "sync_now") as sync_now,
            patch.object(self.window, "review_conflict") as review,
        ):
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
                with (
                    patch.object(self.window, "run_async", side_effect=lambda fn, done: fn()),
                    patch.object(self.window.sync, "connect") as connect,
                    patch.object(self.window.sync, "publish") as publish_account,
                ):
                    self.click(title)
                    expected = publish_account if publish else connect
                    expected.assert_called_once_with(
                        {
                            "url": "https://private-hub:47831",
                            "fingerprint": "fingerprint",
                            "password": "local password",
                            "setupToken": "private token",
                        }
                    )
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
        conflict = {"id": "review", "kind": "ticket", "entity_id": "12345678-1234", "fields": ["title"]}
        with patch.object(self.store, "snapshot", return_value={**snapshot, "conflicts": [conflict]}):
            self.window.sync_finished({}, quiet=True)
        self.assertEqual(self.settings.navigation.currentItem().text(), "Sync (1)")
        self.assertEqual(self.window.settings_section, "sync")
        self.window.sync_finished({}, quiet=True)
        self.assertEqual(self.settings.navigation.currentItem().text(), "Sync")

    def test_pages_fit_themes_sizes_and_larger_text(self):
        for theme in THEME_ORDER:
            for scale in (90, 125):
                self.store.settings({"theme": theme, "textScale": scale, "density": "comfortable"})
                apply_theme(self.store.settings())
                self.window.build_shell()
                self.window.data = self.store.snapshot()
                self.window.data["conflicts"] = [
                    {
                        "id": "long-conflict",
                        "kind": "ticket",
                        "entity_id": "12345678-1234",
                        "fields": [
                            "title",
                            "description",
                            "component",
                            "milestone",
                            "labels",
                            "dependencies",
                            "due_date",
                            "estimate_min",
                        ],
                    }
                ]
                self.window.refresh_page()
                for width, height in ((1280, 800), (980, 640)):
                    self.window.resize(width, height)
                    for section, *_ in self.settings.SECTIONS:
                        with self.subTest(theme=theme, scale=scale, width=width, section=section):
                            page = self.section(section)
                            self.assertEqual(self.window.size().width(), width)
                            self.assertEqual(page.horizontalScrollBar().maximum(), 0)
                            controls = page.findChildren(QPushButton) + page.findChildren(QLineEdit)
                            # Hidden controls (the custom color editor) cannot be reached and are skipped.
                            for control in [c for c in controls if c.isVisibleTo(page)]:
                                point = control.mapTo(page.widget(), control.rect().topLeft())
                                self.assertGreaterEqual(point.x(), 0)
                                self.assertLessEqual(point.x() + control.width(), page.viewport().width())
                            for control in [c for c in page.findChildren(QPushButton) if c.isVisibleTo(page)]:
                                page.ensureWidgetVisible(control)
                                APP.processEvents()
                                point = control.mapTo(page.viewport(), control.rect().center())
                                self.assertTrue(page.viewport().rect().contains(point), control.text())

    def test_old_default_text_size_moves_to_ninety_percent_once(self):
        for saved, expected in ((100, 90), (110, 110)):
            with self.subTest(saved=saved):
                store = Store(Path("build/test-data") / uuid.uuid4().hex)
                try:
                    store.register("upgrade", "tyler")
                    store.settings({"layoutRevision": 3, "textScale": saved})
                    window = DayFrame(store)
                    window.close()
                    self.assertEqual(
                        (store.settings()["textScale"], store.settings()["layoutRevision"]), (expected, 4)
                    )
                    # A size chosen after the upgrade is kept on later starts.
                    store.settings({"textScale": 100})
                    window = DayFrame(store)
                    window.close()
                    self.assertEqual(store.settings()["textScale"], 100)
                finally:
                    APP.processEvents()
                    store.close()

    def test_custom_colors_start_from_the_scheme_and_advanced_roles_apply(self):
        self.section("theme")
        fields = self.settings.fields
        self.choose(fields["theme"], "nord")
        self.choose(fields["themeColor"], "aurora")
        self.choose(fields["themeColor"], "custom")
        self.assertFalse(self.settings.custom_editor.isHidden())
        self.assertEqual(self.settings.pending_custom["nord"]["accent"], "#a3be8c")
        self.settings.set_custom_color("accent", "#ff8800")
        self.settings.advanced_toggle.setChecked(True)
        self.settings.set_custom_color("heading_text", "#123456")
        self.assertEqual(self.settings.role_values["heading_text"].text(), "#123456")
        self.assertEqual(self.settings.role_values["button_text"].text(), "Automatic")
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual(saved["themeColors"], {"nord": "custom"})
        self.assertEqual(saved["customColors"]["nord"]["accent"], "#ff8800")
        self.assertEqual(saved["customColors"]["nord"]["heading_text"], "#123456")
        self.assertEqual(
            (CURRENT["theme"], CURRENT["scheme"], CURRENT["accent"], CURRENT["heading_text"]),
            ("nord", "custom", "#ff8800", "#123456"),
        )
        # Unset advanced roles follow their main color.
        self.assertEqual(CURRENT["button_hover"], "#ff8800")
        self.assertTrue(self.settings.advanced_toggle.isChecked())
        self.settings.reset_custom_color("heading_text")
        self.click("Apply theme")
        self.assertNotIn("heading_text", self.store.settings()["customColors"]["nord"])
        self.assertEqual(CURRENT["heading_text"], CURRENT["text"])

    def test_fonts_corners_and_sizes_are_saved_and_applied(self):
        self.section("theme")
        fields = self.settings.fields
        fields["cornerRadius"].setCurrentIndex(fields["cornerRadius"].findData(14))
        # Use an installed font other than the current one. Qt's offscreen platform on
        # Windows lists no fonts, and then any name is used as given.
        installed = [name for name in QFontDatabase.families() if name != CURRENT["font"]]
        font = installed[0] if installed else "Verdana"
        if fields["fontFamily"].findData(font) < 0:
            fields["fontFamily"].addItem(font, font)
        fields["fontFamily"].setCurrentIndex(fields["fontFamily"].findData(font))
        self.click("Apply theme")
        saved = self.store.settings()
        self.assertEqual((saved["cornerRadius"], saved["fontFamily"]), (14, font))
        self.assertEqual((CURRENT["radius"], CURRENT["font"]), (14, font))
        self.section("view")
        fields = self.settings.fields
        fields["textScale"].setValue(120)
        fields["headingScale"].setValue(150)
        fields["density"].setCurrentIndex(fields["density"].findData("spacious"))
        fields["inspectorWidth"].setValue(360)
        self.click("Apply view settings")
        saved = self.store.settings()
        self.assertEqual(
            (saved["textScale"], saved["headingScale"], saved["density"], saved["inspectorWidth"]),
            (120, 150, "spacious", 360),
        )
        self.assertAlmostEqual(APP.font().pointSizeF(), 8.5 * 1.2, places=1)
        self.assertIn("font-size:%dpx" % round(20 * 1.2 * 1.5), APP.styleSheet())
        self.assertEqual(self.settings.fields["fontFamily"].currentData(), font)

    def test_time_zone_picker_lists_offsets_and_world_clocks_show_in_the_bar(self):
        zone = self.settings.fields["timezone"]
        zone.load()
        labels = [zone.itemText(i) for i in range(zone.count())]
        self.assertGreater(len(labels), 300)
        tokyo = next(text for text in labels if "Asia/Tokyo" in text)
        self.assertTrue(tokyo.startswith("UTC+09:00"))
        self.assertIn("Fixed offset", labels[zone.findData("Etc/GMT-5")])
        zone.set_zone("Etc/GMT-5")
        self.assertIn("UTC+05:00", self.settings.zone_now.text())
        self.settings.fields["worldClock0"].set_zone("Europe/London")
        self.settings.fields["worldClock1"].set_zone("America/New_York")
        self.click("Apply view settings")
        saved = self.store.settings()
        self.assertEqual(saved["timezone"], "Etc/GMT-5")
        self.assertEqual(saved["worldClocks"], ["Europe/London", "America/New_York"])
        self.window.tick()
        self.assertTrue(self.window.world_clock.isVisible())
        self.assertIn("London", self.window.world_clock.text())
        self.assertIn("New York", self.window.world_clock.text())
        self.settings.fields["worldClock0"].set_zone("")
        self.settings.fields["worldClock1"].set_zone("")
        self.click("Apply view settings")
        self.window.tick()
        self.assertEqual(self.store.settings()["worldClocks"], [])
        self.assertFalse(self.window.world_clock.isVisible())


LINUX_FONTS = ("DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif")
WINDOWS_FONTS = ("Segoe UI", "Consolas", "Trebuchet MS", "Georgia", "Bahnschrift", "Verdana", "Cascadia Code")


class ThemeFontFallbackTests(unittest.TestCase):
    """Font choice follows what is installed, so it is pinned here with fixed font sets."""

    def fonts(self, platform, installed, **settings):
        families = {name.casefold(): name for name in installed}
        with (
            patch("dayframe.ui.theme.sys.platform", platform),
            patch("dayframe.ui.theme.installed_families", return_value=families),
        ):
            result = {}
            for theme in ("graphite", "terminal", "light", "studio", "nord", "catppuccin", "editor"):
                colors = palette(theme)
                result[theme] = _fonts(colors, settings)
            return result

    def test_linux_with_only_dejavu_keeps_mono_and_serif_themes_distinct(self):
        fonts = self.fonts("linux", LINUX_FONTS)
        self.assertEqual(fonts["graphite"][:2], ("DejaVu Sans", "DejaVu Sans"))
        self.assertEqual(fonts["terminal"][:2], ("DejaVu Sans Mono", "DejaVu Sans Mono"))
        self.assertEqual(fonts["light"][:2], ("DejaVu Sans", "DejaVu Serif"))
        self.assertEqual(fonts["editor"][1], "DejaVu Sans Mono")
        self.assertTrue(all(mono == "DejaVu Sans Mono" for _, _, mono in fonts.values()))
        self.assertGreaterEqual(len({pair[:2] for pair in fonts.values()}), 3)

    def test_windows_uses_each_themes_own_fonts_and_falls_back_from_missing_ones(self):
        fonts = self.fonts("win32", WINDOWS_FONTS)
        self.assertEqual(fonts["graphite"][0], "Segoe UI")
        self.assertEqual(fonts["terminal"][:2], ("Consolas", "Consolas"))
        self.assertEqual(fonts["light"][:2], ("Trebuchet MS", "Georgia"))
        self.assertEqual(fonts["studio"][0], "Bahnschrift")
        # Segoe UI Variable is missing here, so Nord and Catppuccin fall back to Segoe UI.
        self.assertEqual(fonts["nord"][0], "Segoe UI")
        self.assertEqual(fonts["editor"][1], "Cascadia Code")
        # Graphite, Nord and Catppuccin then share Segoe UI; they differ in shape and color.
        self.assertEqual(len({pair[:2] for pair in fonts.values()}), 5)

    def test_chosen_fonts_win_when_installed_and_fall_back_when_missing(self):
        chosen = self.fonts("win32", WINDOWS_FONTS, fontFamily="Verdana", monoFamily="Cascadia Code")
        self.assertEqual((chosen["graphite"][0], chosen["graphite"][2]), ("Verdana", "Cascadia Code"))
        missing = self.fonts("linux", LINUX_FONTS, fontFamily="Verdana")
        self.assertEqual(missing["graphite"][0], "DejaVu Sans")

    def test_without_any_listed_fonts_the_preferred_name_is_kept(self):
        fonts = self.fonts("win32", ())
        self.assertEqual(fonts["graphite"][0], "Segoe UI")
        self.assertEqual(fonts["nord"][0], "Segoe UI Variable Text")


if __name__ == "__main__":
    unittest.main()
