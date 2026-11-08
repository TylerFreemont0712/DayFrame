import hashlib
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from dayframe.data.store import Store
from dayframe.core import domain as D

BASE=Path("build/test-data")
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(BASE/uuid.uuid4().hex);self.store.register("tester","test-password-123")
        self.project=self.store.command("project.save",{"name":"Test","project_key":"T"})
    def tearDown(self):self.store.close()
    def ticket(self,**p):return self.store.command("ticket.save",{"project_id":self.project["id"],"title":"A ticket",**p})
    def test_password_legacy_and_scope(self):
        salt="0123456789abcdef"
        expected=hashlib.scrypt(b"test-password-123",salt=salt.encode(),n=131072,r=8,p=1,dklen=32,maxmem=256*1024*1024).hex()
        self.assertEqual(D.hash_password("test-password-123",salt)[1],expected)
        self.store.logout()
        with self.assertRaises(ValueError):self.store.snapshot()
        with self.assertRaises(ValueError):self.store.login("tester","incorrect-pass")
        self.store.login("tester","test-password-123")
    def test_ticket_is_persistent_and_normalized(self):
        t=self.ticket(labels=["ui","urgent"],checklist=[{"text":"Implement","done":False}])
        root=self.store.root;self.store.close();self.store=Store(root);self.store.login("tester","test-password-123")
        self.assertEqual(self.store.read("ticket",t["id"])["labels"],["ui","urgent"])
        self.assertEqual(self.store.snapshot()["placement"][0]["ticket_id"],t["id"])
    def test_atomic_dependency_failure(self):
        a=self.ticket();b=self.ticket(dependencies=[a["id"]])
        before=self.store.snapshot()["pending"]
        with self.assertRaises(ValueError):self.store.command("ticket.save",{"id":a["id"],"title":"Must roll back","dependencies":[b["id"]]})
        self.assertEqual(self.store.read("ticket",a["id"])["title"],"A ticket")
        self.assertEqual(self.store.snapshot()["pending"],before)
    def test_map_rules_manual_and_undo(self):
        section=self.store.command("section.save",{"project_id":self.project["id"],"name":"UI","rule_field":"component","rule_value":"UI"})
        t=self.ticket(component="UI")
        old=self.store.read("placement",t["id"]);self.assertEqual(old["section_id"],section["id"])
        self.store.command("placement.save",{"ticket_id":t["id"],"section_id":"","x":20,"y":30})
        self.store.command("ticket.save",{"id":t["id"],"component":"UI"})
        self.assertEqual(self.store.read("placement",t["id"])["section_id"],"")
        self.store.command("placement.save",{"ticket_id":t["id"],"section_id":"","manual":0})
        self.assertEqual(self.store.read("placement",t["id"])["section_id"],section["id"])
        self.store.command("placement.restore",{"ticket_id":t["id"],"classification":{"component":"UI","labels":[],"milestone":""},"placement":{k:v for k,v in old.items() if k!="id"}})
        self.assertEqual(self.store.read("placement",t["id"]),old)
    def test_timer_segments_and_restart(self):
        t=self.ticket();self.store.timer_action("start",t["id"],now=100000)
        self.store.timer_action("pause",now=160000)
        self.assertEqual(self.store.list("entry")[0]["end_at"],160000)
        self.assertEqual(self.store.read("timer","active")["session_ms"],60000)
        self.store.timer_action("start",now=200000)
        root=self.store.root;self.store.close();self.store=Store(root);self.store.login("tester","test-password-123")
        self.assertEqual(self.store.read("timer","active")["start_at"],200000)
        self.store.timer_action("stop",now=230000)
        self.assertEqual(sum(e["end_at"]-e["start_at"] for e in self.store.list("entry")),90000)
        with self.assertRaises(ValueError):self.store.command("time.add",{"start_at":200,"end_at":100})
    def test_deadlines_do_not_roll(self):
        t=self.ticket(due_date="2020-01-01");self.store.snapshot()
        self.assertEqual(self.store.read("ticket",t["id"])["due_date"],"2020-01-01")
    def test_backup_import_copy(self):
        self.ticket();backup=BASE/(uuid.uuid4().hex+".db");self.store.backup(backup)
        before=hashlib.sha256(backup.read_bytes()).hexdigest()
        imported=Store(BASE/uuid.uuid4().hex)
        try:
            imported.import_database(backup);imported.login("tester","test-password-123")
            self.assertEqual(len(imported.list("ticket")),1)
            imported.command("ticket.save",{"id":imported.list("ticket")[0]["id"],"title":"Changed copy"})
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),before)
            with self.assertRaises(ValueError):imported.import_database(backup)
        finally:imported.close()
    def test_all_day_event_and_calendar_dst(self):
        self.store.command("event.save",{"title":"Trip","date":"2026-11-22","start_time":"","end_time":"","major":1})
        a,b=D.day_bounds("2026-03-08","America/New_York");self.assertEqual((b-a)/3600000,23)
        self.assertEqual(D.days_until("2026-11-22","2026-11-04"),18)
    def test_validation_rollback(self):
        for payload in ({"title":""},{"estimate_min":float("nan")},{"due_date":"2026-99-99"}):
            with self.assertRaises(ValueError):self.ticket(**payload)
        self.assertEqual(self.store.list("ticket"),[])
    def test_linked_work_blocks_keep_deadlines_and_survive_restart(self):
        t=self.ticket(due_date="2026-12-20")
        block=self.store.command("block.save",{"ticket_id":t["id"],"date":"2026-11-12","start_time":"09:00","end_time":"11:00"})
        self.store.command("block.save",{"id":block["id"],"date":"2026-11-14","start_time":"14:00","end_time":"15:30"})
        self.assertEqual(self.store.read("ticket",t["id"])["due_date"],"2026-12-20")
        root=self.store.root;self.store.close();self.store=Store(root);self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.snapshot()["block"][0]["date"],"2026-11-14")
        before=self.store.snapshot()["pending"]
        for patch in ({"end_time":"08:00"},{"date":""},{"start_time":"9:00"},{"ticket_id":"another-account-ticket"}):
            with self.assertRaises(ValueError):self.store.command("block.save",{"id":block["id"],**patch})
        self.assertEqual(self.store.snapshot()["pending"],before)
    def test_existing_v1_profile_migrates_without_losing_tickets(self):
        t=self.ticket(due_date="2026-12-20")
        root=self.store.root;self.store.close()
        with sqlite3.connect(root/"timemanager.db") as old:
            old.execute("DROP TABLE work_blocks");old.execute("DELETE FROM schema_migrations WHERE version>=2")
        self.store=Store(root);self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],4)
        self.assertEqual(self.store.read("ticket",t["id"])["due_date"],"2026-12-20")
        self.assertEqual(self.store.snapshot()["block"],[])
    def test_v1_backup_import_migrates_only_the_copy(self):
        t=self.ticket(due_date="2026-12-20")
        backup=BASE/(uuid.uuid4().hex+".db");self.store.backup(backup)
        with sqlite3.connect(backup) as old:
            old.execute("DROP TABLE work_blocks");old.execute("DELETE FROM schema_migrations WHERE version>=2")
        before=hashlib.sha256(backup.read_bytes()).hexdigest()
        imported=Store(BASE/uuid.uuid4().hex)
        try:
            imported.import_database(backup);self.assertFalse(imported.restore_session());imported.login("tester","test-password-123")
            self.assertEqual(imported.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],4)
            self.assertEqual(imported.read("ticket",t["id"])["due_date"],"2026-12-20")
            imported.command("block.save",{"ticket_id":t["id"],"date":"2026-11-12"})
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),before)
        finally:imported.close()

class LocalSignInTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(BASE/uuid.uuid4().hex)
    def tearDown(self):
        self.store.close()
    def reopen(self):
        root=self.store.root;self.store.close();self.store=Store(root)
    def test_simple_and_blank_passwords_are_accepted(self):
        self.store.register("tyler","tyler")
        self.store.logout();self.store.login("tyler","tyler")
        self.assertEqual(self.store.auth()["username"],"tyler")
        blank=Store(BASE/uuid.uuid4().hex)
        try:
            blank.register("blank","");blank.logout();blank.login("blank","")
            self.assertEqual(blank.auth()["username"],"blank")
        finally:blank.close()
    def test_remember_restart_logout_and_sign_back_in(self):
        self.assertFalse(self.store.restore_session())
        self.store.register("tyler","tyler")
        original_id=self.store.auth()["id"]
        marker=json.loads((self.store.root/".local-session.json").read_text(encoding="utf-8"))
        self.assertEqual(set(marker),{"version","account_id","device_id"})
        self.reopen();self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.auth()["id"],original_id)
        self.store.logout();self.reopen()
        self.assertFalse(self.store.restore_session())
        with self.assertRaises(ValueError):self.store.snapshot()
        self.store.login("tyler","tyler");self.reopen()
        self.assertTrue(self.store.restore_session())
    def test_change_local_password_preserves_account_and_auto_login(self):
        self.store.register("owner","original-password-123")
        identity={key:self.store.auth()[key] for key in ("id","username","device_id")}
        old_salt=self.store.auth()["salt"]
        self.store.change_password("tyler")
        self.assertEqual({key:self.store.auth()[key] for key in identity},identity)
        self.assertNotEqual(self.store.auth()["salt"],old_salt)
        self.reopen();self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.auth()["id"],identity["id"])
        self.store.logout()
        with self.assertRaises(ValueError):self.store.login("owner","original-password-123")
        self.store.login("owner","tyler")
        self.reopen();self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.auth()["id"],identity["id"])
        self.store.logout()
        with self.assertRaises(ValueError):self.store.change_password("other")
    def test_import_requires_first_sign_in_and_preserves_source(self):
        self.store.register("tyler","tyler")
        backup=BASE/(uuid.uuid4().hex+".db");self.store.backup(backup)
        before=hashlib.sha256(backup.read_bytes()).hexdigest()
        imported=Store(BASE/uuid.uuid4().hex)
        try:
            # Even an existing stale local marker cannot unlock an imported DB.
            marker=(self.store.root/".local-session.json").read_text(encoding="utf-8")
            (imported.root/".local-session.json").write_text(marker,encoding="utf-8")
            imported.import_database(backup)
            self.assertFalse(imported.restore_session())
            imported.login("tyler","tyler")
            self.assertEqual(imported.auth()["username"],"tyler")
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),before)
        finally:imported.close()
    def test_corrupt_or_wrong_device_marker_does_not_unlock(self):
        self.store.register("tyler","tyler")
        self.reopen();marker_path=self.store.root/".local-session.json"
        marker_path.write_text("not JSON",encoding="utf-8")
        self.assertFalse(self.store.restore_session())
        marker_path.write_text(json.dumps({"version":1,"account_id":123,"device_id":[]}),encoding="utf-8")
        self.assertFalse(self.store.restore_session())
        row=self.store.db.execute("SELECT id FROM accounts").fetchone()
        marker_path.write_text(json.dumps({"version":1,"account_id":row["id"],"device_id":"different-device"}),encoding="utf-8")
        self.assertFalse(self.store.restore_session())
    def test_compact_defaults_and_layout_revision(self):
        self.store.register("tyler","tyler")
        prefs=self.store.settings()
        self.assertEqual(prefs["density"],"compact")
        self.assertLess(prefs["sidebarWidth"],180)
        self.assertEqual(prefs["layoutRevision"],0)
        self.store.settings({"layoutRevision":3,"sidebarWidth":140,"inspectorWidth":240})
        self.reopen();self.assertTrue(self.store.restore_session())
        self.assertEqual(self.store.settings()["layoutRevision"],3)
        with self.assertRaises(ValueError):self.store.settings({"layoutRevision":True})

if __name__=="__main__":unittest.main()
