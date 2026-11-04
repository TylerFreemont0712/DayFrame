"""Shared native tag editor and deterministic label colors."""
import hashlib
from PySide6.QtCore import Qt,QSize,QRect,Signal,QEvent,QTimer
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QIcon
from PySide6.QtWidgets import QWidget,QFrame,QLayout,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QMenu,QCompleter
from .theme import CURRENT as C
from .widgets import button,label

LABEL_PRESETS={"bug":"#e76d79","feature":"#60cdb1","task":"#9badc3","improvement":"#b596e4","documentation":"#80ace8","maintenance":"#dfb274"}
CUSTOM_COLORS=("#8faac9","#b49acf","#80b8a8","#d2a68c","#b3ba8f","#a3a8d2")

def label_color(name):
    key=name.strip().casefold()
    return LABEL_PRESETS.get(key) or CUSTOM_COLORS[int.from_bytes(hashlib.blake2b(key.encode(),digest_size=2).digest(),"big")%len(CUSTOM_COLORS)]

def label_choices(snapshot):
    return list(dict.fromkeys([*LABEL_PRESETS,*sorted({tag for t in snapshot.get("ticket",[]) for tag in t.get("labels",[])},key=str.casefold)]))

def colors(name):
    base=QColor(label_color(name));fill=QColor(base);fill.setAlpha(35 if C.get("mode")!="paper" else 30)
    return base,base.darker(175) if C.get("mode")=="paper" else base.lighter(115),fill

def paint_label_pills(p,rect,names,max_count=2):
    order={key:i for i,key in enumerate(LABEL_PRESETS)}
    names=sorted(names,key=lambda n:order.get(n.casefold(),100))
    p.save();x=rect.x();shown=0
    for name in names:
        available=rect.right()-x
        if shown>=max_count or available<24:break
        width=min(92,p.fontMetrics().horizontalAdvance(name)+12,available)
        r=QRect(round(x),round(rect.y()),round(width),round(rect.height()))
        base,fg,fill=colors(name);p.setPen(QPen(base,.6));p.setBrush(fill);radius=min(6,C.get("radius",3));p.drawRoundedRect(r,radius,radius)
        p.setPen(fg);p.drawText(r.adjusted(5,0,-5,0),Qt.AlignVCenter|Qt.AlignLeft,p.fontMetrics().elidedText(name,Qt.ElideRight,max(0,r.width()-10)))
        x+=width+4;shown+=1
    if shown<len(names) and rect.right()-x>=18:
        p.setPen(QColor(C["muted"]));p.drawText(QRect(round(x),round(rect.y()),int(rect.right()-x),round(rect.height())),Qt.AlignVCenter,"+"+str(len(names)-shown))
    p.restore()

class FlowLayout(QLayout):
    def __init__(self,parent=None):
        super().__init__(parent);self.items=[];self.setContentsMargins(0,0,0,0);self.setSpacing(4)
    def addItem(self,item):self.items.append(item)
    def count(self):return len(self.items)
    def itemAt(self,index):return self.items[index] if 0<=index<len(self.items) else None
    def takeAt(self,index):return self.items.pop(index) if 0<=index<len(self.items) else None
    def expandingDirections(self):return Qt.Orientations()
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self.arrange(QRect(0,0,width,0),True)
    def setGeometry(self,rect):super().setGeometry(rect);self.arrange(rect,False)
    def sizeHint(self):return self.minimumSize()
    def minimumSize(self):
        size=QSize(0,0)
        for item in self.items:size=size.expandedTo(item.minimumSize())
        return size
    def arrange(self,rect,test):
        x,y=rect.x(),rect.y();line=0;right=rect.right()+1
        for item in self.items:
            size=item.sizeHint();width=min(size.width(),max(1,rect.width()))
            if x+width>right and line:y+=line+self.spacing();x=rect.x();line=0
            if not test:item.setGeometry(QRect(x,y,width,size.height()))
            x+=width+self.spacing();line=max(line,size.height())
        return y+line-rect.y()

