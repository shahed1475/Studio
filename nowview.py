"""The "what is happening now" view: whether Autopilot is working, where each video is in the pipeline, today's spend against the cap, and the last log lines.
Served by the dashboard at /now (page) and /api/now (data), behind the same login as everything else. Read-only: it changes nothing."""
import datetime as dt
import json
from collections import deque

import config

SHOWN = 10          # videos listed, newest first
LOG_LINES = 15


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
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "autopilot_on": enabled, "pass_running": running, "dashboard_job": autopilot.JOB_FILE.exists(),
            "working_on": focus, "videos": videos, "money": money, "log": _tail(autopilot.LOG)}
