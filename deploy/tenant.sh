#!/usr/bin/env bash
# User studios on this server. Run it ON the server (ssh in, cd ~/studio):  deploy/tenant.sh <command>
#   create <name> <port>   a new user studio, port 8921..8999 (the address users open is https://HOST:<port>)
#   invite <name>          a first-sign-in link, valid 24 hours and once: the user chooses their own password
#   list                   every user studio, whether it runs, and its storage
#   stop|start <name>      pause or resume one
#   sync [name|all]        copy the newest code into the user studios (the worker is restarted only when no video is rendering)
#   remove <name>          stop it and move its folder to ~/tenants-removed (nothing is deleted)
#   quota                  storage per user studio
#   caddy                  rebuild the web proxy's address list and (re)start it
# Never copied to a user: .env, settings.json, llm.json, token.json, data, videos. client_secret.json is copied once (owner-only file) so the user can sign in to Google.
set -euo pipefail
BASE="${STUDIO_TENANTS_DIR:-$HOME/tenants}"
SRC="${STUDIO_SRC:-$HOME/studio}"
HOST="${STUDIO_PUBLIC_HOST:-srv2029460.hstgr.cloud}"
GATE="$BASE/.gate"
MAX_TENANTS="${STUDIO_MAX_TENANTS:-5}"
export STUDIO_UID="$(id -u)" STUDIO_GID="$(id -g)"
EXCLUDES=(--exclude .git --exclude .venv --exclude '__pycache__' --exclude 'output' --exclude 'output_old' --exclude 'cache' --exclude 'data' --exclude 'logs' --exclude 'ready'
  --exclude '.env' --exclude '.env.*' --exclude 'settings.json' --exclude 'llm.json*' --exclude 'agent.json' --exclude 'autopilot.json*' --exclude 'autopilot_state.json'
  --exclude 'token.json*' --exclude 'client_secret*.json' --exclude 'niche.json' --exclude 'topics.json*' --exclude 'news_topics.json' --exclude 'pinned_topics.json'
  --exclude 'edit_profile.json' --exclude 'reference_channels.json' --exclude 'reference_meta.json' --exclude '*.lock' --exclude '*.bak*' --exclude 'job.pid' --exclude 'tests' --exclude 'music' --exclude 'branding')

die() { echo "tenant.sh: $*" >&2; exit 1; }
valid_name() { [[ "$1" =~ ^[a-z][a-z0-9]{1,14}$ ]] || die "the name must be 2 to 15 lowercase letters or digits, starting with a letter"; }
tdir() { echo "$BASE/$1"; }
exists() { [[ -d "$(tdir "$1")" ]] || die "no user studio named $1"; }
public_port() { grep -E '^PUBLIC_PORT=' "$(tdir "$1")/.env" | cut -d= -f2; }
compose() { # compose <name> <args...>: from the user's own folder, with its own settings
  local n="$1"; shift
  ( cd "$(tdir "$n")" && set -a && . ./.env && set +a && GATE_DIR="$GATE" docker compose -f "$SRC/deploy/tenant-compose.yml" --project-directory "$(tdir "$n")" "$@" )
}
render_running() { docker exec "studio-$1-worker" sh -c 'for p in /proc/[0-9]*/cmdline; do tr "\0" " " < "$p" 2>/dev/null; echo; done' 2>/dev/null | grep -qE 'run\.py (doc|make|redo|clip|newsvideo|batch|autopilot)|ffmpeg' || return 1; }

# Code only, never --delete: a user's own files (videos, settings, login) are never removed by a sync.
copy_code() { rsync -a "${EXCLUDES[@]}" "$SRC/" "$(tdir "$1")/"; }

