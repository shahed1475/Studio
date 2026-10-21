"""Growth strategies: what the agent proposes. Stored, validated, and (for safe kinds) applied to the pipeline."""
import datetime as dt
import difflib
import hashlib
import json
import re

import config
import editprofile
import filelock
import scriptgen
import topicqueue

FILE = config.ROOT / "data" / "agent" / "strategies.json"
KINDS = {"topic", "title", "format", "edit", "schedule", "thumbnail"}
AUTO_KINDS = {"edit", "topic"}  # the only kinds the agent may apply on its own
OPEN_PER_KIND = 3  # proposals the owner has not acted on, per kind: more would only bury the useful ones
SAME = 0.72  # two strategies this alike (difflib ratio on lower-case words) are one idea
CLICKBAIT = re.compile(r"what really happened|untold truth|no one talks about|nobody (?:tells|talks)|history hides|hidden truth|the real story behind|the secret behind|"
                       r"\[legend\]|you won'?t believe|shocking|curiosity[- ]gap", re.I)  # title or thumbnail advice that promises more than a calm retelling delivers
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
    if kind in ("title", "thumbnail") and CLICKBAIT.search(text):
        return None  # YouTube's rules treat a title or thumbnail that promises more than the video delivers as deceptive (docs/COMPLIANCE.md)
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


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def same_idea(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= SAME


def add(items: list[dict]) -> list[dict]:
    added = []
    with filelock.locked(FILE):
        rows = load()
        have = {r["id"] for r in rows}
        for raw in items:
            s = validate(raw)
            if not s or s["id"] in have:
                continue
            same_kind = [r for r in rows + added if r["kind"] == s["kind"]]
            if any(same_idea(s["text"], r["text"]) for r in same_kind):
                continue  # the same advice again, in other words
            if s["kind"] not in AUTO_KINDS and sum(1 for r in same_kind if r["status"] == "proposed") >= OPEN_PER_KIND:
                continue
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
            subject = topicqueue.subject_of(row["text"])  # advice such as "focus on mysteries" guides the research; only a named story is queued
            if subject:
                topicqueue.append_unique(subject)
        row["status"], row["applied_at"] = "applied", _now()
        _save(rows)
        return row


def production_feedback(now: dt.datetime | None = None, days: int = 7) -> dict:
    """What Autopilot's production line learned lately, for the advisor: how many videos it made, which checks failed them, and what it spent. Growth reads this
    so that it stops proposing what the line cannot make well."""
    import agentlog

    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    fails, needs_eyes, fixed = {}, 0, 0
    for e in agentlog.recent(500):
        if str(e.get("at", "")) < since:
            continue
        title = str(e.get("title", ""))
        if title.startswith("Needs your eyes") or title.startswith("Held, facts warning"):
            needs_eyes += 1
            for name in re.findall(r"\b(invented_facts|title_matches|thumbnail_matches|visual_review|variety_script|originality|duplicate_title|script_labels)\b", str(e.get("detail", ""))):
                fails[name] = fails.get(name, 0) + 1
            if "risk" in str(e.get("detail", "")) and "invented_facts" not in fails:
                fails["invented facts"] = fails.get("invented facts", 0) + 1
        elif title.startswith(("Fixed:", "Polished:")):
            fixed += 1
    spent = 0.0
    try:
        import llm

        usage = json.loads((config.ROOT / "data" / "llm_usage.json").read_text())
        spent = round(sum(float(v.get("usd", 0)) for k, v in usage.get("days", usage).items() if isinstance(v, dict) and k >= (now - dt.timedelta(days=days)).strftime("%Y-%m-%d")), 2)
    except Exception:
        pass
    return {"days": days, "videos_that_needed_the_owner": needs_eyes, "repairs_applied": fixed, "most_common_failures": sorted(fails, key=fails.get, reverse=True)[:4],
            "dollars_spent": spent}


def generate(analysis: dict, study: list[dict], chat=None, feedback: dict | None = None) -> list[dict]:
    """One model call. Returns validated, not yet stored, strategies. A model failure returns an empty list."""
    chat = chat or scriptgen._script_chat  # the writer model: advice written by the cheap helper was generic and repeated itself
    nc = config.niche()
    titles = [f"- {v['title']} ({v['views']:,} views, {c.get('channel', '?')})" for c in study for v in c.get("top", [])[:3]][:15]
    prompt = (
        f"You advise a small YouTube channel to get more views.\nChannel: {nc['name']}. Angle: {nc['channel_angle']}. Audience: {nc['audience']}.\n"
        f"Our numbers: {json.dumps(analysis, default=str)}\n"
        + (f"What our production line learned lately (do not propose what it keeps failing at): {json.dumps(feedback, default=str)}\n" if feedback else "")
        + f"Top videos at competitors (only to learn which themes work; never copy wording):\n"
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


def tidy() -> dict:
    """One clean-up of what piled up: of each group of near-identical advice only the newest stays open, advice that fails today's rules is dismissed,
    and no kind keeps more than OPEN_PER_KIND open. Nothing is deleted: dismissed rows stay in the file with the reason."""
    out = {"duplicates": 0, "rule_breaking": 0, "surplus": 0}
    with filelock.locked(FILE):
        rows = load()
        newest_first = sorted(rows, key=lambda r: r.get("created", ""), reverse=True)
        kept = []
        for r in newest_first:
            if r["status"] != "proposed" or r["kind"] in AUTO_KINDS:
                continue
            if r["kind"] in ("title", "thumbnail") and CLICKBAIT.search(r["text"]):
                r["status"], r["note"] = "dismissed", "dismissed: promises more than the video delivers"
                out["rule_breaking"] += 1
            elif any(k["kind"] == r["kind"] and same_idea(k["text"], r["text"]) for k in kept):
                r["status"], r["note"] = "dismissed", "dismissed: the same advice as a newer one"
                out["duplicates"] += 1
            elif sum(1 for k in kept if k["kind"] == r["kind"]) >= OPEN_PER_KIND:
                r["status"], r["note"] = "dismissed", "dismissed: older than the newest open ones of its kind"
                out["surplus"] += 1
            else:
                kept.append(r)
        _save(rows)
    return out
