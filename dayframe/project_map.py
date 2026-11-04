"""Compact native project canvas. Ticket cards share the board's persistent records."""
import math
from PySide6.QtCore import Qt,QRectF,QPointF,QTimer,Signal,QElapsedTimer
from PySide6.QtGui import QColor,QPen,QBrush,QPainter,QPainterPath,QFont,QFontMetricsF,QPolygonF,QTransform,QDrag
from PySide6.QtWidgets import QApplication,QGraphicsView,QGraphicsScene,QGraphicsObject,QGraphicsItem,QMessageBox,QMenu
from .theme import CURRENT as C
from . import domain as D
from .labels import paint_label_pills

CARD_WIDTH=180
CARD_HEIGHT=74
GROUP_WIDTH=205
GROUP_GAP=15
CONTENT_X=12
CONTENT_Y=54
CARD_GAP=10

def text_font(scale=1.0,bold=False):
    font=QFont(QApplication.font())
    font.setPointSizeF(max(7.0,font.pointSizeF()*scale))
    font.setBold(bold)
    return font

class SectionHeader(QGraphicsObject):
    """Compact section title/rule with a real editing action on double-click."""
    def __init__(self,view,section,width,count):
        super().__init__();self.view=view;self.section=section;self.width=width;self.count=count
        if section["id"]:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Drag header: center nests; left/right creates before/after links. Hold 1.5 seconds, release to confirm. Double-click to edit.")
        self.setZValue(8);self.setFlag(QGraphicsItem.ItemIsMovable,bool(section['id']));self.setFlag(QGraphicsItem.ItemSendsGeometryChanges,True);self.origin=QPointF()
    def boundingRect(self):return QRectF(0,0,self.width,48)
    def paint(self,p,option,widget=None):
        p.setClipRect(self.boundingRect());p.setPen(QColor(C["text"]));p.setFont(text_font(1.0,True))
        title=self.section["name"]+"  ·  "+str(self.count)
        p.drawText(QRectF(12,7,self.width-24,19),Qt.AlignVCenter,QFontMetricsF(p.font()).elidedText(title,Qt.ElideRight,self.width-24))
        rule=(self.section["rule_field"]+": "+self.section["rule_value"]) if self.section["rule_field"] else ("Awaiting classification" if not self.section["id"] else "Manual placement")
        p.setPen(QColor(C["muted"]));p.setFont(text_font(.9))
        p.drawText(QRectF(12,27,self.width-24,16),Qt.AlignVCenter,QFontMetricsF(p.font()).elidedText(rule,Qt.ElideRight,self.width-24))
    def mousePressEvent(self,event):
        self.origin=QPointF(self.pos());self.view.begin_hover("section",self.section["id"]);super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event);self.view.consider_hover("section",self.section["id"],event.scenePos())
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event);self.setPos(self.origin)
        if self.view.hover_source:
            self.view.finish_hover("section",self.section["id"],event.scenePos())
    def contextMenuEvent(self,event):
        menu=QMenu();menu.addAction("Edit section",lambda:self.view.window.edit_section(self.section))
        menu.addAction("Add subsection",lambda:self.view.window.new_section(self.section["id"]))
        if self.section.get("parent_id"):menu.addAction("Move to root",lambda:self.view.commit_section(self.section,{"parent_id":""},"Move section to project root?"))
        if self.section.get("predecessor_ids"):menu.addAction("Clear before/after links",lambda:self.view.commit_section(self.section,{"predecessor_ids":[]},"Remove sequence links?"))
        menu.exec(event.screenPos())
    def mouseDoubleClickEvent(self,event):
        action=getattr(self.view.window,"edit_section",None)
        if self.section["id"] and callable(action):
            section=dict(self.section)
            QTimer.singleShot(0,lambda:action(section))
            event.accept()
        else:super().mouseDoubleClickEvent(event)

