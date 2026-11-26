#!/usr/bin/env bash
# Start Claude Code for the studio with a clean, verified environment (25 Nov 2026).
#
# Why: a session started from the workshop folder (/home/fahad/Desktop/Youtube-automation) inherited VIRTUAL_ENV and a PATH that put the workshop's .venv first,
# and the current Docker context was Docker Desktop, whose studio containers mount the workshop as /app. A bare `python3` or a plain `docker exec` then reached
# the folder the owner forbade. This script starts Claude Code IN ~/studio with only the studio's Python and the system Docker daemon (context "default").
#
# Use:   bash /home/fahad/studio/tools/claude-studio.sh            (starts Claude Code; extra arguments go to `claude`)
#        bash /home/fahad/studio/tools/claude-studio.sh --check    (prints what the session would get and exits; starts nothing)
# It changes no global setting, shell profile, Docker context or Claude setting: everything below is for this one process and its children.
set -euo pipefail

STUDIO=/home/fahad/studio
FORBIDDEN=/home/fahad/Desktop/Youtube-automation
DOCKER_SOCK=unix:///var/run/docker.sock

cd "$STUDIO"
unset OLDPWD  # the folder this was started from (often the workshop): not needed, never inherited
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE CONDA_PREFIX CONDA_DEFAULT_ENV DOCKER_HOST DOCKER_CONFIG DOCKER_CERT_PATH DOCKER_TLS_VERIFY

# PATH: every entry inside the forbidden folder is dropped (and junk entries without a leading /), duplicates removed, the studio's venv first.
clean=$(printf '%s' "$PATH" | tr ':' '\n' | grep '^/' | grep -v "^$FORBIDDEN" | awk '!seen[$0]++' | paste -sd: -)
export PATH="$STUDIO/.venv/bin:$clean"
export VIRTUAL_ENV="$STUDIO/.venv"
export DOCKER_CONTEXT=default

fail() { echo "claude-studio: refusing to start: $*" >&2; exit 1; }
if env | grep -q "$FORBIDDEN"; then
    fail "these environment variables still point at the forbidden folder: $(env | grep "$FORBIDDEN" | cut -d= -f1 | paste -sd' ' -)"
fi
py=$(command -v python3)
[ "$py" = "$STUDIO/.venv/bin/python3" ] || fail "python3 resolves to $py, not the studio's $STUDIO/.venv/bin/python3"
prefix=$("$py" -I -c 'import sys; print(sys.prefix)')
[ "$prefix" = "$STUDIO/.venv" ] || fail "the studio interpreter reports sys.prefix $prefix"
endpoint=$(docker context inspect default --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)
[ "$endpoint" = "$DOCKER_SOCK" ] || fail "docker context 'default' points at '$endpoint', not $DOCKER_SOCK"
mount=$(docker --context default inspect studio-worker --format '{{range .Mounts}}{{if eq .Destination "/app"}}{{.Source}}{{end}}{{end}}' 2>/dev/null || true)
[ -z "$mount" ] || [ "$mount" = "$STUDIO" ] || fail "the default daemon's studio-worker mounts $mount as /app, not $STUDIO"

if [ "${1:-}" = "--check" ]; then
    echo "cwd:            $(pwd -P)"
    echo "python3:        $py (sys.prefix $prefix)"
    echo "docker context: $DOCKER_CONTEXT -> $endpoint"
    echo "studio-worker:  /app <- ${mount:-not running}"
    echo "forbidden folder on PATH: $(printf '%s' "$PATH" | tr ':' '\n' | grep -c "^$FORBIDDEN" || true)"
    exit 0
fi
command -v claude >/dev/null || fail "the claude command is not on PATH"
exec claude "$@"
