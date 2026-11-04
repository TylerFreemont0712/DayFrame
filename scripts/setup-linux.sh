#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
dayframe_probe='import sys; sys.exit(0 if (3,12) <= sys.version_info[:2] < (3,15) else 1)'
dayframe_python="${DAYFRAME_PYTHON:-}"
if [ -z "$dayframe_python" ]; then
    for dayframe_candidate in python3.14 python3.13 python3.12 python3; do
        if command -v "$dayframe_candidate" >/dev/null 2>&1 && "$dayframe_candidate" -c "$dayframe_probe"; then
            dayframe_python="$dayframe_candidate"
            break
        fi
    done
fi
if [ -z "$dayframe_python" ] || ! "$dayframe_python" -c "$dayframe_probe"; then
    printf '%s\n' 'Install Python 3.12–3.14 (3.14 recommended), or set DAYFRAME_PYTHON to its executable.' >&2
    exit 1
fi
if [ -x .venv/bin/python ] && ! .venv/bin/python -c "$dayframe_probe"; then
    printf '%s\n' 'Existing .venv uses an older Python. Preserve/rename it before rerunning setup.' >&2
    exit 1
fi
"$dayframe_python" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
printf '%s\n' 'Ready. Run: sh start-dayframe.sh'
