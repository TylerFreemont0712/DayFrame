"""Lane layout for drawing a commit graph, in the spirit of `git log --graph`.

layout() takes commits newest first in topological order (children before parents)
and returns, for every row, the commit's lane plus the line segments to draw in the
top half (from the row above into this commit) and the bottom half (towards parents).
"""

from __future__ import annotations


def layout(commits):
    lanes = []  # commit id expected next in each lane, or None for a free lane
    rows = []
    known = {c["sha"] for c in commits}
    for commit in commits:
        sha = commit["sha"]
        before = list(lanes)
        if sha in lanes:
            col = lanes.index(sha)
        elif None in lanes:
            col = lanes.index(None)
        else:
            col = len(lanes)
            lanes.append(None)
        # Lines entering this row: every waiting lane continues; those waiting for this commit join it.
        top = [(i, col if expected == sha else i) for i, expected in enumerate(before) if expected]
        for i, expected in enumerate(lanes):
            if expected == sha:
                lanes[i] = None
        targets = []
        folded = []
        # Parents missing from a limited log still get a short line down, then end.
        for number, parent in enumerate(commit["parents"]):
            if parent in lanes:
                target = lanes.index(parent)
                # A first parent already waiting further right folds back into this lane.
                if number == 0 and target > col and lanes[col] is None:
                    lanes[target] = None
                    folded.append(target)
                    target = col
            elif number == 0 and lanes[col] is None:
                target = col
            elif None in lanes:
                target = lanes.index(None)
            else:
                target = len(lanes)
                lanes.append(None)
            lanes[target] = parent
            targets.append(target)
        # Lines leaving this row: one to each parent, plus every lane that simply passes by.
        bottom = (
            [(col, t) for t in targets]
            + [(lane, col) for lane in folded]
            + [
                (i, i)
                for i, expected in enumerate(lanes)
                if expected and i != col and i < len(before) and before[i] == expected
            ]
        )
        while lanes and lanes[-1] is None:
            lanes.pop()
        rows.append(
            {
                "col": col,
                "top": top,
                "bottom": bottom,
                "width": max([col + 1, *(max(a, b) + 1 for a, b in top + bottom)]),
                "merge": len(commit["parents"]) > 1,
                "dangling": [t for t, p in zip(targets, commit["parents"]) if p not in known],
            }
        )
    return rows
