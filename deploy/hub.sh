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
# It never touches the studio's containers: its own compose project ("hub"), image (nightloom-hub:local), network and folder (~/hub). DRY=1 prints what would run.
# Settings and secrets live in ~/hub/secrets/hub.env (mode 600, delivered by scp, never git). This script reads that file and never prints a value from it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
HUB_HOME="${HUB_HOME:-$HOME/hub}"
ENV_FILE="$HUB_HOME/secrets/hub.env"
DATA="$HUB_HOME/data"
PRIVACY="${HUB_PRIVACY_FILE:-$REPO/hub/web/privacy.html}"
IMAGE="nightloom-hub:local"
MODULES="agentlog.py config.py filelock.py niche.py topicqueue.py topicrank.py wikipedia.py"
STAGE=""

die() { echo "hub.sh: $*" >&2; exit 2; }
run() { if [[ "${DRY:-0}" == "1" ]]; then echo "DRY: $*"; else "$@"; fi; }
has() { grep -qE "^$1=.+" "$ENV_FILE"; }
compose() { HUB_ENV_FILE="$ENV_FILE" HUB_DATA_DIR="$DATA" HUB_UID="$(id -u)" HUB_GID="$(id -g)" run docker compose -f "$HERE/hub-compose.yml" "$@"; }

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
    if grep -q 'OWNER-TO-FILL' "$PRIVACY"; then die "the privacy page still says OWNER-TO-FILL: the owner must write the contact line first"; fi
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

build() {
  command -v docker >/dev/null || die "docker is not installed"
  if [[ "${DRY:-0}" == "1" ]]; then echo "DRY: git archive HEAD hub $MODULES deploy/Dockerfile.hub deploy/hub-requirements.txt | docker build -t $IMAGE"; return; fi
  STAGE="$(mktemp -d /tmp/hub-build-XXXXXX)"
  trap 'if [[ -n "$STAGE" && -d "$STAGE" ]]; then chmod -R u+w "$STAGE"; rm -r -- "$STAGE"; fi' EXIT
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
  *) sed -n "2,11p" "${BASH_SOURCE[0]}"; exit 1 ;;
esac
