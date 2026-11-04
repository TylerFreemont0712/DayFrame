"""Shared validation, calendar math, and password compatibility."""
from __future__ import annotations
import copy
import hashlib
import hmac
import json
import math
import secrets
from datetime import date, datetime, time, timedelta, timezone
from importlib.resources import files
from zoneinfo import ZoneInfo

DEFINITIONS = json.loads(files("dayframe").joinpath("schema_definitions.json").read_text(encoding="utf-8"))
STATUSES = ("inbox", "ready", "doing", "review", "done")
# Keep stored IDs stable so existing tickets and sync history retain their stage.
STATUS_NAMES = dict(zip(STATUSES, ("Not Started", "In Progress", "Processed", "Review", "Complete")))
PRIORITIES = ("low", "medium", "high", "urgent")

def text(value, maximum=500, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError("Please enter valid text" + (" (required)." if required else "."))
    return value.strip()

def calendar_date(value):
    if not value:
        return ""
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Invalid calendar date.")
    return value

def day_key(zone="Asia/Tokyo", timestamp=None):
    dt = datetime.now(timezone.utc) if timestamp is None else datetime.fromtimestamp(timestamp / 1000, timezone.utc)
    return dt.astimezone(ZoneInfo(zone)).date().isoformat()

def day_bounds(day, zone):
    d = date.fromisoformat(day)
    tz = ZoneInfo(zone)
    return tuple(int(datetime.combine(x, time.min, tz).timestamp()*1000) for x in (d, d+timedelta(days=1)))

def days_until(target, today):
    return (date.fromisoformat(target)-date.fromisoformat(today)).days

def duration(ms):
    seconds = max(0, int(ms // 1000))
    return f"{seconds//3600:02}:{seconds%3600//60:02}:{seconds%60:02}"

def short_time(ms):
    minutes = max(0, round(ms / 60000))
    return f"{minutes//60}h {minutes%60}m" if minutes >= 60 else f"{minutes}m"

def hash_password(password, salt=None):
    if not isinstance(password, str) or len(password) > 128:
        raise ValueError("Use a password of 128 characters or fewer.")
    salt = salt or secrets.token_hex(16)
    # The earlier Node version used the hexadecimal salt string as UTF-8.
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=131072, r=8, p=1, dklen=32, maxmem=256*1024*1024)
    return salt, digest.hex()

def verify_password(password, row):
    try:
        return hmac.compare_digest(hash_password(password, row["salt"])[1], row["password_hash"])
    except (ValueError, TypeError):
        return False

def changes(base, next_record):
    return {k: v for k, v in next_record.items() if (base or {}).get(k) != v}

def merge_fields(base, patch, remote):
    result, conflicts = copy.deepcopy(remote), []
    for key, value in patch.items():
        if remote.get(key) != base.get(key) and remote.get(key) != value:
            conflicts.append(key)
        else:
            result[key] = value
    return result, conflicts

def rule_matches(section, ticket):
    field, value = section.get("rule_field"), section.get("rule_value")
    if not field or not value:
        return False
    return value in ticket.get("labels", []) if field == "label" else ticket.get(field) == value

def assert_acyclic(tickets, ticket_id, dependencies):
    graph = {t["id"]: t.get("dependencies", []) for t in tickets}
    graph[ticket_id] = dependencies
    def visit(node, path):
        if node in path:
            raise ValueError("That dependency creates a cycle.")
        for child in graph.get(node, []):
            visit(child, path | {node})
    visit(ticket_id, set())

def validate(kind, data):
    if kind not in DEFINITIONS or not isinstance(data, dict):
        raise ValueError("Unknown record type.")
    definition = DEFINITIONS[kind]
    for key, value in data.items():
        if key not in definition["fields"]:
            raise ValueError("Unknown field: " + key)
        if key in ("estimate_min","x","y","start_at","end_at","session_ms","sort_order"):
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not 0 <= value <= 1e15:
                raise ValueError("Invalid numeric field: " + key)
        elif key in ("archived","pinned","major","manual","paused"):
            if value not in (0,1):
                raise ValueError("Invalid switch field.")
        elif key in ("labels","dependencies","checklist","predecessor_ids"):
            if not isinstance(value,list) or len(value)>200:
                raise ValueError("Invalid item list.")
            for item in value:
                if key == "checklist":
                    if not isinstance(item,dict) or not isinstance(item.get("done"),bool):
                        raise ValueError("Invalid checklist.")
                    text(item.get("text"),1000,True)
                else:
                    text(item,100,True)
        else:
            text(value,100000 if key in ("body","description") else 500)
    if "status" in data and data["status"] not in STATUSES:
        raise ValueError("Invalid status.")
    if "priority" in data and data["priority"] not in PRIORITIES:
        raise ValueError("Invalid priority.")
    for key in ("date","end_date","due_date"):
        if key in data:
            calendar_date(data[key])
    if data.get("rule_field") and data["rule_field"] not in ("label","component","milestone"):
        raise ValueError("Invalid grouping field.")
    if kind == "entry" and data.get("end_at",0)<data.get("start_at",0):
        raise ValueError("End must follow start.")
    if kind == "event":
        if "date" in data and not data["date"]:raise ValueError("Choose an event date.")
        if data.get("end_date") and data.get("date") and data["end_date"]<data["date"]:
            raise ValueError("End date must be on or after the start date.")
        for key in ("start_time","end_time"):
            if data.get(key):
                if len(data[key])!=5:raise ValueError("Use HH:mm for event times.")
                time.fromisoformat(data[key])
        if "start_time" in data and "end_time" in data and bool(data["start_time"])!=bool(data["end_time"]):
            raise ValueError("Set both event times, or make it all day.")
        if data.get("start_time") and data.get("end_time") and data.get("end_date","")<=data.get("date","") and data["end_time"]<=data["start_time"]:
            raise ValueError("Event must end after it starts.")
        if "recurrence" in data and data["recurrence"] not in ("","yearly"):
            raise ValueError("Choose no repeat or a yearly repeat.")
        if data.get("color") and (len(data["color"])!=7 or data["color"][0]!="#" or any(c not in "0123456789abcdefABCDEF" for c in data["color"][1:])):
            raise ValueError("Choose a valid event color.")
    if kind == "block":
        if "ticket_id" in data:
            text(data["ticket_id"],120,True)
        if "date" in data and not calendar_date(data["date"]):
            raise ValueError("Choose a date for the work block.")
        for key in ("start_time","end_time"):
            if key in data:
                if not isinstance(data[key],str) or len(data[key])!=5:
                    raise ValueError("Use HH:mm for work block times.")
                time.fromisoformat(data[key])
        if "start_time" in data and "end_time" in data and data["end_time"]<=data["start_time"]:
            raise ValueError("Work block must end after it starts.")
    if kind in ("project","ticket","event","note","section"):
        title_key = "name" if kind in ("project","section") else "title"
        if title_key in data:
            text(data[title_key],500,True)
    return data



def check_map_relations(records,record_id,data):
    by_id={r["id"]:r for r in records};by_id[record_id]={"id":record_id,**data}
    project=data["project_id"]
    for field in ("parent_id","predecessor_ids"):
        targets=[data.get(field)] if field=="parent_id" else data.get(field,[])
        for target in filter(None,targets):
            if target not in by_id or by_id[target]["project_id"]!=project:
                raise ValueError("Map relationships must stay within the project.")
        def visit(node,path):
            if node in path:raise ValueError("That map relationship creates a cycle.")
            record=by_id.get(node,{})
            links=[record.get(field)] if field=="parent_id" else record.get(field,[])
            for target in filter(None,links):visit(target,path|{node})
        visit(record_id,set())

def section_path(sections,section_id):
    by_id={s["id"]:s for s in sections};result=[];seen=set()
    while section_id and section_id in by_id and section_id not in seen:
        seen.add(section_id);section=by_id[section_id];result.insert(0,section);section_id=section.get("parent_id","")
    return result

def section_classification(sections,section_id,ticket):
    result={};labels=list(ticket["labels"])
    for section in section_path(sections,section_id):
        field,value=section.get("rule_field"),section.get("rule_value")
        if not field or not value:continue
        if field=="label":
            if value not in labels:labels.append(value)
        else:result[field]=value
    if labels!=ticket["labels"]:result["labels"]=labels
    return changes(ticket,result)

def section_matches(sections,section,ticket):
    return not section_classification(sections,section["id"],ticket)
