"""Trace triage: the activity feed and the stuck videos, turned into a short list of problem families.

Events are grouped by their shape (numbers, names in brackets and ids removed), counted, and marked: known (a lesson that worked matches), recurring (3 or
more times) or new. The top open families become tasks for the trainer agent and the whole list is written to `data/agent/triage.json` for the dashboard.
It changes nothing about any video."""
import datetime as dt
import json
import re
from pathlib import Path

import agentbus
import agentlog
import config
import filelock
import lessons

REPORT = config.ROOT / "data" / "agent" / "triage.json"
RECURRING = 3
TOP = 3


PROBLEM = re.compile(r"problem|could not|couldn't|cannot|failed|\bfail\b|error|missing|not set|refused|rejected|wrong|mismatch|changed its page|needs|paused|removed|"
                     r"unhealthy|stale|blocked|expired|unsupported|invented|did not|taken back|still has", re.I)


def is_problem(e: dict) -> bool:
    """An error is always a problem. A 'found' event is one only when its words say so: 'New competitor: X' or 'Added to your reference channels' are news."""
    return e.get("kind") == "error" or (e.get("kind") == "found" and bool(PROBLEM.search(f"{e.get('title', '')} {e.get('detail', '')}")))


def signature(title: str) -> str:
    return lessons.family(re.sub(r"\([^)]*\)|\[[^\]]*\]|:.*$", " ", str(title)))


def triage(days: int = 7, now: dt.datetime | None = None, events: list[dict] | None = None, report: Path | None = None,
           lessons_file=None, bus_file=None, post: bool = True) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = agentlog._all() if events is None else events
    fams: dict[str, dict] = {}
    for e in events:
        if not is_problem(e) or e.get("at", "") < since:
            continue
        sig = signature(e.get("title", ""))
        if not sig:
            continue
        f = fams.setdefault(sig, {"signature": sig, "count": 0, "kinds": set(), "example": e.get("title", "")[:120], "last": e["at"], "detail": e.get("detail", "")[:160]})
        f["count"] += 1
        f["kinds"].add(e["kind"])
        f["last"] = max(f["last"], e["at"])
    out = []
    for f in fams.values():
        known = any(l["wins"] > l["losses"] for a in {"fixer", "seo", "guardian", "growth", "autopilot"} for l in lessons.recall(a, f["example"], 3, lessons_file))
        out.append({**f, "kinds": sorted(f["kinds"]), "state": "known" if known else ("recurring" if f["count"] >= RECURRING else "new")})
    out.sort(key=lambda f: (f["state"] == "known", -f["count"], f["signature"]))
    stuck = 0
    try:
        import unstick

        stuck = len(unstick.candidates())
    except Exception:  # a broken record must not stop the report
        pass
    data = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "days": days, "events": len(events), "families": out[:30], "stuck_drafts": stuck, "tasks": agentbus.summary(bus_file)}
    if post:
        for f in [f for f in out if f["state"] != "known"][:TOP]:
            agentbus.post("triage_family", "triage", "trainer", f["signature"][:60], reason=f"{f['count']}x in {days} days: {f['example']}", evidence=f["detail"], now=now, file=bus_file)
    rf = report or REPORT
    rf.parent.mkdir(parents=True, exist_ok=True)
    with filelock.locked(rf):
        filelock.write_atomic(rf, json.dumps(data, indent=1))
    return data
