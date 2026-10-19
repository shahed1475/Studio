#!/usr/bin/env bash
# Installs (or with --uninstall removes) the autopilot, news and growth agent timers as systemd USER units.
# Autopilot itself stays off until you switch it on in the dashboard.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/.config/systemd/user"
UNITS=(story-autopilot.service story-autopilot.timer story-newswatch.service story-newswatch.timer story-agent.service story-agent.timer)

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl --user disable --now story-autopilot.timer story-newswatch.timer story-agent.timer 2>/dev/null || true
  for u in "${UNITS[@]}"; do rm -f "$DEST/$u"; done
  systemctl --user daemon-reload
  echo "Timers removed."
  exit 0
fi

mkdir -p "$DEST"
for u in "${UNITS[@]}"; do sed "s#__ROOT__#$ROOT#g" "$ROOT/scripts/$u" > "$DEST/$u"; done
systemctl --user daemon-reload
systemctl --user enable --now story-autopilot.timer story-newswatch.timer story-agent.timer
echo "Installed. Next runs:"
systemctl --user list-timers 'story-*' --no-pager
