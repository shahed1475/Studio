"""Changes to videos on YouTube: a record of every one (what it was before, what it became, who did it and why), a way back, and proposals for public videos.

- `record`: written by every code path that changes a video's title, description or tags on YouTube (recheck, guardian, the title test).
- `rollback`: puts the "before" back (metadata only; a status change such as taking a video back to private is undone in YouTube Studio). Owner command.
- `propose` / `approve` / `reject`: a video that is already public is never changed by an agent. The change is proposed, the owner gets a task with the exact
  commands, and only `approve` (the owner's command, `run.py edits approve <id>`) writes it, after checking the video still reads as it did when proposed.
No agent module calls approve, reject or rollback (agenteval checks that)."""
import datetime as dt
import json
from pathlib import Path

import agentbus
import config
import filelock

ACTIONS = config.ROOT / "data" / "agent" / "actions.json"
EDITS = config.ROOT / "data" / "agent" / "edits.json"
FIELDS = ("title", "description", "tags")
KEEP = 500


def _stamp(now) -> str:
    return (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> list[dict]:
    try:
        rows = json.loads(Path(path).read_text())
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _save(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(path, json.dumps(rows[-KEEP:], indent=1, ensure_ascii=False))


def snap(d: dict) -> dict:
    """The three editable fields of a record or a YouTube snippet, copied."""
    return {k: json.loads(json.dumps(d[k])) for k in FIELDS if k in d}


def record(video_id: str, before: dict, after: dict, source: str, why: str = "", now=None, kind: str = "metadata", file: Path | None = None) -> str:
    """Log one change made on YouTube. Never raises: a full disk must not undo or hide a change that already happened (it returns "")."""
    file = Path(file or ACTIONS)
    try:
        with filelock.locked(file):
            rows = _load(file)
            n = max([int(r["id"][1:]) for r in rows] + [0]) + 1
            rows.append({"id": f"a{n:05d}", "at": _stamp(now), "video_id": video_id, "kind": kind, "source": source, "why": str(why)[:300], "before": before, "after": after,
                         "rolled_back": False})
            _save(file, rows)
            return rows[-1]["id"]
    except OSError:
        return ""


def actions(n: int = 20, file: Path | None = None) -> list[dict]:
    return _load(file or ACTIONS)[-n:][::-1]


def _live(yt, video_id: str) -> dict:
    items = yt.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not items:
        raise LookupError(f"{video_id} is not on YouTube")
    return items[0]["snippet"]


def apply_fields(yt, video_id: str, fields: dict) -> dict:
    """videos.update replaces the whole snippet: send back everything that was there with only `fields` changed. Returns the live values before the change."""
    sn = _live(yt, video_id)
    before = snap(sn)
    sn.update({k: v for k, v in fields.items() if k in FIELDS})
    yt.videos().update(part="snippet", body={"id": video_id, "snippet": {k: sn[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in sn}}).execute()
    return before


def rollback(action_id: str, yt, now=None, file: Path | None = None) -> str:
    """Owner command. Restores the "before" of a metadata change. Refuses a status change and an action already undone."""
    file = Path(file or ACTIONS)
    rows = _load(file)
    hit = next((r for r in rows if r["id"] == action_id), None)
    if not hit:
        return f"no action {action_id}"
    if hit["kind"] != "metadata":
        return f"{action_id} changed the video's status: undo that in YouTube Studio"
    if hit.get("rolled_back"):
        return f"{action_id} was already rolled back"
    try:
        live = apply_fields(yt, hit["video_id"], hit["before"])
    except Exception as e:
        return f"{action_id} not rolled back: {type(e).__name__}: {str(e)[:120]}"
    new = record(hit["video_id"], live, hit["before"], "owner", f"rollback of {action_id}", now, file=file)
    rows = _load(file)
    for r in rows:
        if r["id"] == action_id:
            r["rolled_back"] = new or True
    _save(file, rows)
    return f"{action_id} rolled back ({new})"


def propose(video_id: str, slug: str, before: dict, after: dict, source: str, why: str, now=None, file: Path | None = None, tasks: Path | None = None) -> str | None:
    """Queue a change to a PUBLIC video for the owner. Returns the proposal id, or None when nothing would change. The same proposal is not queued twice."""
    before, after = snap(before), snap(after)
    if all(before.get(k) == after.get(k) for k in after):
        return None
    file = Path(file or EDITS)
    with filelock.locked(file):
        rows = _load(file)
        same = next((r for r in rows if r["state"] == "pending" and r["video_id"] == video_id and r["after"] == after), None)
        if same:
            return same["id"]
        n = max([int(r["id"][1:]) for r in rows] + [0]) + 1
        pid = f"p{n:05d}"
        rows.append({"id": pid, "at": _stamp(now), "video_id": video_id, "slug": slug, "source": source, "why": str(why)[:300], "before": before, "after": after, "state": "pending"})
        _save(file, rows)
    changed = ", ".join(k for k in after if before.get(k) != after[k])
    t = agentbus.post("approve_edit", source, "owner", slug=video_id, reason=f"{slug}: {source} wants to change {changed} on a public video. {str(why)[:150]}",
                      evidence=f"title now: {before.get('title', '')[:80]} | proposed: {after.get('title', '')[:80]}", now=now, file=tasks,
                      commands=[f"python run.py edits approve {pid}", f"python run.py edits reject {pid}"])
    if t.get("id"):
        agentbus.to_owner(t["id"], "a change to a public video waits for you", now, tasks)
    return pid


def pending(file: Path | None = None) -> list[dict]:
    return [r for r in _load(file or EDITS) if r["state"] == "pending"]


def resolve(pid: str, approve: bool, yt=None, now=None, file: Path | None = None, actions_file: Path | None = None) -> str:
    """Owner command. Approve writes the proposed fields after checking the live video still reads as it did when proposed; reject only closes it."""
    file = Path(file or EDITS)
    rows = _load(file)
    hit = next((r for r in rows if r["id"] == pid and r["state"] == "pending"), None)
    if not hit:
        return f"no pending proposal {pid}"
    if approve:
        try:
            live = snap(_live(yt, hit["video_id"]))
            if any(live.get(k) != hit["before"].get(k) for k in hit["before"]):
                return f"{pid} not applied: the video changed on YouTube after it was proposed. Ask again."
            apply_fields(yt, hit["video_id"], hit["after"])
        except Exception as e:
            return f"{pid} not applied: {type(e).__name__}: {str(e)[:120]}"
        aid = record(hit["video_id"], hit["before"], hit["after"], hit["source"], f"approved by the owner ({pid}): {hit['why']}", now, file=actions_file)
        hit["applied"] = aid
    hit["state"] = "approved" if approve else "rejected"
    hit["resolved_at"] = _stamp(now)
    _save(file, rows)
    return f"{pid} approved and applied" if approve else f"{pid} rejected"
