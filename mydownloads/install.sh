#!/usr/bin/env bash
# Sets My Downloads up as a background service on THIS computer, so it is running again after every restart or power cut.
# Run it once:  mydownloads/install.sh      Remove it:  systemctl --user disable --now studio-mydownloads
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
py="$here/.venv/bin/python"
[ -x "$py" ] || { echo "Missing $py. Create the project's virtual environment first." >&2; exit 1; }
"$py" -c "import yt_dlp" 2>/dev/null || { echo "yt-dlp is missing. Run: $py -m pip install -r $here/mydownloads/requirements.txt" >&2; exit 1; }
command -v ffmpeg >/dev/null || echo "Warning: ffmpeg is not installed, so picture and sound cannot be joined. Install it first." >&2
unit="$HOME/.config/systemd/user/studio-mydownloads.service"
mkdir -p "$(dirname "$unit")"
sed "s|@REPO@|$here|g" "$here/mydownloads/service/studio-mydownloads.service" > "$unit"
systemctl --user daemon-reload
systemctl --user enable --now studio-mydownloads.service
sleep 1
systemctl --user --no-pager --lines=3 status studio-mydownloads.service | head -8 || true
echo "My Downloads is running at http://127.0.0.1:8923  (the dashboard's Downloads page opens it)"
