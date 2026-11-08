#!/usr/bin/env sh
# Run the current source version of DayFrame in a separate preview profile.
#   sh scripts/preview.sh                 prepare .venv if needed and start the app
#   sh scripts/preview.sh --copy-profile  first copy your real profile's data into the preview
#   sh scripts/preview.sh --reset         delete the preview profile and start empty
# The real profile ($XDG_DATA_HOME/TimeManager) is never opened.
set -eu
cd "$(dirname "$0")/.."
data="${XDG_DATA_HOME:-$HOME/.local/share}"
real="$data/TimeManager"
preview="$data/TimeManager-preview"
[ -x .venv/bin/python ] || sh scripts/setup-linux.sh
.venv/bin/python -c 'import PySide6, qtawesome, keyring, cryptography, tzdata' 2>/dev/null \
    || .venv/bin/python -m pip install -r requirements.txt
command -v git >/dev/null 2>&1 || echo 'Warning: git is not on PATH; the Code page needs it.' >&2
for option in "$@"; do
    case "$option" in
        --reset) rm -rf "$preview"; echo "Removed the preview profile $preview" ;;
        --copy-profile) .venv/bin/python scripts/copy-profile.py "$real" "$preview" ;;
        *) echo "Unknown option: $option" >&2; exit 2 ;;
    esac
done
echo "DayFrame source preview: $(git branch --show-current 2>/dev/null) $(git log -1 --format='%h %s' 2>/dev/null)"
echo "Profile: $preview"
exec .venv/bin/python app.py --data-dir "$preview"
