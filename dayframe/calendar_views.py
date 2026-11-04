"""Native month, upcoming-event and Sunday-first weekly calendar widgets."""
from __future__ import annotations
import calendar
from datetime import date,datetime,timedelta
from PySide6.QtCore import Qt,QRectF,QPointF,QSize,QTimer,Signal
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QPolygonF
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QStyledItemDelegate,QScrollArea,QFrame,QSizePolicy,QStyle
from .theme import CURRENT as C,icon
from .widgets import label,button,row,combo,column
from . import planning as P,domain as D

def readable(item):
    span=item["date"]+(" → "+item["end_date"] if item["end_date"]!=item["date"] else "")
    times="All day" if item["all_day"] else item["start_time"]+"–"+item["end_time"]
    return span+" · "+times

def paint_item(p,rect,item,compact=False):
    color=QColor(P.event_color(item));fill=QColor(color);fill.setAlpha(53 if C.get("mode")!="paper" else 43)
    p.setPen(QPen(color,.9));p.setBrush(fill)
    radius=min(7,C.get("radius",4));p.drawRoundedRect(rect,radius,radius)
    p.fillRect(QRectF(rect.left()+1,rect.top()+3,3,max(1,rect.height()-6)),color)
    p.save();p.setClipRect(rect.adjusted(5,2,-3,-2));p.setPen(QColor(C["text"]))
    font=QFont(p.font());font.setBold(True);p.setFont(font)
    title=p.fontMetrics().elidedText(item["title"],Qt.ElideRight,max(1,int(rect.width()-13)))
    p.drawText(rect.adjusted(8,3,-4,-2),Qt.AlignTop,title)
    if not compact and rect.height()>=37:
        font.setBold(False);p.setFont(font);p.setPen(QColor(C["muted"]))
        p.drawText(rect.adjusted(8,19,-4,-2),Qt.AlignTop,item["start_time"]+"–"+item["end_time"])
        if item.get("location") and rect.height()>62:
            p.drawText(rect.adjusted(8,35,-4,-2),Qt.AlignTop|Qt.TextWordWrap,item["location"])
    p.restore()

