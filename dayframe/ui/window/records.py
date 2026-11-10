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

    def code_repo(self, project_id):
        """The project's active repository connection, if any."""
        return next(
            (r for r in self.data.get("repo", []) if r["project_id"] == project_id and not r["archived"]),
            None,
        )

    def changeset_count(self, ticket_id):
        return sum(c["ticket_id"] == ticket_id and not c["archived"] for c in self.data.get("changeset", []))

    def tracked_ms(self, ticket_id):
        return sum(e["end_at"] - e["start_at"] for e in self.data["entry"] if e["ticket_id"] == ticket_id)
