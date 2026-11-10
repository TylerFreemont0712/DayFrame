"""Parse unified git diffs into files, hunks and numbered lines for the Code page.

Pure functions only: the change browser, changesets, the working tree and commits
all feed their patch text through parse() and tree().
"""

from __future__ import annotations

# A line inside a hunk: (kind, old line number, new line number, text).
# kind is "ctx", "add", "del" or "note" ("\\ No newline at end of file").


ESCAPES = {"n": 10, "t": 9, '"': 34, "\\": 92, "a": 7, "b": 8, "f": 12, "r": 13, "v": 11}


def _unquote(path):
    """Undo git's C-style quoting of unusual file names (octal bytes and backslash escapes)."""
    body, out, i = path[1:-1], bytearray(), 0
    while i < len(body):
        char = body[i]
        if char == "\\" and i + 1 < len(body):
            following = body[i + 1]
            if following in "01234567" and i + 3 < len(body) + 1 and body[i + 1 : i + 4].isdigit():
                out.append(int(body[i + 1 : i + 4], 8) & 0xFF)
                i += 4
                continue
            out.append(ESCAPES.get(following, ord(following)))
            i += 2
            continue
        out.extend(char.encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


def _strip_prefix(path):
    path = path.strip()
    if path.startswith('"') and path.endswith('"') and len(path) > 1:
        path = _unquote(path)
    if path == "/dev/null":
        return ""
    return path[2:] if path[:2] in ("a/", "b/") else path


def _header_paths(rest):
    """Best effort old/new paths from 'a/X b/Y' when ---/+++ lines are missing."""
    index = rest.rfind(" b/")
    if index < 0:
        return "", ""
    return _strip_prefix(rest[:index]), _strip_prefix(rest[index + 1 :])


def _hunk_start(header):
    """(old start, new start) from '@@ -a,b +c,d @@'."""
    try:
        old, new = header.split("@@")[1].split()[:2]
        return int(old[1:].split(",")[0]), int(new[1:].split(",")[0])
    except (IndexError, ValueError):
        return 0, 0


def parse(text):
    """List of files: path, old_path, status (A/M/D/R/C), binary, added, removed, hunks."""
    files = []
    current = None
    hunk = None
    old_no = new_no = 0
    for line in (text or "").split("\n"):
        if line.startswith("diff --git ") or line.startswith("diff --cc "):
            old, new = _header_paths(line.split(" ", 2)[2])
            current = {
                "path": new or old,
                "old_path": old,
                "status": "M",
                "binary": False,
                "added": 0,
                "removed": 0,
                "hunks": [],
                "mode": "",
            }
            files.append(current)
            hunk = None
            continue
        if current is None:
            continue
        if hunk is None or not line[:1] in (" ", "+", "-", "\\"):
            if line.startswith("@@"):
                old_no, new_no = _hunk_start(line)
                hunk = {"header": line, "lines": []}
                current["hunks"].append(hunk)
            elif line.startswith("new file mode"):
                current["status"] = "A"
                current["mode"] = line.rsplit(" ", 1)[-1]
            elif line.startswith("deleted file mode"):
                current["status"] = "D"
            elif line.startswith("old mode") or line.startswith("new mode"):
                current["mode"] = line.rsplit(" ", 1)[-1]
            elif line.startswith("rename from "):
                current["status"], current["old_path"] = "R", line[12:]
            elif line.startswith("rename to "):
                current["path"] = line[10:]
            elif line.startswith("copy from "):
                current["status"], current["old_path"] = "C", line[10:]
            elif line.startswith("copy to "):
                current["path"] = line[8:]
            elif line.startswith("--- ") and hunk is None:
                current["old_path"] = _strip_prefix(line[4:]) or current["old_path"]
                if line[4:].strip() == "/dev/null":
                    current["status"] = "A"
            elif line.startswith("+++ ") and hunk is None:
                path = _strip_prefix(line[4:])
                if path:
                    current["path"] = path
                else:
                    current["status"] = "D"
                    current["path"] = current["old_path"]
            elif line.startswith("Binary files") or line.startswith("GIT binary patch"):
                current["binary"] = True
            continue
        kind = line[0]
        body = line[1:]
        if kind == " ":
            hunk["lines"].append(("ctx", old_no, new_no, body))
            old_no += 1
            new_no += 1
        elif kind == "-":
            hunk["lines"].append(("del", old_no, None, body))
            current["removed"] += 1
            old_no += 1
        elif kind == "+":
            hunk["lines"].append(("add", None, new_no, body))
            current["added"] += 1
            new_no += 1
        else:
            hunk["lines"].append(("note", None, None, body.strip()))
    for f in files:
        if f["status"] == "M" and f["old_path"] and f["old_path"] != f["path"] and not f["hunks"]:
            f["status"] = "R"
    return files


def summary(files):
    return len(files), sum(f["added"] for f in files), sum(f["removed"] for f in files)


def tree(files):
    """Nested folders for a file list. Folders with a single child folder are merged ('src/app')."""
    root = {"name": "", "path": "", "children": {}, "file": None, "added": 0, "removed": 0, "count": 0}
    for f in files:
        node = root
        parts = f["path"].split("/")
        for depth, part in enumerate(parts[:-1]):
            node = node["children"].setdefault(
                part,
                {
                    "name": part,
                    "path": "/".join(parts[: depth + 1]),
                    "children": {},
                    "file": None,
                    "added": 0,
                    "removed": 0,
                    "count": 0,
                },
            )
        node["children"][parts[-1]] = {
            "name": parts[-1],
            "path": f["path"],
            "children": {},
            "file": f,
            "added": f["added"],
            "removed": f["removed"],
            "count": 1,
        }

    def finish(node):
        for child in node["children"].values():
            finish(child)
        if node["file"] is None:
            node["added"] = sum(c["added"] for c in node["children"].values())
            node["removed"] = sum(c["removed"] for c in node["children"].values())
            node["count"] = sum(c["count"] for c in node["children"].values())
        # Merge chains of single folders, like most code browsers.
        while (
            node["file"] is None
            and node["name"]
            and len(node["children"]) == 1
            and next(iter(node["children"].values()))["file"] is None
        ):
            child = next(iter(node["children"].values()))
            node["name"] += "/" + child["name"]
            node["path"] = child["path"]
            node["children"] = child["children"]
        # Keys follow the (possibly merged) names: folders first, then files, by name.
        node["children"] = {
            c["name"]: c
            for c in sorted(
                node["children"].values(), key=lambda c: (c["file"] is not None, c["name"].casefold())
            )
        }

    finish(root)
    return root


def changed_span(old, new):
    """(start, old_end, new_end) of the differing middle of two lines, for in-line highlighting."""
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    old_end, new_end = len(old), len(new)
    while old_end > start and new_end > start and old[old_end - 1] == new[new_end - 1]:
        old_end -= 1
        new_end -= 1
    return start, old_end, new_end


def pair_rows(lines):
    """Split-view rows: (left line or None, right line or None), pairing deletions with additions."""
    rows = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line[0] in ("del", "add"):
            removed, added = [], []
            while index < len(lines) and lines[index][0] == "del":
                removed.append(lines[index])
                index += 1
            while index < len(lines) and lines[index][0] == "add":
                added.append(lines[index])
                index += 1
            for i in range(max(len(removed), len(added))):
                rows.append((removed[i] if i < len(removed) else None, added[i] if i < len(added) else None))
            continue
        rows.append((line, line))
        index += 1
    return rows
