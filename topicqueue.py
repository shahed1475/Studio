"""The topic queue (topics.json): every writer goes through here, so the dashboard, autopilot and the growth agent cannot lose each other's changes."""
import json
import re

import config
import filelock


def _read() -> list[str]:
    try:
        data = json.loads(config.TOPICS_FILE.read_text())
    except (OSError, ValueError):
        return []
    return [t for t in data if isinstance(t, str)] if isinstance(data, list) else []


def _write(items: list[str]) -> None:
    filelock.write_atomic(config.TOPICS_FILE, json.dumps(items, indent=2))


def items() -> list[str]:
    return _read()


def extend(topics: list[str]) -> list[str]:
    """Add topics that are not queued yet. Returns the ones that were added."""
    with filelock.locked(config.TOPICS_FILE):
        cur = _read()
        new = [t for t in dict.fromkeys(topics) if t not in cur]
        if new:
            _write(cur + new)
        return new


def append_unique(topic: str) -> bool:
    """Add one topic unless it is queued already (ignoring case). True when added."""
    with filelock.locked(config.TOPICS_FILE):
        cur = _read()
        if topic.lower() in (t.lower() for t in cur):
            return False
        _write(cur + [topic])
        return True


def pop_first() -> str | None:
    with filelock.locked(config.TOPICS_FILE):
        cur = _read()
        if not cur:
            return None
        _write(cur[1:])
        return cur[0]


def push_front(topic: str) -> None:
    with filelock.locked(config.TOPICS_FILE):
        _write([topic] + [t for t in _read() if t != topic])


def remove(index: int) -> bool:
    with filelock.locked(config.TOPICS_FILE):
        cur = _read()
        if not 0 <= index < len(cur):
            return False
        cur.pop(index)
        _write(cur)
        return True


MAX_TRIES = 2  # a topic that could not be made this many times (no pictures found) is dropped


def requeue_failed(topic: str) -> bool:
    """A topic that could not be made goes to the back of the queue, so the next run tries a different one. After MAX_TRIES it is dropped.
    Returns True when it was kept."""
    fails_file = config.ROOT / "data" / "topic_fails.json"
    with filelock.locked(config.TOPICS_FILE):
        try:
            fails = json.loads(fails_file.read_text())
        except (OSError, ValueError):
            fails = {}
        fails[topic] = fails.get(topic, 0) + 1
        keep = fails[topic] < MAX_TRIES
        fails_file.parent.mkdir(parents=True, exist_ok=True)
        filelock.write_atomic(fails_file, json.dumps(fails))
        rest = [t for t in _read() if t != topic]
        _write(rest + [topic] if keep else rest)
        return keep


INSTRUCTION = re.compile(r"^\s*(create|focus|make|build|produce|write|use|retell|tell|develop|craft|prepare|publish|post|try|consider|add|explore|highlight|continue)\b", re.I)


def looks_like_topic(text: str) -> bool:
    """A subject to make a video about, not an instruction or advice. 'The Jersey Devil' is one; 'Create content around unsolved mysteries' is not."""
    t = (text or "").strip()
    return 6 <= len(t) <= 110 and not INSTRUCTION.match(t) and not t.endswith(".") and " videos that" not in t.lower() and "content around" not in t.lower()


def subject_of(raw: str, chat=None) -> str | None:
    """The queue takes subjects only. An instruction that names one story ('Create a retelling of the legend of the Jersey Devil...') is cut down to
    that subject ('The Jersey Devil'); advice that names none is turned away."""
    if looks_like_topic(raw):
        return raw.strip()
    import scriptgen

    chat = chat or scriptgen._chat
    try:
        got = chat("Below is an instruction or advice for a YouTube history and legends channel. If it names ONE specific story, person, place, event or object "
                   "(for example the Jersey Devil, the Mary Celeste, Roanoke), give that as a short topic of 2 to 8 words, like 'The Jersey Devil'. "
                   'If it only gives general advice, return an empty topic. Return JSON {"topic": ""}.\n' + (raw or "")[:400])
        t = str(got.get("topic", "")).strip(" .")
    except Exception:
        return None
    return t if looks_like_topic(t) and 2 <= len(t.split()) <= 9 else None


def clean_queue(chat=None, similar=None) -> tuple[list[str], list[str]]:
    """One-time and on demand: turn the queued items into subjects, drop advice and near-duplicates. Returns (removed, kept)."""
    import difflib

    similar = similar or (lambda a, b: difflib.SequenceMatcher(None, re.sub(r"[^a-z0-9 ]", "", a.lower()), re.sub(r"[^a-z0-9 ]", "", b.lower())).ratio() >= 0.75)
    with filelock.locked(config.TOPICS_FILE):
        cur = _read()
        kept, removed = [], []
        for raw in cur:
            t = subject_of(raw, chat)
            if t and not any(similar(t, k) for k in kept):
                kept.append(t)
            else:
                removed.append(raw)
        _write(kept)
        return removed, kept
