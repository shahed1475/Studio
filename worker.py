"""Always-on worker for the container: runs the jobs a desktop would get from systemd timers. All times are UTC."""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import agentlog
import config
import records

STATE = config.ROOT / "data" / "worker_state.json"
HEARTBEAT = config.ROOT / "data" / "worker_heartbeat"
LOG = config.ROOT / "logs" / "worker.log"
TS = "%Y-%m-%dT%H:%M:%SZ"
JOBS = [
    {"name": "autopilot", "every": 1800, "cmds": [["autopilot", "tick"]], "timeout": 7200},
    {"name": "report", "at": "07:00", "cmds": [["report"]], "timeout": 300},
    {"name": "backup", "at": "03:30", "cmds": [["backup"]], "timeout": 600},
    {"name": "recheck", "every": 3600, "cmds": [["recheck"]], "timeout": 900},
    {"name": "guardian", "every": 3600, "cmds": [["guardian"]], "timeout": 900},
    {"name": "unstick", "every": 10800, "cmds": [["unstick"]], "timeout": 1800},
    {"name": "doctor", "every": 21600, "cmds": [["doctor"]], "timeout": 1800},
    {"name": "agent-review", "at": "05:30", "cmds": [["agent-review"]], "timeout": 900},
    {"name": "health", "every": 3600, "cmds": [["health"]], "timeout": 600},
    {"name": "titletest", "at": "08:00", "cmds": [["titletest"]], "timeout": 900},
    {"name": "policywatch", "at": "06:10", "cmds": [["policywatch"]], "timeout": 900},
    {"name": "agent", "at": "06:30", "cmds": [["agent"]], "timeout": 1800},
    {"name": "growthdata", "every": 21600, "cmds": [["growthdata"]], "timeout": 900},  # the channel's own per-video numbers: young videos every 6 hours, older ones daily (growthdata.due)
    {"name": "diagnose", "every": 21600, "cmds": [["diagnose"]], "timeout": 600},  # one problem per video, 48 hours and 7 days after it went public (diagnose.py)
    {"name": "trendwatch", "at": "06:00", "cmds": [["trends"], ["channels"]], "timeout": 3600},  # daily: what is taking off in the niche and in the reference channels (about 1,100 of the 10,000 daily API units: 6 + 4 searches at 100 each, about 120 for the channels)
    {"name": "weekly", "at": "09:00", "weekday": 0, "cmds": [["learn"], ["newswatch"]], "timeout": 3600},
]
if os.getenv("STUDIO_MODE", "").strip().lower() == "tenant":  # a user studio keeps its own storage limit
    JOBS.append({"name": "quota", "every": 3600, "cmds": [["tenant-quota"]], "timeout": 600})
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
    if os.getenv("STUDIO_MODE", "").strip().lower() == "tenant" and not _plan_confirmed():
        out = [j for j in out if j["name"] == "quota"]  # a user who has not chosen a niche yet has nothing to research, check or publish
    return out


def _plan_confirmed() -> bool:
    try:
        return bool(json.loads((config.ROOT / "data" / "niche_brief.json").read_text()).get("confirmed"))
    except (OSError, ValueError):
        return False


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


def prune_uploaded(out: Path, days: int, now: dt.datetime) -> int:
    """Delete the local video file of videos that have been on YouTube for more than `days` days. Off when days is 0 (the default):
    the owner opts in, because this deletes files. The record (meta.json, thumbnails, captions) stays. Returns bytes freed."""
    if days <= 0:
        return 0
    freed = 0
    cutoff = (now - dt.timedelta(days=days)).strftime(TS)
    for m in out.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
            video = m.parent / "video.mp4"
            if meta.get("video_id") and str(meta.get("uploaded_at", "9")) < cutoff and video.exists():
                freed += video.stat().st_size
                video.unlink()
                records.merge(m.parent, {"local_video_removed": True})
        except (OSError, ValueError):
            continue
    return freed


def prune_logs(logs: Path, max_age_days: int, now: dt.datetime) -> int:
    """Delete the per-job logs the dashboard writes (HHMMSS-name.log) once they are old. Named logs (worker, autopilot) are left alone."""
    n, cutoff = 0, now.timestamp() - max_age_days * 86400
    for f in logs.glob("*.log") if logs.exists() else []:
        try:
            if re.fullmatch(r"\d{6}-.+\.log", f.name) and f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
        except OSError:
            continue
    return n


def check_disk(path: Path, min_free_gb: float = 10.0) -> bool:
    """Tell the owner (feed and desktop notification) when the disk is nearly full. True when it is."""
    free = shutil.disk_usage(path).free
    if free < min_free_gb * 1e9:
        agentlog.event("error", "The server disk is almost full", f"{free / 1e9:.1f} GB left. Old videos in output/ can be removed once they are on YouTube.", notify=True)
        return True
    return False


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
            _log(f"pruned {prune_cache(config.CACHE, CACHE_MAX_AGE_DAYS, now)} bytes of old cache, {prune_logs(config.ROOT / 'logs', 14, now)} old job logs")
            days = int(os.getenv("STUDIO_PRUNE_UPLOADED_DAYS", "0") or 0)  # 0 = never delete local videos
            if days:
                _log(f"removed {prune_uploaded(config.OUT, days, now)} bytes of videos already on YouTube for {days}+ days")
            if check_disk(config.ROOT):
                _log("disk is almost full")
            state["prune"] = now.strftime(TS)
            save_state(state)
        time.sleep(30)


if __name__ == "__main__":
    import tenantmode

    if tenantmode.is_tenant():
        tenantmode.apply_defaults()  # first run of a user studio: nothing starts by itself until the user turns it on
    main()
