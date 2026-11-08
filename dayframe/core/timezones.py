"""Time zone choices for the settings pickers and the utility-bar world clocks.

Uses the IANA database from the tzdata package, so results are the same on every OS.
"""

from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, available_timezones

# Legacy aliases and country groups duplicate the Region/City names.
_SKIPPED_PREFIXES = ("Etc/", "SystemV/", "US/", "Canada/", "Mexico/", "Brazil/", "Chile/", "posix", "right/")
FIXED_HOURS = range(-12, 15)


def fixed_zone(hours):
    """IANA name of a whole-hour fixed offset. Etc/GMT signs are inverted: Etc/GMT-9 is UTC+09:00."""
    if hours == 0:
        return "UTC"
    return "Etc/GMT" + ("-" if hours > 0 else "+") + str(abs(hours))


@lru_cache(maxsize=1)
def region_zones():
    """Sorted Region/City zone names, without legacy aliases."""
    try:
        # tzdata ships an index of its zones; reading it is much faster than scanning the package.
        names = files("tzdata").joinpath("zones").read_text(encoding="utf-8").split()
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        names = available_timezones()
    return sorted(
        name
        for name in names
        if "/" in name and not name.startswith(_SKIPPED_PREFIXES) and not name.startswith("Factory")
    )


def offset_minutes(zone, at=None):
    at = at or datetime.now(timezone.utc)
    return int(at.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() // 60)


def format_offset(minutes):
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return "UTC%s%02d:%02d" % (sign, hours, mins)


def place(zone):
    """Short readable place name: Asia/Tokyo -> Tokyo, America/Argentina/Buenos_Aires -> Buenos Aires."""
    if zone == "UTC":
        return "UTC"
    if zone.startswith("Etc/GMT"):
        return format_offset(-int(zone[7:] or 0) * 60)
    return zone.rsplit("/", 1)[-1].replace("_", " ")


def local_time(zone, at=None, fmt="%H:%M"):
    at = at or datetime.now(timezone.utc)
    return at.astimezone(ZoneInfo(zone)).strftime(fmt)


def choices(at=None):
    """Picker entries sorted by current UTC offset, then name.

    Each entry is (zone, label) where the label shows the offset, the zone and its
    current local time, for example "UTC+09:00  Asia/Tokyo  ·  14:05". Whole-hour fixed
    offsets come first within their offset, labelled "Fixed offset".
    """
    at = at or datetime.now(timezone.utc)
    entries = []
    for hours in FIXED_HOURS:
        zone = fixed_zone(hours)
        entries.append((hours * 60, 0, zone, "Fixed offset" if zone != "UTC" else "UTC"))
    for zone in region_zones():
        entries.append((offset_minutes(zone, at), 1, zone, zone))
    entries.sort(key=lambda e: (e[0], e[1], e[3]))
    return [
        (zone, "%s  %s  ·  %s" % (format_offset(offset), name, local_time(zone, at)))
        for offset, _, zone, name in entries
    ]


def describe(zone, at=None):
    """One-line summary such as "Tokyo · Sun 14:05 · UTC+09:00"."""
    at = at or datetime.now(timezone.utc)
    return "%s · %s · %s" % (
        place(zone),
        local_time(zone, at, "%a %H:%M"),
        format_offset(offset_minutes(zone, at)),
    )
