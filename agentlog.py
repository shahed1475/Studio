"""Activity feed of the growth agent: one JSON line per event, plus an optional desktop notification."""
import datetime as dt
import json
import subprocess

import config
import filelock

FILE = config.ROOT / "data" / "agent" / "events.jsonl"
KINDS = ("info", "found", "strategy", "applied", "error")


def event(kind: str, title: str, detail: str = "", notify: bool = False, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    e = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind if kind in KINDS else "info", "title": title, "detail": detail, "read": False}
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        with filelock.locked(FILE), FILE.open("a") as f:
            f.write(json.dumps(e) + "\n")
    except OSError:
        e["saved"] = False  # a feed that cannot be written (disk full) must not stop the agent that wanted to report; the notice below still goes out
    if notify:
        try:
            subprocess.run(["notify-send", "-a", "Story Studio", title, detail], timeout=5, capture_output=True)
        except Exception:  # no notify-send, no desktop session: the feed still has it
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


def unread() -> int:
    return sum(1 for e in _all() if not e.get("read"))


def mark_read() -> None:
    try:
        with filelock.locked(FILE):  # an event another process appends meanwhile waits for the lock instead of being overwritten
            rows = _all()
            if rows:
                filelock.write_atomic(FILE, "".join(json.dumps({**e, "read": True}) + "\n" for e in rows))
    except OSError:
        pass  # the unread count stays as it was
