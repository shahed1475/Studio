"""The "what is happening now" view: whether Autopilot is working, where each video is in the pipeline, today's spend against the cap, and the last log lines.
Served by the dashboard at /now (page) and /api/now (data), behind the same login as everything else. Read-only: it changes nothing."""
import datetime as dt
import json
import re
import time
from collections import deque

import config

SHOWN = 10          # videos listed, newest first
LOG_LINES = 15
# The five stations of a build, in order. The station is inferred from the newest log line that names one: the log says what the build printed last, not more.
STEPS = (("plan", "Plan", re.compile(r"^(Documentary|Short|Topic):|source articles|outline|writing the script", re.I)),
         ("voice", "Voice", re.compile(r"^Voice")),
         ("pictures", "Pictures", re.compile(r"^(Archival images|Footage|Pictures)|animation:|AI art", re.I)),
         ("render", "Render", re.compile(r"^Rendering")),
         ("check", "Check", re.compile(r"^Done:|core phrase|keywords found|verdict|thumbnail", re.I)))
QUIET_LOGS = {"autopilot.log", "backup_push.log"}  # action summaries, not a build's own output
LIVE_SECONDS = 180  # a log written in the last three minutes counts as work in progress
PLAN_TTL = 20.0
_plan_cache: dict = {}


def live_log():
    """(path, last 200 lines, seconds since it was written) of the newest build log, or (None, [], None)."""
    try:
        files = [f for f in (config.ROOT / "logs").glob("*.log") if f.name not in QUIET_LOGS]
        newest = max(files, key=lambda f: f.stat().st_mtime)
    except (OSError, ValueError):
        return None, [], None
    return newest, _tail(newest, 200), max(0, int(time.time() - newest.stat().st_mtime))


def stage_now(lines: list[str], age_s: int | None, running: bool) -> dict:
    """Where the build in progress is: {key, label, index, of, steps, idle, last_line, age_s}. Idle when nothing runs or the log has been quiet for LIVE_SECONDS."""
    steps = [{"key": k, "label": lab} for k, lab, _ in STEPS]
    last = next((ln for ln in reversed(lines) if ln.strip()), "")
    idle = not running or age_s is None or age_s > LIVE_SECONDS
    found = None
    for ln in reversed(lines):
        for i, (k, lab, rx) in enumerate(STEPS):
            if rx.search(ln.strip()):
                found = (i, k, lab, ln.strip().startswith("Done:"))
                break
        if found:
            break
    topic = next((m.group(2).strip()[:120] for ln in reversed(lines) if (m := re.match(r"^(Documentary|Short): (.+)$", ln.strip()))), "")
    out = {"steps": steps, "of": len(STEPS), "idle": idle or found is None or found[3], "last_line": last[:200], "age_s": age_s, "key": None, "label": None, "index": None, "topic": topic}
    if found:
        out.update(key=found[1], label=found[2], index=found[0])
    return out


def next_slots(now: dt.datetime, n: int = 3) -> list[dict]:
    """The next posts (time in US Eastern and Bangladesh, kind, title, status). Built from the planner, kept for PLAN_TTL seconds: the page asks every few seconds."""
    if _plan_cache.get("at", 0) + PLAN_TTL > time.time():
        return _plan_cache["rows"]
    try:
        import autopilot

        rows = [{"format": r["format"], "us": r["us"], "bd": r["bd"], "title": (r.get("title") or "")[:90], "status": r["status"], "slug": r.get("slug")}
                for r in autopilot.plan_view(now)["rows"] if r["status"] != "paused"][:n]
    except Exception:
        rows = []
    _plan_cache.update(at=time.time(), rows=rows)
    return rows


def events(n: int = 8) -> list[dict]:
    try:
        import agentlog

        return [{"at": e["at"], "kind": e["kind"], "title": str(e["title"])[:140], "detail": str(e.get("detail", ""))[:220]} for e in agentlog.recent(n)]
    except Exception:
        return []


