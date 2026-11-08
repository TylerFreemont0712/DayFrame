"""Today's painted hour-by-hour agenda."""
from __future__ import annotations
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
from datetime import datetime
from ...core import domain as D, planning as P
from .calendar import paint_item, readable
from ..theme import CURRENT as C


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
