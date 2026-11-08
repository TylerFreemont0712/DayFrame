"""Projects page: project tree, Map/Kanban/Details views, sections and filters."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QListWidgetItem, QMenu, QProgressBar, QTabBar, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QWidget
from ...core import domain as D
from ..views.kanban import card_size, project_color, TicketList
from ..views.project_map import ProjectMap, UnsortedList
from ..dialogs import SectionDialog
from ..theme import CURRENT as C, icon
from ..widgets import ask_text, button, column, combo, FormDialog, label, panel, row, scroll


class ProjectsPage:
    def projects_context(self):
        l=self.context_layout;l.addWidget(row(label("PROJECTS","section"),None,button("",self.toggle_context,"angle-double-left")))
        l.addWidget(button("All tickets",lambda:self.choose_project(None),"columns"))
        l.addWidget(button("Schedule",lambda:self.navigate("Calendar"),"calendar-alt"));l.addWidget(button("Time tracker",lambda:self.navigate("Time"),"clock"))
        l.addWidget(row(label("YOUR PROJECTS","muted"),None,button("",self.new_project,"plus")))
        tree=QTreeWidget();tree.setHeaderHidden(True);tree.setIndentation(12);tree.setObjectName("projectTree");tree.setRootIsDecorated(True)
        for p in self.data["project"]:
            if p["archived"]:continue
            item=QTreeWidgetItem([p["name"]]);item.setIcon(0,icon("folder",project_color(p["id"]).name()));item.setData(0,Qt.UserRole,("project",p["id"]));tree.addTopLevelItem(item)
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
        views=(["Map"] if self.project_id else [])+["Kanban","Details"]
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
                lst=TicketList(self,status)
                lst.setMinimumWidth(max(180,header.sizeHint().width(),lst.fontMetrics().horizontalAdvance("NEWPRO · FFFFFF")+55))
                for t in group:
                    item=QListWidgetItem(t["title"]);item.setData(Qt.UserRole,t["id"]);item.setData(Qt.UserRole+1,t)
                    item.setToolTip(t["title"]);item.setSizeHint(card_size(t));lst.addItem(item)
                cl.addWidget(lst,1);lanes.addWidget(col,1)
            self.work_layout.addWidget(scroll(board),1)
        else:
            fields=["Ticket","Title","Status","Priority","Due","Estimate","Tracked","Component","Labels"]
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
    def show_code(self):
        p,l=panel("Repository overview · planned")
        l.addWidget(label("Linked GitHub repository, branch, latest commit, release/tag, checks, and local sync status.","muted"))
        l.addWidget(label("Repository connections are a future milestone.","muted"))
        self.work_layout.addWidget(p);self.work_layout.addStretch()
    def new_child_ticket(self,parent):
        if self.leave_editor():self.quick_add("ticket",project_id=parent["project_id"],parent_id=parent["id"],more=True)
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
