#!/usr/bin/env bash
# Run one clip test inside a TEST studio worker container over ssh, then copy the clip and its ledger row back and check the hash.
# Needs: FOOTAGE_SSH_TARGET (user@host), FOOTAGE_CONTAINER (must be in FOOTAGE_ALLOWED_CONTAINERS, default: the test worker).
# Optional: FOOTAGE_SSH_KEY, FOOTAGE_LOCAL_OUT, FOOTAGE_REMOTE_DIR.
set -euo pipefail
: "${FOOTAGE_SSH_TARGET:?set FOOTAGE_SSH_TARGET=user@host}"
: "${FOOTAGE_CONTAINER:?set FOOTAGE_CONTAINER to the test studio worker container}"
ALLOWED="${FOOTAGE_ALLOWED_CONTAINERS:-studio-test-worker}"
case " $ALLOWED " in *" $FOOTAGE_CONTAINER "*) ;; *) echo "refusing: $FOOTAGE_CONTAINER is not an allowed test container (the owner studio is never allowed)"; exit 2;; esac
[[ "$FOOTAGE_CONTAINER" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "bad container name"; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${FOOTAGE_LOCAL_OUT:-./footage-out}"
REMOTE_DIR="${FOOTAGE_REMOTE_DIR:-render-out}"
[[ "$REMOTE_DIR" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "bad FOOTAGE_REMOTE_DIR"; exit 2; }
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15); SCP=(scp -q)
[ -z "${FOOTAGE_SSH_KEY:-}" ] || { SSH+=(-i "$FOOTAGE_SSH_KEY"); SCP+=(-i "$FOOTAGE_SSH_KEY"); }
mkdir -p "$OUT"
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
"${SSH[@]}" "$FOOTAGE_SSH_TARGET" "docker exec -i $FOOTAGE_CONTAINER python3 -" < "$HERE/clipgen.py" | tee "$LOG"
RES="$(sed -n 's/^RESULT //p' "$LOG" | tail -1)"
[ -n "$RES" ] || { echo "no RESULT line: the run failed (see above); a printed 'job:' line means money may have been spent"; exit 1; }
field() { python3 -c 'import json,sys;print(json.loads(sys.argv[1])[sys.argv[2]])' "$RES" "$1"; }
for k in clip ledger; do
  P="$(field "$k")"
  [[ "$P" =~ ^/[A-Za-z0-9_./-]+$ && "$P" != *..* ]] || { echo "refusing an unsafe path from the container: $P"; exit 1; }
  B="$(basename "$P")"
  "${SSH[@]}" "$FOOTAGE_SSH_TARGET" "mkdir -p ~/$REMOTE_DIR && docker cp $FOOTAGE_CONTAINER:$P ~/$REMOTE_DIR/" \
    || { echo "docker cp failed; $P is still inside $FOOTAGE_CONTAINER"; exit 1; }
  "${SSH[@]}" "$FOOTAGE_SSH_TARGET" "docker exec $FOOTAGE_CONTAINER rm -f $P" || echo "warning: could not remove $P inside the container"
  "${SCP[@]}" "$FOOTAGE_SSH_TARGET:$REMOTE_DIR/$B" "$OUT/" || { echo "scp failed; the file is in ~/$REMOTE_DIR on the server"; exit 1; }
  [ -s "$OUT/$B" ] || { echo "copied $k file is empty"; exit 1; }
done
WANT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["sha256"])' "$OUT/$(basename "$(field ledger)")")"
GOT="$(sha256sum "$OUT/$(basename "$(field clip)")" | cut -d' ' -f1)"
[ "$WANT" = "$GOT" ] || { echo "HASH MISMATCH: the copied clip is not the one in the ledger row"; exit 1; }
echo "saved to $OUT (hash matches the ledger row)"
