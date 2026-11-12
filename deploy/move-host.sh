#!/usr/bin/env bash
# Move the studio (and the Creator Hub) to a NEW server (13 Nov 2026, the VPS subscription ends).
# Run it from the owner's PC. It only READS from the old server and only ADDS files on the new one: no --delete, no rm, nothing on the old server is changed or stopped.
#   NEW=deploy@new-host [OLD=deploy@vps-ai] [BACKUP=$HOME/vps-backup-2026-11-13] deploy/move-host.sh <step> [--dry]
# Steps, in order:
#   check     the new host has Docker, Compose, disk and RAM; the old one is reachable
#   studio    copy the studio folder (from the PC backup), load the studio image (from the old server), set the private address, start ONLY the dashboard
#   hub       copy the hub folder and image, start it, put Caddy in front on the new address (https://hub.<ip>.sslip.io)
#   verify    health checks on the new host
#   worker    start the worker on the new host. Refuses unless you type the confirmation: two workers could upload one video twice. Stop the old worker FIRST (docker stop studio-worker on the old server; that stops, it does not delete).
# Needs on the new host (a one-time job for the owner, with sudo): Docker with Compose, Tailscale (tailscale up --hostname vps-ai-new), an ssh login for the deploy user, ports 80 and 443 open for the hub.
set -euo pipefail
: "${NEW:?set NEW=user@new-host}"
OLD="${OLD:-deploy@vps-ai}"
BACKUP="${BACKUP:-$HOME/vps-backup-2026-11-13}"
STEP="${1:-}"; DRY=0; [[ "${2:-}" == "--dry" ]] && DRY=1
say() { printf '%s\n' "$*"; }
run() { say "+ $*"; (( DRY )) || "$@"; }
rsh() { say "+ ssh $NEW $*"; (( DRY )) || ssh "$NEW" "$@"; }
newip() { ssh "$NEW" 'curl -4 -fsS --max-time 8 https://api.ipify.org || hostname -I | cut -d" " -f1'; }
host_for() { echo "hub.$(echo "$1" | tr . -).sslip.io"; }

case "$STEP" in
check)
  ssh -o ConnectTimeout=8 "$OLD" 'echo "old server reachable: $(hostname)"'
  ssh -o ConnectTimeout=8 "$NEW" 'echo "new server: $(hostname)"; docker --version; docker compose version; df -h / | tail -1; echo "cpus: $(nproc)"; free -g | sed -n 2p; (tailscale ip -4 2>/dev/null || echo "tailscale: NOT installed or not up")'
  [[ -d "$BACKUP/studio" ]] && say "backup folder found: $BACKUP ($(du -sh "$BACKUP" | cut -f1))" || { say "NO backup folder at $BACKUP"; exit 1; }
  ;;
studio)
  [[ -d "$BACKUP/studio" ]] || { say "no backup at $BACKUP"; exit 1; }
  if ssh "$NEW" 'test -s ~/studio/.env' && [[ "${FORCE:-0}" != "1" ]]; then say "The new host already has ~/studio/.env: refusing to copy over it (FORCE=1 overrides)."; exit 2; fi
  run rsync -a "$BACKUP/studio/" "$NEW:studio/"                       # add only; never --delete
  say "+ (old server) docker save studio:local | (new server) docker load"
  (( DRY )) || ssh "$OLD" 'docker save studio:local | gzip -1' | ssh "$NEW" 'gunzip | docker load'
  TS_IP="${NEW_TS_IP:-$(ssh "$NEW" 'tailscale ip -4 2>/dev/null | head -1' || true)}"
  [[ -n "$TS_IP" ]] || { say "The new host has no Tailscale address yet. Run: sudo tailscale up --hostname vps-ai-new, then repeat with NEW_TS_IP=<its 100.x address>."; exit 3; }
  rsh "cd studio && cp -n .env .env.from-old-server && sed -i 's/^STUDIO_BIND=.*/STUDIO_BIND=$TS_IP/' .env && sed -i 's/^STUDIO_HOSTS=.*/STUDIO_HOSTS=$TS_IP,vps-ai-new/' .env && grep -E '^STUDIO_(BIND|HOSTS)=' .env"
  rsh 'cd studio && export STUDIO_UID=$(id -u) STUDIO_GID=$(id -g) && docker compose up -d dashboard'   # the WORKER is not started here
  say "Dashboard on the new host: http://$TS_IP:8913 (same login as before). The worker is NOT running there yet."
  ;;
hub)
  [[ -d "$BACKUP/hub" ]] || { say "no hub in the backup"; exit 1; }
  IP="${NEW_PUBLIC_IP:-$(newip)}"; H="$(host_for "$IP")"
  run rsync -a "$BACKUP/hub/" "$NEW:hub/"
  say "+ (old server) docker save nightloom-hub:local | (new server) docker load"
  (( DRY )) || ssh "$OLD" 'docker save nightloom-hub:local | gzip -1' | ssh "$NEW" 'gunzip | docker load'
  rsh "cd hub && chmod 600 secrets/hub.env && ./deploy/hub.sh restart"
  rsh "mkdir -p ~/hub/caddy && printf '%s {\n  encode zstd gzip\n  reverse_proxy 127.0.0.1:8931\n}\n' '$H' > ~/hub/caddy/Caddyfile && if docker inspect hub-caddy >/dev/null 2>&1; then docker restart hub-caddy; else docker run -d --name hub-caddy --restart unless-stopped --network host -v ~/hub/caddy/Caddyfile:/etc/caddy/Caddyfile:ro -v hub_caddy_data:/data caddy:2; fi"
  say "The hub answers on https://$H once DNS/Let's Encrypt are ready (about a minute)."
  say "Then point the Cloudflare Worker at it: set ORIGIN to https://$H in cloudflare/wrangler.jsonc and run 'npx wrangler deploy' (the old address keeps working until the old server is switched off)."
  ;;
verify)
  TS_IP="$(ssh "$NEW" 'tailscale ip -4 2>/dev/null | head -1')"
  ssh "$NEW" "curl -fsS http://$TS_IP:8913/healthz && echo ' <- dashboard ok'; curl -fsS http://127.0.0.1:8931/healthz && echo ' <- hub ok'; docker ps --format '{{.Names}} {{.Status}}' | grep -E 'studio|nightloom|caddy'"
  ;;
worker)
  say "This starts the studio's worker (Autopilot, renders, uploads) on the NEW host."
  say "Two workers at once could upload the same video twice. Have you STOPPED the old worker (docker stop studio-worker on the old server)?"
  read -r -p "Type  old worker is stopped  to continue: " ok
  [[ "$ok" == "old worker is stopped" ]] || { say "Not confirmed. Nothing started."; exit 2; }
  rsh 'cd studio && export STUDIO_UID=$(id -u) STUDIO_GID=$(id -g) && docker compose up -d worker'
  ;;
*) sed -n 2,16p "$0"; exit 2 ;;
esac