class MonthGrid(QWidget):
    daySelected=Signal(str);dayActivated=Signal(str)
    def __init__(self,window,day):
        super().__init__();self.window=window;self.selected=day;self.month=date.fromisoformat(day).replace(day=1)
        self.setMinimumSize(220,200);self.setMouseTracking(True);self.regions=[]
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.selection_timer=QTimer(self);self.selection_timer.setSingleShot(True);self.selection_timer.timeout.connect(lambda:self.daySelected.emit(self.selected))
    def weeks(self):
        return calendar.Calendar(firstweekday=6).monthdatescalendar(self.month.year,self.month.month)
    def day_rect(self,day):
        target=date.fromisoformat(day) if isinstance(day,str) else day
        weeks=self.weeks();height=(self.height()-24)/len(weeks);width=self.width()/7
        for r,week in enumerate(weeks):
            if target in week:return QRectF(week.index(target)*width,24+r*height,width,height)
        return QRectF()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);self.regions=[]
        weeks=self.weeks();items=P.items_between(self.window.data,weeks[0][0],weeks[-1][-1])
        width=self.width()/7
        font=QFont(self.font());font.setPointSizeF(max(7,font.pointSizeF()-.5));p.setFont(font)
        for n,name in enumerate(("S","M","T","W","T","F","S")):
            p.setPen(QColor(C["muted"]));p.drawText(QRectF(n*width,0,width,22),Qt.AlignCenter,name)
        selected_week=P.sunday(self.selected);today=D.day_key(self.window.data["settings"]["timezone"])
        for week in weeks:
            for day in week:
                key=day.isoformat();rect=self.day_rect(day);self.regions.append((rect,key))
                if selected_week<=day<selected_week+timedelta(days=7):
                    tint=QColor(C["accent"]);tint.setAlpha(13);p.fillRect(rect,tint)
                p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(C["line"]),.5));p.drawRect(rect)
                marks=P.segments_for_day(items,key)
                all_day=[x for x in marks if x["all_day"] and x["kind"]=="event"]
                if all_day:
                    fill=QColor(P.event_color(all_day[0]));fill.setAlpha(28)
                    p.fillRect(rect.adjusted(2,19,-2,-3),fill)
                date_rect=QRectF(rect.right()-23,rect.top()+2,21,17)
                if key==self.selected:
                    p.setPen(Qt.NoPen);p.setBrush(QColor(C["accent"]));p.drawRoundedRect(date_rect,4,4);p.setPen(QColor(C["bg"]))
                else:p.setPen(QColor(C["accent"] if key==today else C["text"] if day.month==self.month.month else C["muted"]))
                p.drawText(date_rect,Qt.AlignCenter,str(day.day))
                y=rect.top()+23;available=rect.width()-7
                max_marks=max(1,int((rect.height()-28)/6))
                if len(marks)>max_marks:available=max(4,available-14)
                for item in marks[:max_marks]:
                    length=available if item["all_day"] else max(2.5,available*min(1,(item["end_min"]-item["start_min"])/720))
                    p.setPen(Qt.NoPen);p.setBrush(QColor(P.event_color(item)));p.drawRoundedRect(QRectF(rect.left()+3,y,length,3),1.5,1.5);y+=6
                if len(marks)>max_marks:
                    p.setPen(QColor(C["muted"]));p.drawText(QRectF(rect.right()-17,rect.top()+18,15,13),Qt.AlignRight|Qt.AlignTop,"+"+str(len(marks)-max_marks))
        p.end()
    def mousePressEvent(self,event):
        for rect,day in self.regions:
            if rect.contains(event.position()):self.selected=day;self.update();self.selection_timer.start(250);break
    def mouseDoubleClickEvent(self,event):
        for rect,day in self.regions:
            if rect.contains(event.position()):self.selection_timer.stop();self.dayActivated.emit(day);break
    def mouseMoveEvent(self,event):
        for rect,day in self.regions:
            if rect.contains(event.position()):
                items=P.day_items(self.window.data,day)
                self.setToolTip((day+"\n"+"\n".join(("All day" if x["all_day"] else x["start_time"]+"–"+x["end_time"])+"  "+x["title"] for x in items)).replace("<","‹").replace(">","›"));break