cmd_create() {
  local n="${1:?name}" port="${2:?port 8921..8999}"
  valid_name "$n"
  [[ "$port" =~ ^89[2-9][0-9]$ && "$port" -ge 8921 ]] || die "the port must be 8921 to 8999"
  [[ ! -e "$(tdir "$n")" ]] || die "$n already exists"
  [[ $(find "$BASE" -maxdepth 1 -mindepth 1 -type d ! -name '.*' ! -name caddy 2>/dev/null | wc -l) -lt "$MAX_TENANTS" ]] || die "the limit of $MAX_TENANTS user studios is reached"
  grep -qsE "^PUBLIC_PORT=$port$" "$BASE"/*/.env && die "port $port is taken"
  [[ -d "$SRC" ]] || die "the owner's studio folder $SRC is missing"
  mkdir -p "$(tdir "$n")" "$GATE"
  copy_code "$n"
  mkdir -p "$(tdir "$n")/data" "$(tdir "$n")/output" "$(tdir "$n")/logs" "$(tdir "$n")/cache" "$(tdir "$n")/branding"
  if [[ -f "$SRC/client_secret.json" ]]; then cp "$SRC/client_secret.json" "$(tdir "$n")/client_secret.json"; chmod 600 "$(tdir "$n")/client_secret.json"; fi
  cat > "$(tdir "$n")/.env" <<ENV
TENANT=$n
PUBLIC_HOST=$HOST
PUBLIC_PORT=$port
DASH_PORT=$((port + 10000))
ENV
  chmod 600 "$(tdir "$n")/.env"
  compose "$n" up -d
  echo "created $n: https://$HOST:$port  (run: deploy/tenant.sh caddy   to publish the address, then: deploy/tenant.sh invite $n)"
}

cmd_invite() {
  local n="${1:?name}"; exists "$n"
  docker exec "studio-$n-dashboard" python tenantmode.py invite "https://$HOST:$(public_port "$n")"
}

cmd_list() {
  printf '%-12s %-7s %-9s %s\n' name port state storage
  for d in "$BASE"/*/; do
    n="$(basename "$d")"; [[ "$n" == caddy || ! -f "$d/.env" ]] && continue
    st="$(docker inspect -f '{{.State.Status}}' "studio-$n-dashboard" 2>/dev/null || echo missing)"
    q="$(docker exec "studio-$n-dashboard" python tenantmode.py quota 2>/dev/null || echo '{}')"
    printf '%-12s %-7s %-9s %s\n' "$n" "$(public_port "$n")" "$st" "$q"
  done
}

cmd_stop() { exists "${1:?name}"; compose "$1" stop; }
cmd_start() { exists "${1:?name}"; compose "$1" up -d; }

cmd_sync() {
  local which="${1:-all}" names=()
  if [[ "$which" == all ]]; then for d in "$BASE"/*/; do [[ -f "$d/.env" ]] && names+=("$(basename "$d")"); done; else exists "$which"; names=("$which"); fi
  for n in "${names[@]}"; do
    copy_code "$n"
    docker restart "studio-$n-dashboard" >/dev/null 2>&1 || true
    if render_running "$n"; then echo "$n: code copied; its worker was NOT restarted (a video is rendering). Every new job already uses the new code."
    else docker restart "studio-$n-worker" >/dev/null 2>&1 || true; echo "$n: code copied and restarted"; fi
  done
}

cmd_remove() {
  local n="${1:?name}"; exists "$n"
  compose "$n" down || true
  mkdir -p "$HOME/tenants-removed"
  mv "$(tdir "$n")" "$HOME/tenants-removed/$n-$(date -u +%Y%m%d%H%M)"
  echo "removed $n (its folder is in ~/tenants-removed; delete it yourself when you are sure)"
}

cmd_quota() { cmd_list; }

cmd_caddy() {
  mkdir -p "$BASE/caddy/data" "$BASE/caddy/config"
  {
    echo "$HOST {"; echo "  respond \"Story Studio. Ask the owner for your invite link.\" 200"; echo "}"
    for d in "$BASE"/*/; do
      n="$(basename "$d")"; [[ "$n" == caddy || ! -f "$d/.env" ]] && continue
      p="$(public_port "$n")"
      echo "$HOST:$p {"; echo "  reverse_proxy 127.0.0.1:$((p + 10000))"; echo "}"
    done
  } > "$BASE/caddy/Caddyfile"
  cat > "$BASE/caddy/docker-compose.yml" <<'YML'
name: studio-proxy
services:
  caddy:
    image: caddy:2
    container_name: studio-proxy
    network_mode: host
    restart: unless-stopped
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro", "./data:/data", "./config:/config"]
    security_opt: ["no-new-privileges:true"]
YML
  ( cd "$BASE/caddy" && docker compose up -d && docker compose restart caddy >/dev/null )
  echo "proxy updated:"; cat "$BASE/caddy/Caddyfile"
}

mkdir -p "$BASE"
case "${1:-}" in
  create) shift; cmd_create "$@" ;;
  invite) shift; cmd_invite "$@" ;;
  list) cmd_list ;;
  stop) shift; cmd_stop "$@" ;;
  start) shift; cmd_start "$@" ;;
  sync) shift; cmd_sync "$@" ;;
  remove) shift; cmd_remove "$@" ;;
  quota) cmd_quota ;;
  caddy) cmd_caddy ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