class LabelsEditor(QWidget):
    textChanged=Signal(str)
    labelsChanged=Signal(list)
    def __init__(self,text="",suggestions=(),parent=None):
        super().__init__(parent);self.values=[];self.known=[];self._updating=False
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(4)
        self.chips=QWidget();self.flow=FlowLayout(self.chips);outer.addWidget(self.chips)
        controls=QWidget();line=QHBoxLayout(controls);line.setContentsMargins(0,0,0,0);line.setSpacing(4)
        self.input=QLineEdit();self.input.setPlaceholderText("Add a label…");self.input.setAccessibleName("Add label");self.input.installEventFilter(self)
        add=button("",self.commit_pending,"plus");add.setFixedWidth(25);add.setToolTip("Add label");add.setAccessibleName("Add label")
        self.presets=button("Labels",None,"tags");self.presets.setToolTip("Preset and previously used labels")
        self.menu=QMenu(self);self.presets.setMenu(self.menu)
        line.addWidget(self.input,1);line.addWidget(add);line.addWidget(self.presets);outer.addWidget(controls)
        self.completer=QCompleter([],self);self.completer.setCaseSensitivity(Qt.CaseInsensitive);self.input.setCompleter(self.completer)
        self.completer.activated.connect(self.choose)
        self.input.textChanged.connect(self.pending_changed);self.set_suggestions(suggestions);self.setText(text)
    def set_suggestions(self,suggestions):
        self.known=list(dict.fromkeys([*LABEL_PRESETS,*suggestions,*self.known]))
        self.completer.model().setStringList(self.known);self.update_menu()
    def setPlaceholderText(self,text):self.input.setPlaceholderText(text)
    def labels(self):
        return list(dict.fromkeys([*self.values,*[s.strip() for s in self.input.text().split(",") if s.strip()]]))
    def text(self):return ", ".join(self.labels())
    def setText(self,text):
        self._updating=True;self.values=list(dict.fromkeys(s.strip() for s in text.split(",") if s.strip()));self.input.clear();self._updating=False
        self.refresh_chips();QTimer.singleShot(0,self.update_menu);self.textChanged.emit(self.text());self.labelsChanged.emit(list(self.values))
    def choose(self,text):
        self.input.setText(text);self.commit_pending()
    def pending_changed(self,text):
        if self._updating:return
        if "," in text:self.commit_pending()
        else:self.textChanged.emit(self.text())
    def commit_pending(self):
        tokens=[s.strip() for s in self.input.text().split(",") if s.strip()]
        if not tokens:return
        tokens=[s.casefold() if s.casefold() in LABEL_PRESETS else s for s in tokens]
        self.set_suggestions(tokens);self.setText(", ".join(dict.fromkeys([*self.values,*tokens])))
    def update_selection(self,values):
        pending=self.input.text();self.setText(", ".join(values))
        if pending:self.input.setText(pending)
    def remove(self,name):self.update_selection([x for x in self.values if x!=name])
    def toggle(self,name):
        if name in self.values:self.remove(name)
        else:self.update_selection([*self.values,name])
    def update_menu(self):
        if not hasattr(self,"menu"):return
        self.menu.clear()
        for name in self.known:
            pm=QPixmap(12,12);pm.fill(Qt.transparent);p=QPainter(pm);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);p.setBrush(QColor(label_color(name)));p.drawEllipse(2,2,8,8);p.end()
            action=self.menu.addAction(QIcon(pm),name);action.setCheckable(True);action.setChecked(name in self.values)
            action.triggered.connect(lambda checked=False,n=name:self.toggle(n))
    def refresh_chips(self):
        while self.flow.count():
            item=self.flow.takeAt(0);item.widget().hide();item.widget().deleteLater()
        for name in self.values:
            chip=QFrame();chip.setObjectName("tagChip");chip.setToolTip(name);layout=QHBoxLayout(chip);layout.setContentsMargins(6,1,3,1);layout.setSpacing(3)
            text=label(chip.fontMetrics().elidedText(name,Qt.ElideRight,112));text.setToolTip(name)
            remove=QPushButton("×");remove.setAutoDefault(False);remove.setObjectName("tagRemove");remove.setFixedSize(16,17);remove.setAccessibleName("Remove label "+name)
            remove.clicked.connect(lambda checked=False,n=name:self.remove(n));layout.addWidget(text);layout.addWidget(remove);self.flow.addWidget(chip)
            base,fg,fill=colors(name);radius=min(6,C.get("radius",3))
            chip.setStyleSheet("QFrame#tagChip {background:rgba("+str(fill.red())+","+str(fill.green())+","+str(fill.blue())+",38);border:1px solid "+base.name()+";border-radius:"+str(radius)+"px;} QLabel {color:"+fg.name()+";background:transparent;border:0;padding:0;} QPushButton#tagRemove {color:"+fg.name()+";background:transparent;border:0;padding:0;} QPushButton#tagRemove:hover {background:"+C["raised"]+";}")
        self.chips.setVisible(bool(self.values));self.flow.invalidate();self.chips.updateGeometry();self.updateGeometry()
    def eventFilter(self,obj,event):
        if obj is self.input and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Return,Qt.Key_Enter):
            self.commit_pending();self.completer.popup().hide();return True
        return super().eventFilter(obj,event)
