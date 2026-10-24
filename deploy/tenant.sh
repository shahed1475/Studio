#!/usr/bin/env bash
# User studios on this server. Run it ON the server (ssh in, cd ~/studio):  deploy/tenant.sh <command>
#   create <name>          a new user studio. Everyone uses https://HOST (port 443, the only public port besides 80): the invite link
#                          https://HOST/u/<name>/claim?token=... sets a cookie that sends that browser to its own studio
#   invite <name>          a first-sign-in link, valid 24 hours and once: the user chooses their own password
#   list                   every user studio, whether it runs, and its storage
#   stop|start <name>      pause or resume one
#   sync [name|all]        copy the newest code into the user studios (the worker is restarted only when no video is rendering)
#   remove <name>          stop it and move its folder to ~/tenants-removed (nothing is deleted)
#   quota                  storage per user studio, and refreshes data/tenants.json (the owner's Risks card reads it; run hourly from cron)
#   caddy                  rebuild the web proxy's routes and (re)start it
# Their settings live in ~/tenants/.meta (owner-only, not mounted). Never copied to a user: .env, settings.json, llm.json, token.json, data, videos. client_secret.json is copied once (owner-only file) so the user can sign in to Google.
set -euo pipefail
BASE="${STUDIO_TENANTS_DIR:-$HOME/tenants}"
SRC="${STUDIO_SRC:-$HOME/studio}"
HOST="${STUDIO_PUBLIC_HOST:-srv2029460.hstgr.cloud}"
GATE="$BASE/.gate"
META="$BASE/.meta"   # one owner-only settings file per user studio, OUTSIDE the folder the user's containers can write; it is read with strict patterns and never sourced
MAX_TENANTS="${STUDIO_MAX_TENANTS:-5}"
export STUDIO_UID="$(id -u)" STUDIO_GID="$(id -g)"
EXCLUDES=(--exclude .git --exclude .venv --exclude '__pycache__' --exclude 'render' --exclude 'output' --exclude 'output_old' --exclude 'cache' --exclude 'data' --exclude 'logs' --exclude 'ready'
  --exclude '.env' --exclude '.env.*' --exclude 'settings.json' --exclude 'llm.json*' --exclude 'agent.json' --exclude 'autopilot.json*' --exclude 'autopilot_state.json'
  --exclude 'token.json*' --exclude 'client_secret*.json' --exclude 'niche.json' --exclude 'topics.json*' --exclude 'news_topics.json' --exclude 'pinned_topics.json'
  --exclude 'edit_profile.json' --exclude 'reference_channels.json' --exclude 'reference_meta.json' --exclude '*.lock' --exclude '*.bak*' --exclude 'job.pid' --exclude 'tests' --exclude 'music' --exclude 'branding')

