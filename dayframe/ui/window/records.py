"""Read-only lookups over the current snapshot shared by every page."""

from __future__ import annotations


class RecordLookups:
    def find_ticket(self, ticket_id):
        return next((t for t in self.data["ticket"] if t["id"] == ticket_id), None)

    def ticket_key(self, t):
        p = next((p for p in self.data["project"] if p["id"] == t["project_id"]), {})
        # The stable short UUID identifies tickets across devices.
        return p.get("project_key", "T") + " · " + t["id"][:6].upper()

    def blocked(self, t):
        return any(
            self.find_ticket(dep) and self.find_ticket(dep)["status"] != "done" for dep in t["dependencies"]
        )

    def project_name(self, project_id):
        return next((p["name"] for p in self.data["project"] if p["id"] == project_id), "Project")

    def tracked_ms(self, ticket_id):
        return sum(e["end_at"] - e["start_at"] for e in self.data["entry"] if e["ticket_id"] == ticket_id)
