"""Growth strategies: what the agent proposes. Stored, validated, and (for safe kinds) applied to the pipeline."""
import datetime as dt
import hashlib
import json

import config
import editprofile
import filelock
import scriptgen
import topicqueue

FILE = config.ROOT / "data" / "agent" / "strategies.json"
KINDS = {"topic", "title", "format", "edit", "schedule", "thumbnail"}
AUTO_KINDS = {"edit", "topic"}  # the only kinds the agent may apply on its own
STATUSES = {"proposed", "applied", "dismissed"}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    kind, text = raw.get("kind"), raw.get("text")
    if kind not in KINDS or not isinstance(text, str) or not 8 <= len(text.strip()) <= 300:
        return None
    text = text.strip()
    why = raw.get("why") if isinstance(raw.get("why"), str) else ""
    ev = raw.get("evidence") if isinstance(raw.get("evidence"), list) else []
    s = {"id": hashlib.sha1((kind + text.lower()).encode()).hexdigest()[:10], "kind": kind, "text": text, "why": why[:400],
         "evidence": [e[:200] for e in ev if isinstance(e, str)][:5], "status": "proposed", "auto_ok": kind in AUTO_KINDS, "created": _now()}
    if kind == "edit":
        profile = editprofile.validate(raw.get("profile") if isinstance(raw.get("profile"), dict) else {})
        if not profile:
            return None
        s["profile"] = profile
    return s


def load() -> list[dict]:
    return json.loads(FILE.read_text()) if FILE.exists() else []


def _save(rows: list[dict]) -> None:
    filelock.write_atomic(FILE, json.dumps(rows, indent=2))


def add(items: list[dict]) -> list[dict]:
    added = []
    with filelock.locked(FILE):
        rows = load()
        have = {r["id"] for r in rows}
        for raw in items:
            s = validate(raw)
            if s and s["id"] not in have:
                have.add(s["id"])
                added.append(s)
        if added:
            _save(rows + added)
    return added


def _find(rows: list[dict], sid: str) -> dict:
    row = next((r for r in rows if r["id"] == sid), None)
    if row is None:
        raise ValueError("unknown strategy")
    return row


def set_status(sid: str, status: str) -> dict:
    if status not in STATUSES:
        raise ValueError("unknown status")
    with filelock.locked(FILE):
        rows = load()
        row = _find(rows, sid)
        row["status"] = status
        _save(rows)
        return row


def apply(sid: str) -> dict:
    with filelock.locked(FILE):
        rows = load()
        row = _find(rows, sid)
        if row["kind"] not in AUTO_KINDS:
            raise ValueError("advice only: this one is for you to do, the agent cannot change it")
        if row["kind"] == "edit":
            editprofile.update(row["profile"])
        else:
            topicqueue.append_unique(row["text"])
        row["status"], row["applied_at"] = "applied", _now()
        _save(rows)
        return row


def generate(analysis: dict, study: list[dict], chat=None) -> list[dict]:
    """One model call. Returns validated, not yet stored, strategies. A model failure returns an empty list."""
    chat = chat or scriptgen._chat
    nc = config.niche()
    titles = [f"- {v['title']} ({v['views']:,} views, {c.get('channel', '?')})" for c in study for v in c.get("top", [])[:3]][:15]
    prompt = (
        f"You advise a small YouTube channel to get more views.\nChannel: {nc['name']}. Angle: {nc['channel_angle']}. Audience: {nc['audience']}.\n"
        f"Our numbers: {json.dumps(analysis, default=str)}\nTop videos at competitors (only to learn which themes work; never copy wording):\n"
        + "\n".join(titles) +
        "\n\nGive up to 6 strategies the numbers support. Each is JSON with kind, text (one plain sentence), why (one sentence), evidence (short facts from the data). "
        "Kinds: topic (an original story idea from public-domain legends or well-documented history), title, format, schedule, thumbnail (advice), "
        'and edit, which also needs "profile" using only these keys: target_lufs (-20 to -12), sentence_pause_ms (100 to 900), motion (0 plain, 1 camera shots and word captions, 2 also crossfades and film grain), caption_pos (\"bottom\" or \"top\"). '
        'Reply JSON {"strategies": [...]}. Do not invent numbers that are not in the data.')
    try:
        got = chat(prompt)
    except Exception:
        return []
    items = got.get("strategies", []) if isinstance(got, dict) else []
    return [s for s in (validate(i) for i in items) if s]