class TicketNode(QGraphicsObject):
    def __init__(self,view,ticket,placement):
        super().__init__();self.view=view;self.ticket=ticket;self.placement=placement
        self.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsFocusable|QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(ticket["title"]+"\n"+D.STATUS_NAMES[ticket["status"]]+" · "+ticket["priority"]+
                        ("\n"+ticket["description"] if ticket["description"] else "")+("\nLabels: "+", ".join(ticket["labels"]) if ticket["labels"] else "")+
                        ("\nManual placement" if placement and placement["manual"] else ""))
        self.setZValue(10);self.origin=QPointF()
    def boundingRect(self):return QRectF(0,0,CARD_WIDTH,CARD_HEIGHT)
    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.Antialiasing);p.setClipRect(self.boundingRect().adjusted(-1,-1,1,1))
        selected=self.isSelected() or getattr(self.view.window,"selected",None)==self.ticket["id"]
        pen=QPen(QColor(C["accent"] if selected else C["line"]),1.6 if selected else 1);pen.setCosmetic(True)
        p.setPen(pen);p.setBrush(QColor(C["raised"]));p.drawRoundedRect(self.boundingRect().adjusted(1,1,-1,-1),C.get("radius",5),C.get("radius",5))
        p.setPen(QColor(C["muted"]));p.setFont(text_font(.88))
        key=self.view.window.ticket_key(self.ticket)
        if self.placement and self.placement["manual"]:key+=" · pin"
        p.drawText(QRectF(10,5,CARD_WIDTH-34,15),Qt.AlignVCenter,QFontMetricsF(p.font()).elidedText(key,Qt.ElideRight,CARD_WIDTH-34))
        colors={"urgent":C["danger"],"high":"#edba71","medium":"#86c99a","low":C["muted"]}
        p.setPen(Qt.NoPen);p.setBrush(QColor(colors.get(self.ticket["priority"],C["muted"])))
        p.drawEllipse(QRectF(CARD_WIDTH-16,9,6,6))
        p.setFont(text_font(1.0,True));p.setPen(QColor(C["text"]))
        p.drawText(QRectF(10,22,CARD_WIDTH-20,30),Qt.AlignLeft|Qt.TextWordWrap,self.ticket["title"])
        p.setFont(text_font(.88));p.setPen(QColor(C["accent"] if selected else C["muted"]))
        status="Blocked" if self.view.window.blocked(self.ticket) else D.STATUS_NAMES[self.ticket["status"]]
        footer=status+" · "+str(int(self.ticket["estimate_min"]))+"m"
        footer_width=min(100,QFontMetricsF(p.font()).horizontalAdvance(footer))
        p.drawText(QRectF(10,55,footer_width,15),Qt.AlignVCenter,QFontMetricsF(p.font()).elidedText(footer,Qt.ElideRight,footer_width))
        if self.ticket["labels"]:paint_label_pills(p,QRectF(18+footer_width,54,CARD_WIDTH-28-footer_width,16),self.ticket["labels"],1)
    def mousePressEvent(self,event):
        self.origin=QPointF(self.pos());self.view.begin_hover("ticket",self.ticket["id"]);super().mousePressEvent(event)
        self.view.window.select_ticket(self.ticket["id"],rebuild=False)
        self.update()
    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event);self.view.consider_hover("ticket",self.ticket["id"],event.scenePos())
    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionHasChanged and not self.view.building:self.view.redraw_edges()
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if (self.pos()-self.origin).manhattanLength()<4:self.view.clear_hover();return
        self.view.finish_hover("ticket",self.ticket["id"],event.scenePos(),self)
    def contextMenuEvent(self,event):
        menu=QMenu();w=self.view.window;t=self.ticket
        menu.addAction("Open ticket",lambda:w.select_ticket(t["id"]))
        menu.addAction("Start timer",lambda:w.execute("timer.action",{"action":"start","ticket_id":t["id"]}))
        menu.addAction("Schedule work",lambda:w.schedule_ticket(t))
        menu.addAction("Create child ticket",lambda:w.new_child_ticket(t))
        menu.addAction("Complete ticket",lambda:w.complete_ticket(t))
        if t.get("parent_id"):menu.addAction("Remove parent link",lambda:self.view.commit_ticket(t,{"parent_id":""},"Remove this parent/child link?"))
        menu.exec(event.screenPos())

