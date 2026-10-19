#!/usr/bin/env bash
# Opens the server dashboard at http://127.0.0.1:8913 on this computer. Keep it running while you use the dashboard.
set -euo pipefail
: "${STUDIO_VPS:?set STUDIO_VPS=user@host}"
exec ssh -N -o ServerAliveInterval=30 -L 8913:127.0.0.1:8913 "$STUDIO_VPS"
