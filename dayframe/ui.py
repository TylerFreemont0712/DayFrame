"""DayFrame's native Qt Widgets application. No embedded browser is used."""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime,date,timedelta
from pathlib import Path
from PySide6.QtCore import (Qt,QTimer,QDate,QDateTime,QTime,QObject,Signal,QRunnable,QThreadPool,QMimeData,QSize,QRectF,QPointF)
from PySide6.QtGui import QColor,QPainter,QPen,QDrag,QKeySequence,QShortcut,QFont
from PySide6.QtWidgets import *
from . import domain as D,planning as P
from .theme import apply_theme,icon,app_icon,CURRENT as C
from .widgets import label,button,column,row,panel,scroll,combo,error,FormDialog,ask_text,ElidingLabel
from .dialogs import AddDialog,SectionDialog,ConflictDialog
from .project_map import ProjectMap
from .labels import LabelsEditor,label_choices,paint_label_pills
from .kanban import BoardDelegate,TicketList,card_size
from .calendar_views import MiniMonth,UpcomingPanel,WeekCalendar,paint_item,readable
from .sync import Sync

class WorkerSignals(QObject):
    done=Signal(object); failed=Signal(str)

class Worker(QRunnable):
    def __init__(self,fn):
        super().__init__(); self.fn=fn; self.signals=WorkerSignals()
    def run(self):
        try: self.signals.done.emit(self.fn())
        except Exception as exc: self.signals.failed.emit(str(exc))

