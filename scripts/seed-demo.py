"""Create a demo profile for looking around DayFrame from source.

Usage: python scripts/seed-demo.py PROFILE_DIR

Creates a local account (username "demo", password "demo"; it is remembered, so the app
opens signed in), loads the large demo workspace, and when git is installed creates a
small repository inside the profile folder with branches, a merge, a tag, uncommitted
changes and one saved changeset, connected to the Website project. Never point this at
a real profile; it refuses a folder that already has a database.
"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dayframe.code import git as G  # noqa: E402
from dayframe.data.store import Store  # noqa: E402

FILES = {
    "README.md": "# Website\n\nPublic site and customer dashboard.\n",
    "src/app.py": "from views.board import board\n\n\ndef main():\n    print(board([]))\n",
    "src/model.py": "class Ticket:\n    title = ''\n    status = 'open'\n",
    "src/views/board.py": "def board(tickets):\n    return [t.title for t in tickets]\n",
}


def git(repo, *args):
    subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=repo, check=True, capture_output=True)


def write(repo, name, text):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(root):
    origin = root / "demo-origin.git"
    repo = root / "demo-repo"
    origin.mkdir(parents=True)
    git(origin, "init", "--bare", "-b", "main")
    git(root, "clone", str(origin), str(repo))
    for key, value in (("user.name", "Demo"), ("user.email", "demo@example.invalid"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    for name, text in FILES.items():
        write(repo, name, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Start the website project")
    git(repo, "tag", "v0.1")
    git(repo, "switch", "-c", "web-dashboard")
    write(repo, "src/views/dashboard.py", "def dashboard(tickets):\n    return len(tickets)\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Add the dashboard view")
    write(repo, "src/views/board.py", "def board(tickets):\n    return [t.title.strip() for t in tickets]\n")
    git(repo, "commit", "-am", "Trim titles on the board")
    git(repo, "switch", "main")
    write(repo, "src/model.py", "class Ticket:\n    title = ''\n    status = 'inbox'\n    labels = []\n")
    git(repo, "commit", "-am", "Default new tickets to inbox")
    git(repo, "merge", "--no-ff", "-m", "Merge the dashboard view", "web-dashboard")
    git(repo, "tag", "v0.2")
    git(repo, "push", "--all", "origin")
    git(repo, "push", "--tags", "origin")
    git(repo, "switch", "-c", "web-pricing-page")
    write(repo, "src/views/pricing.py", "PLANS = ['Free', 'Team']\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Sketch the pricing page")
    return repo


def main(profile):
    profile = Path(profile).resolve()
    if (profile / "timemanager.db").exists():
        raise SystemExit("That folder already has a DayFrame database: " + str(profile))
    store = Store(profile)
    store.register("demo", "demo")
    store.command("demo.load")
    print("Loaded the demo workspace into " + str(profile))
    if not G.git_executable():
        print("git is not installed; the Code page demo repository was skipped.")
        store.close()
        return
    repo = build_repo(profile)
    project = next(p for p in store.list("project") if p["project_key"] == "WEB")
    record = store.command(
        "repo.save",
        {"project_id": project["id"], "name": "website", "github_repo": "", "default_branch": "main"},
    )
    store.settings({"repoPaths": {record["id"]: str(repo)}})
    ticket = next(
        t for t in store.list("ticket") if t["project_id"] == project["id"] and t["status"] in ("doing", "ready")
    )
    write(repo, "src/views/pricing.py", "PLANS = ['Free', 'Team', 'Business']\n\n\ndef price(plan):\n    return 0\n")
    write(repo, "notes.md", "# Pricing notes\n\n- compare yearly and monthly\n")
    captured = G.GitRepo(repo).shelve("demo-changeset", "Pricing table draft", keep=True)
    store.command(
        "changeset.save",
        {
            "id": "demo-changeset",
            "repo_id": record["id"],
            "ticket_id": ticket["id"],
            "title": "Pricing table draft",
            "branch": captured["branch"],
            "base_commit": captured["base_commit"],
            "diff": captured["diff"],
            "stat": captured["stat"],
            "updated_at": int(time.time() * 1000),
        },
    )
    store.settings({"activeChangesets": {record["id"]: "demo-changeset"}})
    store.close()
    print("Created a demo git repository at " + str(repo))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
