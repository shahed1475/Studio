"""Activity feed of the growth agent: one JSON line per event, plus an optional desktop notification."""
import datetime as dt
import json
import subprocess

import config
import filelock

FILE = config.ROOT / "data" / "agent" / "events.jsonl"
KINDS = ("info", "found", "strategy", "applied", "error")
ROUTINE = ("info", "found")  # kinds whose exact repeat within REPEAT_WINDOW is not logged again; errors, actions taken and strategies always are
REPEAT_WINDOW = dt.timedelta(hours=24)
TAIL = 400  # lines read back to find a repeat


def _repeat_of(e: dict, now: dt.datetime) -> dict | None:
    """The same routine event (kind, title and detail all equal) logged within REPEAT_WINDOW, or None. 22 Nov 2026: the doctor posted
    "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing" 25 times in a week with nothing changed, and each one counted in the bell."""
    try:
        lines = FILE.read_text().splitlines()[-TAIL:]
    except OSError:
        return None
    since = (now - REPEAT_WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    for line in reversed(lines):
        try:
            old = json.loads(line)
        except ValueError:
            continue
        if str(old.get("at", "")) < since:
            break
        if (old.get("kind"), old.get("title"), old.get("detail")) == (e["kind"], e["title"], e["detail"]):
            return old
    return None


def record(kind: str, title: str, detail: str = "", notify: bool = False, now: dt.datetime | None = None) -> dict:
    """The line the feed keeps. An event the code marks important (notify) carries "alert": the bell counts it and the dashboard shows it as a toast even
    when it is not an error (22 Nov 2026: "Possible algorithm change", "Credit is low" and "Re-check: a public video has a problem" are found or applied
    events, and counting errors alone would have hidden them)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    e = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind if kind in KINDS else "info", "title": title, "detail": detail, "read": False}
    if notify:
        e["alert"] = True
    return e


def event(kind: str, title: str, detail: str = "", notify: bool = False, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    e = record(kind, title, detail, notify, now)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        with filelock.locked(FILE):
            old = _repeat_of(e, now) if e["kind"] in ROUTINE and not notify else None
            if old is not None:
                return {**old, "repeat": True}  # nothing new to say: no second line, no toast, no alert
            with FILE.open("a") as f:
                f.write(json.dumps(e) + "\n")
    except OSError:
        e["saved"] = False  # a feed that cannot be written (disk full) must not stop the agent that wanted to report; the notice below still goes out
    if notify:
        try:
            subprocess.run(["notify-send", "-a", "Story Studio", title, detail], timeout=5, capture_output=True)
        except Exception:  # no notify-send, no desktop session: the feed still has it
            pass
    try:  # an important event also reaches the owner's Telegram (alerts.py: best effort, deduped, capped, never raises)
        import alerts

        alerts.push(e["kind"], title, detail, notify, now)
    except Exception:
        pass
    return e


def _all() -> list[dict]:
    try:
        lines = FILE.read_text().splitlines()
    except OSError:
        return []  # no feed yet, or one that cannot be read: an empty feed, not a crash in the dashboard or an agent
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a half-written line must not break the feed
    return out


def recent(n: int = 50) -> list[dict]:
    return _all()[::-1][:n]


def unread(attention_only: bool = False) -> int:
    """Unread events; with attention_only, only errors and alerts: the count the menu shows, matching the bell (notifyview.needs_attention, 22 Nov 2026)."""
    return sum(1 for e in _all() if not e.get("read") and (not attention_only or e.get("kind") == "error" or bool(e.get("alert"))))


def mark_read() -> None:
    try:
        with filelock.locked(FILE):  # an event another process appends meanwhile waits for the lock instead of being overwritten
            rows = _all()
            if rows:
                filelock.write_atomic(FILE, "".join(json.dumps({**e, "read": True}) + "\n" for e in rows))
    except OSError:
        pass  # the unread count stays as it was
