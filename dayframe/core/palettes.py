"""Theme palettes, color schemes and custom colors, kept free of Qt so settings and tests can use them.

Each theme owns its type, shape and surfaces. A color scheme only overrides colors, so
the first scheme of every theme is empty and reproduces the base palette exactly.

Besides its preset schemes, every theme accepts a "custom" scheme whose colors the user
picks. Custom colors cover the core roles below plus optional advanced roles (button,
heading and input colors and so on). An advanced role that is not set is derived from
the core roles, so preset palettes and partial custom sets always resolve completely.

Several presets adapt published open-source palettes (Nord, Catppuccin, Dracula, Tokyo
Night, One Dark, Monokai, Gruvbox, Solarized, Rosé Pine, Everforest); see
docs/operations/THIRD_PARTY.md. Secondary text, accent and danger values were adjusted
where needed so every scheme keeps readable contrast.
"""

import re

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
    "nord": {
        "label": "Nord",
        "base": {
            "bg": "#2e3440",
            "panel": "#3b4252",
            "raised": "#434c5e",
            "line": "#4c566a",
            "text": "#eceff4",
            "muted": "#c0c8d6",
            "accent": "#88c0d0",
            "danger": "#eba0a6",
            "rail": "#272c36",
            "radius": 6,
            "mode": "arctic",
            "font_win": "Segoe UI Variable Text",
            "font_linux": "Noto Sans",
            "heading": "Segoe UI Variable Display",
            "weight": 600,
        },
        "schemes": (
            ("polar", "Polar Night", {}),
            ("frost", "Frost", {"accent": "#8fbcbb"}),
            ("aurora", "Aurora", {"accent": "#a3be8c", "danger": "#ebcb8b"}),
            ("dusk", "Dusk", {"accent": "#cfaecb"}),
            (
                "snow",
                "Snow Storm",
                {
                    "bg": "#e5e9f0",
                    "panel": "#eceff4",
                    "raised": "#d8dee9",
                    "line": "#c0c8d6",
                    "text": "#2e3440",
                    "muted": "#4c566a",
                    "accent": "#46668e",
                    "danger": "#a3404a",
                    "rail": "#d8dee9",
                },
            ),
        ),
    },
    "catppuccin": {
        "label": "Catppuccin",
        "base": {
            "bg": "#1e1e2e",
            "panel": "#28283b",
            "raised": "#313244",
            "line": "#45475a",
            "text": "#cdd6f4",
            "muted": "#a6adc8",
            "accent": "#cba6f7",
            "danger": "#f38ba8",
            "rail": "#11111b",
            "radius": 10,
            "mode": "pastel",
            "font_win": "Segoe UI Variable Text",
            "font_linux": "Cantarell",
            "heading": "Segoe UI Variable Display",
            "weight": 700,
        },
        "schemes": (
            ("mocha", "Mocha", {}),
            (
                "macchiato",
                "Macchiato",
                {
                    "bg": "#24273a",
                    "panel": "#2c3045",
                    "raised": "#363a4f",
                    "line": "#494d64",
                    "text": "#cad3f5",
                    "muted": "#a5adcb",
                    "accent": "#c6a0f6",
                    "danger": "#ed8796",
                    "rail": "#181926",
                },
            ),
            (
                "frappe",
                "Frappé",
                {
                    "bg": "#303446",
                    "panel": "#373b50",
                    "raised": "#414559",
                    "line": "#51576d",
                    "text": "#c6d0f5",
                    "muted": "#b5bddc",
                    "accent": "#ca9ee6",
                    "danger": "#eb9a9c",
                    "rail": "#232634",
                },
            ),
            (
                "latte",
                "Latte",
                {
                    "bg": "#e6e9ef",
                    "panel": "#eff1f5",
                    "raised": "#ccd0da",
                    "line": "#bcc0cc",
                    "text": "#4c4f69",
                    "muted": "#5c5f77",
                    "accent": "#8839ef",
                    "danger": "#d20f39",
                    "rail": "#dce0e8",
                },
            ),
            ("mocha_blue", "Mocha Blue", {"accent": "#89b4fa"}),
            ("mocha_peach", "Mocha Peach", {"accent": "#fab387"}),
        ),
    },
    "editor": {
        "label": "Editor",
        "base": {
            "bg": "#282a36",
            "panel": "#2f3241",
            "raised": "#44475a",
            "line": "#565a73",
            "text": "#f8f8f2",
            "muted": "#b4bad6",
            "accent": "#bd93f9",
            "danger": "#ff7070",
            "rail": "#21222c",
            "radius": 4,
            "mode": "editor",
            "font_win": "Segoe UI",
            "font_linux": "Ubuntu",
            "heading": "Cascadia Code",
            "weight": 650,
        },
        "schemes": (
            ("dracula", "Dracula", {}),
            (
                "tokyo",
                "Tokyo Night",
                {
                    "bg": "#1a1b26",
                    "panel": "#1f2335",
                    "raised": "#292e42",
                    "line": "#3b4261",
                    "text": "#c0caf5",
                    "muted": "#9aa5ce",
                    "accent": "#7aa2f7",
                    "danger": "#f7768e",
                    "rail": "#16161e",
                },
            ),
            (
                "onedark",
                "One Dark",
                {
                    "bg": "#282c34",
                    "panel": "#2c313a",
                    "raised": "#353b45",
                    "line": "#4b5263",
                    "text": "#d7dae0",
                    "muted": "#a3a9b5",
                    "accent": "#61afef",
                    "danger": "#e88a92",
                    "rail": "#21252b",
                },
            ),
            (
                "monokai",
                "Monokai",
                {
                    "bg": "#272822",
                    "panel": "#2f302a",
                    "raised": "#3e3d32",
                    "line": "#57564a",
                    "text": "#f8f8f2",
                    "muted": "#b8b49e",
                    "accent": "#a6e22e",
                    "danger": "#ff6c9a",
                    "rail": "#1e1f1a",
                },
            ),
            (
                "gruvbox",
                "Gruvbox Dark",
                {
                    "bg": "#282828",
                    "panel": "#32302f",
                    "raised": "#3c3836",
                    "line": "#5a524c",
                    "text": "#ebdbb2",
                    "muted": "#bdae93",
                    "accent": "#fabd2f",
                    "danger": "#fb6b5b",
                    "rail": "#1d2021",
                },
            ),
            (
                "gruvbox_light",
                "Gruvbox Light",
                {
                    "bg": "#f2e5bc",
                    "panel": "#fbf1c7",
                    "raised": "#ebdbb2",
                    "line": "#d5c4a1",
                    "text": "#3c3836",
                    "muted": "#5f5650",
                    "accent": "#9d3b03",
                    "danger": "#9d0006",
                    "rail": "#ebdbb2",
                },
            ),
            (
                "solarized",
                "Solarized Dark",
                {
                    "bg": "#002b36",
                    "panel": "#073642",
                    "raised": "#0d4351",
                    "line": "#2b5864",
                    "text": "#d3dbd9",
                    "muted": "#a0aeae",
                    "accent": "#5aaee8",
                    "danger": "#f0726e",
                    "rail": "#00212b",
                },
            ),
            (
                "solarized_light",
                "Solarized Light",
                {
                    "bg": "#eee8d5",
                    "panel": "#fdf6e3",
                    "raised": "#e4ddc8",
                    "line": "#cfc7b0",
                    "text": "#2d4249",
                    "muted": "#4f6168",
                    "accent": "#1c6698",
                    "danger": "#b42d2a",
                    "rail": "#e4ddc8",
                },
            ),
            (
                "rosepine",
                "Rosé Pine",
                {
                    "bg": "#191724",
                    "panel": "#1f1d2e",
                    "raised": "#26233a",
                    "line": "#403d52",
                    "text": "#e0def4",
                    "muted": "#a9a5c2",
                    "accent": "#c4a7e7",
                    "danger": "#eb6f92",
                    "rail": "#12101b",
                },
            ),
            (
                "everforest",
                "Everforest",
                {
                    "bg": "#2d353b",
                    "panel": "#343f44",
                    "raised": "#3d484d",
                    "line": "#56635f",
                    "text": "#d3c6aa",
                    "muted": "#a7b1a9",
                    "accent": "#a7c080",
                    "danger": "#ee9a9b",
                    "rail": "#232a2e",
                },
            ),
        ),
    },
}
THEME_ORDER = ("graphite", "terminal", "light", "studio", "nord", "catppuccin", "editor")
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


