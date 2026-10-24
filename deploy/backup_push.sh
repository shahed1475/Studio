#!/usr/bin/env bash
# Push the newest nightly backups (records only: no secrets, no videos, see backup.py) to the private records repo. Run ON the server, as the deploy user, after the 03:30 backup.
# Settings (names only here; the values live in ~/studio/.env, never in git): BACKUP_REPO_URL (a git@github.com:... address) and BACKUP_SSH_KEY_FILE (the deploy key's path on this server).
# The repo holds one commit that is replaced each time, with the newest two archives. The key is a deploy key for that one repo only.
set -euo pipefail
SRC="${STUDIO_SRC:-$HOME/studio}"
die() { echo "backup_push: $*" >&2; exit 1; }
envval() { grep -E "^$1=" "$SRC/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }   # read one line; the file is never sourced
REPO="${BACKUP_REPO_URL:-$(envval BACKUP_REPO_URL)}"
KEY="${BACKUP_SSH_KEY_FILE:-$(envval BACKUP_SSH_KEY_FILE)}"
KNOWN="${BACKUP_KNOWN_HOSTS:-$HOME/.ssh/known_hosts_studio_backup}"
[[ "$REPO" =~ ^git@github\.com:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.git$ ]] || die "BACKUP_REPO_URL is missing or not a git@github.com:owner/repo.git address"
[[ -f "$KEY" && -f "$KNOWN" ]] || die "BACKUP_SSH_KEY_FILE or the known-hosts file is missing"
mapfile -t ARCHIVES < <(ls -1t "$SRC"/backups/backup-*.tar.gz 2>/dev/null | head -2)
[[ ${#ARCHIVES[@]} -ge 1 ]] || die "no backup archive in $SRC/backups"
NEWEST="${ARCHIVES[0]}"
AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$NEWEST") ) / 3600 ))
[[ $AGE_H -lt 30 ]] || die "the newest backup is $AGE_H hours old: not pushing a stale copy as if it were fresh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp "${ARCHIVES[@]}" "$WORK/"
cd "$WORK"
git init -q -b main
git add .
git -c user.name=studio-backup -c user.email=backup@localhost commit -q -m "records backup, newest $(basename "$NEWEST")"
GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN" git push -q --force "$REPO" main
echo "backup_push: pushed ${#ARCHIVES[@]} archive(s), newest $(basename "$NEWEST"), $AGE_H h old"
