"""Calendar page: week timeline, mini month, upcoming list and drag edits."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter
from datetime import date, timedelta
from ...core import domain as D, planning as P
from ..views.calendar import MiniMonth, UpcomingPanel, WeekCalendar
from ..widgets import button, label


class CalendarPage:
    def show_calendar(self):
        day=getattr(self,"calendar_day",D.day_key(self.data["settings"]["timezone"]));start=P.sunday(day);end=start+timedelta(days=6)
        self.page_header.layout().addWidget(button("Today",lambda:self.calendar_selected(D.day_key(self.data["settings"]["timezone"]))))
        self.page_header.layout().addWidget(button("",lambda:self.calendar_selected((date.fromisoformat(day)-timedelta(days=7)).isoformat()),"chevron-left"))
        self.page_header.layout().addWidget(label(start.strftime("%b %d")+" – "+end.strftime("%b %d, %Y"),"section"))
        self.page_header.layout().addWidget(button("",lambda:self.calendar_selected((date.fromisoformat(day)+timedelta(days=7)).isoformat()),"chevron-right"))
        self.page_header.layout().addWidget(button("Add event",lambda:self.quick_add("event",day=day),"plus",True))
        split=QSplitter(Qt.Horizontal);split.setHandleWidth(3)
        side=QSplitter(Qt.Vertical);side.setHandleWidth(5);side.setMinimumWidth(246);side.setMaximumWidth(360);side.setChildrenCollapsible(False)
        self.mini_month=MiniMonth(self,day);self.upcoming_panel=UpcomingPanel(self,day);side.addWidget(self.mini_month);side.addWidget(self.upcoming_panel);side.setSizes([290,310]);side.setStretchFactor(1,1)
        self.week_calendar=WeekCalendar(self,day);split.addWidget(side);split.addWidget(self.week_calendar);split.setStretchFactor(0,0);split.setStretchFactor(1,1);split.setSizes([290,900])
        self.work_layout.addWidget(split,1)
        hint=label("Sunday–Saturday · click to edit · drag timed cards to move · drag their bottom edge to resize · double-click empty time to add","muted")
        hint.setWordWrap(True);self.work_layout.addWidget(hint)
    def open_calendar_item(self,item):
        if not self.leave_editor():return
        if item["kind"]=="event":
            record=self.store.read("event",item["id"])
            if record:self.quick_add("event",record)
        elif item["kind"]=="block":
            ticket=self.find_ticket(item["ticket_id"]);record=self.store.read("block",item["id"])
            if ticket and record:self.schedule_ticket(ticket,record)
        elif item["kind"]=="deadline":
            self.page="Projects";self.project_id=item["record"]["project_id"];self.project_view="Details";self.selected=item["ticket_id"];self.refresh_page()
    def move_calendar_item(self,item,day,start,end):
        if item["kind"] not in ("event","block") or not self.leave_editor():return
        kind=item["kind"];old=self.store.read(kind,item["id"])
        if not old:return
        if old.get("recurrence"):
            self.toast.setText("Repeating event: adjust the whole series in Event details.");self.quick_add("event",old);return
        patch={"id":old["id"],"date":day,"start_time":start,"end_time":end}
        if kind=="event":patch["end_date"]=day
        previous={key:old[key] for key in patch if key!="id"}
        if self.execute(kind+".save",patch):
            self.undo_action=lambda:self.execute(kind+".save",{"id":old["id"],**previous})
            self.toast.setText("Schedule updated · Ctrl+Z to undo")
    def calendar_selected(self,day):self.calendar_day=day;self.refresh_page()
