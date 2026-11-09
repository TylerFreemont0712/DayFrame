"""A large, realistic demo workspace for looking around DayFrame.

Eight projects with about 120 tickets spread over the last ten weeks: every status and
priority, labels, components, milestones, checklists, dependencies and parent/child
links, map sections, three weeks of tracked time, scheduled work blocks, events and
countdowns, comment threads and a few screenshot attachments. Generation is seeded,
so the same dates relative to today produce the same workspace.
"""

from __future__ import annotations
import base64
import random
import struct
import time
import zlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from ..core import domain as D

DAY_MS = 86_400_000

PROJECTS = [
    (
        "Website",
        "WEB",
        "Public site and customer dashboard.",
        ["Frontend", "Backend", "Content"],
        [
            "Redesign pricing page",
            "Fix broken links in footer",
            "Add dark mode toggle",
            "Speed up dashboard first load",
            "Cookie banner keeps reappearing",
            "Write onboarding guide",
            "Search results ignore accents",
            "Add CSV export to reports",
            "Image lazy loading",
            "Update privacy policy page",
            "Team page photos are blurry",
            "Sitemap generation",
            "Login form loses focus on error",
            "Migrate blog to new CMS",
            "Accessibility audit fixes",
            "Newsletter signup confirmation",
            "Customer logos carousel",
        ],
    ),
    (
        "Mobile app",
        "APP",
        "iOS and Android companion app.",
        ["iOS", "Android", "Shared"],
        [
            "Push notification opt-in screen",
            "Crash when rotating on the settings screen",
            "Offline mode for task list",
            "Biometric unlock",
            "Widget for today's agenda",
            "App store screenshots",
            "Reduce app size below 40 MB",
            "Sync conflict banner",
            "Haptic feedback on completion",
            "Tablet layout",
            "Deep links from email",
            "Battery drain in background sync",
            "Localized date formats",
            "Onboarding carousel",
        ],
    ),
    (
        "API platform",
        "API",
        "Public REST API, auth and billing.",
        ["Auth", "Billing", "Search"],
        [
            "Rate limit headers",
            "Token refresh race condition",
            "Invoice PDF rendering",
            "Webhook retries with backoff",
            "Pagination cursor for search",
            "OAuth device flow",
            "Usage-based billing meter",
            "Search index rebuild job",
            "Deprecate v1 endpoints",
            "API key rotation",
            "OpenAPI spec cleanup",
            "Slow query on /projects",
            "Audit log export",
            "Idempotency keys for payments",
        ],
    ),
    (
        "Design system",
        "DS",
        "Shared tokens, components and documentation.",
        ["Tokens", "Components", "Docs"],
        [
            "Color tokens for high contrast",
            "Date picker component",
            "Button focus ring",
            "Spacing scale v2",
            "Icon set refresh",
            "Table component sorting",
            "Document form patterns",
            "Toast component",
            "Motion guidelines",
            "Dark theme surfaces",
            "Typography ramp",
            "Storybook deployment",
        ],
    ),
    (
        "Infrastructure",
        "OPS",
        "CI, hosting and monitoring.",
        ["CI", "Monitoring", "Hosting"],
        [
            "Cache dependencies in CI",
            "Alert on error rate spikes",
            "Upgrade database to the next major version",
            "Nightly backups restore test",
            "Move staging to new region",
            "Flaky integration test on Windows",
            "Log retention policy",
            "TLS certificate auto-renewal",
            "Dashboard for queue latency",
            "Reduce build time below 8 minutes",
            "Secrets rotation runbook",
        ],
    ),
    (
        "Marketing",
        "MKT",
        "Campaigns, launch and content calendar.",
        ["Campaigns", "Social", "Events"],
        [
            "Launch announcement post",
            "Product hunt listing",
            "Webinar landing page",
            "Case study with a customer",
            "Social media calendar for next month",
            "Conference booth materials",
            "Email drip for trial users",
            "Update brand guidelines",
            "Video walkthrough script",
        ],
    ),
    (
        "Home",
        "HOME",
        "Personal errands and chores.",
        ["Errands", "House"],
        [
            "Renew car insurance",
            "Fix leaking kitchen tap",
            "Plan weekend trip",
            "Sort out tax documents",
            "Buy birthday present",
            "Clean out the garage",
            "Book dentist appointment",
        ],
    ),
    (
        "Learning",
        "LEARN",
        "Courses, books and practice.",
        ["Reading", "Courses"],
        [
            "Finish chapter 6 of the systems book",
            "Rust ownership exercises",
            "Watch talk on CRDTs",
            "Japanese vocabulary review",
            "Write notes on SQLite internals",
            "Practice drawing perspective",
        ],
    ),
]