class MiniMonth(QWidget):
    def __init__(self,window,day):
        super().__init__();self.window=window
        layout=QVBoxLayout(self);layout.setContentsMargins(8,7,8,7);layout.setSpacing(5)
        self.grid=MonthGrid(window,day);self.caption=label("","section")
        previous=button("",lambda:self.change_month(-1),"chevron-left");next_=button("",lambda:self.change_month(1),"chevron-right")
        previous.setFixedWidth(25);next_.setFixedWidth(25)
        layout.addWidget(row(self.caption,None,previous,next_));layout.addWidget(self.grid,1)
        self.grid.daySelected.connect(window.calendar_selected)
        self.grid.dayActivated.connect(lambda d:window.quick_add("event",day=d,all_day=True))
        self.update_caption();self.setMinimumHeight(243);self.setMaximumHeight(290)
    def change_month(self,delta):
        m=self.grid.month;number=m.year*12+m.month-1+delta;self.grid.month=date(number//12,number%12+1,1)
        self.grid.update();self.update_caption()
    def update_caption(self):self.caption.setText(self.grid.month.strftime("%B %Y"))

class UpcomingDelegate(QStyledItemDelegate):
    def paint(self,p,option,index):
        item=index.data(Qt.UserRole)
        if not item:return
        p.save();rect=QRectF(option.rect).adjusted(2,2,-2,-2)
        color=QColor(P.event_color(item));p.setPen(Qt.NoPen);p.setBrush(color)
        p.drawRoundedRect(QRectF(rect.left()+3,rect.top()+7,3,rect.height()-12),1,1)
        if option.state & QStyle.State_MouseOver:
            fill=QColor(C["accent"]);fill.setAlpha(12);p.fillRect(rect,fill)
        p.setPen(QColor(C["text"]));font=QFont(p.font());font.setBold(True);p.setFont(font)
        p.drawText(rect.adjusted(12,4,-6,-3),Qt.AlignTop,p.fontMetrics().elidedText(item["title"],Qt.ElideRight,int(rect.width()-18)))
        font.setBold(False);p.setFont(font);p.setPen(QColor(C["muted"]))
        text=item["date"][5:]+" · "+("All day" if item["all_day"] else item["start_time"]+"–"+item["end_time"])
        p.drawText(rect.adjusted(12,22,-5,-2),Qt.AlignTop,text);p.restore()

class UpcomingPanel(QWidget):
    def __init__(self,window,day):
        super().__init__();self.window=window;l=QVBoxLayout(self);l.setContentsMargins(8,7,8,7);l.setSpacing(6)
        l.addWidget(row(label("Upcoming events","section"),None))
        self.list=QListWidget();self.list.setItemDelegate(UpcomingDelegate(self.list));self.list.setMinimumHeight(60);self.list.setMouseTracking(True)
        items=P.upcoming(window.data,day,20,False)
        for entry in items:
            item=QListWidgetItem(entry["title"]);item.setData(Qt.UserRole,entry);item.setSizeHint(QSize(200,46))
            item.setToolTip((readable(entry)+"\n"+entry.get("location","")+"\n"+entry.get("description","")).replace("<","‹").replace(">","›"));self.list.addItem(item)
        self.list.itemClicked.connect(lambda item:window.open_calendar_item(item.data(Qt.UserRole)))
        self.list.itemActivated.connect(lambda item:window.open_calendar_item(item.data(Qt.UserRole)) if not self.list.underMouse() else None)
        l.addWidget(self.list,1)
        if not items:l.addWidget(label("No upcoming events. Add one below.","muted"))
        self.preset=combo([(k,n) for k,n,color in P.EVENT_TYPES]);self.preset.setAccessibleName("Event template")
        l.addWidget(row(self.preset,button("Add",lambda:window.quick_add("event",day=day,event_type=self.preset.currentData()),"plus",True)))
        hint=label("Click an item for details and time editing.","muted");hint.setWordWrap(True);l.addWidget(hint)

class WeekHeader(QWidget):
    def __init__(self,week):
        super().__init__();self.week=week;self.regions=[];self.setMouseTracking(True)
        self.pending_day=week.day;self.selection_timer=QTimer(self);self.selection_timer.setSingleShot(True)
        self.selection_timer.timeout.connect(lambda:self.week.window.calendar_selected(self.pending_day))
        self.rows=[];ends=[]
        first=week.start;last=first+timedelta(days=6)
        for item in week.items:
            if not item["all_day"]:continue
            start=max(0,(date.fromisoformat(item["date"])-first).days);end=min(6,(date.fromisoformat(item["end_date"])-first).days)
            lane=next((n for n,value in enumerate(ends) if value<start),len(ends))
            if lane==len(ends):ends.append(end)
            else:ends[lane]=end
            self.rows.append((item,start,end,lane))
        self.band=max(48,min(96,len(ends)*18+10));self.setFixedHeight(46+self.band)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);self.regions=[]
        left=self.week.gutter;width=(self.width()-left)/7;today=D.day_key(self.week.window.data["settings"]["timezone"])
        p.fillRect(self.rect(),QColor(C["panel"]))
        for n in range(7):
            day=self.week.start+timedelta(days=n);x=left+n*width
            if day.isoformat()==self.week.day:
                fill=QColor(C["accent"]);fill.setAlpha(12);p.fillRect(QRectF(x,0,width,self.height()),fill)
            p.setPen(QColor(C["muted"]));p.drawText(QRectF(x,3,width,16),Qt.AlignCenter,day.strftime("%a").upper())
            font=QFont(self.font());font.setPointSizeF(font.pointSizeF()+2);font.setBold(True);p.setFont(font)
            p.setPen(QColor(C["accent"] if day.isoformat()==today else C["text"]));p.drawText(QRectF(x,19,width,23),Qt.AlignCenter,str(day.day));p.setFont(self.font())
            p.setPen(QPen(QColor(C["line"]),.6));p.drawLine(int(x),0,int(x),self.height())
        p.setPen(QColor(C["muted"]));p.drawText(QRectF(0,48,left-4,35),Qt.AlignRight|Qt.AlignTop,"all day")
        max_rows=max(1,int((self.band-4)/18))
        for item,start,end,lane in self.rows:
            if lane>=max_rows:continue
            rect=QRectF(left+start*width+3,47+lane*18,(end-start+1)*width-6,16)
            paint_item(p,rect,item,True);self.regions.append((rect,item))
        p.setPen(QPen(QColor(C["line"]),1));p.drawLine(0,self.height()-1,self.width(),self.height()-1);p.end()
    def mousePressEvent(self,event):
        for rect,item in reversed(self.regions):
            if rect.contains(event.position()):QTimer.singleShot(0,lambda x=item:self.week.window.open_calendar_item(x));return
        index=int((event.position().x()-self.week.gutter)/max(1,(self.width()-self.week.gutter)/7))
        if 0<=index<7:
            day=(self.week.start+timedelta(days=index)).isoformat()
            self.pending_day=day;self.selection_timer.start(250)
    def mouseDoubleClickEvent(self,event):
        self.selection_timer.stop()
        index=int((event.position().x()-self.week.gutter)/max(1,(self.width()-self.week.gutter)/7))
        if 0<=index<7:
            day=(self.week.start+timedelta(days=index)).isoformat()
            QTimer.singleShot(0,lambda:self.week.window.quick_add("event",day=day,all_day=True))

