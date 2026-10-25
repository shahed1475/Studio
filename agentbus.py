"""The agents' inbox: one list of tasks saying who asked whom to do what, and how it ended.

An agent posts a task (`post`), the target takes it (`claim`) and ends it (`finish`), or hands it to the owner (`to_owner`). The same open task (kind, target,
video) is never posted twice. The file is `data/agent/tasks.json`; the dashboard and the triage agent read it. Text is cleaned and capped."""
import datetime as dt
import json
from pathlib import Path

import config
import filelock

FILE = config.ROOT / "data" / "agent" / "tasks.json"
STATES = ("open", "working", "done", "failed", "owner")
LIVE = ("open", "working")
KEEP = 400


def _stamp(now) -> str:
    return (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(file: Path) -> list[dict]:
    try:
        rows = json.loads(file.read_text())
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _save(file: Path, rows: list[dict]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    keep = [r for r in rows if r["state"] in LIVE + ("owner",)] + [r for r in rows if r["state"] in ("done", "failed")][-KEEP:]
    filelock.write_atomic(file, json.dumps(sorted(keep, key=lambda r: r["id"]), indent=1))


def _text(t, cap: int) -> str:
    import seo

    s = seo.plain(t)[:cap]
    return "" if seo.linky(s) else s


def post(kind: str, source: str, target: str, slug: str = "", reason: str = "", evidence: str = "", now=None, file: Path | None = None,
         commands: list[str] | None = None) -> dict:
    """Ask `target` to do `kind` for a video. An open task with the same kind, target and video is returned instead of a second one.
    `commands` are exact lines for the owner to run, written by our own code only (never from outside text): kept as given, 5 lines of 200 characters at most."""
    file = file or FILE
    with filelock.locked(file):
        rows = _load(file)
        for r in rows:
            if r["state"] in LIVE and (r["kind"], r["target"], r["slug"]) == (kind, target, slug):
                r["seen"] = r.get("seen", 1) + 1
                _save(file, rows)
                return r
        n = max([int(r["id"][1:]) for r in rows] + [0]) + 1
        t = {"id": f"t{n:05d}", "kind": kind, "source": source, "target": target, "slug": slug, "reason": _text(reason, 300), "evidence": _text(evidence, 600),
             "commands": [str(c)[:200] for c in (commands or [])[:5]], "state": "open", "at": _stamp(now), "seen": 1, "history": [f"{_stamp(now)} posted by {source}"]}
        rows.append(t)
        _save(file, rows)
        return t


def _move(task_id: str, state: str, note: str, now, file: Path | None) -> dict | None:
    file = file or FILE
    with filelock.locked(file):
        rows = _load(file)
        for r in rows:
            if r["id"] == task_id:
                r["state"] = state
                r["history"] = (r.get("history") or [])[-20:] + [f"{_stamp(now)} {state}: {_text(note, 200)}"]
                _save(file, rows)
                return r
    return None


def claim(task_id: str, who: str, now=None, file: Path | None = None) -> dict | None:
    return _move(task_id, "working", f"taken by {who}", now, file)


def finish(task_id: str, outcome: str, ok: bool = True, now=None, file: Path | None = None) -> dict | None:
    return _move(task_id, "done" if ok else "failed", outcome, now, file)


def to_owner(task_id: str, note: str, now=None, file: Path | None = None) -> dict | None:
    return _move(task_id, "owner", note, now, file)


def tasks(file: Path | None = None) -> list[dict]:
    return _load(file or FILE)


def open_for(target: str, file: Path | None = None) -> list[dict]:
    return [r for r in _load(file or FILE) if r["target"] == target and r["state"] == "open"]


def close_for(slug: str, outcome: str, ok: bool = True, kind: str | None = None, now=None, file: Path | None = None) -> int:
    n = 0
    for r in _load(file or FILE):
        if r["slug"] == slug and r["state"] in LIVE and (kind is None or r["kind"] == kind):
            _move(r["id"], "done" if ok else "failed", outcome, now, file)
            n += 1
    return n


def summary(file: Path | None = None) -> dict:
    rows = _load(file or FILE)
    return {s: sum(r["state"] == s for r in rows) for s in STATES}
