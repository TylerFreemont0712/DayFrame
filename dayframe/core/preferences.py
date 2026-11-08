"""Device preferences: defaults and validation for the per-account settings record.

Preferences are local to a device (they are not synchronized). Store.settings() merges
these defaults with the saved record and validates every patch here before writing.
"""

from zoneinfo import ZoneInfo

from .palettes import (
    LEGACY_THEMES,
    THEME_IDS,
    valid_custom_colors,
    valid_theme_colors,
)

DENSITIES = (("compact", "Compact"), ("comfortable", "Comfortable"), ("spacious", "Spacious"))
# Corner radius in pixels; -1 keeps each theme's own shape.
CORNER_STYLES = (
    (-1, "Theme default"),
    (0, "Square"),
    (3, "Slight"),
    (6, "Rounded"),
    (10, "Soft"),
    (14, "Round"),
)
# 90% is the base text size; the scale multiplies an 8.5 pt design size.
TEXT_SCALE = (75, 140)
HEADING_SCALE = (80, 160)
MAX_WORLD_CLOCKS = 3
MAX_FONT_NAME = 80

DEFAULTS = {
    "theme": "graphite",
    "density": "compact",
    "textScale": 90,
    "headingScale": 100,
    "cornerRadius": -1,
    "fontFamily": "",
    "headingFamily": "",
    "monoFamily": "",
    "timezone": "Asia/Tokyo",
    "worldClocks": [],
    "sidebarWidth": 164,
    "inspectorWidth": 280,
    "layoutRevision": 0,
    "themeColors": {},
    "customColors": {},
}
# Saved alongside the defaults but without a default value.
OPTIONAL = {"syncUrl", "syncEnabled", "syncFingerprint", "windowGeometry", "windowState"}
LAYOUT_REVISION = 4
NUMBER_RANGES = {
    "textScale": TEXT_SCALE,
    "headingScale": HEADING_SCALE,
    "sidebarWidth": (140, 280),
    "inspectorWidth": (240, 420),
}


def sanitize(saved):
    """Repair a saved record from an older version or a damaged file; returns a new dict."""
    current = dict(saved)
    if current.get("theme") in LEGACY_THEMES:
        current["theme"] = LEGACY_THEMES[current["theme"]]
    for key, valid in (("themeColors", valid_theme_colors), ("customColors", valid_custom_colors)):
        if key in current and not valid(current[key]):
            current.pop(key)
    return current


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _font_name(value):
    return isinstance(value, str) and len(value) <= MAX_FONT_NAME and value.isprintable()


def valid_zone(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        ZoneInfo(value)
    except (ValueError, KeyError, OSError):
        return False
    return True


def validate(patch):
    """Raise ValueError when a settings patch has an unknown key or an invalid value."""
    if set(patch) - set(DEFAULTS) - OPTIONAL:
        raise ValueError("Unknown preference.")
    if "theme" in patch and patch["theme"] not in THEME_IDS:
        raise ValueError("Invalid theme.")
    if "themeColors" in patch and not valid_theme_colors(patch["themeColors"]):
        raise ValueError("Invalid theme colors.")
    if "customColors" in patch and not valid_custom_colors(patch["customColors"]):
        raise ValueError("Invalid custom colors.")
    if "density" in patch and patch["density"] not in dict(DENSITIES):
        raise ValueError("Invalid density.")
    if "cornerRadius" in patch and patch["cornerRadius"] not in dict(CORNER_STYLES):
        raise ValueError("Invalid corner style.")
    for key, (low, high) in NUMBER_RANGES.items():
        if key in patch and (not _number(patch[key]) or not low <= patch[key] <= high):
            raise ValueError("Invalid " + key + ".")
    for key in ("fontFamily", "headingFamily", "monoFamily"):
        if key in patch and not _font_name(patch[key]):
            raise ValueError("Invalid font name.")
    if "layoutRevision" in patch and (
        type(patch["layoutRevision"]) is not int or not 0 <= patch["layoutRevision"] <= LAYOUT_REVISION
    ):
        raise ValueError("Invalid layout revision.")
    if "timezone" in patch and not valid_zone(patch["timezone"]):
        raise ValueError("Unknown time zone: " + str(patch["timezone"]))
    if "worldClocks" in patch:
        clocks = patch["worldClocks"]
        if (
            not isinstance(clocks, list)
            or len(clocks) > MAX_WORLD_CLOCKS
            or not all(valid_zone(zone) for zone in clocks)
        ):
            raise ValueError("Invalid world clocks.")
    if "syncEnabled" in patch and not isinstance(patch["syncEnabled"], bool):
        raise ValueError("Invalid sync switch.")
