"""The DayFrame main window.

``DayFrame`` (main.py) owns the window state, async jobs and the refresh cycle.
Each page or concern adds its methods through a mixin; all of them share the
same ``self`` and reach data through ``self.store`` / ``self.data``:

- records.py    snapshot lookups (tickets, keys, project names, tracked time)
- account.py    sign-in, imports, local password, logout
- shell.py      navigation rail, masthead, utility bar, search, timer tick
- today.py      Today page
- projects.py   Projects page (tree, Map/Kanban/Details, sections, filters)
- inspector.py  ticket inspector panel and work-block scheduling
- schedule.py   Calendar page
- tracking.py   Time page
- settings.py   Settings page host, backup, conflicts, sync
- capture.py    Quick Add dialog wiring
"""
from .main import DayFrame

__all__ = ["DayFrame"]
