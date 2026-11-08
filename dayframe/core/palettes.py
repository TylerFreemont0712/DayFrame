"""Theme palettes and their color schemes, kept free of Qt so settings and tests can use them.

Each theme owns its type, shape and surfaces. A color scheme only overrides colors, so
the first scheme of every theme is empty and reproduces the base palette exactly.
"""

THEMES = {
    "graphite": {
        "label": "Graphite",
        "base": {
            "bg": "#151c22",
            "panel": "#1b252d",
            "raised": "#25313a",
            "line": "#394750",
            "text": "#e4edf1",
            "muted": "#91a3ae",
            "accent": "#54e1e9",
            "danger": "#ee858a",
            "rail": "#11191f",
            "radius": 3,
            "mode": "technical",
            "font_win": "Segoe UI",
            "font_linux": "Noto Sans",
            "heading": "Segoe UI",
            "weight": 650,
        },
        "schemes": (
            ("cyan", "Cyan", {}),
            ("azure", "Azure", {"accent": "#7ab4ff"}),
            ("mint", "Mint", {"accent": "#6fdc9a"}),
            ("orange", "Orange", {"accent": "#ffa862"}),
            ("rose", "Rose", {"accent": "#ff8fb0", "danger": "#f2a25f"}),
        ),
    },
    "terminal": {
        "label": "Terminal",
        "base": {
            "bg": "#11120e",
            "panel": "#191b13",
            "raised": "#26291b",
            "line": "#586040",
            "text": "#f2e5bc",
            "muted": "#b7af88",
            "accent": "#ffc65e",
            "danger": "#f29275",
            "rail": "#080b06",
            "radius": 0,
            "mode": "terminal",
            "font_win": "Consolas",
            "font_linux": "DejaVu Sans Mono",
            "heading": "Consolas",
            "weight": 700,
        },
        "schemes": (
            ("amber", "Amber", {}),
            (
                "green",
                "Green",
                {
                    "bg": "#0b110c",
                    "panel": "#101a11",
                    "raised": "#18281a",
                    "line": "#35553a",
                    "text": "#cdf5d0",
                    "muted": "#86b48b",
                    "accent": "#5df07a",
                    "rail": "#060a07",
                },
            ),
            (
                "ice",
                "Ice",
                {
                    "bg": "#0a1114",
                    "panel": "#0f1b20",
                    "raised": "#172b32",
                    "line": "#34545d",
                    "text": "#cdeff5",
                    "muted": "#84b0ba",
                    "accent": "#4fd8f0",
                    "rail": "#060b0d",
                },
            ),
            (
                "magenta",
                "Magenta",
                {
                    "bg": "#130d14",
                    "panel": "#1c121e",
                    "raised": "#2b1b2e",
                    "line": "#5b3d60",
                    "text": "#f5d9f6",
                    "muted": "#b891bb",
                    "accent": "#ff7ae0",
                    "rail": "#0a060b",
                },
            ),
            (
                "mono",
                "Mono",
                {
                    "bg": "#101010",
                    "panel": "#181818",
                    "raised": "#262626",
                    "line": "#4a4a4a",
                    "text": "#ececec",
                    "muted": "#9a9a9a",
                    "accent": "#ffffff",
                    "rail": "#080808",
                },
            ),
        ),
    },
    "light": {
        "label": "Paper",
        "base": {
            "bg": "#eee7d9",
            "panel": "#fffcf4",
            "raised": "#e6dcc8",
            "line": "#c9bca2",
            "text": "#392f27",
            "muted": "#7b6b56",
            "accent": "#537260",
            "danger": "#a3473e",
            "rail": "#ddd1ba",
            "radius": 8,
            "mode": "paper",
            "font_win": "Trebuchet MS",
            "font_linux": "Noto Sans",
            "heading": "Georgia",
            "weight": 600,
        },
        "schemes": (
            ("sage", "Sage", {}),
            ("clay", "Clay", {"accent": "#8f4a2e", "danger": "#8f3a52"}),
            ("ocean", "Ocean", {"accent": "#38617f"}),
            ("plum", "Plum", {"accent": "#70436a"}),
        ),
    },
    "studio": {
        "label": "Midnight",
        "base": {
            "bg": "#17142a",
            "panel": "#231d3c",
            "raised": "#33294f",
            "line": "#54446f",
            "text": "#f1eafa",
            "muted": "#b3a4cd",
            "accent": "#c4a1ff",
            "danger": "#f99fc2",
            "rail": "#100e20",
            "radius": 11,
            "mode": "studio",
            "font_win": "Bahnschrift",
            "font_linux": "DejaVu Sans",
            "heading": "Bahnschrift",
            "weight": 600,
        },
        "schemes": (
            ("lavender", "Lavender", {}),
            (
                "ocean",
                "Ocean",
                {
                    "bg": "#0f1a2b",
                    "panel": "#162338",
                    "raised": "#21324d",
                    "line": "#3b5577",
                    "text": "#e6f0fb",
                    "muted": "#9fb6d3",
                    "accent": "#6fc3ff",
                    "danger": "#f99fb0",
                    "rail": "#0a1220",
                },
            ),
            (
                "forest",
                "Forest",
                {
                    "bg": "#101a17",
                    "panel": "#17251f",
                    "raised": "#223630",
                    "line": "#3c5a50",
                    "text": "#e6f5ee",
                    "muted": "#9fc0b2",
                    "accent": "#6fe0b0",
                    "danger": "#f9a39a",
                    "rail": "#0a120f",
                },
            ),
            (
                "wine",
                "Wine",
                {
                    "bg": "#1e1220",
                    "panel": "#2b1a2e",
                    "raised": "#3d2641",
                    "line": "#6a4470",
                    "text": "#f8e6f4",
                    "muted": "#c9a1c4",
                    "accent": "#ff8fc4",
                    "danger": "#ffb0a0",
                    "rail": "#150b17",
                },
            ),
            (
                "ember",
                "Ember",
                {
                    "bg": "#201611",
                    "panel": "#2d2019",
                    "raised": "#413027",
                    "line": "#6e5242",
                    "text": "#f8ece1",
                    "muted": "#c7ab97",
                    "accent": "#ffb061",
                    "danger": "#f99fa0",
                    "rail": "#170f0b",
                },
            ),
        ),
    },
}
THEME_ORDER = ("graphite", "terminal", "light", "studio")
THEME_IDS = THEME_ORDER + ("system",)
# Theme ids saved by earlier versions.
LEGACY_THEMES = {"amber": "terminal"}


def theme_label(theme):
    return "System" if theme == "system" else THEMES[theme]["label"]


def schemes(theme):
    """(id, label) pairs for a theme; empty for System, which follows the OS."""
    return [(key, label) for key, label, _ in THEMES[theme]["schemes"]] if theme in THEMES else []


def default_scheme(theme):
    return THEMES[theme]["schemes"][0][0]


def scheme_colors(theme, scheme=None):
    """Complete palette for a theme and scheme id; unknown ids fall back to the default."""
    entry = THEMES[theme]
    chosen = next((overrides for key, _, overrides in entry["schemes"] if key == scheme), {})
    return {**entry["base"], **chosen}


def valid_theme_colors(value):
    """True when value maps theme ids to one of that theme's scheme ids."""
    return isinstance(value, dict) and all(
        theme in THEMES and scheme in dict(schemes(theme)) for theme, scheme in value.items()
    )