LABELS = ["bug", "feature", "ui", "api", "docs", "perf", "tech-debt", "security", "ux", "research"]
STATUS_WEIGHTS = [("done", 40), ("review", 9), ("doing", 13), ("ready", 19), ("inbox", 19)]
PRIORITY_WEIGHTS = [("low", 20), ("medium", 48), ("high", 24), ("urgent", 8)]
STEPS = [
    "Reproduce the issue",
    "Write the failing test",
    "Implement the change",
    "Update the docs",
    "Review with the team",
    "Check on mobile",
    "Deploy to staging",
    "Verify in production",
]
COMMENTS = [
    "I looked into this today. The root cause is in **{component}**: the value is read before it is ready.",
    "Quick update:\n\n- first pass is done\n- still need to check the edge cases\n- tests are green locally",
    "Can we split this into two tickets? The second half depends on `{key}` landing first.",
    "Pushed a draft. Screenshot attached of the current state.",
    "This is blocking the release checklist, bumping the priority.",
    "Tested on Windows and Linux, works on both. Waiting for review.",
    "Notes from the call:\n\n1. keep the old behaviour behind a flag\n2. measure before and after\n3. ship next week",
    "Found a simpler approach: reuse the existing helper instead of adding a new one.",
    "Moved the estimate up, this touches more files than expected.",
    "Done. Leaving this open for a day in case anything regresses.",
]


def weighted(rng, choices):
    total = sum(weight for _, weight in choices)
    pick = rng.uniform(0, total)
    for value, weight in choices:
        pick -= weight
        if pick <= 0:
            return value
    return choices[-1][0]