die() { echo "tenant.sh: $*" >&2; exit 1; }
valid_name() { [[ "$1" =~ ^[a-z][a-z0-9]{1,14}$ ]] || die "the name must be 2 to 15 lowercase letters or digits, starting with a letter"; }
tdir() { echo "$BASE/$1"; }
exists() { [[ -d "$(tdir "$1")" ]] || die "no user studio named $1"; }
dash_port() { # the studio's internal port, read from the settings file and checked before any use
  local p; p="$(sed -n 's/^DASH_PORT=\(.*\)$/\1/p' "$META/$1.env" | head -1)"
  [[ "$p" =~ ^189[2-9][0-9]$ && "$p" -ge 18921 ]] || die "bad port in the settings of $1"
  echo "$p"
}
next_port() { # a port is never reused while the proxy's route file or the removed-studio records still name it
  local p; for p in $(seq 18921 18999); do
    grep -qsE "^DASH_PORT=$p$" "$META"/*.env "$HOME"/tenants-removed/*.env && continue
    grep -qs "127.0.0.1:$p\$" "$BASE/caddy/Caddyfile" && continue
    echo "$p"; return
  done; die "no free port"; }
compose() { # compose <name> <args...>: the user's folder is mounted, the settings come from the owner-only file
  local n="$1"; shift
  GATE_DIR="$GATE" docker compose --env-file "$META/$n.env" -f "$SRC/deploy/tenant-compose.yml" --project-directory "$(tdir "$n")" "$@"
}
owner_channels() { # the owner's channel ids, read from the owner's own login; letters, digits, - and _ only
  docker exec studio-dashboard python -c "import dashboard; print(dashboard.yt_channel()['id'])" 2>/dev/null | tr -cd 'A-Za-z0-9_,-' | head -c 200
}
studios() { local f; for f in "$META"/*.env; do [[ -f "$f" ]] && basename "$f" .env; done; true; }
render_running() { docker exec "studio-$1-worker" sh -c 'for p in /proc/[0-9]*/cmdline; do tr "\0" " " < "$p" 2>/dev/null; echo; done' 2>/dev/null | grep -qE 'run\.py (doc|make|redo|clip|newsvideo|batch|autopilot)|ffmpeg' || return 1; }

# Code only, never --delete: a user's own files (videos, settings, login) are never removed by a sync.
copy_code() { rsync -a "${EXCLUDES[@]}" "$SRC/" "$(tdir "$1")/"; }

cmd_create() {
  local n="${1:?name}" port
  valid_name "$n"
  [[ ! -e "$(tdir "$n")" ]] || die "$n already exists"
  [[ "$HOST" =~ ^[A-Za-z0-9.-]+$ ]] || die "STUDIO_PUBLIC_HOST must be a plain host name"
  [[ $(studios | wc -l) -lt "$MAX_TENANTS" ]] || die "the limit of $MAX_TENANTS user studios is reached"
  mkdir -p -m 700 "$META"; port="$(next_port)"
  [[ -d "$SRC" ]] || die "the owner's studio folder $SRC is missing"
  mkdir -p "$(tdir "$n")" "$GATE"; mkdir -p -m 700 "$META"
  copy_code "$n"
  mkdir -p "$(tdir "$n")/data" "$(tdir "$n")/output" "$(tdir "$n")/logs" "$(tdir "$n")/cache" "$(tdir "$n")/branding"
  if [[ -f "$SRC/client_secret.json" ]]; then cp "$SRC/client_secret.json" "$(tdir "$n")/client_secret.json"; chmod 600 "$(tdir "$n")/client_secret.json"; fi
  cat > "$META/$n.env" <<ENV
TENANT=$n
PUBLIC_HOST=$HOST
DASH_PORT=$port
OWNER_CHANNELS=$(owner_channels)
ENV
  chmod 600 "$META/$n.env"
  compose "$n" up -d
  echo "created $n (internal port $port). Next: deploy/tenant.sh caddy   to publish it, then: deploy/tenant.sh invite $n"
}

cmd_invite() {
  local n="${1:?name}"; exists "$n"
  docker exec "studio-$n-dashboard" python tenantmode.py invite "https://$HOST/u/$n"
}

cmd_list() {
  printf '%-12s %-7s %-9s %s\n' name port state storage
  local rows=""
  for n in $(studios); do
    st="$(docker inspect -f '{{.State.Status}}' "studio-$n-dashboard" 2>/dev/null || echo missing)"
    q="$(docker exec "studio-$n-dashboard" python tenantmode.py quota 2>/dev/null || echo '{}')"
    printf '%-12s %-7s %-9s %s\n' "$n" "$(dash_port "$n")" "$st" "$q"
    rows+="$n|$st|$q"$'\n'
  done
  write_status "$rows"
}

write_status() { # data/tenants.json in the owner's studio: name, state, storage, proxy; read by the Risks card
  local proxy="missing"; [[ "$(docker inspect -f '{{.State.Status}}' studio-proxy 2>/dev/null)" == running ]] && proxy="running"
  ROWS="$1" PROXY="$proxy" python3 - "$SRC/data/tenants.json" <<'PY'
import json, os, sys, datetime as dt
studios = []
for line in os.environ["ROWS"].splitlines():
    name, state, q = (line.split("|", 2) + ["{}"])[:3]
    try:
        q = json.loads(q)
    except ValueError:
        q = {}
    studios.append({"name": name, "state": state, "used_gb": q.get("used_gb"), "pct": q.get("pct"), "quota": q.get("state", "unknown")})
os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)
json.dump({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "proxy": os.environ["PROXY"], "studios": studios}, open(sys.argv[1], "w"))
PY
}

cmd_stop() { exists "${1:?name}"; compose "$1" stop; }
cmd_start() { exists "${1:?name}"; compose "$1" up -d; }

cmd_sync() {
  local which="${1:-all}" names=()
  if [[ "$which" == all ]]; then mapfile -t names < <(studios); else exists "$which"; names=("$which"); fi
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
  mv "$META/$n.env" "$HOME/tenants-removed/$n-$(date -u +%Y%m%d%H%M).env"
  cmd_caddy >/dev/null   # its route goes at once, so a later studio on the same internal port can never be reached through the old cookie
  echo "removed $n (its folder is in ~/tenants-removed; delete it yourself when you are sure)"
}

cmd_quota() { cmd_list; }

cmd_caddy() {
  mkdir -p "$BASE/caddy/data" "$BASE/caddy/config"
  {
    echo "$HOST {"
    for n in $(studios); do
      p="$(dash_port "$n")"   # checked: five digits from 18921, so nothing else can reach the proxy's settings
      echo "  @t_$n header_regexp tc Cookie (^|;\\s*)studio_tenant=$n(;|\$)"
      echo "  @enter_$n path /u/$n /u/$n/"
      echo "  @claim_$n path /u/$n/claim"
      echo "  handle @enter_$n {"; echo "    header Set-Cookie \"studio_tenant=$n; Path=/; Max-Age=31536000; Secure; HttpOnly; SameSite=Lax\""; echo "    redir * / 303"; echo "  }"
      echo "  handle @claim_$n {"; echo "    header Set-Cookie \"studio_tenant=$n; Path=/; Max-Age=31536000; Secure; HttpOnly; SameSite=Lax\""; echo "    redir * /claim?{query} 303"; echo "  }"
      # the browser sends every studio's session cookie to this one address: this studio gets its own and nothing else (RE2 has no look-ahead, so its own is set aside, the rest removed, its own put back)
      echo "  handle @t_$n {"; echo "    reverse_proxy 127.0.0.1:$p {"
      echo "      header_up Cookie \"studio_session_$n=\" \"__own=\""
      echo "      header_up Cookie \"studio_(session|tenant)[A-Za-z0-9_]*=[^;]*;?[ ]*\" \"\""
      echo "      header_up Cookie \"__own=\" \"studio_session_$n=\""
      echo "    }"; echo "  }"
    done
    echo "  handle {"; echo "    respond \"Story Studio. Open the link you were sent.\" 200"; echo "  }"
    echo "}"
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