class WeekCanvas(QWidget):
    def __init__(self,week):
        super().__init__();self.week=week;self.regions=[];self.press=None;self.preview=None
        self.hour_height=48;self.setMinimumWidth(490);self.setFixedHeight(self.hour_height*24)
        self.setMouseTracking(True);self.setFocusPolicy(Qt.StrongFocus)
    def day_geometry(self,day):
        index=(date.fromisoformat(day)-self.week.start).days;width=(self.width()-self.week.gutter)/7
        return self.week.gutter+index*width,width
    def item_rect(self,item):
        left,width=self.day_geometry(item["day"]);available=width-6
        lanes=item.get("lanes",1);lane=item.get("lane",0)
        return QRectF(left+3+lane*available/lanes,item["start_min"]/60*self.hour_height+2,
                      available/lanes-2,max(16,(item["end_min"]-item["start_min"])/60*self.hour_height-3))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);self.regions=[]
        p.fillRect(self.rect(),QColor(C["bg"]));gutter=self.week.gutter;width=(self.width()-gutter)/7
        today=D.day_key(self.week.window.data["settings"]["timezone"])
        for n in range(7):
            day=(self.week.start+timedelta(days=n)).isoformat();x=gutter+n*width
            if day==self.week.day:
                fill=QColor(C["accent"]);fill.setAlpha(7);p.fillRect(QRectF(x,0,width,self.height()),fill)
            p.setPen(QPen(QColor(C["line"]),.6));p.drawLine(int(x),0,int(x),self.height())
        font=QFont(self.font());font.setPointSizeF(max(7,font.pointSizeF()-.5));p.setFont(font)
        for hour in range(24):
            y=hour*self.hour_height;p.setPen(QColor(C["muted"]));p.drawText(QRectF(0,y+3,gutter-7,16),Qt.AlignRight,f"{hour:02}:00")
            p.setPen(QPen(QColor(C["line"]),.7));p.drawLine(gutter,y,self.width(),y)
            p.setPen(QPen(QColor(C["line"]),.35,Qt.DotLine));p.drawLine(gutter,y+self.hour_height//2,self.width(),y+self.hour_height//2)
        for n in range(7):
            day=(self.week.start+timedelta(days=n)).isoformat()
            items=P.overlap_lanes(x for x in P.segments_for_day(self.week.items,day) if not x["all_day"])
            for item in items:
                rect=self.item_rect(item);paint_item(p,rect,item);self.regions.append((rect,item))
        now=datetime.now(D.ZoneInfo(self.week.window.data["settings"]["timezone"]))
        if self.week.start<=now.date()<=self.week.start+timedelta(days=6):
            x,width=self.day_geometry(today);y=(now.hour+now.minute/60)*self.hour_height
            p.setPen(QPen(QColor(C["danger"]),1.4));p.drawLine(int(x),int(y),int(x+width),int(y));p.setBrush(QColor(C["danger"]));p.drawEllipse(QPointF(x,y),3,3)
        if self.preview:
            item={**self.press["item"],**self.preview,"lane":0,"lanes":1};rect=self.item_rect(item)
            p.setPen(QPen(QColor(C["accent"]),2,Qt.DashLine));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect,4,4)
        p.end()
    def hit(self,point):
        return next(((r,x) for r,x in reversed(self.regions) if r.contains(point)),None)
    def mousePressEvent(self,event):
        found=self.hit(event.position())
        if found and found[1]["kind"] in ("event","block"):
            rect,item=found;self.press={"item":item,"pos":QPointF(event.position()),"resize":event.position().y()>rect.bottom()-6}
            self.preview=None;event.accept()
    def mouseMoveEvent(self,event):
        if self.press:
            item=self.press["item"]
            if item["date"]!=item["end_date"]:return
            distance=event.position()-self.press["pos"]
            if distance.manhattanLength()<5:return
            delta=round(distance.y()/self.hour_height*60/15)*15
            if self.press["resize"]:
                start=item["start_min"];end=max(start+15,min(1439,item["end_min"]+delta));day=item["day"]
            else:
                duration=item["end_min"]-item["start_min"];start=max(0,min(1439-duration,item["start_min"]+delta));end=start+duration
                col=max(0,min(6,int((event.position().x()-self.week.gutter)/max(1,(self.width()-self.week.gutter)/7))))
                day=(self.week.start+timedelta(days=col)).isoformat()
            self.preview={"start_min":start,"end_min":end,"day":day};self.update();return
        found=self.hit(event.position())
        if found:
            rect,item=found;self.setCursor(Qt.SizeVerCursor if event.position().y()>rect.bottom()-6 else Qt.PointingHandCursor)
            self.setToolTip((item["title"]+"\n"+readable(item)+"\n"+item.get("location","")+"\nDrag to move; drag the bottom edge to resize.").replace("<","‹").replace(">","›"))
        else:self.setCursor(Qt.ArrowCursor);self.setToolTip("")
    def mouseReleaseEvent(self,event):
        if not self.press:return
        item=self.press["item"];preview=self.preview;self.press=None;self.preview=None;self.update()
        if preview:
            QTimer.singleShot(0,lambda:self.week.window.move_calendar_item(item,preview["day"],P.clock(preview["start_min"]),P.clock(preview["end_min"])))
        else:QTimer.singleShot(0,lambda:self.week.window.open_calendar_item(item))
    def mouseDoubleClickEvent(self,event):
        if self.hit(event.position()):return
        width=(self.width()-self.week.gutter)/7;index=int((event.position().x()-self.week.gutter)/max(1,width))
        if 0<=index<7 and event.position().x()>=self.week.gutter:
            minute=max(0,min(1380,round(event.position().y()/self.hour_height*60/15)*15));day=(self.week.start+timedelta(days=index)).isoformat()
            QTimer.singleShot(0,lambda:self.week.window.quick_add("event",day=day,start_time=P.clock(minute),end_time=P.clock(minute+60)))

class WeekCalendar(QWidget):
    def __init__(self,window,day):
        super().__init__();self.window=window;self.day=day;self.start=P.sunday(day);self.gutter=43
        self.items=P.items_between(window.data,self.start,self.start+timedelta(days=6))
        l=QVBoxLayout(self);l.setContentsMargins(0,0,0,0);l.setSpacing(0)
        self.header=WeekHeader(self);l.addWidget(self.header,0,Qt.AlignLeft)
        self.canvas=WeekCanvas(self);self.scroll=QScrollArea();self.scroll.setFrameShape(QFrame.NoFrame);self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.scroll.setWidget(self.canvas);l.addWidget(self.scroll,1)
        self.scroll.verticalScrollBar().rangeChanged.connect(lambda:self.sync_header())
        QTimer.singleShot(0,self.initial_scroll)
    def sync_header(self):self.header.setFixedWidth(self.scroll.viewport().width())
    def initial_scroll(self):
        self.sync_header();self.scroll.verticalScrollBar().setValue(8*self.canvas.hour_height)
    def resizeEvent(self,event):
        super().resizeEvent(event);QTimer.singleShot(0,self.sync_header)
