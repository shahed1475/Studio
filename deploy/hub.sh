#!/usr/bin/env bash
# The Creator Hub's container. Subcommands:
#   build                       build the image from `git archive HEAD` of exactly the files in deploy/Dockerfile.hub (uncommitted changes are not included)
#   check [--public] [--open]   look at the settings without starting anything; --public is the stricter set a public launch needs
#   up [--public] [--open]      check, then start the container (needs the image)
#   down                        stop it (the data stays: this is also the rollback)
#   restart                     recreate the container so changed settings are read
#   configure                   the Gmail and Google prompt (python -m hub.configure) in a throwaway container; then run restart
#   status | logs               what is running; the last 100 log lines
#   backup                      a consistent copy of the database into ~/hub/backups, seven kept
#   caddy-block                 print the web-proxy site block for $HUB_HOST (deploy/tenant.sh caddy adds it when HUB_HOST is set)
#   caddy-merge FILE            print the proxy file with the hub block added or replaced (never writes)
#   caddy-apply --public [--open]  put the hub on the studio's proxy: validate with real Caddy, write in place, reload gracefully, undo if refused
# It never touches the studio's containers: its own compose project ("hub"), image (nightloom-hub:local), network and folder (~/hub). DRY=1 prints what would run.
# Settings and secrets live in ~/hub/secrets/hub.env (mode 600, delivered by scp, never git). This script reads that file and never prints a value from it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
HUB_HOME="${HUB_HOME:-$HOME/hub}"
ENV_FILE="$HUB_HOME/secrets/hub.env"
DATA="$HUB_HOME/data"
IMAGE="nightloom-hub:local"
MODULES="agentlog.py config.py filelock.py niche.py topicqueue.py topicrank.py wikipedia.py"
STAGE=""; CAND=""; PREV=""
BEGIN_MARK="# >>> creator-hub (managed by deploy/hub.sh caddy-apply; deploy/tenant.sh caddy rewrites this file, so run caddy-apply again after it)"
END_MARK="# <<< creator-hub"
cleanup() {  # scratch files and folders this script made, whichever way it ends
  if [[ -n "$STAGE" && -d "$STAGE" ]]; then chmod -R u+w "$STAGE"; rm -r -- "$STAGE"; fi
  if [[ -n "$CAND" ]]; then rm -f -- "$CAND"; fi
  if [[ -n "$PREV" ]]; then rm -f -- "$PREV"; fi
  return 0
}
trap cleanup EXIT

die() { echo "hub.sh: $*" >&2; exit 2; }
run() { if [[ "${DRY:-0}" == "1" ]]; then echo "DRY: $*"; else "$@"; fi; }
has() { grep -qE "^$1=.+" "$ENV_FILE"; }
MAIL_DIR="${HUB_MAIL_DIR:-$HOME/studio/data/hubmail}"   # written by the studio dashboard (Settings, Mail for the Creator Hub); mounted read-only
compose() { mkdir -p "$MAIL_DIR"; chmod 700 "$MAIL_DIR"; HUB_MAIL_DIR="$MAIL_DIR" HUB_ENV_FILE="$ENV_FILE" HUB_DATA_DIR="$DATA" HUB_UID="$(id -u)" HUB_GID="$(id -g)" run docker compose -f "$HERE/hub-compose.yml" "$@"; }

