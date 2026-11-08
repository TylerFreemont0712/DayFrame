"""The Today page: priorities, countdowns, upcoming events and day agenda."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QSizePolicy, QSplitter, QTabWidget
from ...core import domain as D, planning as P
from ..views.agenda import Agenda
from ..widgets import button, column, ElidingLabel, label, panel, row, scroll


class TodayPage:
    def ticket_row(self,t,overdue=False):
        w=QFrame();w.setObjectName("overdueRow" if overdue else "taskRow");w.setMinimumHeight(28)
        l=QHBoxLayout(w);l.setContentsMargins(5,2,5,2);l.setSpacing(5)
        check=QCheckBox();check.setToolTip("Complete ticket");check.setAccessibleName("Complete "+t["title"])
        check.clicked.connect(lambda checked:self.complete_ticket(t,checked));l.addWidget(check)
        pin=button("",lambda:self.execute("ticket.save",{"id":t["id"],"pinned":int(not t["pinned"])}),"thumbtack")
        pin.setObjectName("iconOnly");pin.setFixedWidth(20);pin.setToolTip("Unpin priority" if t["pinned"] else "Pin priority");l.addWidget(pin)
        key=ElidingLabel(self.ticket_key(t),"muted");key.setFixedWidth(94);l.addWidget(key)
        project=ElidingLabel(self.project_name(t["project_id"]),"badge");project.setFixedWidth(86);project.setAlignment(Qt.AlignCenter);l.addWidget(project)
        title=button(t["title"],lambda:self.select_ticket(t["id"]));title.setObjectName("rowTitle");title.setMinimumWidth(65);title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);title.setToolTip(t["title"]);l.addWidget(title,1)
        meta=label(("Due "+t["due_date"][5:]) if overdue else D.STATUS_NAMES[t["status"]],"warning" if overdue else "muted")
        meta.setFixedWidth(max(66,meta.fontMetrics().horizontalAdvance(meta.text())+4));l.addWidget(meta)
        estimate=label(D.short_time(t["estimate_min"]*60000),"muted");estimate.setFixedWidth(31);l.addWidget(estimate)
        play=button("",lambda:self.execute("timer.action",{"action":"start","ticket_id":t["id"]}),"play");play.setObjectName("iconOnly");play.setFixedWidth(23);play.setToolTip("Start tracking");l.addWidget(play)
        return w
    def show_today(self):
        today=D.day_key(self.data["settings"]["timezone"]);split=QSplitter(Qt.Horizontal);split.setHandleWidth(2)
        tasks,tl=column(spacing=5);tasks.setMinimumWidth(470)
        focus,fl=panel();focus.setObjectName("focusPanel")
        self.home_focus_title=button("",self.open_focus_ticket,"stopwatch");self.home_focus_title.setObjectName("rowTitle");self.home_focus_title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.home_focus_clock=label("","clock");self.home_focus_toggle=button("",self.toggle_timer,"play");self.home_focus_toggle.setFixedWidth(26)
        fl.addWidget(row(label("Focus","section"),self.home_focus_title,self.home_focus_clock,self.home_focus_toggle))
        tl.addWidget(focus)
        for title,group in P.home_groups(self.data,today):
            if not group and title in (D.STATUS_NAMES["ready"],"Recent tickets"):continue
            tl.addWidget(row(label(title,"section"),label(str(len(group)),"count"),None))
            if group:
                for ticket in group:tl.addWidget(self.ticket_row(ticket,title=="Overdue"))
            else:tl.addWidget(label("Pin a ticket to focus on it." if title=="Top priorities" else "Nothing here.","muted"))
        all_upcoming=P.upcoming(self.data,today,500,False)
        majors=sorted([x for x in all_upcoming if x["kind"]=="event" and x["record"]["major"]],key=lambda x:(not x["record"]["pinned"],x["date"]))[:3]
        tl.addWidget(row(label("Next major events","section"),None,button("",lambda:self.quick_add("event"),"plus")))
        for item in majors:
            days=max(0,D.days_until(item["date"],today));count=label("Today" if not days else str(days)+" days","badge");count.setFixedWidth(70)
            event_row=row(self.event_button(item),count);event_row.layout().setStretch(0,1);tl.addWidget(event_row)
        if not majors:tl.addWidget(label("Mark major events to see three countdowns here.","muted"))
        tl.addWidget(row(label("Upcoming","section"),None,button("Calendar",lambda:self.navigate("Calendar"),"calendar-alt")))
        upcoming=[x for x in all_upcoming if x["kind"]=="event"][:5]
        for item in upcoming:tl.addWidget(self.event_button(item))
        if not upcoming:tl.addWidget(label("Appointments, birthdays, trips and plans appear here.","muted"))
        tl.addStretch();split.addWidget(scroll(tasks))
        agenda,al=column(margins=7,spacing=4);agenda.setObjectName("agendaPane");agenda.setMinimumWidth(270)
        al.addWidget(row(label("Day Agenda","section"),None,button("",lambda:self.quick_add("event"),"plus")))
        for item in P.day_items(self.data,today):
            if item["all_day"]:al.addWidget(self.event_button(item))
        al.addWidget(Agenda(self,today),1);split.addWidget(agenda);split.setStretchFactor(0,3);split.setStretchFactor(1,2);split.setSizes([710,425])
        self._today_narrow=self.width()-48-(280 if self.selected else 0)<840
        if self._today_narrow:
            task_scroll=split.widget(0);agenda_widget=split.widget(1);task_scroll.setParent(None);agenda_widget.setParent(None)
            tabs=QTabWidget();tabs.addTab(task_scroll,"Tasks");tabs.addTab(agenda_widget,"Day Agenda");split.deleteLater();self.work_layout.addWidget(tabs,1)
        else:self.work_layout.addWidget(split,1)
    def event_button(self,item):
        text=item["title"]+" · "+item["date"][5:]+" · "+("All day" if item["all_day"] else item["start_time"]+"–"+item["end_time"])
        b=button(text,lambda checked=False,x=item:self.open_calendar_item(x),"calendar-alt");b.setObjectName("rowTitle")
        b.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);b.setMinimumHeight(24);b.setToolTip((text+"\n"+item.get("description","")).replace("<","‹").replace(">","›"))
        return b
    def open_focus_ticket(self):
        timer=next((x for x in self.data["timer"] if x["id"]=="active"),{})
        ticket=self.find_ticket(timer.get("ticket_id"))
        if ticket:self.select_ticket(ticket["id"])
        else:self.navigate("Time")
    def complete_ticket(self,ticket,checked=True):
        self.undo_action=lambda:self.execute("ticket.save",{"id":ticket["id"],"status":ticket["status"]})
        self.execute("ticket.save",{"id":ticket["id"],"status":"done" if checked else "ready"})