def png(width, height, blocks, background):
    """A small flat-colour PNG drawn from rectangles, used as a stand-in screenshot."""
    rows = []
    for y in range(height):
        row = bytearray(background * width)
        for x0, y0, x1, y1, color in blocks:
            if y0 <= y < y1:
                row[x0 * 3 : x1 * 3] = bytes(color) * (x1 - x0)
        rows.append(b"\x00" + bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def mock_screenshot(rng):
    """A 480×300 app-like mock: title bar, sidebar, cards and a highlighted region."""
    width, height = 480, 300
    accent = rng.choice([(86, 182, 194), (203, 166, 247), (137, 180, 250), (166, 227, 161), (250, 179, 135)])
    blocks = [
        (0, 0, width, 28, (40, 44, 52)),
        (12, 9, 60, 19, accent),
        (0, 28, 96, height, (33, 37, 43)),
    ]
    for i in range(6):
        blocks.append((12, 44 + i * 26, 84, 56 + i * 26, (62, 68, 81) if i else accent))
    x = 110
    for column in range(3):
        y = 44
        for _ in range(rng.randint(2, 4)):
            card = rng.randint(40, 70)
            blocks.append((x, y, x + 110, y + card, (52, 58, 70)))
            blocks.append((x + 8, y + 8, x + 8 + rng.randint(40, 90), y + 16, (171, 178, 191)))
            y += card + 10
        x += 120
    hx, hy = rng.randint(120, 330), rng.randint(60, 200)
    blocks.append((hx, hy, hx + 110, hy + 3, (224, 108, 117)))
    blocks.append((hx, hy + 50, hx + 110, hy + 53, (224, 108, 117)))
    blocks.append((hx, hy, hx + 3, hy + 53, (224, 108, 117)))
    blocks.append((hx + 107, hy, hx + 110, hy + 53, (224, 108, 117)))
    return png(width, height, blocks, (30, 33, 39)), width, height


def load_demo(store, now_ms=None):
    """Fill an empty workspace with the demo data in one transaction."""
    rng = random.Random(20261109)
    now = int(time.time() * 1000) if now_ms is None else now_ms
    with store.atomic():
        if store.list("project"):
            raise ValueError("The demo workspace can only be loaded into an empty workspace.")
        account = store.auth()
        zone = store.settings()["timezone"]
        tz = ZoneInfo(zone)
        today = date.fromisoformat(D.day_key(zone, now))

        def day(offset):
            return (today + timedelta(days=offset)).isoformat()

        def at(day_offset, hour, minute=0):
            moment = datetime.combine(today + timedelta(days=day_offset), datetime.min.time(), tz)
            return int((moment + timedelta(hours=hour, minutes=minute)).timestamp() * 1000)

        tickets = []
        for name, key, description, components, titles in PROJECTS:
            project = store._save("project", {"name": name, "project_key": key, "description": description})
            for order, component in enumerate(components):
                store._save(
                    "section",
                    {
                        "project_id": project["id"],
                        "name": component,
                        "rule_field": "component",
                        "rule_value": component,
                        "sort_order": order,
                    },
                )
            made = []
            for index, title in enumerate(titles):
                status = weighted(rng, STATUS_WEIGHTS)
                # Skewed towards recent days so this week's numbers are never empty.
                age = 0.05 + 72 * rng.random() ** 1.5
                if status == "done" and age < 1.2:
                    status = "review"
                created = now - int(age * DAY_MS)
                completed = 0
                if status == "done":
                    # Mostly finished in the last few weeks, so weekly charts have something to show.
                    completed = max(created + DAY_MS // 4, now - int(24 * rng.random() ** 1.7 * DAY_MS))
                    completed = min(completed, now - 600_000)
                steps = []
                if rng.random() < 0.45:
                    count = rng.randint(2, 5)
                    finished = {"done": count, "review": count, "doing": rng.randint(1, count)}.get(status, 0)
                    steps = [
                        {"text": text, "done": i < finished}
                        for i, text in enumerate(rng.sample(STEPS, count))
                    ]
                due = ""
                if status != "done" and rng.random() < 0.62:
                    due = day(rng.randint(-8, 30))
                elif status == "done" and rng.random() < 0.4:
                    due = day(-rng.randint(1, 40))
                labels = rng.sample(LABELS, rng.choice([0, 1, 1, 2, 2, 3]))
                component = rng.choice(components)
                milestone = (
                    rng.choice(["", "", "", "Beta", "1.0", "Q4"]) if key not in ("HOME", "LEARN") else ""
                )
                payload = {
                    "project_id": project["id"],
                    "title": title,
                    "status": status,
                    "priority": weighted(rng, PRIORITY_WEIGHTS),
                    "component": component,
                    "milestone": milestone,
                    "due_date": due,
                    "estimate_min": rng.choice([15, 30, 45, 60, 90, 120, 180, 240, 360, 480]),
                    "labels": labels,
                    "checklist": steps,
                    "pinned": int(status in ("ready", "doing") and rng.random() < 0.08),
                    "created_at": created,
                    "completed_at": completed,
                    "description": rng.choice(
                        [
                            "",
                            "Customers reported this in support. Keep the fix small and add a test.",
                            "## Goal\n\nMake this faster and easier to understand.\n\n## Notes\n\n- measure first\n- keep the API stable",
                            "Follow-up from last week's review. See the linked tickets for context.",
                            "Acceptance:\n\n1. works offline\n2. no layout shift\n3. covered by tests",
                        ]
                    ),
                }
                if made and rng.random() < 0.18:
                    earlier = rng.choice(made)
                    payload["dependencies"] = [earlier["id"]]
                if made and rng.random() < 0.12:
                    payload["parent_id"] = rng.choice(made)["id"]
                ticket = store._save("ticket", payload)
                made.append(ticket)
                tickets.append(ticket)
            for ticket in made:
                store.auto_placement(store.read("ticket", ticket["id"]))
        tickets = [store.read("ticket", t["id"]) for t in tickets]
        workable = [t for t in tickets if t["status"] != "inbox"]

        # Three weeks of tracked time on weekdays, plus a little at weekends.
        for offset in range(-21, 0):
            weekday = (today + timedelta(days=offset)).weekday()
            sessions = rng.randint(4, 7) if weekday < 5 else rng.randint(0, 2)
            minute = 9 * 60 + rng.randint(0, 40)
            for _ in range(sessions):
                length = rng.choice([20, 30, 45, 60, 75, 90, 120, 150])
                start = at(offset, 0, minute)
                existing = [t for t in workable if t["created_at"] <= start]
                if not existing:
                    continue
                ticket = rng.choice(existing)
                store._save(
                    "entry",
                    {
                        "ticket_id": ticket["id"],
                        "start_at": start,
                        "end_at": start + length * 60_000,
                        "device_id": account["device_id"],
                        "note": "",
                    },
                )
                minute += length + rng.randint(5, 40)
        today_start = at(0, 9, 5)
        if today_start < now:
            store._save(
                "entry",
                {
                    "ticket_id": rng.choice(workable)["id"],
                    "start_at": today_start,
                    "end_at": min(now, today_start + 50 * 60_000),
                    "device_id": account["device_id"],
                    "note": "",
                },
            )

        # Scheduled work for the next ten days.
        upcoming = [t for t in tickets if t["status"] in ("ready", "doing", "review")]
        for offset in range(0, 10):
            if (today + timedelta(days=offset)).weekday() >= 5:
                continue
            for hour in rng.sample([9, 10, 13, 14, 15, 16], rng.randint(1, 2)):
                store._save(
                    "block",
                    {
                        "ticket_id": rng.choice(upcoming)["id"],
                        "date": day(offset),
                        "start_time": "%02d:00" % hour,
                        "end_time": "%02d:30" % (hour + 1),
                    },
                )

        # Events, countdowns and birthdays.
        for offset in range(0, 12):
            if (today + timedelta(days=offset)).weekday() < 5:
                store._save(
                    "event",
                    {
                        "title": "Team standup",
                        "date": day(offset),
                        "start_time": "09:30",
                        "end_time": "09:45",
                    },
                )
        for title, offset, start, end in (
            ("Design review", 1, "14:00", "15:00"),
            ("1:1 with manager", 2, "11:00", "11:30"),
            ("Sprint planning", 6, "10:00", "11:30"),
            ("Dentist", 4, "17:30", "18:15"),
            ("Customer call", 3, "16:00", "16:45"),
        ):
            store._save("event", {"title": title, "date": day(offset), "start_time": start, "end_time": end})
        for title, offset in (("Version 2.0 launch", 12), ("Quarterly review", 26), ("Conference talk", 41)):
            store._save("event", {"title": title, "date": day(offset), "major": 1, "event_type": "event"})
        for title, offset in (("Mum's birthday", 9), ("Anniversary", 33)):
            store._save(
                "event",
                {
                    "title": title,
                    "date": day(offset),
                    "start_time": "",
                    "end_time": "",
                    "event_type": "birthday",
                    "recurrence": "yearly",
                },
            )
        store._save(
            "event",
            {
                "title": "Weekend in the mountains",
                "date": day(15),
                "end_date": day(17),
                "start_time": "",
                "end_time": "",
                "event_type": "trip",
                "location": "Nagano",
            },
        )

        # Comment threads and screenshots.
        keyed = {p["id"]: p["project_key"] for p in store.list("project")}
        shots = 0
        for ticket in tickets:
            if rng.random() > 0.45:
                continue
            moment = ticket["created_at"] + int(rng.uniform(0.1, 1.5) * DAY_MS)
            for _ in range(rng.randint(1, 4)):
                if moment >= now:
                    break
                body = rng.choice(COMMENTS).format(
                    component=ticket["component"] or "the view",
                    key=keyed[ticket["project_id"]] + "-" + ticket["id"][:6].upper(),
                )
                post = store._save(
                    "post",
                    {
                        "ticket_id": ticket["id"],
                        "body": body,
                        "author": account["username"],
                        "created_at": moment,
                    },
                )
                if "Screenshot" in body and shots < 14:
                    data, width, height = mock_screenshot(rng)
                    store._save(
                        "attachment",
                        {
                            "ticket_id": ticket["id"],
                            "post_id": post["id"],
                            "name": "screenshot-%d.png" % (shots + 1),
                            "media_type": "image/png",
                            "data": base64.b64encode(data).decode(),
                            "size": len(data),
                            "width": width,
                            "height": height,
                            "created_at": moment,
                        },
                    )
                    shots += 1
                moment += int(rng.uniform(0.2, 3) * DAY_MS)
        for ticket in [t for t in tickets if t["status"] in ("doing", "review")][:4]:
            data, width, height = mock_screenshot(rng)
            store._save(
                "attachment",
                {
                    "ticket_id": ticket["id"],
                    "post_id": "",
                    "name": "current-state.png",
                    "media_type": "image/png",
                    "data": base64.b64encode(data).decode(),
                    "size": len(data),
                    "width": width,
                    "height": height,
                    "created_at": ticket["created_at"] + 3_600_000,
                },
            )
    return True
