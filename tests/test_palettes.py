import unittest

from dayframe.palettes import (LEGACY_THEMES, THEMES, THEME_IDS, default_scheme, scheme_colors,
                               schemes, valid_theme_colors)

COLOR_KEYS = {"bg", "panel", "raised", "line", "text", "muted", "accent", "danger", "rail"}


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class PaletteTests(unittest.TestCase):
    def test_every_theme_offers_a_default_scheme_that_matches_its_base(self):
        for theme, entry in THEMES.items():
            with self.subTest(theme=theme):
                first = entry["schemes"][0]
                self.assertEqual(first[2], {})
                self.assertEqual(default_scheme(theme), first[0])
                self.assertEqual(scheme_colors(theme), entry["base"])
                self.assertGreaterEqual(len(schemes(theme)), 4)
                self.assertEqual(len({key for key, _ in schemes(theme)}), len(schemes(theme)))

    def test_schemes_change_colors_only_and_keep_the_theme_typography(self):
        for theme, entry in THEMES.items():
            for key, _, overrides in entry["schemes"]:
                with self.subTest(theme=theme, scheme=key):
                    self.assertLessEqual(set(overrides), COLOR_KEYS)
                    colors = scheme_colors(theme, key)
                    for setting in ("mode", "radius", "font_win", "font_linux", "heading", "weight"):
                        self.assertEqual(colors[setting], entry["base"][setting])

    def test_terminal_has_more_than_amber(self):
        names = [label for _, label in schemes("terminal")]
        self.assertIn("Amber", names)
        self.assertGreaterEqual(len(names), 4)
        self.assertEqual(len({scheme_colors("terminal", key)["accent"] for key, _ in schemes("terminal")}),
                         len(names))

    def test_text_and_accents_stay_readable_in_every_scheme(self):
        for theme in THEMES:
            for key, _ in schemes(theme):
                c = scheme_colors(theme, key)
                with self.subTest(theme=theme, scheme=key):
                    self.assertGreaterEqual(contrast(c["text"], c["bg"]), 4.5)
                    self.assertGreaterEqual(contrast(c["text"], c["panel"]), 4.5)
                    self.assertGreaterEqual(contrast(c["muted"], c["panel"]), 4.0)
                    self.assertGreaterEqual(contrast(c["accent"], c["panel"]), 4.0)
                    self.assertGreaterEqual(contrast(c["bg"], c["accent"]), 4.0)
                    self.assertGreaterEqual(contrast(c["danger"], c["panel"]), 4.0)

    def test_theme_color_validation(self):
        self.assertTrue(valid_theme_colors({}))
        self.assertTrue(valid_theme_colors({"terminal": "green", "light": "clay"}))
        for bad in ({"terminal": "purple"}, {"system": "cyan"}, {"amber": "green"}, ["green"], "green"):
            self.assertFalse(valid_theme_colors(bad), bad)

    def test_ids_cover_legacy_names(self):
        self.assertEqual(THEME_IDS[-1], "system")
        self.assertTrue(set(LEGACY_THEMES.values()) <= set(THEMES))


if __name__ == "__main__":
    unittest.main()
