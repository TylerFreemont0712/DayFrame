"""Desktop entry point and isolated packaging smoke check."""
import argparse
import json
import os
import sys
from pathlib import Path
from PySide6.QtCore import QTimer,QLockFile,QEventLoop
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication,QMessageBox
from .store import Store
from .ui import DayFrame
from .dialogs import AddDialog
from .theme import apply_theme
from . import __version__

def data_directory():
    # Retain the established profile identity across the DayFrame rename.
    if sys.platform=="win32":
        return Path(os.environ.get("LOCALAPPDATA",Path.home()/"AppData"/"Local"))/"TimeManager"
    return Path(os.environ.get("XDG_DATA_HOME",Path.home()/".local"/"share"))/"TimeManager"

def main():
    parser=argparse.ArgumentParser(description="DayFrame native desktop")
    parser.add_argument("--data-dir",type=Path,default=data_directory())
    parser.add_argument("--smoke-test",action="store_true",help="Create isolated example data, capture native screens, then exit.")
    parser.add_argument("--screenshots",type=Path)
    args=parser.parse_args()
    if args.smoke_test and "--data-dir" not in sys.argv:
        parser.error("--smoke-test requires an explicit, empty --data-dir")
    app=QApplication(sys.argv[:1]);app.setOrganizationName("DayFrame");app.setApplicationName("DayFrame")
    if sys.platform=="win32" and os.environ.get("QT_QPA_PLATFORM")=="offscreen":
        # Qt's offscreen plugin does not enumerate Windows system fonts.
        for name in ("segoeui.ttf","segoeuib.ttf","consola.ttf","consolab.ttf","georgia.ttf","georgiab.ttf","trebuc.ttf","trebucbd.ttf","bahnschrift.ttf"):
            font=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
            if font.exists():QFontDatabase.addApplicationFont(str(font))
    app.setApplicationVersion(__version__)
    args.data_dir.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(args.data_dir/"native-desktop.lock"));lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None,"DayFrame","This workspace is already open in another DayFrame window.")
        return 1
    store=Store(args.data_dir)
    if args.smoke_test and store.status()["configured"]:
        parser.error("--smoke-test must use an empty data directory")
    window=DayFrame(store)
    if args.smoke_test:
        store.register("preview","tyler");store.load_examples()
        tracked=next(t for t in store.list("ticket") if t["status"]=="doing")
        store.command("timer.action",{"action":"start","ticket_id":tracked["id"]});window.signed_in()
        window.resize(1280,800)
        captures=args.screenshots or args.data_dir/"screenshots";captures.mkdir(parents=True,exist_ok=True)
        def capture():
            try:
                screens=[]
                def grab(name):
                    app.processEvents();settle=QEventLoop();QTimer.singleShot(80,settle.quit);settle.exec()
                    path=captures/(name+".png");window.grab().save(str(path));screens.append(str(path))
                grab("native-today")
                window.navigate("Calendar");grab("native-calendar")
                window.resize(980,640);grab("native-calendar-small");window.resize(1280,800)
                window.navigate("Projects");grab("native-kanban")
                selected=next(t for t in window.data["ticket"] if t["status"]=="doing")
                window.select_ticket(selected["id"]);grab("native-inspector")
                project=next(p for p in window.data["project"] if p["project_key"]=="WEB")
                window.choose_project(project["id"]);grab("native-project-map")
                window.map_unsorted_open=True;window.refresh_page();grab("native-unsorted")
                window.map_unsorted_open=False;window.refresh_page()
                target=next((rect for section,rect in window.map.regions if section["name"]=="Calendar"),None)
                if target:
                    window.map.begin_hover("ticket",selected["id"]);window.map.consider_hover("ticket",selected["id"],target.center())
                    hold=QEventLoop();QTimer.singleShot(1600,hold.quit);hold.exec();grab("native-map-ghost");window.map.clear_hover()
                window.select_ticket(selected["id"]);grab("native-map-inspector")
                window.store.settings({"theme":"light"});apply_theme(window.store.settings());window.build_shell();window.navigate("Today");grab("native-light")
                for theme in ("amber","studio"):
                    window.store.settings({"theme":theme});apply_theme(window.store.settings());window.build_shell();window.navigate("Calendar");grab("native-"+theme)
                window.store.settings({"theme":"graphite"});apply_theme(window.store.settings());window.build_shell();window.navigate("Today")
                dialog=AddDialog(window,window.data,"event");dialog.title.setText("Weekly planning");dialog.show();app.processEvents()
                dialog_path=captures/"native-event-dialog.png";dialog.grab().save(str(dialog_path));screens.append(str(dialog_path));dialog.reject()
                window.store.command("project.save",{"id":project["id"],"name":"DayFrame","project_key":"DAYFR"})
                window.store.command("ticket.save",{"id":selected["id"],"labels":["bug","frontend"]})
                calendar_ticket=next(t for t in window.store.list("ticket") if t["title"]=="Build week timeline")
                window.store.command("ticket.save",{"id":calendar_ticket["id"],"labels":["feature","calendar"]})
                window.store.settings({"theme":"studio"});apply_theme(window.store.settings());window.build_shell();window.navigate("Today")
                window.select_ticket(selected["id"]);grab("native-studio-inspector");window.close_inspector();grab("native-studio-rows")
                window.navigate("Projects");window.choose_project(None);grab("native-labels-board")
                for theme in ("graphite","amber"):
                    window.store.settings({"theme":theme});apply_theme(window.store.settings());window.build_shell();window.navigate("Today")
                    capture=AddDialog(window,window.data,"ticket",project["id"]);capture.set_submit_handler(lambda *args:True)
                    capture.title.setText("Refine the calendar interactions")
                    capture.preset.setCurrentIndex(capture.preset.findData("bug" if theme=="amber" else "feature"))
                    capture.labels.input.setText("frontend");capture.labels.commit_pending();capture.show();app.processEvents()
                    path=captures/("native-quick-add-"+theme+".png");capture.grab().save(str(path));screens.append(str(path))
                    if theme=="graphite":
                        capture.more.setChecked(True);capture.detail_tabs.setCurrentIndex(1);capture.preset.setCurrentIndex(capture.preset.findData("feature"))
                        capture.labels.setText("feature, calendar");capture.section.setCurrentIndex(capture.section.count()-1);app.processEvents()
                        capture.fit_to_contents();app.processEvents();path=captures/"native-quick-add-details.png";capture.grab().save(str(path));screens.append(str(path))
                    capture.reject()
                report={"ok":True,"runtime":"PySide6 / Qt Widgets","screenshots":screens,"projects":len(window.data["project"]),"tickets":len(window.data["ticket"])}
                (captures/"smoke-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
                window.close()
            except Exception:
                import traceback
                (captures/"smoke-error.txt").write_text(traceback.format_exc(),encoding="utf-8");app.exit(1)
        QTimer.singleShot(600,capture)
    window.show()
    result=app.exec();store.close();lock.unlock();return result

if __name__=="__main__":
    raise SystemExit(main())
