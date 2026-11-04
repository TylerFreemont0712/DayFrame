"""Create native HWNDs without showing windows; verify DWM values on this Windows host."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication,QMainWindow
from dayframe.theme import apply_theme,CURRENT
from dayframe.window_frame import apply_native_frame,read_native_frame,colorref
from dayframe.widgets import FormDialog
if sys.platform!="win32":raise SystemExit("Run this check on Windows with QT_QPA_PLATFORM=windows.")
Path("build").mkdir(exist_ok=True)
app=QApplication([]);main=QMainWindow();dialog=FormDialog(main,"Frame check");report={}
for theme in ("graphite","amber","light","studio"):
    apply_theme({"theme":theme})
    report[theme]={}
    for name,widget in (("main",main),("dialog",dialog)):
        widget.winId();status=apply_native_frame(widget);actual=read_native_frame(widget)
        wanted={20:0 if CURRENT["mode"]=="paper" else 1,34:colorref(CURRENT["line"]),35:colorref(CURRENT["bg"]),36:colorref(CURRENT["text"])}
        assert status and all(value==0 for value in status.values()),status
        assert actual["20"]=={"status":0,"value":wanted[20]},(theme,name,actual)
        # Caption/border/text colors are set-only attributes on this DWM build.
        # Successful HRESULTs prove acceptance; do not claim readback for them.
        report[theme][name]={"set":status,"darkModeReadback":actual["20"],"requestedColors":wanted}
assert not main.isVisible() and not dialog.isVisible()
Path("build/native-frame-verification.json").write_text(json.dumps({"ok":True,"platform":app.platformName(),"windows":sys.getwindowsversion().build,"themes":report},indent=2),encoding="utf-8")
print("Windows accepted all frame attributes for 4 themes, main window and dialog; dark-mode readback matched. No windows were shown.")
dialog.close();main.close()
