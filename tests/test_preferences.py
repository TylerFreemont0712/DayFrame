"""Preference validation, custom palettes and time zone choices (no Qt needed)."""

import unittest
from datetime import datetime, timezone

from dayframe.core import preferences as PREFS
from dayframe.core import timezones as TZ
from dayframe.core.palettes import (
    ADVANCED_ROLES,
    CORE_ROLES,
    CUSTOM,
    THEME_ORDER,
    THEMES,
    is_dark,
    palette,
    scheme_colors,
    schemes,
    valid_custom_colors,
    valid_theme_colors,
)


class PaletteCustomizationTests(unittest.TestCase):
    def test_new_themes_exist_with_light_and_dark_schemes(self):
        for theme in ("nord", "catppuccin", "editor"):
            self.assertIn(theme, THEME_ORDER)
            darkness = {is_dark(scheme_colors(theme, key)) for key, _ in schemes(theme)}
            self.assertEqual(darkness, {True, False}, theme)
        names = {name for _, name in schemes("editor")}
        self.assertTrue({"Dracula", "Tokyo Night", "Gruvbox Dark", "Solarized Light"} <= names)

    def test_every_palette_has_every_role(self):
        roles = {key for key, _ in CORE_ROLES} | {key for key, _, _ in ADVANCED_ROLES}
        for theme in THEMES:
            for key, _ in schemes(theme):
                self.assertLessEqual(roles, set(palette(theme, key)), (theme, key))
            self.assertLessEqual(roles, set(palette(theme, CUSTOM)), theme)

    def test_custom_colors_override_and_advanced_roles_derive(self):
        colors = palette("graphite", CUSTOM, {"accent": "#112233", "button_text": "#abcdef"})
        self.assertEqual(colors["accent"], "#112233")
        self.assertEqual(colors["button_hover"], "#112233")
        self.assertEqual(colors["selection"], "#112233")
        self.assertEqual(colors["button_text"], "#abcdef")
        self.assertEqual(colors["heading_text"], colors["text"])
        # Malformed values and unknown roles fall back to the theme.
        broken = palette("graphite", CUSTOM, {"accent": "red", "sparkle": "#ffffff"})
        self.assertEqual(broken["accent"], THEMES["graphite"]["base"]["accent"])
        self.assertNotIn("sparkle", broken)
        # Custom colors only apply to the custom scheme.
        self.assertEqual(palette("graphite", "mint", {"accent": "#112233"})["accent"], "#6fdc9a")

    def test_custom_validation(self):
        self.assertTrue(valid_theme_colors({"nord": CUSTOM, "editor": "tokyo"}))
        self.assertTrue(valid_custom_colors({"nord": {"accent": "#A3BE8C", "clock": "#000000"}}))
        for bad in (
            {"nord": {"accent": "#fff"}},
            {"nord": {"accent": "blue"}},
            {"nord": {"glow": "#ffffff"}},
            {"system": {"accent": "#ffffff"}},
            {"nord": ["#ffffff"]},
            [],
        ):
            self.assertFalse(valid_custom_colors(bad), bad)


class PreferenceValidationTests(unittest.TestCase):
    def test_defaults_use_ninety_percent_text(self):
        self.assertEqual(PREFS.DEFAULTS["textScale"], 90)
        self.assertEqual(PREFS.DEFAULTS["cornerRadius"], -1)
        self.assertEqual(PREFS.DEFAULTS["worldClocks"], [])

    def test_valid_patches_pass(self):
        PREFS.validate(
            {
                "textScale": 75,
                "headingScale": 160,
                "density": "spacious",
                "cornerRadius": 0,
                "fontFamily": "Inter",
                "headingFamily": "",
                "monoFamily": "JetBrains Mono",
                "timezone": "Etc/GMT-9",
                "worldClocks": ["Europe/London", "America/New_York", "UTC"],
                "themeColors": {"catppuccin": "latte"},
                "customColors": {"editor": {"bg": "#000000"}},
                "layoutRevision": 4,
            }
        )

    def test_invalid_patches_are_rejected(self):
        for bad in (
            {"textScale": 74},
            {"textScale": 141},
            {"textScale": True},
            {"headingScale": 200},
            {"density": "roomy"},
            {"cornerRadius": 5},
            {"fontFamily": "x" * 81},
            {"fontFamily": "Bad\nName"},
            {"timezone": "Invalid/TimeZone"},
            {"worldClocks": ["UTC", "UTC", "UTC", "UTC"]},
            {"worldClocks": "UTC"},
            {"worldClocks": ["Mars/Base"]},
            {"customColors": {"nord": {"accent": "nope"}}},
            {"layoutRevision": 6},
            {"unknown": 1},
        ):
            with self.assertRaises(ValueError, msg=bad):
                PREFS.validate(bad)

    def test_sanitize_drops_damaged_color_records(self):
        cleaned = PREFS.sanitize(
            {"theme": "amber", "themeColors": {"terminal": "purple"}, "customColors": {"x": 1}}
        )
        self.assertEqual(cleaned, {"theme": "terminal"})


class TimeZoneTests(unittest.TestCase):
    def test_offsets_labels_and_places(self):
        at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(TZ.format_offset(TZ.offset_minutes("Asia/Tokyo", at)), "UTC+09:00")
        self.assertEqual(TZ.format_offset(TZ.offset_minutes("Asia/Kolkata", at)), "UTC+05:30")
        self.assertEqual(TZ.format_offset(TZ.offset_minutes("America/New_York", at)), "UTC-05:00")
        self.assertEqual(TZ.fixed_zone(9), "Etc/GMT-9")
        self.assertEqual(TZ.fixed_zone(-3), "Etc/GMT+3")
        self.assertEqual(TZ.place("Etc/GMT-9"), "UTC+09:00")
        self.assertEqual(TZ.place("America/Argentina/Buenos_Aires"), "Buenos Aires")
        self.assertEqual(TZ.local_time("Asia/Tokyo", at), "21:00")
        self.assertEqual(TZ.describe("Europe/London", at), "London · Thu 12:00 · UTC+00:00")

    def test_choices_are_sorted_by_offset_and_include_fixed_offsets(self):
        at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        entries = TZ.choices(at)
        zones = [zone for zone, _ in entries]
        self.assertIn("Asia/Tokyo", zones)
        self.assertIn("Etc/GMT-14", zones)
        self.assertNotIn("US/Eastern", zones)
        offsets = [TZ.offset_minutes(zone, at) for zone in zones]
        self.assertEqual(offsets, sorted(offsets))
        label = dict(entries)["Asia/Tokyo"]
        self.assertEqual(label, "UTC+09:00  Asia/Tokyo  ·  21:00")


if __name__ == "__main__":
    unittest.main()
