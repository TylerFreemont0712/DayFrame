"""Quick Add dialog wiring for tickets and events (new and existing)."""
from __future__ import annotations
from ...core import domain as D
from ..dialogs import AddDialog


class CaptureMixin:
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
