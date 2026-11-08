"""Shared calendar projections used by Home, month, upcoming and week views."""

from __future__ import annotations
from calendar import monthrange
from datetime import date, timedelta
from . import domain as D

EVENT_TYPES = (
    ("appointment", "Appointment", "#72b6cf"),
    ("meeting", "Meeting", "#6d9fea"),
    ("birthday", "Birthday", "#ca93df"),
    ("trip", "Trip", "#68bba5"),
    ("personal", "Personal plan", "#c7a46b"),
    ("routine", "Routine", "#95b67d"),
    ("holiday", "Holiday", "#db8d89"),
    ("work", "Work session", "#52c5d3"),
    ("event", "Other event", "#a4aebc"),
)
TYPE_NAMES = {key: name for key, name, color in EVENT_TYPES}
TYPE_COLORS = {key: color for key, name, color in EVENT_TYPES}


def sunday(day):
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return d - timedelta(days=(d.weekday() + 1) % 7)


def minutes(text):
    hour, minute = map(int, text[:5].split(":"))
    return hour * 60 + minute


def clock(value):
    value = max(0, min(1439, int(value)))
    return f"{value // 60:02}:{value % 60:02}"


def event_color(item):
    return item.get("color") or TYPE_COLORS.get(item.get("event_type"), "#8da7b7")


def _year_date(day, year):
    # February 29 birthdays are observed on February 28 in a non-leap year.
    return day.replace(year=year, day=min(day.day, monthrange(year, day.month)[1]))


def event_occurrences(event, start, end):
    original = date.fromisoformat(event["date"])
    finish = date.fromisoformat(event.get("end_date") or event["date"])
    span = finish - original
    years = range(start.year - 1, end.year + 1) if event.get("recurrence") == "yearly" else (original.year,)
    for year in years:
        occurrence = _year_date(original, year) if event.get("recurrence") == "yearly" else original
        last = occurrence + span
        if last >= start and occurrence <= end:
            yield occurrence, last


def items_between(snapshot, start, end, include_deadlines=True):
    start = date.fromisoformat(start) if isinstance(start, str) else start
    end = date.fromisoformat(end) if isinstance(end, str) else end
    result = []
    for e in snapshot.get("event", []):
        if e.get("archived") or not e.get("date"):
            continue
        for first, last in event_occurrences(e, start, end):
            result.append(
                {
                    "key": "event:" + e["id"] + ":" + first.isoformat(),
                    "kind": "event",
                    "id": e["id"],
                    "record": e,
                    "title": e["title"],
                    "date": first.isoformat(),
                    "end_date": last.isoformat(),
                    "start_time": e["start_time"],
                    "end_time": e["end_time"],
                    "all_day": not bool(e["start_time"]),
                    "event_type": e["event_type"],
                    "color": e.get("color") or TYPE_COLORS.get(e["event_type"], "#8da7b7"),
                    "description": e.get("description", ""),
                    "location": e.get("location", ""),
                    "ticket_id": "",
                }
            )
    tickets = {t["id"]: t for t in snapshot.get("ticket", []) if not t["archived"]}
    for b in snapshot.get("block", []):
        ticket = tickets.get(b["ticket_id"])
        if ticket and start.isoformat() <= b["date"] <= end.isoformat():
            result.append(
                {
                    "key": "block:" + b["id"],
                    "kind": "block",
                    "id": b["id"],
                    "record": b,
                    "title": ticket["title"],
                    "date": b["date"],
                    "end_date": b["date"],
                    "start_time": b["start_time"],
                    "end_time": b["end_time"],
                    "all_day": False,
                    "event_type": "work",
                    "color": TYPE_COLORS["work"],
                    "description": ticket["description"],
                    "location": "",
                    "ticket_id": ticket["id"],
                }
            )
    if include_deadlines:
        for t in tickets.values():
            if (
                t["status"] != "done"
                and t["due_date"]
                and start.isoformat() <= t["due_date"] <= end.isoformat()
            ):
                result.append(
                    {
                        "key": "deadline:" + t["id"],
                        "kind": "deadline",
                        "id": t["id"],
                        "record": t,
                        "title": "Due · " + t["title"],
                        "date": t["due_date"],
                        "end_date": t["due_date"],
                        "start_time": "",
                        "end_time": "",
                        "all_day": True,
                        "event_type": "deadline",
                        "color": "#dfae65" if t["priority"] != "urgent" else "#ec8688",
                        "description": t["description"],
                        "location": "",
                        "ticket_id": t["id"],
                    }
                )
    return sorted(
        result, key=lambda item: (item["date"], not item["all_day"], item["start_time"], item["title"])
    )


def segments_for_day(items, day):
    result = []
    for item in items:
        if item["date"] <= day <= item["end_date"]:
            segment = {**item, "day": day}
            segment["start_min"] = (
                0 if item["all_day"] or item["date"] != day else minutes(item["start_time"])
            )
            segment["end_min"] = (
                1440 if item["all_day"] or item["end_date"] != day else minutes(item["end_time"])
            )
            if segment["end_min"] > segment["start_min"]:
                result.append(segment)
    return sorted(result, key=lambda x: (not x["all_day"], x["start_min"], x["end_min"], x["key"]))


def day_items(snapshot, day, include_deadlines=True):
    return segments_for_day(items_between(snapshot, day, day, include_deadlines), day)


def upcoming(snapshot, day, limit=12, include_deadlines=True):
    end = date.fromisoformat(day) + timedelta(days=366)
    return items_between(snapshot, day, end, include_deadlines)[:limit]


def overlap_lanes(items):
    """Give every connected overlap cluster enough columns; touching ends don't overlap."""
    ordered = sorted((dict(x) for x in items), key=lambda x: (x["start_min"], x["end_min"], x["key"]))
    result = []
    cluster = []
    until = -1

    def flush():
        ends = []
        assigned = []
        for item in cluster:
            free = next((n for n, last in enumerate(ends) if last <= item["start_min"]), len(ends))
            if free == len(ends):
                ends.append(item["end_min"])
            else:
                ends[free] = item["end_min"]
            assigned.append({**item, "lane": free})
        result.extend({**item, "lanes": len(ends)} for item in assigned)

    for item in ordered:
        if cluster and item["start_min"] >= until:
            flush()
            cluster = []
            until = -1
        cluster.append(item)
        until = max(until, item["end_min"])
    if cluster:
        flush()
    return result


def home_groups(snapshot, day):
    tickets = [t for t in snapshot.get("ticket", []) if not t["archived"] and t["status"] != "done"]
    timer = next((x for x in snapshot.get("timer", []) if x["id"] == "active"), None)
    active = timer.get("ticket_id") if timer and (timer["start_at"] or timer["paused"]) else None
    groups = []
    seen = set()

    def group(name, records, limit=None):
        records = [t for t in records if t["id"] not in seen]
        if limit:
            records = records[:limit]
        seen.update(t["id"] for t in records)
        groups.append((name, records))

    group("Top priorities", [t for t in tickets if t["pinned"]], 3)
    group("Due today", [t for t in tickets if t["due_date"] == day])
    group(
        "Overdue",
        sorted([t for t in tickets if t["due_date"] and t["due_date"] < day], key=lambda t: t["due_date"]),
    )
    group(
        D.STATUS_NAMES["ready"],
        sorted(
            [t for t in tickets if t["status"] == "ready" or t["id"] == active],
            key=lambda t: t["id"] != active,
        ),
    )
    group("Recent tickets", list(reversed(tickets)), 5)
    return groups