class ProjectMap(QGraphicsView):
    scaleChanged=Signal(int)
    def __init__(self,window,project_id):
        super().__init__();self.window=window;self.project_id=project_id;self.setScene(QGraphicsScene(self));self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag);self.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse);self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFrameShape(QGraphicsView.NoFrame);self.setFocusPolicy(Qt.StrongFocus);self.setAcceptDrops(True)
        self.nodes={};self.headers={};self.edges=[];self.regions=[];self.building=True;self._first_show=True
        self.hover_source=None;self.hover_target=None;self.hover_elapsed=QElapsedTimer();self.hover_armed=False;self.ghost_items=[]
        self.hover_timer=QTimer(self);self.hover_timer.setInterval(50);self.hover_timer.timeout.connect(self.advance_hover)
        self.tickets=[t for t in window.data["ticket"] if t["project_id"]==project_id and not t["archived"]]
        self.sections=sorted([s for s in window.data["section"] if s["project_id"]==project_id],key=lambda s:(s["sort_order"],s["name"],s["id"]))
        self.placements={p["ticket_id"]:p for p in window.data["placement"]};self.section_ids={s["id"] for s in self.sections}
        def section_for(t):
            value=self.placements.get(t["id"],{}).get("section_id","");return value if value in self.section_ids else ""
        self.unsorted=[t for t in self.tickets if not section_for(t)]
        groups={sec["id"]:[t for t in self.tickets if section_for(t)==sec["id"]] for sec in self.sections}
        children={sec["id"]:[c for c in self.sections if c.get("parent_id")==sec["id"]] for sec in self.sections}
        sizes={};coords={}
        def measure(section,seen):
            sid=section["id"]
            if sid in seen:return GROUP_WIDTH,154
            occupied=[];coordinates={}
            for t in groups[sid]:
                placement=self.placements.get(t["id"])
                if placement and placement["manual"]:
                    coordinates[t["id"]]=(placement["x"],placement["y"])
                    occupied.append(QRectF(placement["x"],placement["y"],CARD_WIDTH,CARD_HEIGHT).adjusted(-4,-4,4,4))
            auto_y=0
            by_id={t["id"]:t for t in groups[sid]}
            def depth(t,seen=None):
                seen=seen or set();parent=by_id.get(t.get("parent_id"))
                return 0 if not parent or parent["id"] in seen else 1+depth(parent,seen|{t["id"]})
            for t in sorted(groups[sid],key=depth):
                if t["id"] in coordinates:continue
                anchor=coordinates.get(t.get("parent_id"));auto_x=anchor[0]+CARD_WIDTH+30 if anchor else 0
                if anchor:auto_y=anchor[1]
                candidate=QRectF(auto_x,auto_y,CARD_WIDTH,CARD_HEIGHT)
                while any(candidate.intersects(rect) for rect in occupied):auto_y+=CARD_HEIGHT+CARD_GAP;candidate.moveTop(auto_y)
                coordinates[t["id"]]=(auto_x,auto_y);occupied.append(candidate);auto_y+=CARD_HEIGHT+CARD_GAP
            own_width=max([GROUP_WIDTH]+[CONTENT_X+x+CARD_WIDTH+12 for x,y in coordinates.values()])
            own_height=max([CONTENT_Y+12]+[CONTENT_Y+y+CARD_HEIGHT+12 for x,y in coordinates.values()])
            child_sizes=[measure(c,seen|{sid}) for c in children[sid]]
            width=max(own_width,sum(w for w,h in child_sizes)+max(0,len(child_sizes)-1)*GROUP_GAP+24 if child_sizes else 0)
            height=max(154,own_height+(max(h for w,h in child_sizes)+12 if child_sizes else 0))
            coords[sid]=coordinates;sizes[sid]=(width,height,own_height);return width,height
        roots=[s for s in self.sections if not s.get("parent_id") or s["parent_id"] not in self.section_ids]
        for section in roots:measure(section,set())
        def place(section,x,y,depth=0):
            sid=section["id"]
            if sid not in sizes:return
            width,height,own_height=sizes[sid];rect=QRectF(x,y,width,height);self.regions.append((section,rect))
            fill=QColor(C["panel"] if depth%2==0 else C["bg"])
            region=self.scene().addRect(rect,QPen(QColor(C["line"])),QBrush(fill));region.setZValue(-8+depth*.1)
            header=SectionHeader(self,section,width,len(groups[sid]));self.scene().addItem(header);header.setPos(x,y);self.headers[sid]=header
            for t in groups[sid]:
                node=TicketNode(self,t,self.placements.get(t["id"]));self.scene().addItem(node);nx,ny=coords[sid][t["id"]]
                node.setPos(x+CONTENT_X+nx,y+CONTENT_Y+ny);self.nodes[t["id"]]=node
                if getattr(window,"selected",None)==t["id"]:node.setSelected(True)
            child_x=x+12
            for child in children[sid]:
                place(child,child_x,y+own_height,depth+1);child_x+=sizes[child["id"]][0]+GROUP_GAP
        next_x=0
        for section in roots:
            place(section,next_x,0);next_x+=sizes[section["id"]][0]+GROUP_GAP
        if not self.sections:
            hint=self.scene().addText("Add a section to organize this project.\nUnsorted tickets are in the side tray.")
            hint.setDefaultTextColor(QColor(C["muted"]));hint.setFont(text_font());hint.setPos(20,25)
        self.building=False;self.redraw_edges();self.update_scene_bounds()
    def update_scene_bounds(self):
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-12,-12,12,12))
    def drawBackground(self,p,rect):
        p.fillRect(rect,QColor(C["bg"]))
        spacing=20 if self.transform().m11()>=.6 else 40
        pen=QPen(QColor(C["line"]));pen.setCosmetic(True);pen.setWidthF(1)
        p.setPen(pen)
        points=[]
        left=math.floor(rect.left()/spacing)*spacing;top=math.floor(rect.top()/spacing)*spacing
        for x in range(int(left),int(rect.right())+spacing,spacing):
            for y in range(int(top),int(rect.bottom())+spacing,spacing):points.append(QPointF(x,y))
        if points:p.drawPoints(QPolygonF(points))
    def add_edge(self,start,end,color,style,tooltip):
        path=QPainterPath(start);bend=max(34,abs(end.x()-start.x())/2);path.cubicTo(start+QPointF(bend,0),end-QPointF(bend,0),end)
        pen=QPen(QColor(color),1.25,style);pen.setCosmetic(True);edge=self.scene().addPath(path,pen);edge.setZValue(3);edge.setToolTip(tooltip)
        arrow=self.scene().addPolygon(QPolygonF([end,end+QPointF(-7,-3.5),end+QPointF(-7,3.5)]),QPen(Qt.NoPen),QBrush(QColor(color)));arrow.setZValue(3)
        self.edges.extend([edge,arrow])
    def redraw_edges(self):
        if self.building:return
        for item in self.edges:self.scene().removeItem(item)
        self.edges=[]
        for node in self.nodes.values():
            links=[(x,Qt.DashLine,"#dfae65","Dependency") for x in node.ticket["dependencies"]]
            if node.ticket.get("parent_id"):links.append((node.ticket["parent_id"],Qt.SolidLine,C["accent"],"Parent → child"))
            for target,style,color,name in links:
                other=self.nodes.get(target)
                if other:self.add_edge(QPointF(other.sceneBoundingRect().right(),other.sceneBoundingRect().center().y()),
                    QPointF(node.sceneBoundingRect().left(),node.sceneBoundingRect().center().y()),color,style,name)
        for section in self.sections:
            node=self.headers.get(section["id"])
            if not node:continue
            for target in section.get("predecessor_ids",[]):
                other=self.headers.get(target)
                if other:self.add_edge(QPointF(other.sceneBoundingRect().right(),other.sceneBoundingRect().center().y()),
                    QPointF(node.sceneBoundingRect().left(),node.sceneBoundingRect().center().y()),"#ba94e5",Qt.DotLine,"Section sequence: before → after")
    def begin_hover(self,kind,source):
        self.clear_hover();self.hover_source=(kind,source);self.hover_timer.start()
    def target_at(self,kind,source,pos):
        if kind=="ticket":
            for tid,node in self.nodes.items():
                if tid==source:continue
                rect=node.sceneBoundingRect().adjusted(-14,0,14,0)
                if rect.contains(pos):
                    if pos.x()<=rect.left()+38:return ("ticket",tid,"left",rect)
                    if pos.x()>=rect.right()-38:return ("ticket",tid,"right",rect)
        candidates=[]
        for section,rect in self.regions:
            if kind=="section" and source in [s["id"] for s in D.section_path(self.sections,section["id"])]:continue
            if rect.contains(pos):candidates.append((section,rect))
        if not candidates:return None
        section,rect=min(candidates,key=lambda pair:pair[1].width()*pair[1].height())
        zone="center"
        if kind=="section":
            if pos.x()<rect.left()+24:zone="left"
            elif pos.x()>rect.right()-24:zone="right"
        return ("section",section["id"],zone,rect)
    def consider_hover(self,kind,source,pos):
        if self.hover_source!=(kind,source):self.begin_hover(kind,source)
        target=self.target_at(kind,source,pos)
        if (target[:3] if target else None)!=(self.hover_target[:3] if self.hover_target else None):
            self.hover_target=target;self.hover_elapsed.start();self.hover_armed=False
        self.draw_ghost()
    def advance_hover(self):
        if self.hover_target:
            self.hover_armed=self.hover_elapsed.elapsed()>=1500;self.draw_ghost()
    def ghost_text(self):
        kind,source=self.hover_source;target_kind,target,zone,rect=self.hover_target
        if target_kind=="ticket":
            return "Make dragged ticket a CHILD" if zone=="right" else "Make dragged ticket the PARENT"
        if kind=="ticket":return "Place ticket INSIDE section · apply rules"
        return "Nest section INSIDE" if zone=="center" else "Section comes BEFORE target" if zone=="left" else "Section comes AFTER target"
    def draw_ghost(self):
        for item in self.ghost_items:self.scene().removeItem(item)
        self.ghost_items=[]
        if not self.hover_target:return
        target_kind,target,zone,rect=self.hover_target;rect=QRectF(rect)
        if zone=="left":rect.setWidth(24)
        elif zone=="right":rect.setLeft(rect.right()-24)
        color=QColor(C["accent"] if self.hover_armed else "#dfae65");fill=QColor(color);fill.setAlpha(35)
        ghost=self.scene().addRect(rect,QPen(color,2,Qt.DashLine),QBrush(fill));ghost.setZValue(10000)
        percent=min(100,int(self.hover_elapsed.elapsed()/15)) if self.hover_elapsed.isValid() else 0
        text=self.ghost_text()+(" · RELEASE TO CONFIRM" if self.hover_armed else " · hold "+str(percent)+"%")
        caption=self.scene().addSimpleText(text,text_font(.95,True));caption.setBrush(color);visible=self.mapToScene(self.viewport().rect()).boundingRect()
        caption.setPos(max(visible.left()+8,min(rect.left(),visible.right()-caption.boundingRect().width()-8)),max(visible.top()+8,rect.top()-23));caption.setZValue(10002)
        bg=self.scene().addRect(caption.sceneBoundingRect().adjusted(-4,-2,4,2),QPen(color),QBrush(QColor(C["bg"])));bg.setZValue(10001)
        self.ghost_items=[ghost,bg,caption]
    def clear_hover(self):
        self.hover_timer.stop()
        for item in self.ghost_items:self.scene().removeItem(item)
        self.ghost_items=[];self.hover_source=None;self.hover_target=None;self.hover_armed=False
    def remember(self,kind,record):
        return {"kind":kind,"data":{key:record[key] for key in ("id",*D.DEFINITIONS[kind]["fields"]) if key in record}}
    def apply_confirmed(self,method,payload,records,message):
        if QMessageBox.question(self.window,"Confirm map change",message+"\n\nApply this change? Ctrl+Z can undo it.",QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        def commit():
            if self.window.execute(method,payload,refresh=False):
                self.window.undo_action=lambda:self.window.execute("map.restore",{"records":records})
                self.window.refresh()
        QTimer.singleShot(0,commit)
    def commit_ticket(self,ticket,patch,message):
        self.apply_confirmed("ticket.save",{"id":ticket["id"],**patch},[self.remember("ticket",ticket)],message)
    def commit_section(self,section,patch,message):
        records=[self.remember("section",section)]
        if "parent_id" in patch:
            records.extend(self.remember("ticket",t) for t in self.tickets)
            proposed=[{**s,**patch} if s["id"]==section["id"] else s for s in self.sections]
            affected=[]
            for placement in self.placements.values():
                if section["id"] in [s["id"] for s in D.section_path(proposed,placement["section_id"])]:
                    ticket=next((t for t in self.tickets if t["id"]==placement["ticket_id"]),None)
                    if ticket:
                        changes=D.section_classification(proposed,placement["section_id"],ticket)
                        if changes:affected.append(ticket["title"]+": "+str(changes))
            if affected:message+="\nInherited rule changes:\n"+"\n".join(affected[:8])+("\n…" if len(affected)>8 else "")
        records.extend(self.remember("placement",p) for p in self.placements.values())
        self.apply_confirmed("section.save",{"id":section["id"],**patch},records,message)
    def finish_hover(self,kind,source,pos,node=None):
        target=self.hover_target;armed=self.hover_armed
        if node:node.setPos(node.origin)
        self.clear_hover()
        if not target:return
        target_kind,target_id,zone,rect=target
        if kind=="ticket":
            ticket=next(t for t in self.tickets if t["id"]==source);old=self.placements.get(source,{})
            # Position changes within the same section do not classify or link.
            if target_kind=="section" and old.get("section_id")==target_id:
                if node:
                    payload={"ticket_id":source,"section_id":target_id,"manual":1,"x":max(0,pos.x()-rect.x()-CONTENT_X-CARD_WIDTH/2),"y":max(0,pos.y()-rect.y()-CONTENT_Y-CARD_HEIGHT/2)}
                    records=[self.remember("placement",old)] if old else []
                    def move():
                        if self.window.execute("placement.save",payload,refresh=False):
                            self.window.undo_action=lambda:self.window.execute("map.restore",{"records":records});self.window.refresh()
                    QTimer.singleShot(0,move)
                return
        if not armed:
            if hasattr(self.window,"toast"):self.window.toast.setText("Hold over the target for 1.5 seconds, then release to confirm.")
            return
        if kind=="ticket" and target_kind=="ticket":
            other=next(t for t in self.tickets if t["id"]==target_id)
            parent,child=(other,ticket) if zone=="right" else (ticket,other)
            records=[self.remember("ticket",child)]
            if child["id"] in self.placements:records.append(self.remember("placement",self.placements[child["id"]]))
            inherited=list(dict.fromkeys(child["labels"]+parent["labels"]))
            message=parent["title"]+" → "+child["title"]+"\nCreate parent/child link. Child inherits parent tags and empty component/milestone fields.\nTags: "+(", ".join(inherited) or "none")
            if child.get("parent_id"):message+="\nThis replaces the child's current parent link."
            self.apply_confirmed("ticket.relate",{"parent_id":parent["id"],"child_id":child["id"]},records,message)
        elif kind=="ticket":
            patch=D.section_classification(self.sections,target_id,ticket);records=[self.remember("ticket",ticket)]
            if old:records.append(self.remember("placement",old))
            changes="\n".join(k+": "+str(v) for k,v in patch.items()) or "No tag or field changes."
            self.apply_confirmed("placement.save",{"ticket_id":source,"section_id":target_id,"manual":1,"x":max(0,pos.x()-rect.x()-CONTENT_X-CARD_WIDTH/2),"y":max(0,pos.y()-rect.y()-CONTENT_Y-CARD_HEIGHT/2)},
                                 records,"Move into "+next(s["name"] for s in self.sections if s["id"]==target_id)+"\n"+changes)
        else:
            section=next(s for s in self.sections if s["id"]==source);other=next(s for s in self.sections if s["id"]==target_id)
            if zone=="center":self.commit_section(section,{"parent_id":target_id},"Nest "+section["name"]+" inside "+other["name"]+"?")
            elif zone=="right":self.commit_section(section,{"predecessor_ids":list(dict.fromkeys(section.get("predecessor_ids",[])+[target_id]))},section["name"]+" comes AFTER "+other["name"])
            else:self.commit_section(other,{"predecessor_ids":list(dict.fromkeys(other.get("predecessor_ids",[])+[source]))},section["name"]+" comes BEFORE "+other["name"])
    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat("application/x-timemanager-ticket"):event.acceptProposedAction()
        else:super().dragEnterEvent(event)
    def dragMoveEvent(self,event):
        if event.mimeData().hasFormat("application/x-timemanager-ticket"):
            source=bytes(event.mimeData().data("application/x-timemanager-ticket")).decode()
            if any(t["id"]==source for t in self.tickets):
                self.consider_hover("ticket",source,self.mapToScene(event.position().toPoint()));event.acceptProposedAction()
        else:super().dragMoveEvent(event)
    def dragLeaveEvent(self,event):
        self.clear_hover();event.accept()
    def dropEvent(self,event):
        if event.mimeData().hasFormat("application/x-timemanager-ticket"):
            source=bytes(event.mimeData().data("application/x-timemanager-ticket")).decode()
            if any(t["id"]==source for t in self.tickets):
                self.finish_hover("ticket",source,self.mapToScene(event.position().toPoint()));event.acceptProposedAction()
        else:super().dropEvent(event)
    def zoom_percent(self):
        return round(self.transform().m11()*100)
    def zoom_by(self,factor):
        if not math.isfinite(factor) or factor<=0:return self.zoom_percent()
        current=self.transform().m11();target=min(2.5,max(.3,current*factor))
        self.scale(target/current,target/current);self.scaleChanged.emit(self.zoom_percent())
        return self.zoom_percent()
    def fit(self):
        self.update_scene_bounds()
        bounds=self.sceneRect()
        factor=min(1.0,max(.3,min(max(1,self.viewport().width()-12)/max(1,bounds.width()),
                                max(1,self.viewport().height()-12)/max(1,bounds.height()))))
        self.setTransform(QTransform.fromScale(factor,factor))
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        self.scaleChanged.emit(self.zoom_percent())
    def showEvent(self,event):
        super().showEvent(event)
        if self._first_show:
            self._first_show=False;QTimer.singleShot(0,self.fit)
    def wheelEvent(self,event):
        if event.modifiers() & Qt.ControlModifier:
            self.zoom_by(1.15 if event.angleDelta().y()>0 else 1/1.15);event.accept()
        else:super().wheelEvent(event)
    def keyPressEvent(self,event):
        if event.modifiers() & Qt.ControlModifier and event.key() in (Qt.Key_Plus,Qt.Key_Equal,Qt.Key_Minus,Qt.Key_0):
            if event.key()==Qt.Key_0:self.fit()
            else:self.zoom_by(1/1.15 if event.key()==Qt.Key_Minus else 1.15)
            event.accept()
        else:super().keyPressEvent(event)