CUSTOM = "custom"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Roles every palette defines; labels appear in Settings > Theme > Custom colors.
CORE_ROLES = (
    ("bg", "Background"),
    ("panel", "Panels and lists"),
    ("raised", "Raised surfaces"),
    ("line", "Borders and dividers"),
    ("text", "Text"),
    ("muted", "Secondary text"),
    ("accent", "Accent"),
    ("danger", "Danger and errors"),
    ("rail", "Navigation rail"),
)
# Optional per-element colors. Each falls back to the core role named here when unset.
ADVANCED_ROLES = (
    ("button", "Button background", "raised"),
    ("button_text", "Button text", "text"),
    ("button_hover", "Button hover outline", "accent"),
    ("accent_text", "Text on accent buttons", "bg"),
    ("heading_text", "Headings and bold labels", "text"),
    ("input", "Input fields", "panel"),
    ("selection", "Selection highlight", "accent"),
    ("warning", "Warnings and overdue", None),
    ("clock", "Timer and clocks", "accent"),
)
ROLE_IDS = tuple(key for key, _ in CORE_ROLES) + tuple(key for key, _, _ in ADVANCED_ROLES)
WARNING_DARK = "#d4b16c"
WARNING_LIGHT = "#8a6414"


def luminance(color):
    """Relative luminance (WCAG) of a #rrggbb color."""
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def is_dark(colors):
    return luminance(colors["bg"]) < 0.3


def is_hex(value):
    return isinstance(value, str) and bool(HEX.match(value))


def with_derived_roles(colors):
    """Fill every advanced role the palette does not set from its core roles."""
    result = dict(colors)
    for key, _, source in ADVANCED_ROLES:
        if not result.get(key):
            result[key] = result[source] if source else (WARNING_DARK if is_dark(result) else WARNING_LIGHT)
    return result


def palette(theme, scheme=None, custom=None):
    """Complete palette, advanced roles included, for a theme and scheme.

    custom is the saved {role: color} mapping for this theme and is used only when the
    scheme is "custom". Unknown roles and malformed colors are ignored.
    """
    if scheme == CUSTOM:
        colors = dict(THEMES[theme]["base"])
        if isinstance(custom, dict):
            colors.update({k: v for k, v in custom.items() if k in ROLE_IDS and is_hex(v)})
    else:
        colors = scheme_colors(theme, scheme)
    return with_derived_roles(colors)


def valid_theme_colors(value):
    """True when value maps theme ids to one of that theme's scheme ids or "custom"."""
    return isinstance(value, dict) and all(
        theme in THEMES and (scheme == CUSTOM or scheme in dict(schemes(theme)))
        for theme, scheme in value.items()
    )


def valid_custom_colors(value):
    """True when value maps theme ids to {role: "#rrggbb"} dictionaries of known roles."""
    return isinstance(value, dict) and all(
        theme in THEMES
        and isinstance(roles, dict)
        and all(role in ROLE_IDS and is_hex(color) for role, color in roles.items())
        for theme, roles in value.items()
    )
