#!/usr/bin/env bash
# Run one clip test inside a TEST studio worker container over ssh, then copy the run's files back and check the clip's hash against its ledger row.
# Export these first (this script does not read .env):
#   FOOTAGE_SSH_TARGET   user@host                        FOOTAGE_CONTAINER   the worker container; must be listed in config/footage.json "allowed_containers"
# Optional: FOOTAGE_SSH_KEY, FOOTAGE_LOCAL_OUT (default ./footage-out), FOOTAGE_REMOTE_DIR (default render-out), FOOTAGE_CONTAINER_STORE (default /app/data/footage).
# The files stay in the studio's own data/footage folder too: the dashboard's "Footage clips" page reads them there.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$HERE/../../config/footage.json"
: "${FOOTAGE_SSH_TARGET:?set FOOTAGE_SSH_TARGET=user@host}"
: "${FOOTAGE_CONTAINER:?set FOOTAGE_CONTAINER to the test studio worker container}"
[[ "$FOOTAGE_SSH_TARGET" =~ ^[A-Za-z0-9_][A-Za-z0-9_.@:-]*$ ]] || { echo "bad FOOTAGE_SSH_TARGET"; exit 2; }
[[ "$FOOTAGE_CONTAINER" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "bad container name"; exit 2; }
ALLOWED="$(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1]))["allowed_containers"]))' "$CONFIG")" || { echo "cannot read $CONFIG"; exit 2; }
case " $ALLOWED " in *" $FOOTAGE_CONTAINER "*) ;; *) echo "refusing: $FOOTAGE_CONTAINER is not an allowed test container (the owner studio is never allowed)"; exit 2;; esac
OUT="${FOOTAGE_LOCAL_OUT:-./footage-out}"
REMOTE_DIR="${FOOTAGE_REMOTE_DIR:-render-out}"
STORE="${FOOTAGE_CONTAINER_STORE:-/app/data/footage}"
[[ "$REMOTE_DIR" =~ ^[A-Za-z0-9_][A-Za-z0-9_-]*$ ]] || { echo "bad FOOTAGE_REMOTE_DIR"; exit 2; }
[[ "$STORE" =~ ^/[A-Za-z0-9_./-]+$ && "$STORE" != *..* ]] || { echo "bad FOOTAGE_CONTAINER_STORE"; exit 2; }
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=20 -o ServerAliveCountMax=6); SCP=(scp -q -o BatchMode=yes -o ConnectTimeout=15)
[ -z "${FOOTAGE_SSH_KEY:-}" ] || { SSH+=(-i "$FOOTAGE_SSH_KEY"); SCP+=(-i "$FOOTAGE_SSH_KEY"); }
mkdir -p "$OUT"
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT

"${SSH[@]}" "$FOOTAGE_SSH_TARGET" "docker exec -i $FOOTAGE_CONTAINER python3 -" < "$HERE/clipgen.py" | tee "$LOG"
RC=${PIPESTATUS[0]}
RES="$(sed -n 's/^RESULT //p' "$LOG" | tail -1)"
if [ -z "$RES" ]; then
  JOBLINE="$(grep -m1 '^job: ' "$LOG" || true)"
  RUNLINE="$(sed -n 's/^run: //p' "$LOG" | head -1)"; [[ "$RUNLINE" =~ ^[A-Za-z0-9_-]+\ [A-Za-z0-9_-]+$ ]] || RUNLINE="<scope> <run_id>"  # the text came from the server: only a plain scope and run id go into the hint
  KEYOPT=""; [ -z "${FOOTAGE_SSH_KEY:-}" ] || KEYOPT="-i $(printf %q "$FOOTAGE_SSH_KEY") "
  echo "no RESULT line (ssh exit $RC): the run did not finish."
  [ -z "$JOBLINE" ] || echo "A paid job was sent ($JOBLINE) and its cost is booked. If the run is still going it will say so; otherwise fetch it with: ssh ${KEYOPT}$FOOTAGE_SSH_TARGET \"docker exec -i $FOOTAGE_CONTAINER python3 - --resume $RUNLINE\" < $(printf %q "$HERE/clipgen.py") (the run is on the dashboard's Footage clips page)."
  exit 1
fi
field() { python3 -c 'import json,sys;d=json.loads(sys.argv[1]);print(d["files"].get(sys.argv[2],""))' "$RES" "$1" 2>/dev/null; }
LEDGER_LOCAL="" CLIP_LOCAL=""
for k in clip ledger contact thumb log; do
  P="$(field "$k")"
  [ -n "$P" ] || { [ "$k" = clip ] || [ "$k" = ledger ] && { echo "the result lists no $k file"; exit 1; }; continue; }
  [[ "$P" =~ ^"$STORE"/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$ && "$P" != *..* ]] || { echo "refusing a path outside the footage store: $P"; exit 1; }
  B="$(basename "$P")"
  "${SSH[@]}" "$FOOTAGE_SSH_TARGET" "mkdir -p ~/$REMOTE_DIR && docker cp $FOOTAGE_CONTAINER:$P ~/$REMOTE_DIR/" || { echo "docker cp failed; $P is still inside $FOOTAGE_CONTAINER"; exit 1; }
  "${SCP[@]}" "$FOOTAGE_SSH_TARGET:$REMOTE_DIR/$B" "$OUT/" || { echo "scp failed; the file is in ~/$REMOTE_DIR on the server"; exit 1; }
  [ -s "$OUT/$B" ] || { echo "copied $k file is empty"; exit 1; }
  [ "$k" = clip ] && CLIP_LOCAL="$OUT/$B"
  [ "$k" = ledger ] && LEDGER_LOCAL="$OUT/$B"
done
WANT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["sha256"])' "$LEDGER_LOCAL")" || { echo "the ledger row cannot be read"; exit 1; }
GOT="$(sha256sum "$CLIP_LOCAL" | cut -d' ' -f1)"
[ "$WANT" = "$GOT" ] || { echo "HASH MISMATCH: the copied clip is not the one in the ledger row"; exit 1; }
echo "saved to $OUT (hash matches the ledger row)"
