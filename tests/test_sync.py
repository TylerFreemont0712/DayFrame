import unittest
import uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dayframe.data.store import Store
from dayframe.sync.hub import Hub
from dayframe.sync.client import Sync,request
BASE=Path("build/test-data")
class SyncTests(unittest.TestCase):
    def setUp(self):
        self.root=BASE/uuid.uuid4().hex;self.hub=Hub(self.root/"hub",port=0,setup_token="private-token").start()
        self.url=f"http://127.0.0.1:{self.hub.port}"
        self.a=Store(self.root/"a");self.a.register("owner","tyler");self.sa=Sync(self.a,False)
        self.sa.publish({"url":self.url,"password":"tyler","setupToken":"private-token"})
        self.b=Store(self.root/"b");self.sb=Sync(self.b,False)
        self.sb.connect({"url":self.url,"username":"owner","password":"tyler"},True)
    def tearDown(self):
        self.a.close();self.b.close();self.hub.close()
    def run_ok(self,s):
        result=s.run();self.assertTrue(result["connected"],result["error"])
    def test_pairing_remembers_registered_device_for_restart(self):
        device=self.b.auth()["device_id"];root=self.b.root
        self.b.close();self.b=Store(root)
        self.assertTrue(self.b.restore_session())
        self.assertEqual(self.b.auth()["device_id"],device)
    def test_linked_work_blocks_sync_and_never_change_ticket_deadline(self):
        project=self.a.command("project.save",{"name":"P"})
        ticket=self.a.command("ticket.save",{"project_id":project["id"],"title":"Work","due_date":"2026-12-20"})
        block=self.a.command("block.save",{"ticket_id":ticket["id"],"date":"2026-11-12","start_time":"13:00","end_time":"14:00"})
        self.run_ok(self.sa);self.run_ok(self.sb)
        self.assertEqual(self.b.read("block",block["id"])["ticket_id"],ticket["id"])
        self.b.command("block.save",{"id":block["id"],"date":"2026-11-14"})
        self.run_ok(self.sb);self.run_ok(self.sa)
        self.assertEqual(self.a.read("block",block["id"])["date"],"2026-11-14")
        self.assertEqual(self.a.read("ticket",ticket["id"])["due_date"],"2026-12-20")
    def test_event_metadata_nested_map_and_parent_links_sync(self):
        project=self.a.command("project.save",{"name":"Native project"})
        front=self.a.command("section.save",{"project_id":project["id"],"name":"Frontend","rule_field":"component","rule_value":"UI"})
        calendar=self.a.command("section.save",{"project_id":project["id"],"name":"Calendar","parent_id":front["id"],"rule_field":"label","rule_value":"calendar"})
        parent=self.a.command("ticket.save",{"project_id":project["id"],"title":"Calendar parent","labels":["calendar"],"component":"UI"})
        child=self.a.command("ticket.save",{"project_id":project["id"],"title":"Calendar child"})
        self.a.command("ticket.relate",{"parent_id":parent["id"],"child_id":child["id"]})
        event=self.a.command("event.save",{"title":"Trip","date":"2026-11-07","end_date":"2026-11-09","start_time":"","end_time":"","event_type":"trip","location":"Kyoto","description":"Details","color":"#123456","recurrence":"yearly"})
        self.run_ok(self.sa);self.run_ok(self.sb)
        self.assertEqual(self.b.read("ticket",child["id"])["parent_id"],parent["id"])
        self.assertEqual(self.b.read("ticket",child["id"])["labels"],["calendar"])
        self.assertEqual(self.b.read("section",calendar["id"])["parent_id"],front["id"])
        self.assertEqual(self.b.read("event",event["id"])["location"],"Kyoto")
        self.b.command("event.save",{"id":event["id"],"description":"From second device"})
        self.a.command("event.save",{"id":event["id"],"location":"Osaka"})
        self.run_ok(self.sa);self.run_ok(self.sb);self.run_ok(self.sa)
        self.assertEqual(self.a.read("event",event["id"])["description"],"From second device")
        self.assertEqual(self.b.read("event",event["id"])["location"],"Osaka")


    def test_round_trip_independent_fields_and_conflict(self):
        project=self.a.command("project.save",{"name":"P"})
        ticket=self.a.command("ticket.save",{"project_id":project["id"],"title":"Original"})
        self.run_ok(self.sa);self.run_ok(self.sb)
        self.a.command("ticket.save",{"id":ticket["id"],"title":"Edited A"})
        self.b.command("ticket.save",{"id":ticket["id"],"priority":"high"})
        self.run_ok(self.sa);self.run_ok(self.sb);self.run_ok(self.sa)
        self.assertEqual(self.a.read("ticket",ticket["id"])["priority"],"high")
        self.assertEqual(self.b.read("ticket",ticket["id"])["title"],"Edited A")
        self.a.command("ticket.save",{"id":ticket["id"],"title":"Version A","component":"Remote field"})
        self.b.command("ticket.save",{"id":ticket["id"],"title":"Version B"})
        self.run_ok(self.sa);self.run_ok(self.sb)
        conflicts=self.b.snapshot()["conflicts"];self.assertEqual(conflicts[0]["fields"],["title"])
        self.assertEqual(self.b.read("ticket",ticket["id"])["title"],"Version B")
        self.sb.resolve(conflicts[0]["id"],"local");self.run_ok(self.sb);self.run_ok(self.sa)
        self.assertEqual(self.a.read("ticket",ticket["id"])["title"],"Version B")
        self.assertEqual(self.a.read("ticket",ticket["id"])["component"],"Remote field")
        self.b.command("ticket.save",{"id":ticket["id"],"estimate_min":42})
        self.b.settings({"syncEnabled":False})
        self.sb.run(force=True);self.run_ok(self.sa)
        self.assertEqual(self.a.read("ticket",ticket["id"])["estimate_min"],42)
    def test_account_isolation_revocation_and_private_setup(self):
        with self.assertRaises(ValueError):request(self.url,"/register",{"id":str(uuid.uuid4()),"username":"other","password":"test-password-123"})
        result=request(self.url,"/register",{"id":str(uuid.uuid4()),"username":"other","password":"test-password-123"},setup_token="private-token")
        other=request(self.url,"/login",{"username":"other","password":"test-password-123","device_id":"other"})
        self.a.command("project.save",{"name":"Secret"});self.run_ok(self.sa)
        self.assertEqual(request(self.url,"/pull",{"cursor":0},other["token"])["changes"],[])
        request(self.url,"/revoke",{"device_id":self.b.account["device_id"]},self.sa.token)
        result=self.sb.run();self.assertFalse(result["connected"])
    def test_https_pin_verified_before_login(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"DayFrame test hub")])
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
              .sign(key,hashes.SHA256()))
        cert_path=self.root/"cert.pem";key_path=self.root/"key.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM));key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        hub=Hub(self.root/"tls",port=0,setup_token="token",cert=str(cert_path),key=str(key_path)).start()
        try:
            url=f"https://127.0.0.1:{hub.port}"
            params={"id":str(uuid.uuid4()),"username":"tls-user","password":"test-password-123"}
            with self.assertRaisesRegex(ValueError,"fingerprint"):request(url,"/register",params,fingerprint="00"*32,setup_token="token")
            self.assertEqual(hub.db.execute("SELECT count(*) FROM users").fetchone()[0],0)
            fp=cert.fingerprint(hashes.SHA256()).hex()
            self.assertTrue(request(url,"/register",params,fingerprint=fp,setup_token="token")["ok"])
        finally:hub.close()

if __name__=="__main__":unittest.main()
