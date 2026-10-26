#!/usr/bin/env bash
# Run the whole test suite on a CLEAN checkout of HEAD (what a push would carry), not on the working folder.
# Why: another session may have uncommitted edits in this folder; a commit that only works with them would pass here and fail on the server.
# Also compiles every Python file of that checkout. Nothing is deleted with rm: the temporary folder is a git worktree and is removed by git.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="${PYTHON:-$(pwd)/.venv/bin/python}"
dir=$(mktemp -d "${TMPDIR:-/tmp}/studio-clean.XXXXXX")
trap 'git worktree remove --force "$dir" >/dev/null 2>&1 || true' EXIT
git worktree add -q --detach "$dir" HEAD
echo "Clean checkout of $(git rev-parse --short HEAD) in a temporary worktree"
( cd "$dir" && "$PY" -I -m compileall -q . >/dev/null && echo "Every Python file compiles" && "$PY" -m pytest -q )