class Agenda(QWidget):
    def __init__(self,window,day):
        super().__init__();self.window=window;self.day=day;self.setMinimumSize(265,360);self.regions=[];self.setMouseTracking(True)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setFont(QApplication.font());self.regions=[]
        items=[x for x in P.day_items(self.window.data,self.day) if not x["all_day"]]
        first=min([9]+[x["start_min"]//60 for x in items]);last=max([19]+[(x["end_min"]+59)//60 for x in items])
        left,top=43,12;span=max(300,self.height()-34);hour=span/max(1,last-first);width=self.width()-left-5
        for h in range(first,last+1):
            y=top+(h-first)*hour;p.setPen(QColor(C["muted"]));p.drawText(2,int(y+4),f"{h:02}:00")
            p.setPen(QPen(QColor(C["line"]),.6));p.drawLine(left,int(y),self.width()-4,int(y))
        for item in P.overlap_lanes(items):
            rect=QRectF(left+item["lane"]*width/item["lanes"],top+(item["start_min"]/60-first)*hour+2,
                        width/item["lanes"]-4,max(22,(item["end_min"]-item["start_min"])/60*hour-4))
            paint_item(p,rect,item);self.regions.append((rect,item))
        now=datetime.now(D.ZoneInfo(self.window.data["settings"]["timezone"]))
        if now.date().isoformat()==self.day and first<=now.hour<last:
            y=top+(now.hour+now.minute/60-first)*hour;p.setPen(QPen(QColor(C["accent"]),1.2));p.drawLine(left,int(y),self.width()-3,int(y))
            p.setBrush(QColor(C["accent"]));p.setPen(Qt.NoPen);p.drawRoundedRect(QRectF(0,y-9,39,18),3,3)
            p.setPen(QColor(C["bg"]));p.drawText(QRectF(0,y-9,39,18),Qt.AlignCenter,now.strftime("%H:%M"))
        p.end()
    def mouseReleaseEvent(self,event):
        for rect,item in reversed(self.regions):
            if rect.contains(event.position()):
                QTimer.singleShot(0,lambda x=item:self.window.open_calendar_item(x));break
    def mouseMoveEvent(self,event):
        item=next((x for r,x in self.regions if r.contains(event.position())),None)
        self.setCursor(Qt.PointingHandCursor if item else Qt.ArrowCursor)
        self.setToolTip((item["title"]+"\n"+readable(item)).replace("<","‹").replace(">","›") if item else "")


class UnsortedList(QListWidget):
    def startDrag(self,actions):
        item=self.currentItem()
        if not item:return
        mime=QMimeData();mime.setData("application/x-timemanager-ticket",item.data(Qt.UserRole).encode())
        drag=QDrag(self);drag.setMimeData(mime);drag.exec(Qt.MoveAction)

class DayFrame(QMainWindow):
    def __init__(self,store):
        super().__init__();self.store=store;self.sync=Sync(store)
        self.setWindowTitle("DayFrame");self.setWindowIcon(app_icon());self.resize(1280,800);self.setMinimumSize(980,640)
        self.page="Today";self.project_id=None;self.project_view="Kanban";self.selected=None
        self.filter_project=None;self.filter_status="all";self.filter_label="";self.context_collapsed=False
        self.search_text="";self.data=None;self.undo_action=None;self.busy=False;self.jobs=set();self.rebuilding=False
        self.draft_reader=None;self.draft_save=None;self.day=None
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000)
        self.sync_timer=QTimer(self);self.sync_timer.timeout.connect(self.auto_sync);self.sync_timer.start(5000)
        apply_theme({"theme":"graphite","density":"compact"})
        if self.store.account or self.store.restore_session():self.signed_in()
        else:self.show_auth()
        QShortcut(QKeySequence("Ctrl+K"),self,activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"),self,activated=lambda:self.quick_add() if self.data else None)
        QShortcut(QKeySequence("Ctrl+Z"),self,activated=self.undo)

    def run_async(self,fn,done,owner=None):
        job=Worker(fn); self.jobs.add(job)
        job.signals.done.connect(lambda result:self._job_done(job,done,result))
        job.signals.failed.connect(lambda message:self._job_error(job,message))
        QThreadPool.globalInstance().start(job)
    def _job_done(self,job,done,result):
        self.jobs.discard(job)
        try: done(result)
        except Exception as exc: error(self,exc)
    def _job_error(self,job,message):
        self.jobs.discard(job); self.busy=False
        if hasattr(self,"auth_submit"): self.auth_submit.setEnabled(True)
        error(self,message)
    def show_auth(self):
        self.data=None; root,l=column(margins=40); l.addStretch()
        card,cl=panel(); card.setMaximumWidth(540)
        cl.addWidget(label("DayFrame","heading")); cl.addWidget(label("Your projects. Your day. Your space.","muted"))
        configured=self.store.status()["configured"]
        cl.addWidget(label("Sign in to this device" if configured else "Create your private workspace","section"))
        self.username=QLineEdit(); self.username.setPlaceholderText("Username"); self.username.setAccessibleName("Username")
        self.password=QLineEdit(); self.password.setPlaceholderText("Password"); self.password.setEchoMode(QLineEdit.Password)
        cl.addWidget(self.username); cl.addWidget(self.password)
        self.auth_submit=button("Sign in" if configured else "Create account",self.submit_auth,accent=True); cl.addWidget(self.auth_submit)
        self.password.returnPressed.connect(self.submit_auth)
        if not configured:
            cl.addWidget(label("Everything stays in your local SQLite database.","muted"))
            cl.addWidget(button("Import an existing DayFrame database",self.import_database,"database"))
            cl.addWidget(button("Connect to my existing LAN account",self.import_hub,"network-wired"))
        cl.addWidget(label(str(self.store.root),"muted"))
        center=row(None,card,None); l.addWidget(center); l.addStretch(); self.setCentralWidget(root)
    def submit_auth(self):
        if self.busy: return
        self.busy=True; self.auth_submit.setEnabled(False)
        name,pw=self.username.text(),self.password.text()
        fn=self.store.login if self.store.status()["configured"] else self.store.register
        self.run_async(lambda:fn(name,pw),lambda result:self.signed_in())
    def signed_in(self):
        self.busy=False
        if hasattr(self,"password"):
            try:self.password.clear()
            except RuntimeError:pass
        self.data=self.store.snapshot();apply_theme(self.data["settings"])
        self.day=D.day_key(self.data["settings"]["timezone"])
        if self.data["settings"].get("layoutRevision",0)<3:
            self.store.settings({"layoutRevision":3,"density":"compact","sidebarWidth":164,"inspectorWidth":280,"windowGeometry":""})
            self.data=self.store.snapshot();apply_theme(self.data["settings"]);self.resize(1280,800)
        self.build_shell()
        geometry=self.data["settings"].get("windowGeometry")
        if geometry:
            from PySide6.QtCore import QByteArray
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
        screen=self.screen().availableGeometry()
        if self.width()>screen.width() or self.height()>screen.height():
            self.resize(min(1280,screen.width()-40),min(800,screen.height()-60))
        self.refresh()

    def import_database(self):
        file,_=QFileDialog.getOpenFileName(self,"Import a copy of an existing database",str(Path.home()),"SQLite database (*.db *.sqlite *.sqlite3);;All files (*)")
        if not file: return
        try:
            self.store.import_database(file); self.show_auth()
            QMessageBox.information(self,"Import complete","A copy was imported. Sign in with your existing account. The original database was not changed.")
        except Exception as exc: error(self,exc)
    def import_hub(self):
        d=FormDialog(self,"Connect this device to your account"); f=QFormLayout(); d.layout.addLayout(f)
        edits={}
        for key,title in (("url","HTTPS hub address"),("fingerprint","Certificate SHA-256"),("username","Username"),("password","Password")):
            edits[key]=QLineEdit(); f.addRow(title,edits[key])
        edits["password"].setEchoMode(QLineEdit.Password); d.finish_form()
        if d.exec()!=QDialog.Accepted:return
        p={k:w.text() for k,w in edits.items()}
        self.run_async(lambda:self.sync.connect(p,importing=True),lambda result:self.signed_in())
    def build_shell(self):
        outer=QWidget();layout=QHBoxLayout(outer);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        rail,rl=column(margins=6,spacing=5);rail.setObjectName("navigationRail");rail.setFixedWidth(48)
        mark=QLabel();mark.setPixmap(app_icon().pixmap(30,30));mark.setAlignment(Qt.AlignCenter);rl.addWidget(mark)
        self.nav={}
        for page,glyph in (("Today","home"),("Projects","layer-group"),("Calendar","calendar-alt"),("Time","clock"),("Code","code")):
            b=button("",lambda checked=False,p=page:self.navigate(p),glyph);b.setCheckable(True);b.setFixedSize(34,34)
            b.setIconSize(QSize(17,17));b.setToolTip(page);b.setAccessibleName(page);self.nav[page]=b;rl.addWidget(b)
        rl.addStretch();b=button("",lambda:self.navigate("Settings"),"cog");b.setFixedSize(34,34);b.setCheckable(True);b.setToolTip("Settings");b.setAccessibleName("Settings");self.nav["Settings"]=b;rl.addWidget(b)
        layout.addWidget(rail)
        body,bl=column(spacing=0);layout.addWidget(body,1)
        top=QFrame();top.setObjectName("masthead");tl=QHBoxLayout(top);tl.setContentsMargins(10,4,8,4);tl.setSpacing(6)
        personal=button("Personal",None,"user");personal.setCheckable(True);personal.setChecked(True)
        team=button("Team",lambda:QMessageBox.information(self,"Team","Team workspaces are planned. Your personal workspace and device sync are available."),"users")
        tl.addWidget(personal);tl.addWidget(team);tl.addStretch()
        self.search=QLineEdit();self.search.setPlaceholderText("Search tickets…  Ctrl+K");self.search.setMinimumWidth(140);self.search.setMaximumWidth(300);self.search.textChanged.connect(self.search_changed);tl.addWidget(self.search)
        self.sync_label=label("Local","muted");self.sync_label.setMaximumWidth(100);tl.addWidget(self.sync_label)
        tl.addWidget(button("Add",lambda:self.quick_add(),"plus",True))
        self.options=button("",None,"ellipsis-h");self.options.setAccessibleName("Options");self.options.setToolTip("Options");self.options.setFixedWidth(32)
        self.options_menu=QMenu(self)
        self.options_menu.addAction(icon("cog"),"Settings",lambda:self.navigate("Settings"))
        self.options_menu.addAction(icon("sync-alt"),"Sync now",lambda:self.sync_now(False))
        self.options_menu.addAction(icon("undo"),"Undo",self.undo);self.options_menu.addSeparator()
        self.options_menu.addAction(icon("sign-out-alt"),"Log out",self.logout)
        self.options.setMenu(self.options_menu);tl.addWidget(self.options);bl.addWidget(top)
        self.splitter=QSplitter(Qt.Horizontal);self.splitter.setHandleWidth(2)
        self.context,self.context_layout=column(margins=8,spacing=5);self.context.setObjectName("contextPane");self.context.setMinimumWidth(140);self.context.setMaximumWidth(280)
        self.workspace,self.work_layout=column(margins=9,spacing=6);self.workspace.setMinimumWidth(410)
        self.inspector,self.inspect_layout=column();self.inspector.setObjectName("ticketInspector");self.inspector.setMinimumWidth(240);self.inspector.setMaximumWidth(420)
        self.splitter.addWidget(self.context);self.splitter.addWidget(self.workspace);self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(1,1);self.splitter.setSizes([self.data["settings"]["sidebarWidth"],820,self.data["settings"]["inspectorWidth"]]);bl.addWidget(self.splitter,1)
        footer=QFrame();footer.setObjectName("utilityBar");fl=QHBoxLayout(footer);fl.setContentsMargins(9,4,8,4);fl.setSpacing(6)
        self.timer_title=label("No timer","section");self.timer_title.setMaximumWidth(120);self.timer_clock=label("00:00:00","clock");self.timer_clock.setFixedWidth(88)
        self.timer_toggle=button("",self.toggle_timer,"play");self.timer_toggle.setFixedWidth(27);self.timer_toggle.setToolTip("Start / pause timer");self.timer_toggle.setAccessibleName("Start or pause timer")
        stop=button("",lambda:self.execute("timer.action",{"action":"stop"}),"stop");stop.setFixedWidth(27);stop.setToolTip("Stop timer");stop.setAccessibleName("Stop timer")
        timer_icon=label("");timer_icon.setPixmap(icon("stopwatch").pixmap(14,14))
        for w in (timer_icon,self.timer_title,self.timer_clock,self.timer_toggle,stop):fl.addWidget(w)
        self.today_total=label("Today 0m","section");self.today_total.setMinimumWidth(85);fl.addWidget(self.today_total)
        fl.addSpacing(8)
        self.quick_input=QLineEdit();self.quick_input.setPlaceholderText("Add a ticket or event…");self.quick_input.setAccessibleName("Quick capture");self.quick_input.setMinimumWidth(140);self.quick_input.returnPressed.connect(self.inline_add);fl.addWidget(self.quick_input,1)
        self.quick_type=combo([("ticket","Ticket"),("event","Event")]);self.quick_type.setFixedWidth(78);fl.addWidget(self.quick_type)
        add=button("",self.inline_add,"plus");add.setFixedWidth(27);add.setToolTip("Capture");fl.addWidget(add);bl.addWidget(footer)
        if hasattr(self,"toast"):
            try:self.statusBar().removeWidget(self.toast);self.toast.deleteLater()
            except RuntimeError:pass
        self.toast=label("Ready","muted");self.statusBar().setSizeGripEnabled(True);self.statusBar().addWidget(self.toast,1)
        self.statusBar().show();self.setCentralWidget(outer)

    def scope_changed(self):
        if self.scope.currentData()=="team":
            QMessageBox.information(self,"Team workspace","Personal accounts and LAN sync are available. Shared team workspaces are planned.")
            self.scope.setCurrentIndex(0)
    def focus_search(self):
        if self.data: self.search.setFocus()
    def search_changed(self,text):
        self.search_text=text.casefold()
        if text and self.page!="Projects": self.navigate("Projects")
        else: self.refresh_page()
    def navigate(self,page):
        if page not in self.nav:return
        if not self.leave_editor():return
        self.page=page
        if page!="Projects": self.selected=None
        self.refresh()
    def clear_layout(self,layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
            elif item.layout(): self.clear_layout(item.layout())
    def refresh(self):
        self.data=self.store.snapshot()
        self.refresh_page(); self.tick()
    def refresh_page(self):
        if not self.data or not hasattr(self,"work_layout"):return
        if self.has_draft():
            self.toast.setText("Your editor draft stays open.");return
        self.draft_reader=None;self.draft_save=None;self.rebuilding=True
        self.clear_layout(self.work_layout);self.clear_layout(self.context_layout)
        self.context.setVisible(self.page=="Projects" and not self.context_collapsed)
        for name,w in self.nav.items():w.setChecked(name==self.page)
        if self.page=="Projects":self.projects_context()
        title=self.page
        if self.page=="Projects":title=self.project_name(self.project_id) if self.project_id else "All tickets"
        self.page_header=row(label(title,"heading"))
        self.page_header.layout().setSpacing(12)
        if self.page=="Today":
            dt=datetime.strptime(D.day_key(self.data["settings"]["timezone"]),"%Y-%m-%d")
            self.page_header.layout().addWidget(label(dt.strftime("%A, %b %d").replace(" 0"," "),"muted"))
        self.page_header.layout().addStretch()
        if self.page=="Projects" and self.context_collapsed:
            self.page_header.layout().addWidget(button("",self.toggle_context,"bars"))
        self.work_layout.addWidget(self.page_header)
        getattr(self,"show_"+self.page.lower())()
        self.render_inspector();self.rebuilding=False

    def execute(self,method,payload=None,refresh=True):
        try:
            result=self.store.command(method,payload); self.data=self.store.snapshot()
            if refresh:self.refresh_page()
            self.tick(); self.toast.setText("Saved locally")
            return result or True
        except Exception as exc:
            error(self,exc); return None
    def find_ticket(self,ticket_id):return next((t for t in self.data["ticket"] if t["id"]==ticket_id),None)
    def ticket_key(self,t):
        p=next((p for p in self.data["project"] if p["id"]==t["project_id"]),{})
        # The stable short UUID identifies tickets across devices.
        return p.get("project_key","T")+" · "+t["id"][:6].upper()
    def blocked(self,t):
        return any(self.find_ticket(dep) and self.find_ticket(dep)["status"]!="done" for dep in t["dependencies"])
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

    def projects_context(self):
        l=self.context_layout;l.addWidget(row(label("PROJECTS","section"),None,button("",self.toggle_context,"angle-double-left")))
        l.addWidget(button("All tickets",lambda:self.choose_project(None),"columns"))
        l.addWidget(button("Schedule",lambda:self.navigate("Calendar"),"calendar-alt"));l.addWidget(button("Time tracker",lambda:self.navigate("Time"),"clock"))
        l.addWidget(row(label("YOUR PROJECTS","muted"),None,button("",self.new_project,"plus")))
        tree=QTreeWidget();tree.setHeaderHidden(True);tree.setIndentation(12);tree.setObjectName("projectTree");tree.setRootIsDecorated(True)
        for p in self.data["project"]:
            if p["archived"]:continue
            item=QTreeWidgetItem([p["name"]]);item.setIcon(0,icon("folder"));item.setData(0,Qt.UserRole,("project",p["id"]));tree.addTopLevelItem(item)
            for kind,name,glyph in (("project","Overview","th-large"),("milestones","Milestones","flag"),("code","Code","code")):
                child=QTreeWidgetItem([name]);child.setIcon(0,icon(glyph));child.setData(0,Qt.UserRole,(kind,p["id"]));item.addChild(child)
            item.setExpanded(p["id"]==self.project_id)
        tree.itemClicked.connect(self.context_clicked);l.addWidget(tree,1)

    def choose_project(self,project_id):
        if not self.leave_editor():return
        self.project_id=project_id; self.selected=None; self.project_view="Map" if project_id else "Kanban"; self.refresh_page()
    def new_project(self):
        name=ask_text(self,"New project","Project name")
        if name and self.execute("project.save",{"name":name,"project_key":"".join(c for c in name.upper() if c.isalnum())[:6] or "PROJ"}): self.refresh()
    def filtered_tickets(self):
        result=[]
        for t in self.data["ticket"]:
            if t["archived"] or (self.project_id and t["project_id"]!=self.project_id):continue
            if not self.project_id and self.filter_project and t["project_id"]!=self.filter_project:continue
            if self.filter_status=="open" and t["status"]=="done":continue
            if self.filter_status not in ("all","open") and t["status"]!=self.filter_status:continue
            if self.filter_label and self.filter_label not in t["labels"]:continue
            if self.search_text and self.search_text not in " ".join([t["title"],t["description"],*t["labels"],self.ticket_key(t),self.project_name(t["project_id"])]).casefold():continue
            result.append(t)
        return result

    def show_projects(self):
        views=(["Map"] if self.project_id else [])+["Kanban","List","Details"]
        if self.project_view not in views:self.project_view="Kanban"
        tabs=QTabBar();tabs.setExpanding(False);[tabs.addTab(v) for v in views];tabs.setCurrentIndex(views.index(self.project_view))
        tabs.currentChanged.connect(lambda index:self.change_project_view(views[index]));self.page_header.layout().addWidget(tabs)
        if not self.data["project"]:
            empty,l=panel("Start with a project");l.addWidget(label("Create a project or load the example workspace.","muted"))
            l.addWidget(row(button("Create project",self.new_project,"plus",True),button("Load examples",lambda:self.execute("examples.load"))));self.work_layout.addWidget(empty);self.work_layout.addStretch();return
        if self.project_view=="Map":
            self.map=ProjectMap(self,self.project_id);zoom=label("100%","muted");zoom.setFixedWidth(38)
            if hasattr(self.map,"scaleChanged"):self.map.scaleChanged.connect(lambda n:zoom.setText(str(n)+"%"))
            count=len(self.map.unsorted);tray_button=button("Unsorted ("+str(count)+")",None,"inbox")
            tray_button.setCheckable(True);tray_button.setChecked(getattr(self,"map_unsorted_open",False));tray_button.setAccessibleName("Unsorted tickets")
            tray_button.setStyleSheet("color:"+C["danger"]+";font-weight:700;" if count else "color:"+C["muted"]+";")
            self.work_layout.addWidget(row(button("Section",self.new_section,"plus"),button("Rules",self.map_rules,"sliders-h"),button("Ticket",lambda:self.quick_add("ticket"),"plus"),tray_button,None,
                button("−",lambda:self.map.zoom_by(1/1.15)),zoom,button("+",lambda:self.map.zoom_by(1.15)),button("Fit",self.map.fit,"expand")))
            body,bl=column();body_layout=QHBoxLayout();body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(7);bl.addLayout(body_layout)
            body_layout.addWidget(self.map,1);drawer,dl=panel("Unsorted · "+str(count));drawer.setFixedWidth(220)
            hint=label("Drag a ticket onto the map. Hold over a target for 1.5 seconds, then release to confirm.","muted");hint.setWordWrap(True);dl.addWidget(hint)
            items=UnsortedList();items.setDragEnabled(True);items.setWordWrap(True)
            for t in self.map.unsorted:
                item=QListWidgetItem(t["title"]);item.setData(Qt.UserRole,t["id"]);item.setToolTip(t["title"]);items.addItem(item)
            items.itemClicked.connect(lambda item:self.select_ticket(item.data(Qt.UserRole),rebuild=False));dl.addWidget(items,1)
            if not count:dl.addWidget(label("Everything is organized.","muted"))
            body_layout.addWidget(drawer);drawer.setVisible(getattr(self,"map_unsorted_open",False))
            def toggle_tray(checked):self.map_unsorted_open=checked;drawer.setVisible(checked)
            tray_button.toggled.connect(toggle_tray);self.work_layout.addWidget(body,1)
            legend=label("Drag section header or ticket · hold 1.5s for ghost preview · release to confirm · solid = parent/child · dashed = dependency · dotted = sequence","muted");legend.setWordWrap(True)
            self.work_layout.addWidget(legend);return
        project_filter=combo([(None,"All projects")]+[(p["id"],p["name"]) for p in self.data["project"] if not p["archived"]],self.filter_project)
        project_filter.setMaximumWidth(170);project_filter.setVisible(not self.project_id)
        status_filter=combo([("all","All statuses"),("open","Open tickets")]+[(s,D.STATUS_NAMES[s]) for s in D.STATUSES],self.filter_status);status_filter.setMaximumWidth(170)
        labels=sorted({v for t in self.data["ticket"] for v in t["labels"]})
        label_filter=combo([("","Label: All")]+[(v,v) for v in labels],self.filter_label);label_filter.setMaximumWidth(140)
        project_filter.currentIndexChanged.connect(lambda:self.change_filter("filter_project",project_filter.currentData()))
        status_filter.currentIndexChanged.connect(lambda:self.change_filter("filter_status",status_filter.currentData()))
        label_filter.currentIndexChanged.connect(lambda:self.change_filter("filter_label",label_filter.currentData()))
        self.work_layout.addWidget(row(project_filter,status_filter,label_filter,None,button("Ticket",lambda:self.quick_add("ticket"),"plus",True)))
        tickets=self.filtered_tickets()
        if self.project_view=="Kanban":
            board=QWidget();lanes=QHBoxLayout(board);lanes.setContentsMargins(0,0,0,0);lanes.setSpacing(5)
            for status in D.STATUSES:
                col,cl=column(spacing=3);group=[t for t in tickets if t["status"]==status]
                header=row(label(D.STATUS_NAMES[status],"section"),label(str(len(group)),"count"),None);cl.addWidget(header)
                lst=TicketList(self,status);lst.setMinimumWidth(max(138,header.sizeHint().width()))
                for t in group:
                    item=QListWidgetItem(t["title"]);item.setData(Qt.UserRole,t["id"]);item.setData(Qt.UserRole+1,t)
                    item.setToolTip(t["title"]);item.setSizeHint(card_size(t));lst.addItem(item)
                cl.addWidget(lst,1);lanes.addWidget(col,1)
            self.work_layout.addWidget(scroll(board),1)
        else:
            fields=["Ticket","Title","Status","Priority","Due","Estimate","Tracked","Component","Labels"] if self.project_view=="Details" else ["Ticket","Title","Status","Priority","Due"]
            table=QTableWidget(len(tickets),len(fields));table.setHorizontalHeaderLabels(fields);table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setAlternatingRowColors(True);table.verticalHeader().hide();table.verticalHeader().setDefaultSectionSize(25)
            for r,t in enumerate(tickets):
                values=[self.ticket_key(t),t["title"],D.STATUS_NAMES[t["status"]]+(" · Blocked" if self.blocked(t) else ""),t["priority"],t["due_date"],D.short_time(t["estimate_min"]*60000),D.short_time(self.tracked_ms(t["id"])),t["component"],", ".join(t["labels"])]
                for c,value in enumerate(values[:len(fields)]):
                    item=QTableWidgetItem(value);item.setData(Qt.UserRole,t["id"]);table.setItem(r,c,item)
            table.resizeColumnsToContents();table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
            table.cellClicked.connect(lambda r,c:self.select_ticket(table.item(r,0).data(Qt.UserRole)));self.work_layout.addWidget(table,1)

    def change_project_view(self,view):
        if self.leave_editor():self.project_view=view;self.refresh_page()
    def new_section(self,parent_id=""):
        if not self.project_id:return
        if isinstance(parent_id,bool):parent_id=""
        sections=[s for s in self.data["section"] if s["project_id"]==self.project_id]
        d=SectionDialog(self,sections=sections,parent_id=parent_id)
        if d.exec()==QDialog.Accepted:self.execute("section.save",{"project_id":self.project_id,"sort_order":len(sections),**d.payload()})
    def select_ticket(self,ticket_id,rebuild=True):
        if ticket_id!=self.selected and not self.leave_editor():return
        if ticket_id==self.selected and self.has_draft():return
        self.selected=ticket_id
        if self.page=="Today":
            self.refresh_page();return
        # Avoid destroying a map item during its mouse event.
        self.render_inspector()
    def render_inspector(self):
        self.clear_layout(self.inspect_layout);t=self.find_ticket(self.selected) if self.selected else None
        self.inspector.setVisible(bool(t))
        if not t:return
        root,l=column(margins=8,spacing=5)
        header=row(label(self.ticket_key(t),"section"),None,button("",lambda:self.close_inspector(),"times"));l.addWidget(header)
        title=QLineEdit(t["title"]);title.setAccessibleName("Ticket title");title.setObjectName("ticketTitle");l.addWidget(title)
        status=combo([(s,D.STATUS_NAMES[s]) for s in D.STATUSES],t["status"])
        status.setToolTip("Workflow status");l.addWidget(status)
        if self.blocked(t):l.addWidget(label("Blocked · unfinished prerequisites","warning"))
        tabs=QTabWidget();tabs.setDocumentMode(True);tabs.tabBar().setDrawBase(False)
        details,dl=column(spacing=5)
        f=QFormLayout();f.setContentsMargins(0,0,0,0);f.setSpacing(4);dl.addLayout(f)
        priority=combo([(s,s.title()) for s in D.PRIORITIES],t["priority"]);f.addRow("Priority",priority)
        project_badge=ElidingLabel(self.project_name(t["project_id"]),"badge");project_badge.setMaximumWidth(170);f.addRow("Project",project_badge)
        candidates=[other for other in self.data["ticket"] if other["project_id"]==t["project_id"] and other["id"]!=t["id"] and not other["archived"]]
        parent=combo([("","No parent")]+[(other["id"],other["title"]) for other in candidates],t.get("parent_id",""));f.addRow("Parent",parent)
        children=[other for other in candidates if other.get("parent_id")==t["id"]]
        for child in children:
            child_button=button("Child · "+child["title"],lambda checked=False,c=child:self.select_ticket(c["id"]));child_button.setObjectName("rowTitle");dl.addWidget(child_button)
        labels=LabelsEditor(", ".join(t["labels"]),label_choices(self.data));labels.setAccessibleName("Ticket labels");f.addRow("Labels",labels)
        due=QLineEdit(t["due_date"]);due.setPlaceholderText("YYYY-MM-DD");f.addRow("Due",due)
        estimate=QSpinBox();estimate.setRange(0,100000);estimate.setValue(int(t["estimate_min"]));estimate.setSuffix(" min");f.addRow("Estimate",estimate)
        f.addRow("Tracked",label(D.short_time(self.tracked_ms(t["id"])),"muted"))
        more=QToolButton();more.setText("Component / milestone");more.setArrowType(Qt.RightArrow);more.setCheckable(True);more.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);dl.addWidget(more)
        extra,exl=column();exf=QFormLayout();exf.setContentsMargins(0,0,0,0);exf.setSpacing(4);exl.addLayout(exf)
        component=QLineEdit(t["component"]);milestone=QLineEdit(t["milestone"]);exf.addRow("Component",component);exf.addRow("Milestone",milestone)
        extra.setVisible(False);more.toggled.connect(lambda checked:(extra.setVisible(checked),more.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)));dl.addWidget(extra)
        description=QPlainTextEdit(t["description"]);description.setPlaceholderText("Description");description.setMinimumHeight(45);description.setMaximumHeight(64);dl.addWidget(description)
        pin=QCheckBox("Pin to Today");pin.setChecked(bool(t["pinned"]));dl.addWidget(pin)
        done=sum(bool(x["done"]) for x in t["checklist"])
        dl.addWidget(label("Checklist  "+str(done)+" / "+str(len(t["checklist"])),"section"))
        checklist=QListWidget();checklist.setObjectName("checklist")
        for step in t["checklist"]:
            item=QListWidgetItem(step["text"]);item.setFlags(item.flags()|Qt.ItemIsUserCheckable|Qt.ItemIsEditable);item.setCheckState(Qt.Checked if step["done"] else Qt.Unchecked);checklist.addItem(item)
        checklist.setMinimumHeight(28);checklist.setMaximumHeight(min(90,max(28,len(t["checklist"])*23+4)));dl.addWidget(checklist)
        step_edit=QLineEdit();step_edit.setPlaceholderText("Add a step…")
        def add_step():
            if step_edit.text().strip():
                item=QListWidgetItem(step_edit.text().strip());item.setFlags(item.flags()|Qt.ItemIsUserCheckable|Qt.ItemIsEditable);item.setCheckState(Qt.Unchecked);checklist.addItem(item);step_edit.clear();checklist.setMaximumHeight(min(90,checklist.count()*23+4))
        step_edit.returnPressed.connect(add_step);dl.addWidget(row(step_edit,button("",add_step,"plus")))
        dep_ids=list(t["dependencies"])
        dep_summary=label("Depends on "+(", ".join(self.ticket_key(self.find_ticket(x)) for x in dep_ids if self.find_ticket(x)) or "—"),"muted");dep_summary.setWordWrap(True)
        def edit_dependencies():
            d=FormDialog(self,"Ticket prerequisites");d.resize(400,320);options=QListWidget();options.setMinimumHeight(150)
            for other in self.data["ticket"]:
                if other["id"]==t["id"] or other["project_id"]!=t["project_id"] or other["archived"]:continue
                item=QListWidgetItem(other["title"]);item.setData(Qt.UserRole,other["id"]);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if other["id"] in dep_ids else Qt.Unchecked);options.addItem(item)
            d.layout.addWidget(options);d.finish_form()
            if d.exec()==QDialog.Accepted:
                dep_ids[:]=[options.item(i).data(Qt.UserRole) for i in range(options.count()) if options.item(i).checkState()==Qt.Checked]
                dep_summary.setText("Depends on "+(", ".join(self.ticket_key(self.find_ticket(x)) for x in dep_ids if self.find_ticket(x)) or "—"))
        dl.addWidget(row(dep_summary,None,button("",edit_dependencies,"link")));dl.addStretch();tabs.addTab(scroll(details),"Details")
        log,ll=column(margins=6)
        for e in sorted([e for e in self.data["entry"] if e["ticket_id"]==t["id"]],key=lambda e:e["start_at"],reverse=True):
            ll.addWidget(button(datetime.fromtimestamp(e["start_at"]/1000,D.ZoneInfo(self.data["settings"]["timezone"])).strftime("%b %d %H:%M")+" · "+D.short_time(e["end_at"]-e["start_at"]),lambda checked=False,e=e:self.manual_time(e),"clock"))
        ll.addStretch();tabs.addTab(scroll(log),"Time");l.addWidget(tabs,1)
        def payload():
            result={"title":title.text(),"description":description.toPlainText(),"status":status.currentData(),"priority":priority.currentData(),
                "labels":[s.strip() for s in labels.text().split(",") if s.strip()],"component":component.text(),"milestone":milestone.text(),
                "due_date":due.text().strip(),"estimate_min":estimate.value(),"pinned":int(pin.isChecked()),
                "checklist":[{"text":checklist.item(i).text(),"done":checklist.item(i).checkState()==Qt.Checked} for i in range(checklist.count())],
                "dependencies":list(dep_ids),"parent_id":parent.currentData()}
            return D.changes(t,result)
        def save():
            try:self.store.command("ticket.save",{"id":t["id"],**payload()})
            except Exception as exc:error(self,exc);return False
            self.draft_reader=None;self.draft_save=None;self.refresh();return True
        self.draft_reader=payload;self.draft_save=save
        l.addWidget(row(button("Save ticket",save,"save",True),button("Track",lambda:self.execute("timer.action",{"action":"start","ticket_id":t["id"]}),"play")))
        l.addWidget(row(button("Full details",lambda:self.open_details(t),"external-link-alt"),button("Schedule",lambda:self.schedule_ticket(t),"calendar-plus")))
        menu=QMenu(self);menu.addAction("Archive ticket",lambda:self.archive_ticket(t))
        placement=next((p for p in self.data["placement"] if p["ticket_id"]==t["id"]),None)
        if placement and placement["manual"]:menu.addAction("Return to automatic placement",lambda:self.execute("placement.save",{"ticket_id":t["id"],"section_id":placement["section_id"],"manual":0}))
        more_actions=button("More actions");more_actions.setMenu(menu);l.addWidget(more_actions)
        self.inspect_layout.addWidget(root,1)
        for field in details.findChildren(QWidget):
            if isinstance(field,(QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QListWidget)):
                field.setMinimumWidth(0);field.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        for lane in self.findChildren(TicketList):lane.viewport().update()

    def open_details(self,t):
        if not self.leave_editor():return
        self.page="Projects";self.project_id=t["project_id"];self.project_view="Details";self.refresh_page()
    def close_inspector(self):
        if self.leave_editor():self.selected=None;self.render_inspector()
    def archive_ticket(self,t):
        if self.execute("ticket.save",{"id":t["id"],"archived":1}):self.close_inspector()
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
            self.page="Projects";self.project_id=item["record"]["project_id"];self.project_view="List";self.select_ticket(item["ticket_id"])
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
    def show_time(self):
        self.work_layout.addWidget(row(label("Recorded sessions · editable manual entries","muted"),None,button("Add time",self.manual_time,"plus")))
        entries=sorted(self.data["entry"],key=lambda e:e["start_at"],reverse=True);table=QTableWidget(len(entries),5);table.setHorizontalHeaderLabels(["Ticket / activity","Start","End","Duration","Review"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.verticalHeader().hide()
        zone=D.ZoneInfo(self.data["settings"]["timezone"])
        for r,e in enumerate(entries):
            ticket=self.find_ticket(e["ticket_id"]);overlap=any(x["id"]!=e["id"] and x["start_at"]<e["end_at"] and x["end_at"]>e["start_at"] for x in entries)
            values=[ticket["title"] if ticket else "Unassigned",datetime.fromtimestamp(e["start_at"]/1000,zone).strftime("%Y-%m-%d %H:%M"),
                    datetime.fromtimestamp(e["end_at"]/1000,zone).strftime("%Y-%m-%d %H:%M"),D.short_time(e["end_at"]-e["start_at"]),"Overlaps another session" if overlap else ""]
            for c,value in enumerate(values):table.setItem(r,c,QTableWidgetItem(value))
        table.resizeColumnsToContents();table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        table.cellClicked.connect(lambda r,c:self.manual_time(entries[r]))
        self.work_layout.addWidget(table,1)
    def manual_time(self,existing=None):
        if isinstance(existing,bool):existing=None
        e=existing or {};d=FormDialog(self,"Edit time entry" if existing else "Add time");f=QFormLayout();d.layout.addLayout(f)
        ticket=combo([("","Unassigned")]+[(t["id"],t["title"]) for t in self.data["ticket"] if not t["archived"]],e.get("ticket_id",""));f.addRow("Ticket",ticket)
        zone=D.ZoneInfo(self.data["settings"]["timezone"])
        now=datetime.now(zone)
        start=QDateTimeEdit(QDateTime.fromString(datetime.fromtimestamp(e.get("start_at",int(now.timestamp()*1000))/1000,zone).strftime("%Y-%m-%d %H:%M"),"yyyy-MM-dd HH:mm"))
        end=QDateTimeEdit(QDateTime.fromString(datetime.fromtimestamp(e.get("end_at",int(now.timestamp()*1000)+1800000)/1000,zone).strftime("%Y-%m-%d %H:%M"),"yyyy-MM-dd HH:mm"))
        for title,w in (("Start",start),("End",end)):w.setDisplayFormat("yyyy-MM-dd HH:mm");w.setCalendarPopup(True);f.addRow(title,w)
        note=QLineEdit(e.get("note",""));f.addRow("Note",note);d.finish_form()
        if d.exec()!=QDialog.Accepted:return
        def stamp(w):return int(datetime.strptime(w.dateTime().toString("yyyy-MM-dd HH:mm"),"%Y-%m-%d %H:%M").replace(tzinfo=zone).timestamp()*1000)
        payload={"ticket_id":ticket.currentData(),"start_at":stamp(start),"end_at":stamp(end),"note":note.text()}
        if existing:payload["id"]=e["id"]
        self.execute("time.add",payload)
    def show_code(self):
        p,l=panel("Repository overview · planned")
        l.addWidget(label("Linked GitHub repository, branch, latest commit, release/tag, checks, and local sync status.","muted"))
        l.addWidget(label("Repository connections are a future milestone.","muted"))
        self.work_layout.addWidget(p);self.work_layout.addStretch()
    def show_settings(self):
        root,l=column(spacing=18);p,pl=panel("Appearance");f=QFormLayout();pl.addLayout(f)
        theme=combo([("graphite","Graphite / Cyan"),("amber","Terminal / Amber"),("light","Paper / Linen"),("studio","Midnight / Studio"),("system","System")],self.data["settings"]["theme"])
        density=combo([("comfortable","Comfortable"),("compact","Compact")],self.data["settings"]["density"])
        scale=QSpinBox();scale.setRange(90,125);scale.setSuffix("%");scale.setValue(self.data["settings"]["textScale"])
        zone=QLineEdit(self.data["settings"]["timezone"])
        f.addRow("Theme",theme);f.addRow("Density",density);f.addRow("Text size",scale);f.addRow("Time zone",zone)
        def appearance():
            if self.execute("settings.save",{"theme":theme.currentData(),"density":density.currentData(),"textScale":scale.value(),"timezone":zone.text()},refresh=False):
                apply_theme(self.data["settings"]);self.build_shell();self.refresh()
        pl.addWidget(button("Apply appearance",appearance,"palette",True));l.addWidget(p)
        p,pl=panel("Local data")
        pl.addWidget(label("SQLite storage: "+str(self.store.root/"timemanager.db"),"muted"))
        pl.addWidget(row(button("Back up database",self.backup,"database"),button("Load example workspace",lambda:self.execute("examples.load"))))
        pl.addWidget(label("Backups contain your project data and password verifier. Protect them with your disk or backup encryption.","muted"));l.addWidget(p)
        p,pl=panel("Private LAN synchronization");f=QFormLayout();pl.addLayout(f)
        url=QLineEdit(self.data["settings"].get("syncUrl",""));url.setPlaceholderText("https://linux-hub:47831")
        fp=QLineEdit(self.data["settings"].get("syncFingerprint",""));fp.setPlaceholderText("SHA-256 of the trusted hub certificate")
        password=QLineEdit();password.setEchoMode(QLineEdit.Password)
        setup=QLineEdit();setup.setEchoMode(QLineEdit.Password)
        for title,w in (("Hub address",url),("Certificate fingerprint",fp),("Account password",password),("Private setup token",setup)):f.addRow(title,w)
        enabled=QCheckBox("Automatically sync while the app is open");enabled.setChecked(self.data["settings"].get("syncEnabled",False))
        enabled.toggled.connect(lambda value:self.execute("settings.save",{"syncEnabled":value},refresh=False));pl.addWidget(enabled)
        pl.addWidget(label("Use Connect for an existing hub account; Publish creates this account on your private hub.","muted"))
        def connect(publish=False):
            params={"url":url.text().strip(),"fingerprint":fp.text().strip(),"password":password.text(),"setupToken":setup.text()}
            password.clear();setup.clear()
            self.run_async(lambda:self.sync.publish(params) if publish else self.sync.connect(params),self.sync_finished)
        pl.addWidget(row(button("Connect",lambda:connect(False),"link"),button("Publish account to hub",lambda:connect(True),"upload"),button("Sync now",self.sync_now,"sync-alt")))
        pl.addWidget(label(self.sync.state.get("error") or "Credentials use the OS keyring when available; otherwise they last for this session.","muted"))
        l.addWidget(p)
        if self.data["conflicts"]:
            p,pl=panel("Sync conflicts · "+str(len(self.data["conflicts"])))
            for conflict in self.data["conflicts"]:
                pl.addWidget(button(conflict["kind"]+" · "+conflict["entity_id"][:8]+" · "+", ".join(conflict["fields"]),lambda checked=False,c=conflict:self.review_conflict(c)))
            l.addWidget(p)
        p,pl=panel("Account");pl.addWidget(label("Signed in as "+self.data["account"]["username"],"section"))
        pl.addWidget(row(button("Change local password",self.change_local_password,"key"),button("Log out",self.logout,"sign-out-alt")));l.addWidget(p);l.addStretch()
        for hint in root.findChildren(QLabel):
            if len(hint.text())>60:hint.setWordWrap(True)
        self.work_layout.addWidget(scroll(root),1)
    def backup(self):
        file,_=QFileDialog.getSaveFileName(self,"Back up DayFrame","DayFrame-backup-"+D.day_key()+".db","SQLite database (*.db)")
        if file:
            try:self.store.backup(file);self.toast.setText("Backup saved: "+file)
            except Exception as exc:error(self,exc)
    def review_conflict(self,c):
        d=ConflictDialog(self,c,self.store.read(c["kind"],c["entity_id"]))
        if d.exec()==QDialog.Accepted:
            try:self.sync.resolve(c["id"],d.choice);self.refresh()
            except Exception as exc:error(self,exc)
    def lock_workspace(self):
        self.logout()

    def new_child_ticket(self,parent):
        if self.leave_editor():self.quick_add("ticket",project_id=parent["project_id"],parent_id=parent["id"],more=True)
    def quick_add(self,kind="ticket",existing=None,**defaults):
        if not self.data or kind not in ("ticket","event"):return False
        if kind=="event" and not existing:
            defaults.setdefault("date",defaults.pop("day",getattr(self,"calendar_day",D.day_key(self.data["settings"]["timezone"])) if self.page=="Calendar" else D.day_key(self.data["settings"]["timezone"])))
            if defaults.get("event_type") in ("birthday","trip","holiday"):defaults.setdefault("all_day",True)
        d=AddDialog(self,self.data,kind,defaults.get("project_id",self.project_id),existing,defaults)
        def save_capture(k,p,section):
            if existing:
                p={"id":existing["id"],**D.changes(existing,{key:value for key,value in p.items() if key!="id"})}
                result=self.store.command(k+".save",p)
            elif k=="ticket":result=self.store.command("ticket.capture",{"ticket":p,"section_id":section})
            else:result=self.store.command("event.save",p)
            self.data=self.store.snapshot();d.snapshot=self.data;d.project_changed();self.refresh_page();self.tick();self.toast.setText("Saved locally")
            return result
        d.set_submit_handler(save_capture);d.exec()
        if d.archive_requested and existing:
            if self.execute("event.save",{"id":existing["id"],"archived":1}):
                self.undo_action=lambda:self.execute("event.save",{"id":existing["id"],"archived":0})
        return d.saved_count>0

    def toggle_timer(self):
        t=next((t for t in self.data["timer"] if t["id"]=="active"),None)
        self.execute("timer.action",{"action":"pause" if t and t["start_at"] else "start"})
    def tick(self):
        if not self.data or not hasattr(self,"timer_title"):return
        now=int(time.time()*1000);t=next((t for t in self.data["timer"] if t["id"]=="active"),None)
        ticket=self.find_ticket(t["ticket_id"]) if t else None
        active=bool(t and (t["start_at"] or t["paused"]))
        self.timer_title.setText(self.ticket_key(ticket) if ticket else "Unassigned" if active else "No timer")
        self.timer_title.setToolTip(ticket["title"] if ticket else "Start unassigned tracking with the play button")
        ms=(t["session_ms"]+max(0,now-t["start_at"]) if t and t["start_at"] else t["session_ms"] if t else 0)
        self.timer_clock.setText(D.duration(ms));self.timer_toggle.setIcon(icon("pause" if t and t["start_at"] else "play"))
        self.timer_toggle.setToolTip("Pause timer" if t and t["start_at"] else "Resume / start timer")
        today=D.day_key(self.data["settings"]["timezone"]);start,end=D.day_bounds(today,self.data["settings"]["timezone"])
        total=sum(max(0,min(e["end_at"],end)-max(e["start_at"],start)) for e in self.data["entry"])
        if t and t["start_at"]:total+=max(0,min(now,end)-max(t["start_at"],start))
        self.today_total.setText("Today "+D.short_time(total))
        self.sync_label.setText("Sync: attention" if self.sync.state.get("error") else "Synced" if self.sync.state["connected"] else "Local")
        self.sync_label.setToolTip((self.sync.state.get("error") or "Local workspace")+" · "+str(self.data["pending"])+" queued")
        if self.day!=today:self.day=today;self.refresh()
        if self.page=="Today" and hasattr(self,"home_focus_title"):
            self.home_focus_title.setText(ticket["title"] if ticket and active else "Unassigned session" if active else "Start a timer")
            self.home_focus_title.setToolTip(ticket["title"] if ticket else "Open time tracking")
            self.home_focus_clock.setText(D.duration(ms));self.home_focus_toggle.setIcon(icon("pause" if t and t["start_at"] else "play"))
        for agenda in self.findChildren(Agenda):agenda.update()
        for week in self.findChildren(WeekCalendar):week.canvas.update()

    def auto_sync(self):
        if self.data and self.data["settings"].get("syncEnabled") and not self.jobs:self.sync_now(quiet=True)
    def sync_now(self,quiet=False):
        if isinstance(quiet,bool) and not self.data:return
        self.run_async(lambda:self.sync.run(force=not quiet),lambda result:self.sync_finished(result,quiet))
    def sync_finished(self,result,quiet=False):
        latest=self.store.snapshot()
        changed=any(latest[k]!=self.data[k] for k in D.DEFINITIONS) if self.data else True
        self.data=latest
        if changed:self.refresh_page()
        self.tick()
        if not quiet:self.toast.setText(result.get("error") or ("Synced · credentials remembered" if result.get("remembered") else "Sync complete"))
    def undo(self):
        action=self.undo_action;self.undo_action=None
        if action:action()
    def has_draft(self):
        return bool(self.draft_reader and self.draft_reader())
    def leave_editor(self):
        if not self.has_draft():
            self.draft_reader=None;self.draft_save=None;return True
        choice=QMessageBox.question(self,"Unsaved changes","Save your editor changes before leaving?",QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if choice==QMessageBox.Cancel:return False
        if choice==QMessageBox.Save and self.draft_save and not self.draft_save():return False
        self.draft_reader=None;self.draft_save=None;return True
    def closeEvent(self,event):
        if self.jobs:
            self.toast.setText("Finishing a database or sync operation. Close again once it completes.");event.ignore();return
        if not self.leave_editor():event.ignore();return
        if self.data:
            try:
                sizes=self.splitter.sizes()
                patch={"windowGeometry":bytes(self.saveGeometry().toBase64()).decode()}
                if 140<=sizes[0]<=280:patch["sidebarWidth"]=sizes[0]
                if 240<=sizes[2]<=420:patch["inspectorWidth"]=sizes[2]
                self.store.settings(patch)
            except Exception:pass
        self.timer.stop();self.sync_timer.stop();event.accept()


    def project_name(self,project_id):
        return next((p["name"] for p in self.data["project"] if p["id"]==project_id),"Project")
    def tracked_ms(self,ticket_id):
        return sum(e["end_at"]-e["start_at"] for e in self.data["entry"] if e["ticket_id"]==ticket_id)
    def toggle_context(self):
        self.context_collapsed=not self.context_collapsed;self.refresh_page()
    def change_filter(self,key,value):
        if not self.leave_editor():return
        setattr(self,key,value);self.refresh_page()
    def context_clicked(self,item,column):
        kind,project_id=item.data(0,Qt.UserRole)
        if kind=="project":self.choose_project(project_id)
        elif kind=="milestones":self.show_milestones(project_id)
        else:self.project_id=project_id;self.navigate("Code")
    def show_milestones(self,project_id):
        d=FormDialog(self,self.project_name(project_id)+" · Milestones");d.resize(470,360)
        tickets=[t for t in self.data["ticket"] if t["project_id"]==project_id and t["milestone"] and not t["archived"]]
        names=sorted({t["milestone"] for t in tickets})
        if not names:d.layout.addWidget(label("Set a milestone on a ticket to group its progress here.","muted"))
        for name in names:
            group=[t for t in tickets if t["milestone"]==name];done=sum(t["status"]=="done" for t in group)
            d.layout.addWidget(label(name+" · "+str(done)+"/"+str(len(group))+" complete","section"))
            bar=QProgressBar();bar.setRange(0,len(group));bar.setValue(done);d.layout.addWidget(bar)
            for ticket in group:d.layout.addWidget(label(D.STATUS_NAMES[ticket["status"]]+" · "+ticket["title"],"muted"))
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(d.reject);d.set_footer(close);d.exec()
    def inline_add(self):
        title=self.quick_input.text().strip()
        if not title:return
        kind=self.quick_type.currentData();projects=[p for p in self.data["project"] if not p["archived"]]
        project_id=self.project_id or self.filter_project
        if kind=="ticket" and (not projects or (not project_id and len(projects)>1)):
            if self.quick_add(kind,title=title,project_id=project_id):self.quick_input.clear()
            return
        p={"title":title}
        if kind=="ticket":p["project_id"]=project_id or projects[0]["id"]
        else:p.update(date=D.day_key(self.data["settings"]["timezone"]),start_time="",end_time="")
        if self.execute(kind+".save",p):self.quick_input.clear()
    def schedule_ticket(self,ticket,existing=None):
        if not self.leave_editor():return
        d=FormDialog(self,"Schedule ticket work");d.resize(440,250);d.layout.addWidget(label(ticket["title"],"section"));f=QFormLayout();f.setSpacing(6);d.layout.addLayout(f)
        day=QDateEdit(QDate.fromString((existing or {}).get("date",D.day_key(self.data["settings"]["timezone"])),"yyyy-MM-dd"));day.setDisplayFormat("yyyy-MM-dd");day.setCalendarPopup(True);f.addRow("Date",day)
        start=QTimeEdit(QTime.fromString((existing or {}).get("start_time","09:00"),"HH:mm"));end=QTimeEdit(QTime.fromString((existing or {}).get("end_time","10:00"),"HH:mm"));start.setDisplayFormat("HH:mm");end.setDisplayFormat("HH:mm")
        f.addRow("Work session",row(start,label("to","muted"),end))
        hint=label("Ticket deadline stays "+(ticket["due_date"] or "unset")+".","muted");hint.setWordWrap(True);d.layout.addWidget(hint);d.finish_form()
        if d.exec()==QDialog.Accepted:
            payload={"ticket_id":ticket["id"],"date":day.date().toString("yyyy-MM-dd"),"start_time":start.time().toString("HH:mm"),"end_time":end.time().toString("HH:mm")}
            if existing:payload["id"]=existing["id"]
            self.execute("block.save",payload)
    def edit_section(self,section):
        if not self.leave_editor():return
        d=SectionDialog(self,section,[s for s in self.data["section"] if s["project_id"]==section["project_id"]])
        if d.exec()==QDialog.Accepted:
            self.execute("section.save",{"id":section["id"],"project_id":section["project_id"],**d.payload()})
    def map_rules(self):
        sections=[s for s in self.data["section"] if s["project_id"]==self.project_id]
        if not sections:self.new_section();return
        menu=QMenu(self)
        for section in sections:menu.addAction(section["name"]+" · "+(section["rule_field"]+" = "+section["rule_value"] if section["rule_field"] else "manual"),lambda checked=False,s=section:self.edit_section(s))
        sender=self.sender();menu.exec(sender.mapToGlobal(sender.rect().bottomLeft()) if isinstance(sender,QWidget) else self.mapToGlobal(self.rect().center()))
    def change_local_password(self):
        d=FormDialog(self,"Change local password");d.resize(430,170)
        hint=label("Choose any password. Your hub password stays unchanged.","muted");hint.setWordWrap(True);d.layout.addWidget(hint)
        value=QLineEdit();value.setEchoMode(QLineEdit.Password);value.setPlaceholderText("New local password");d.layout.addWidget(value);d.finish_form()
        if d.exec()!=QDialog.Accepted:return
        password=value.text();value.clear()
        self.run_async(lambda:self.store.change_password(password),lambda result:self.toast.setText("Local password updated."))
    def logout(self):
        if not self.leave_editor():return
        if self.jobs:self.toast.setText("Wait for the current operation before logging out.");return
        try:self.store.logout()
        except Exception as exc:error(self,exc);return
        self.sync.token=None;self.selected=None;self.search_text="";self.statusBar().hide();self.show_auth()

    def complete_ticket(self,ticket,checked=True):
        self.undo_action=lambda:self.execute("ticket.save",{"id":ticket["id"],"status":ticket["status"]})
        self.execute("ticket.save",{"id":ticket["id"],"status":"done" if checked else "ready"})
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"data") and self.data and self.page=="Today" and not self.rebuilding:
            narrow=self.width()-48-(280 if self.selected else 0)<840
            if narrow!=getattr(self,"_today_narrow",narrow):
                QTimer.singleShot(0,self.refresh_page)
            self._today_narrow=narrow
