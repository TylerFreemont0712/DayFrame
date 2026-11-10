"""Ticket statistics for the Tickets overview: counts, trends and breakdowns.

Pure functions over a Store snapshot. Weeks are Sunday-first and days follow the
configured time zone, the same as the calendar and the daily tracked total.
"""

from __future__ import annotations
from datetime import date, timedelta
from statistics import median
from . import domain as D
from . import planning as P

OPEN_STAGES = ("inbox", "ready", "doing", "review")


def is_blocked(ticket, by_id):
    return any(by_id.get(dep) and by_id[dep]["status"] != "done" for dep in ticket["dependencies"])


def day_of(ms, zone):
    return D.day_key(zone, ms) if ms else ""


def overlap(entry, start, end):
    return max(0, min(entry["end_at"], end) - max(entry["start_at"], start))


def overview(snapshot, today, zone, now_ms):
    """Every number and series the Tickets overview shows."""
    tickets = [t for t in snapshot["ticket"] if not t["archived"]]
    by_id = {t["id"]: t for t in snapshot["ticket"]}
    projects = {p["id"]: p for p in snapshot["project"]}
    open_tickets = [t for t in tickets if t["status"] != "done"]
    this_week = P.sunday(today)
    last_week = this_week - timedelta(days=7)
    week_start = D.day_bounds(this_week.isoformat(), zone)[0]
    last_week_start = D.day_bounds(last_week.isoformat(), zone)[0]
    entries = snapshot["entry"]

    def completed_between(start, end):
        return [t for t in tickets if t["completed_at"] and start <= t["completed_at"] < end]

    def tracked_between(start, end):
        return sum(overlap(e, start, end) for e in entries)

    soon = (date.fromisoformat(today) + timedelta(days=7)).isoformat()
    recent = [
        t
        for t in tickets
        if t["completed_at"] and t["created_at"] and now_ms - t["completed_at"] < 30 * 86_400_000
    ]
    cycle = median([(t["completed_at"] - t["created_at"]) / 86_400_000 for t in recent]) if recent else None

    # Daily series for the last 14 days, oldest first.
    days = [(date.fromisoformat(today) - timedelta(days=n)).isoformat() for n in range(13, -1, -1)]
    completed_by_day = {d: 0 for d in days}
    for t in tickets:
        key = day_of(t["completed_at"], zone)
        if key in completed_by_day:
            completed_by_day[key] += 1
    tracked_by_day = []
    for d in days:
        start, end = D.day_bounds(d, zone)
        tracked_by_day.append((d, tracked_between(start, min(end, now_ms)) if start <= now_ms else 0))

    # Weekly created and completed for the last 8 weeks.
    weekly = []
    for n in range(7, -1, -1):
        start_day = this_week - timedelta(days=7 * n)
        start, _ = D.day_bounds(start_day.isoformat(), zone)
        end = D.day_bounds((start_day + timedelta(days=7)).isoformat(), zone)[0]
        created = sum(1 for t in tickets if t["created_at"] and start <= t["created_at"] < end)
        weekly.append((start_day.isoformat(), created, len(completed_between(start, end))))

    by_status = [(D.STATUS_NAMES[s], sum(t["status"] == s for t in open_tickets)) for s in OPEN_STAGES]
    counts = {}
    for t in open_tickets:
        counts[t["project_id"]] = counts.get(t["project_id"], 0) + 1
    by_project = sorted(
        ((projects.get(pid, {}).get("name", "Project"), n) for pid, n in counts.items()),
        key=lambda x: (-x[1], x[0]),
    )
    tracked_by_ticket = {}
    for e in entries:
        tracked_by_ticket[e["ticket_id"]] = (
            tracked_by_ticket.get(e["ticket_id"], 0) + e["end_at"] - e["start_at"]
        )
    effort = {}
    for t in tickets:
        name = projects.get(t["project_id"], {}).get("name", "Project")
        estimate, tracked = effort.get(name, (0, 0))
        effort[name] = (estimate + t["estimate_min"] * 60_000, tracked + tracked_by_ticket.get(t["id"], 0))
    effort_rows = sorted(effort.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:6]
    return {
        "open": len(open_tickets),
        "active": sum(t["status"] in ("ready", "doing", "review") for t in open_tickets),
        "completed_week": len(completed_between(week_start, now_ms + 1)),
        "completed_last_week": len(completed_between(last_week_start, week_start)),
        "created_week": sum(1 for t in tickets if t["created_at"] >= week_start),
        "overdue": sum(1 for t in open_tickets if t["due_date"] and t["due_date"] < today),
        "due_soon": sum(1 for t in open_tickets if t["due_date"] and today <= t["due_date"] <= soon),
        "blocked": sum(1 for t in open_tickets if is_blocked(t, by_id)),
        "tracked_week": tracked_between(week_start, now_ms),
        "tracked_last_week": tracked_between(last_week_start, week_start),
        "estimate_open": sum(t["estimate_min"] for t in open_tickets) * 60_000,
        "cycle_days": cycle,
        "completed_days": [(d, completed_by_day[d]) for d in days],
        "tracked_days": tracked_by_day,
        "weekly": weekly,
        "by_status": by_status,
        "by_project": by_project,
        "effort": effort_rows,
        "week_start": this_week.isoformat(),
    }


QUICK_VIEWS = (
    ("open", "All open"),
    ("mine", "Assigned to me"),
    ("week", "Due this week"),
    ("overdue", "Overdue"),
    ("blocked", "Blocked"),
    ("unscheduled", "No due date"),
    ("done_week", "Completed this week"),
    ("all", "Everything"),
)


def quick_filter(view, tickets, by_id, today, week_start_ms):
    """Tickets for a quick view in the Tickets context pane."""
    week_end = (P.sunday(today) + timedelta(days=6)).isoformat()
    tests = {
        "open": lambda t: t["status"] != "done",
        # A personal workspace: every ticket is yours until team assignment exists.
        "mine": lambda t: t["status"] != "done",
        "week": lambda t: t["status"] != "done" and t["due_date"] and t["due_date"] <= week_end,
        "overdue": lambda t: t["status"] != "done" and t["due_date"] and t["due_date"] < today,
        "blocked": lambda t: t["status"] != "done" and is_blocked(t, by_id),
        "unscheduled": lambda t: t["status"] != "done" and not t["due_date"],
        "done_week": lambda t: t["completed_at"] and t["completed_at"] >= week_start_ms,
        "all": lambda t: True,
    }
    test = tests.get(view, tests["open"])
    return [t for t in tickets if not t["archived"] and test(t)]