def credit() -> dict | None:
    """The OpenRouter balance as last read (the Home page reads it live, cached half an hour): never a new network call from here."""
    try:
        import risk

        c = risk._credit_cache
        return {"left": c["v"], "age_s": int(time.time() - c.get("at", 0))} if c.get("v") is not None else None
    except Exception:
        return None


def stage(folder, meta: dict, now: dt.datetime | None = None) -> str:
    """Plain words for where one video stands, from its record and files."""
    held = "ON HOLD · " if meta.get("hold") else ""
    if meta.get("video_id"):
        when = meta.get("publish_at")
        try:
            past = bool(when) and dt.datetime.fromisoformat(when.replace("Z", "+00:00")) <= (now or dt.datetime.now(dt.timezone.utc))
        except ValueError:
            past = False
        if held:
            return held + "on YouTube, kept private"
        if past:
            return f"on YouTube, its public time ({when}) has passed"  # from the record: YouTube itself was not asked
        return "on YouTube, private until " + when if when else "on YouTube"
    if not (folder / "video.mp4").exists():
        return held + "being made (script, voice, pictures, render)"
    verdict = (meta.get("review") or {}).get("verdict")
    if verdict is None:
        return held + "made, waiting for the review"
    if verdict in ("fail", "needs_human"):
        return held + ("needs your attention" if verdict == "needs_human" else "failed the review: waiting for a repair")
    if not meta.get("approved"):
        return held + "passed the review, waiting for approval"
    return held + "approved, waiting for its upload time" + (f" ({meta['publish_at']})" if meta.get("publish_at") else "")


def _tail(path, n: int = LOG_LINES) -> list[str]:
    try:
        with open(path, errors="replace") as f:
            return [ln.rstrip("\n")[:300] for ln in deque(f, maxlen=n)]
    except OSError:
        return []


def footage_status(now: dt.datetime) -> dict | None:
    """The newest footage run (status and age) and how many started today (UTC); None when the footage store cannot be read. Never raises."""
    try:
        import footagestore

        runs = footagestore.runs()
    except Exception:
        return None
    today = now.strftime("%Y-%m-%d")
    newest = runs[0] if runs else None
    return {"last_status": newest.get("status") if newest else None, "last_at": (newest.get("created_at") if newest else None),
            "runs_today": sum(1 for r in runs if str(r.get("created_at") or "").startswith(today)), "runs_total": len(runs)}


def build(now: dt.datetime | None = None) -> dict:
    import autopilot
    import llm

    now = now or dt.datetime.now(dt.timezone.utc)
    rows = []
    for m in config.OUT.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
        except (OSError, ValueError):
            continue
        rows.append((m.stat().st_mtime, m.parent, meta))
    rows.sort(key=lambda r: r[0], reverse=True)
    videos = [{"slug": f.name, "title": (d.get("title") or f.name)[:120], "format": d.get("format") or "short", "stage": stage(f, d, now)} for _, f, d in rows[:SHOWN]]
    try:
        cap, spent = llm.load_config()["daily_budget_usd"], llm.spent_today(now)
        money = {"spent_today": round(spent, 2), "cap": cap, "left": round(cap - spent, 2)}
    except Exception:
        money = None
    try:
        focus = autopilot.focus_view(now)
    except Exception:
        focus = None
    try:
        enabled = bool(autopilot.load_config().get("enabled"))
        running = autopilot.is_running()
    except Exception:
        enabled, running = None, None
    path, lines, age = live_log()
    busy = bool(running) or autopilot.JOB_FILE.exists()
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "autopilot_on": enabled, "pass_running": running, "dashboard_job": autopilot.JOB_FILE.exists(),
            "working_on": focus, "videos": videos, "money": money, "footage": footage_status(now), "log": _tail(autopilot.LOG),
            "stage": stage_now(lines, age, busy), "busy": busy, "build_log": [ln[:300] for ln in lines[-LOG_LINES:]], "build_log_name": path.name if path else None,
            "next": next_slots(now), "events": events(), "credit": credit()}