check() {
  local public=0 open=0 a
  for a in "$@"; do case "$a" in --public) public=1 ;; --open) open=1 ;; *) die "unknown option $a" ;; esac; done
  [[ -f "$ENV_FILE" ]] || die "no settings file at $ENV_FILE (copy hub.env there with scp, then chmod 600)"
  [[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || die "$ENV_FILE must be mode 600 (chmod 600 it)"
  [[ "$(stat -c %u "$ENV_FILE")" == "$(id -u)" ]] || die "$ENV_FILE must belong to the user running this script"
  has HUB_KEYSTORE_KEY || die "HUB_KEYSTORE_KEY is missing from hub.env (the key that encrypts creators' AI keys)"
  if (( public )); then
    if grep -qE '^HUB_INSECURE_DEV=1' "$ENV_FILE"; then die "HUB_INSECURE_DEV=1 must not be set for a public launch"; fi
    grep -qE '^HUB_PUBLIC_URL=https://[^ ]+' "$ENV_FILE" || die "HUB_PUBLIC_URL must be an https:// address for a public launch"
    has HUB_CONTACT || die "HUB_CONTACT is missing: the public privacy page needs a contact line. Set it with  hub.sh configure --contact"
    if ! has HUB_ALLOWED_EMAILS && (( ! open )); then die "sign-up would be open to anyone: set HUB_ALLOWED_EMAILS, or add --open to choose open sign-up on purpose"; fi
  fi
  echo "hub.sh: settings look right"
}

caddy_block() {
  local h="${HUB_HOST:-}"
  [[ "$h" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ && ${#h} -le 253 ]] || die "HUB_HOST must be a lower-case host name like hub.example.org"
  cat <<EOF
$h {
  encode zstd gzip
  request_body {
    max_size 128KB
  }
  reverse_proxy 127.0.0.1:8931
}
EOF
}

caddy_merge() {
  # the proxy file with the hub's block added, or replaced if it is already there: prints, never writes. Everything else in the file is kept exactly.
  local f="${1:-}"
  [[ -n "$f" && -f "$f" ]] || die "caddy-merge needs the proxy file (for example ~/tenants/caddy/Caddyfile)"
  local block; block="$(caddy_block)"
  awk -v endmark="$END_MARK" '
    index($0, "# >>> creator-hub") == 1 { skip = 1 }
    !skip { lines[n++] = $0 }
    skip && index($0, endmark) == 1 { skip = 0 }
    END { while (n > 0 && lines[n-1] ~ /^[ \t]*$/) n--; for (i = 0; i < n; i++) print lines[i] }
  ' "$f"
  printf '\n%s\n%s\n%s\n' "$BEGIN_MARK" "$block" "$END_MARK"
}

caddy_apply() {
  # Put the hub on the studio's web proxy (HUB_HOST, on 443). Only for a hub that passes  check --public. The new file is validated by the real Caddy first, written IN PLACE
  # (the proxy bind-mounts this one file: a rename would leave it reading the old one), and the proxy is reloaded gracefully; if the reload is refused the old file is put back.
  check --public "$@"
  local dir="${TENANTS_DIR:-$HOME/tenants}/caddy" f out
  f="$dir/Caddyfile"
  [[ -f "$f" ]] || die "no proxy file at $f"
  CAND="$dir/.hub-candidate.$$"; PREV="$dir/.hub-previous.$$"
  caddy_merge "$f" > "$CAND"
  cp -p "$f" "$PREV"
  if ! out="$(run docker run --rm -v "$CAND:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1)"; then
    echo "$out" | tail -5 >&2; die "the new proxy file did not validate; nothing was changed"
  fi
  echo "$out" | tail -1
  [[ -e "$f.bak-before-hub" ]] || run cp -p "$f" "$f.bak-before-hub"
  run sh -c 'cat "$1" > "$2"' _ "$CAND" "$f"
  if ! run docker exec studio-proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
    run sh -c 'cat "$1" > "$2"' _ "$PREV" "$f"
    die "the proxy did not accept the new file; the old file is back"
  fi
  echo "hub.sh: the hub is on the proxy at https://${HUB_HOST}"
}

build() {
  command -v docker >/dev/null || die "docker is not installed"
  if [[ "${DRY:-0}" == "1" ]]; then echo "DRY: git archive HEAD hub $MODULES deploy/Dockerfile.hub deploy/hub-requirements.txt | docker build -t $IMAGE"; return; fi
  STAGE="$(mktemp -d /tmp/hub-build-XXXXXX)"
  # shellcheck disable=SC2086
  git -C "$REPO" archive --format=tar HEAD hub $MODULES deploy/Dockerfile.hub deploy/hub-requirements.txt | tar -x -C "$STAGE"
  docker build -f "$STAGE/deploy/Dockerfile.hub" -t "$IMAGE" "$STAGE"
}

up() {
  check "$@"
  if [[ "${DRY:-0}" != "1" ]]; then
    docker image inspect "$IMAGE" >/dev/null 2>&1 || die "no image yet: run  deploy/hub.sh build  first"
    mkdir -p "$DATA"; chmod 700 "$DATA"
  fi
  compose up -d
}

configure() {
  # the terminal prompt for the Gmail app password and the Google client id, run in a throwaway locked-down container with only the secrets folder mounted:
  # what is typed goes straight into ~/hub/secrets/hub.env (mode 600) and nowhere else. Run it as  ssh -t <server> '~/hub/deploy/hub.sh configure', then  hub.sh restart.
  [[ -f "$ENV_FILE" ]] || die "no settings file at $ENV_FILE yet"
  run docker run -it --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:size=8m,noexec,nosuid -u "$(id -u):$(id -g)" \
    -v "$HUB_HOME/secrets:/secrets" "$IMAGE" python -m hub.configure --file /secrets/hub.env "$@"
}

backup() {
  local dest="$HUB_HOME/backups" stamp f
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  if [[ "${DRY:-0}" != "1" ]]; then mkdir -p "$dest"; chmod 700 "$dest"; fi
  run docker exec nightloom-hub python -c "import sqlite3; s = sqlite3.connect('/app/data/hub/hub.db'); d = sqlite3.connect('/app/data/hub/backup.tmp'); s.backup(d); d.close(); s.close()"
  run mv "$DATA/backup.tmp" "$dest/hub-$stamp.db"
  if [[ "${DRY:-0}" != "1" ]]; then
    chmod 600 "$dest/hub-$stamp.db"
    # keep the seven newest; only files named like our own backups are ever removed
    ls -1t "$dest" | grep -E '^hub-[0-9]{8}-[0-9]{6}\.db$' | tail -n +8 | while read -r f; do rm -- "$dest/$f"; done
  fi
}

case "${1:-}" in
  build) build ;;
  check) shift; check "$@" ;;
  up) shift; up "$@" ;;
  down) compose down ;;
  restart) check; compose up -d --force-recreate ;;  # a plain restart does not re-read the env file; recreating does
  configure) shift; configure "$@" ;;
  status) run docker ps --filter name=nightloom-hub --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' ;;
  logs) run docker logs --tail 100 nightloom-hub ;;
  backup) backup ;;
  caddy-block) caddy_block ;;
  caddy-merge) shift; caddy_merge "$@" ;;
  caddy-apply) shift; caddy_apply "$@" ;;
  *) sed -n "2,13p" "${BASH_SOURCE[0]}"; exit 1 ;;
esac
