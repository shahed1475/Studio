#!/usr/bin/env bash
# Update the studio on your server. Needs: STUDIO_VPS=user@host (ssh key login), Docker with Compose on the server.
#   First time:  STUDIO_VPS=deploy@your.host deploy/deploy.sh first   (also copies your secret files by scp, never through git)
#   Later:       STUDIO_VPS=deploy@your.host deploy/deploy.sh
set -euo pipefail
: "${STUDIO_VPS:?set STUDIO_VPS=user@host}"
REPO="${STUDIO_REPO:-https://github.com/shahed1475/Studio.git}"
DIR="${STUDIO_DIR:-studio}"
if [[ "${1:-}" == "first" ]]; then
  ssh "$STUDIO_VPS" "test -d $DIR/.git || git clone $REPO $DIR"
  cd "$(dirname "$0")/.."
  for f in .env client_secret.json token.json; do [[ -f "$f" ]] && scp -q "$f" "$STUDIO_VPS:$DIR/$f" && ssh "$STUDIO_VPS" "chmod 600 $DIR/$f"; done
fi
ssh "$STUDIO_VPS" "cd $DIR && git pull -q --ff-only && STUDIO_UID=\$(id -u) STUDIO_GID=\$(id -g) docker compose up -d --build && docker compose ps"
