#!/usr/bin/env bash
# Start Claude Code for the studio with a clean, verified environment (25 Nov 2026).
#
# Why: a session started from the workshop folder (/home/fahad/Desktop/Youtube-automation) inherited VIRTUAL_ENV and a PATH that put the workshop's .venv first,
# and the current Docker context was Docker Desktop, whose studio containers mount the workshop as /app. A bare `python3` or a plain `docker exec` then reached
# the folder the owner forbade. This script starts Claude Code IN ~/studio with only the studio's Python and the system Docker daemon (context "default").
#
# Use:   bash /home/fahad/studio/tools/claude-studio.sh            (starts Claude Code; extra arguments go to `claude`)
#        bash /home/fahad/studio/tools/claude-studio.sh --check    (prints what the session would get and exits; starts nothing)
# Run both from a normal terminal: inside a Claude Code session it refuses, and so does a docker daemon it cannot ask.
# Tests: tests/test_claude_studio_launcher.py (fake docker and claude, empty environment).
# It changes no global setting, shell profile, Docker context or Claude setting: everything below is for this one process and its children.
set -euo pipefail

STUDIO=/home/fahad/studio
FORBIDDEN=/home/fahad/Desktop/Youtube-automation
DOCKER_SOCK=unix:///var/run/docker.sock

fail() { echo "claude-studio: refusing to start: $*" >&2; exit 1; }

# Inside a Claude Code session (26 Nov 2026): a shell that Claude Code started keeps that session's start folder, sandbox
# and git trust (GIT_CONFIG_* safe.directory), so nothing started from it is clean. Never unset those variables to get past this.
if [ -n "${CLAUDECODE:-}" ]; then
    fail "this shell belongs to a running Claude Code session (it keeps that session's folder, sandbox and git settings). Exit Claude Code, open a normal terminal and run: bash $STUDIO/tools/claude-studio.sh"
fi

cd "$STUDIO"
unset OLDPWD  # the folder this was started from (often the workshop): not needed, never inherited
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE CONDA_PREFIX CONDA_DEFAULT_ENV DOCKER_HOST DOCKER_CONFIG DOCKER_CERT_PATH DOCKER_TLS_VERIFY

# PATH: every entry inside the forbidden folder is dropped (and junk entries without a leading /), duplicates removed, the studio's venv first.
clean=$(printf '%s' "$PATH" | tr ':' '\n' | grep '^/' | grep -v "^$FORBIDDEN" | awk '!seen[$0]++' | paste -sd: -)
export PATH="$STUDIO/.venv/bin:$clean"
export VIRTUAL_ENV="$STUDIO/.venv"
export DOCKER_CONTEXT=default

if env | grep -q "$FORBIDDEN"; then
    fail "these environment variables still point at the forbidden folder: $(env | grep "$FORBIDDEN" | cut -d= -f1 | paste -sd' ' -)"
fi
py=$(command -v python3)
[ "$py" = "$STUDIO/.venv/bin/python3" ] || fail "python3 resolves to $py, not the studio's $STUDIO/.venv/bin/python3"
prefix=$("$py" -I -c 'import sys; print(sys.prefix)')
[ "$prefix" = "$STUDIO/.venv" ] || fail "the studio interpreter reports sys.prefix $prefix"
endpoint=$(docker context inspect default --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)
[ "$endpoint" = "$DOCKER_SOCK" ] || fail "docker context 'default' points at '$endpoint', not $DOCKER_SOCK"
# Fails closed (26 Nov 2026): only "no such container" counts as not running. Any other docker error (daemon down,
# permission denied) refuses, so a worker whose mount could not be read is never reported as fine.
if mount=$(docker --context default inspect studio-worker --format '{{range .Mounts}}{{if eq .Destination "/app"}}{{.Source}}{{end}}{{end}}' 2>&1); then
    [ -z "$mount" ] || [ "$mount" = "$STUDIO" ] || fail "the default daemon's studio-worker mounts $mount as /app, not $STUDIO"
elif printf '%s' "$mount" | grep -q -i -E 'no such (object|container)'; then
    mount=""
else
    fail "cannot ask the default docker daemon about studio-worker: $(printf '%s' "$mount" | head -n 1)"
fi

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
