"""The notification centre: one feed from everything that wants the owner's attention or tells what happened.

Served at /api/notifications (data) and shown in the dashboard's bell, its toasts and the /notifications small window. Read-only; the only write is
"mark all read", which the dashboard already offers for the agent feed (agentlog.mark_read).

Two kinds of item:
- an EVENT is something that happened (agentlog): Activity (what Autopilot and the agents did), Growth (what the growth agent found or proposes), Warnings (an error).
  Events are unread until the owner marks them read.
- a STANDING item is something that is true now and waits for the owner (a video to decide on, rule changes to approve, a policy hold, a risk to watch). It has
  no read state: it goes away when the thing is dealt with.
The badge counts what needs a person: unread events plus standing items that wait for a decision. Risks at "watch" are listed but not counted (six of them can
stay at watch for weeks), risks at "act" are counted."""
import datetime as dt
import hashlib

SOURCES = ("Warnings", "Growth", "Activity", "Autopilot")
MAX_EVENTS = 40


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def event_item(e: dict) -> dict:
    kind = e.get("kind", "info")
    source, level = {"error": ("Warnings", "bad"), "applied": ("Activity", "ok"), "found": ("Growth", "info"), "strategy": ("Growth", "info")}.get(kind, ("Activity", "info"))
    tab = {"Growth": "growth", "Warnings": "activity"}.get(source, "activity")
    return {"id": f"e:{e.get('at', '')}:{hashlib.md5(str(e.get('title', '')).encode()).hexdigest()[:8]}", "at": e.get("at", ""), "level": level, "source": source, "title": str(e.get("title", ""))[:160],
            "detail": str(e.get("detail", ""))[:240], "tab": tab, "unread": not e.get("read", True), "pinned": False}


def standing(now: dt.datetime, risks: list | None, needs_you: int, growth: dict | None, failed_jobs: list | None) -> list[dict]:
    at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def item(key, level, source, title, detail, tab, counted):
        return {"id": f"s:{key}", "at": at, "level": level, "source": source, "title": title, "detail": detail, "tab": tab, "unread": False, "pinned": True, "counted": counted}

    out = []
    if needs_you:
        out.append(item("needs", "warn", "Autopilot", f"{needs_you} video{'s' if needs_you != 1 else ''} need{'' if needs_you != 1 else 's'} your decision",
                        "The reviewer is unsure about it and Autopilot cannot repair it. Nothing goes live until you decide.", "autopilot", True))
    g = growth or {}
    if g.get("hold"):
        out.append(item("hold", "bad", "Growth", "A policy hold is active", "New scheduling and uploads wait until you run `run.py policy release`.", "growth", True))
    pending = (g.get("rules") or {}).get("pending") or 0
    if pending:
        out.append(item("rules", "warn", "Growth", f"{pending} rule change{'s' if pending != 1 else ''} wait for you", "Agents only propose. Approve or reject with `run.py rules`.", "growth", True))
    if g.get("edits_pending"):
        n = g["edits_pending"]
        out.append(item("edits", "warn", "Growth", f"{n} edit{'s' if n != 1 else ''} to public videos wait for your approval", "An agent never changes a public video on its own.", "growth", True))
    diag = len(g.get("diagnoses") or [])
    if diag:
        out.append(item("diag", "info", "Growth", f"{diag} video{'s have' if diag != 1 else ' has'} a diagnosis", "One main problem per video, from your own numbers.", "growth", False))
    for e in ((g.get("drift") or {}).get("events") or [])[:2]:
        out.append(item("drift:" + str(e)[:30], "info", "Growth", "A shift in your numbers", str(e)[:240], "growth", False))
    for j in failed_jobs or []:
        out.append(item("job:" + str(j.get("id")), "bad", "Warnings", f"A job failed: {str(j.get('cmd', ''))[:60]}", "Open Activity for its log.", "activity", True))
    for r in risks or []:
        if r.get("level") in ("act", "watch"):
            act = r["level"] == "act"
            out.append(item("risk:" + str(r.get("name", ""))[:40], "bad" if act else "warn", "Warnings", str(r.get("name", ""))[:100], str(r.get("owner_decision") or r.get("evidence") or "")[:240], "home", act))
    return out


def build(now: dt.datetime | None = None, risks: list | None = None, needs_you: int = 0, growth: dict | None = None, failed_jobs: list | None = None,
          events: list | None = None) -> dict:
    """{"at", "items": [pinned first, then events newest first], "counts": {"badge", "unread", "waiting", "warnings"}, "sources": {source: n}}. Every source may be missing."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if events is None:
        import agentlog

        events = _safe(lambda: agentlog.recent(MAX_EVENTS), [])
    pinned = standing(now, risks, needs_you, growth, failed_jobs)
    recent = [event_item(e) for e in events][:MAX_EVENTS]
    order = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    pinned.sort(key=lambda i: order.get(i["level"], 2))
    unread = sum(1 for i in recent if i["unread"])
    waiting = sum(1 for i in pinned if i.get("counted"))
    items = pinned + recent
    sources = {s: sum(1 for i in items if i["source"] == s) for s in SOURCES}
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items, "sources": sources,
            "counts": {"badge": unread + waiting, "unread": unread, "waiting": waiting, "warnings": sum(1 for i in items if i["level"] in ("bad", "warn"))}}
