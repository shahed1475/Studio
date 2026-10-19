"""Always-on worker for the container: runs the jobs a desktop would get from systemd timers. All times are UTC."""
import datetime as dt
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import config

STATE = config.ROOT / "data" / "worker_state.json"
HEARTBEAT = config.ROOT / "data" / "worker_heartbeat"
LOG = config.ROOT / "logs" / "worker.log"
TS = "%Y-%m-%dT%H:%M:%SZ"
JOBS = [
    {"name": "autopilot", "every": 1800, "cmds": [["autopilot", "tick"]], "timeout": 7200},
    {"name": "agent", "at": "06:30", "cmds": [["agent"]], "timeout": 1800},
    {"name": "weekly", "at": "09:00", "weekday": 0, "cmds": [["newswatch"], ["trends"], ["channels"]], "timeout": 3600},
]
CACHE_MAX_AGE_DAYS = 21


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def _last_slot(job: dict, now: dt.datetime) -> dt.datetime:
    """The most recent moment this daily or weekly job was supposed to start."""
    h, m = (int(x) for x in job["at"].split(":"))
    slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if "weekday" in job:
        slot -= dt.timedelta(days=(now.weekday() - job["weekday"]) % 7)
        if slot > now:
            slot -= dt.timedelta(days=7)
    elif slot > now:
        slot -= dt.timedelta(days=1)
    return slot


def due(now: dt.datetime, last: dict, jobs: list[dict] = JOBS) -> list[dict]:
    """Jobs to run now. Missed slots run once, never several times."""
    out = []
    for job in jobs:
        ran = _parse(last[job["name"]]) if job["name"] in last else None
        if "every" in job:
            if ran is None or (now - ran).total_seconds() >= job["every"]:
                out.append(job)
        elif ran is None or ran < _last_slot(job, now):
            out.append(job)
    return out


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 2_000_000:  # keep the log small: one old copy
        LOG.replace(LOG.with_suffix(".log.1"))
    with LOG.open("a") as f:
        f.write(f"{dt.datetime.now(dt.timezone.utc).strftime(TS)} {msg}\n")


def run_job(job: dict) -> int:
    """Run the job's commands one after another. A failing command never stops the next. Returns 0 only if all passed."""
    bad = 0
    for args in job["cmds"]:
        try:
            r = subprocess.run([sys.executable, "run.py", *args], cwd=config.ROOT, timeout=job["timeout"])
            _log(f"{job['name']} {' '.join(args)} -> exit {r.returncode}")
            bad |= r.returncode != 0
        except subprocess.TimeoutExpired:
            _log(f"{job['name']} {' '.join(args)} timed out after {job['timeout']}s")
            bad = 1
        except Exception as e:  # the worker itself must never die because one job could not start
            _log(f"{job['name']} {' '.join(args)} could not start: {type(e).__name__}: {e}")
            bad = 1
    return int(bad)


def prune_cache(cache: Path, max_age_days: int, now: dt.datetime) -> int:
    """Delete cached downloads older than max_age_days (they are downloaded again on demand). Returns bytes freed."""
    freed = 0
    if not cache.exists():
        return 0
    cutoff = now.timestamp() - max_age_days * 86400
    for f in cache.rglob("*"):
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                f.unlink()
                freed += size
        except OSError:
            continue
    return freed


def _beat() -> None:
    while True:
        try:
            HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT.write_text(str(int(time.time())))
        except OSError:
            pass
        time.sleep(30)


def alive() -> bool:
    """True while a worker process keeps its heartbeat fresh (this is what replaces systemd timers in the container)."""
    try:
        return time.time() - HEARTBEAT.stat().st_mtime < 120
    except OSError:
        return False


def main() -> None:
    threading.Thread(target=_beat, daemon=True).start()
    _log("worker started")
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        state = load_state()
        for job in due(now, state):
            run_job(job)
            state = load_state()
            state[job["name"]] = dt.datetime.now(dt.timezone.utc).strftime(TS)
            save_state(state)
        state = load_state()
        if state.get("prune", "")[:10] != now.strftime("%Y-%m-%d"):
            _log(f"pruned {prune_cache(config.CACHE, CACHE_MAX_AGE_DAYS, now)} bytes of old cache")
            state["prune"] = now.strftime(TS)
            save_state(state)
        time.sleep(30)


if __name__ == "__main__":
    main()
