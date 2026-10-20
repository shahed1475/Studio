#!/usr/bin/env bash
# Update the studio on your server. Needs: STUDIO_VPS=user@host (ssh key login), Docker with Compose on the server.
#   First time:  STUDIO_VPS=deploy@your.host deploy/deploy.sh first   (also copies your secret files by scp, never through git)
#   Later:       STUDIO_VPS=deploy@your.host deploy/deploy.sh
#
# Render-safe: the code folder is mounted into the containers, so most changes need NO restart (every job starts a fresh Python process).
# It restarts only what changed, and never the worker while a render is running (that kills the render). Override with FORCE=1.
set -euo pipefail
: "${STUDIO_VPS:?set STUDIO_VPS=user@host}"
REPO="${STUDIO_REPO:-https://github.com/shahed1475/Studio.git}"
DIR="${STUDIO_DIR:-studio}"
if [[ "${1:-}" == "first" ]]; then
  ssh "$STUDIO_VPS" "test -d $DIR/.git || git clone $REPO $DIR"
  cd "$(dirname "$0")/.."
  for f in .env client_secret.json token.json; do [[ -f "$f" ]] && scp -q "$f" "$STUDIO_VPS:$DIR/$f" && ssh "$STUDIO_VPS" "chmod 600 $DIR/$f"; done
fi
ssh "$STUDIO_VPS" "FORCE=${FORCE:-0} DIR=$DIR bash -s" <<'REMOTE'
set -euo pipefail
cd "$DIR"
OLD=$(git rev-parse HEAD)
git pull -q --ff-only
NEW=$(git rev-parse HEAD)
changed=$(git diff --name-only "$OLD" "$NEW" || true)
export STUDIO_UID=$(id -u) STUDIO_GID=$(id -g)
renders=$(docker exec studio-worker sh -c 'for p in /proc/[0-9]*/cmdline; do tr "\0" " " < "$p" 2>/dev/null; echo; done' 2>/dev/null | grep -E 'run\.py (doc|make|redo|clip|newsvideo|batch|autopilot)' | head -3 || true)
if [[ "$OLD" == "$NEW" ]]; then echo "Already up to date ($NEW)."; fi
if echo "$changed" | grep -qE '^(Dockerfile|requirements.*\.txt|docker-compose\.yml)$'; then
  if [[ -n "$renders" && "${FORCE:-0}" != "1" ]]; then
    echo "A render is running, so containers are NOT rebuilt (a restart would kill it):"; echo "$renders"
    echo "The Dockerfile, requirements or compose file changed. Run again after the render ends, or with FORCE=1."; exit 3
  fi
  docker compose up -d --build
elif echo "$changed" | grep -qE '^worker\.py$'; then
  if [[ -n "$renders" && "${FORCE:-0}" != "1" ]]; then
    echo "worker.py changed but a render is running: not restarting the worker. Restart it after the render ends."; echo "$renders"
  else
    docker compose restart worker
  fi
fi
if echo "$changed" | grep -qE '^(dashboard\.(py|html)|webauth\.py|login\.html|risk\.py|static/)'; then docker compose restart dashboard; fi
docker compose ps --format '{{.Name}} {{.Status}}'
echo "Deployed ${NEW:0:7}. Changed files: $(echo "$changed" | grep -c . || true)"
REMOTE
