"""Run git in a local checkout for the Code page.

Everything here is blocking and meant for a worker thread. Commands never prompt on
the terminal, never force-push and pull only fast-forwards, so a mistaken click cannot
rewrite history. Callers confirm destructive steps before calling in.
"""

from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LOCAL_TIMEOUT = 30
NETWORK_TIMEOUT = 180
# Stash messages carry this prefix plus the changeset id, so DayFrame can find its own entries.
STASH_PREFIX = "dayframe:"


class GitError(ValueError):
    pass


def git_executable():
    return shutil.which("git")


def branch_name(project_key, ticket_id, title):
    """A readable branch for a ticket, such as web-1a2b3c-build-dashboard."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    prefix = re.sub(r"[^a-z0-9]+", "", project_key.lower()) or "ticket"
    return (prefix + "-" + ticket_id[:6].lower() + ("-" + slug if slug else ""))[:60].rstrip("-")


def github_repo_from_url(url):
    """'owner/name' for a github.com remote URL, or '' for anything else."""
    match = re.match(
        r"^(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
        r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        url.strip(),
    )
    return match.group(1) + "/" + match.group(2) if match else ""


def stash_marker(changeset_id):
    return STASH_PREFIX + changeset_id


class GitRepo:
    def __init__(self, path):
        self.path = Path(path)

    # Running ------------------------------------------------------------------------------

    def run(self, *args, check=True, timeout=LOCAL_TIMEOUT):
        executable = git_executable()
        if not executable:
            raise GitError("Git is not installed or not on PATH.")
        if not self.path.is_dir():
            raise GitError("The checkout folder does not exist: " + str(self.path))
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            done = subprocess.run(
                [executable, "-c", "core.quotepath=off", "-c", "color.ui=never", *args],
                cwd=self.path,
                env=env,
                capture_output=True,
                timeout=timeout,
                creationflags=flags,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError("git " + args[0] + " took too long and was stopped.") from exc
        out = done.stdout.decode("utf-8", "replace")
        if check and done.returncode:
            message = (done.stderr.decode("utf-8", "replace") or out).strip()
            raise GitError(message or "git " + args[0] + " failed.")
        return out

    def is_repository(self):
        try:
            return self.run("rev-parse", "--is-inside-work-tree").strip() == "true"
        except GitError:
            return False

    # Reading ------------------------------------------------------------------------------

    def status(self):
        """Branch, upstream, ahead/behind and changed files from porcelain v2."""
        raw = self.run("status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
        result = {
            "branch": "",
            "head": "",
            "upstream": "",
            "ahead": 0,
            "behind": 0,
            "files": [],
        }
        parts = raw.split("\0")
        index = 0
        while index < len(parts):
            entry = parts[index]
            index += 1
            if not entry:
                continue
            if entry.startswith("# branch.oid "):
                oid = entry[13:]
                result["head"] = "" if oid == "(initial)" else oid
            elif entry.startswith("# branch.head "):
                head = entry[14:]
                result["branch"] = "" if head == "(detached)" else head
            elif entry.startswith("# branch.upstream "):
                result["upstream"] = entry[18:]
            elif entry.startswith("# branch.ab "):
                ahead, behind = entry[12:].split()
                result["ahead"], result["behind"] = int(ahead), -int(behind)
            elif entry[0] == "1":
                fields = entry.split(" ", 8)
                result["files"].append({"code": fields[1], "path": fields[8]})
            elif entry[0] == "2":
                fields = entry.split(" ", 9)
                # Renames carry the original path as the next NUL-separated part.
                result["files"].append({"code": fields[1], "path": fields[9], "from": parts[index]})
                index += 1
            elif entry[0] == "u":
                fields = entry.split(" ", 10)
                result["files"].append({"code": "UU", "path": fields[10]})
            elif entry[0] == "?":
                result["files"].append({"code": "??", "path": entry[2:]})
        return result

    def branches(self):
        return [
            line
            for line in self.run("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
            if line
        ]

    def remote_url(self, name="origin"):
        return self.run("remote", "get-url", name, check=False).strip()

    def default_branch(self):
        ref = self.run("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False).strip()
        return ref.split("/", 1)[1] if "/" in ref else ""

    def working_diff(self):
        """Uncommitted changes against HEAD, including untracked files, as one patch."""
        has_head = bool(self.run("rev-parse", "--verify", "--quiet", "HEAD", check=False).strip())
        patch = self.run("diff", "HEAD", "--binary") if has_head else self.run("diff", "--cached", "--binary")
        untracked = [p for p in self.run("ls-files", "--others", "--exclude-standard", "-z").split("\0") if p]
        for path in untracked:
            # --no-index exits 1 when the files differ, which is always the case here.
            patch += self.run("diff", "--no-index", "--binary", "--", os.devnull, path, check=False)
        return patch

    def log(self, count=20, revision="HEAD"):
        raw = self.run(
            "log", "-n", str(count), "--format=%h%x00%s%x00%an%x00%cr", revision, "--", check=False
        )
        return [
            dict(zip(("sha", "subject", "author", "when"), line.split("\0")))
            for line in raw.splitlines()
            if line
        ]

    def outgoing(self):
        """Commits that a push would send."""
        status = self.status()
        if status["upstream"]:
            revision = "@{u}..HEAD"
        else:
            revision = "HEAD"
        args = ["log", "--format=%h%x00%s", revision]
        if not status["upstream"]:
            args += ["--not", "--remotes"]
        raw = self.run(*args, check=False)
        return [dict(zip(("sha", "subject"), line.split("\0", 1))) for line in raw.splitlines() if line]

    # Shelving -----------------------------------------------------------------------------

    def find_stash(self, changeset_id):
        """Newest local stash entry made for a changeset, as stash@{n}, or ''."""
        marker = stash_marker(changeset_id)
        for line in self.run("stash", "list", "--format=%gd%x00%gs").splitlines():
            ref, _, subject = line.partition("\0")
            if marker in subject.split(": ", 1)[-1].split(" "):
                return ref
        return ""

    def shelve(self, changeset_id, title, keep=False):
        """Stash every change (untracked files too) and return the patch for storage.

        keep=True puts the changes straight back, so the working tree is unchanged but
        a stash entry and the stored diff exist as a snapshot.
        """
        status = self.status()
        if not status["files"]:
            raise GitError("There are no changes to shelve.")
        if any(f["code"] == "UU" for f in status["files"]):
            raise GitError("Resolve the merge conflicts before shelving.")
        if not status["head"]:
            raise GitError("Make a first commit before shelving changes.")
        self.run("stash", "push", "--include-untracked", "-m", stash_marker(changeset_id) + " " + title)
        ref = "stash@{0}"
        try:
            patch = self.run("stash", "show", "-p", "--include-untracked", "--binary", ref)
        except GitError:
            patch = self.run("stash", "show", "-p", "--binary", ref)
        stat = self.run("stash", "show", "--include-untracked", "--shortstat", ref, check=False).strip()
        if keep:
            # Restore staged state where possible; fall back to a plain apply.
            self.run("stash", "apply", "--index", ref, check=False)
            if not self.status()["files"]:
                self.run("stash", "apply", ref)
        return {
            "diff": patch,
            "stat": stat or str(len(status["files"])) + " files changed",
            "branch": status["branch"],
            "base_commit": status["head"],
        }

    def apply_patch(self, patch):
        """Apply a stored patch to the working tree; three-way merge if it no longer fits."""
        handle, name = tempfile.mkstemp(prefix="dayframe-", suffix=".diff")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
                stream.write(patch)
            if self._applies(name):
                self.run("apply", "--binary", "--whitespace=nowarn", name)
                return "applied"
            try:
                self.run("apply", "--3way", "--binary", "--whitespace=nowarn", name)
            except GitError as exc:
                if "conflict" in str(exc).lower():
                    return "conflicts"
                raise GitError("The stored changes no longer apply to this checkout: " + str(exc)) from exc
            return "merged"
        finally:
            Path(name).unlink(missing_ok=True)

    def _applies(self, name):
        try:
            self.run("apply", "--check", "--binary", name)
            return True
        except GitError:
            return False

    def restore(self, changeset):
        """Bring a changeset's files into a clean working tree."""
        if self.status()["files"]:
            raise GitError("The working tree has uncommitted changes. Shelve them first.")
        if changeset.get("diff"):
            return self.apply_patch(changeset["diff"])
        ref = self.find_stash(changeset["id"])
        if not ref:
            raise GitError("No stored diff or local stash exists for this changeset.")
        self.run("stash", "apply", ref)
        return "applied"

    # Branches and history -----------------------------------------------------------------

    def switch(self, branch, create=False):
        if create:
            self.run("switch", "-c", branch)
        else:
            self.run("switch", branch)

    def commit(self, message, paths):
        if not message.strip():
            raise GitError("Write a commit message.")
        if not paths:
            raise GitError("Choose at least one file to commit.")
        self.run("add", "-A", "--", *paths)
        # Naming the paths commits only them, even if other files are already staged.
        self.run("commit", "-m", message, "--", *paths)
        return self.run("rev-parse", "--short", "HEAD").strip()

    def fetch(self):
        return self.run("fetch", "--prune", timeout=NETWORK_TIMEOUT)

    def pull(self):
        return self.run("pull", "--ff-only", timeout=NETWORK_TIMEOUT)

    def push(self):
        status = self.status()
        if not status["branch"]:
            raise GitError("Switch to a branch before pushing.")
        if status["behind"]:
            raise GitError("The remote branch has commits you do not have. Pull first.")
        if status["upstream"]:
            return self.run("push", timeout=NETWORK_TIMEOUT)
        return self.run("push", "--set-upstream", "origin", status["branch"], timeout=NETWORK_TIMEOUT)
