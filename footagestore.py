"""Where one footage run keeps what the dashboard shows: a record (status, error, cost, decision), a log and the files, in data/footage/<scope>/<run_id>/.
Written by tools/footage/clipgen.py, read by footageview.py and the dashboard. Every write is atomic under a lock. Nothing here touches a video's meta.json."""
import datetime as dt
import json
import re
import secrets
from pathlib import Path

import config
import filelock

ROOT = config.ROOT / "data" / "footage"
SAFE = re.compile(r"[A-Za-z0-9_-]{1,80}")
STATUSES = ("queued", "running", "done", "failed")
DECISIONS = ("used", "blocked", "fallback")  # what the studio did with the clip; None while nothing was decided
FILE_KINDS = ("clip", "ledger", "contact", "thumb", "log")  # the only things the dashboard may serve from a run
RECORD, LOG = "run.json", "run.log"
LOG_LINE_MAX = 300


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(text) -> str:
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:LOG_LINE_MAX]


def _read(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a run record")
    return data


class Run:
    """One run: its folder and the three things written to it. Created by create(), or re-opened by open_run()."""

    def __init__(self, folder: Path):
        self.dir = Path(folder)

    @property
    def record_path(self) -> Path:
        return self.dir / RECORD

    def read(self) -> dict:
        return _read(self.record_path)

    def update(self, **changes) -> dict:
        if "status" in changes and changes["status"] not in STATUSES:
            raise ValueError(f"unknown status {changes['status']!r}")
        if changes.get("decision") not in (None, *DECISIONS):
            raise ValueError(f"unknown decision {changes['decision']!r}")
        bad = [k for k in changes.get("files", {}) if k not in FILE_KINDS]
        if bad:
            raise ValueError(f"unknown file kind {bad}")
        with filelock.locked(self.record_path):
            data = self.read()
            files = {**data.get("files", {}), **changes.pop("files", {})}
            data.update(changes, files=files)
            filelock.write_atomic(self.record_path, json.dumps(data, indent=2))
            return data

    def take_cost(self) -> float:
        """Claim the booked cost for giving it back: returns it and writes 0 in ONE locked step, so two processes (a run and a resume of the same job) can never both
        claim it."""
        with filelock.locked(self.record_path):
            data = self.read()
            try:
                amount = float(data.get("cost_booked") or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount > 0:
                data["cost_booked"] = 0.0
                filelock.write_atomic(self.record_path, json.dumps(data, indent=2))
            return max(amount, 0.0)

    def restore_cost(self, amount: float) -> None:
        """Put a claimed cost back (the give-back failed and nothing was written)."""
        with filelock.locked(self.record_path):
            data = self.read()
            try:
                now = float(data.get("cost_booked") or 0.0)
            except (TypeError, ValueError):
                now = 0.0
            data["cost_booked"] = round(now + amount, 4)
            filelock.write_atomic(self.record_path, json.dumps(data, indent=2))

    def log(self, line) -> None:
        """One line to the run log, with the time. Never pass a key: callers log what happened, not what they sent."""
        with filelock.locked(self.dir / LOG):
            with open(self.dir / LOG, "a") as f:
                f.write(f"{_utc()} {_clean(line)}\n")


def create(scope: str, status: str = "running", **fields) -> Run:
    """Open a new run under `scope` (the video's folder name, or a test name). Raises ValueError for a name that is not a plain word."""
    if not SAFE.fullmatch(scope or ""):
        raise ValueError(f"bad scope {scope!r}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    folder = ROOT / scope / run_id
    folder.mkdir(parents=True, exist_ok=False)
    run = Run(folder)
    record = {"run_id": run_id, "scope": scope, "status": status, "created_at": _utc(), "finished_at": None, "error": None, "decision": None,
              "reason": "", "cost_booked": 0.0, "files": {}, **fields}
    with filelock.locked(run.record_path):
        filelock.write_atomic(run.record_path, json.dumps(record, indent=2))
    return run


def open_run(scope: str, run_id: str) -> Run | None:
    if not (SAFE.fullmatch(scope or "") and SAFE.fullmatch(run_id or "")):
        return None
    folder = (ROOT / scope / run_id).resolve()
    return Run(folder) if folder.is_dir() and ROOT.resolve() in folder.parents else None


def runs() -> list[dict]:
    """Every readable run record, newest first. A folder with a broken record is skipped, not fatal."""
    out = []
    for rec in ROOT.glob("*/*/" + RECORD):
        scope, run_id = rec.parent.parent.name, rec.parent.name  # the folder is the truth, not a field inside the record
        if not (SAFE.fullmatch(scope) and SAFE.fullmatch(run_id)):
            continue
        try:
            data = _read(rec)
        except (OSError, ValueError):
            continue
        if not isinstance(data.get("files"), dict):
            data["files"] = {}
        out.append({**data, "scope": scope, "run_id": run_id})
    return sorted(out, key=lambda r: (str(r.get("created_at") or ""), run_id_of(r)), reverse=True)


def run_id_of(rec: dict) -> str:
    return str(rec.get("run_id") or "")


def tail(scope: str, run_id: str, n: int = 50) -> list[str]:
    run = open_run(scope, run_id)
    if run is None:
        return []
    try:
        return [ln.rstrip("\n")[:LOG_LINE_MAX + 40] for ln in (run.dir / LOG).read_text(errors="replace").splitlines()[-n:]]
    except OSError:
        return []


def file_path(scope: str, run_id: str, kind: str) -> Path | None:
    """The file of this kind that the run's own record lists, or None. A name the record does not list is never served."""
    run = open_run(scope, run_id)
    if run is None or kind not in FILE_KINDS:
        return None
    try:
        files = run.read().get("files")
        name = files.get(kind) if isinstance(files, dict) else None
    except (OSError, ValueError):
        return None
    if not isinstance(name, str) or Path(name).name != name:
        return None
    p = (run.dir / name).resolve()
    return p if p.is_file() and run.dir.resolve() in p.parents else None
