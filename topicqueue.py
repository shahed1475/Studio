"""The topic queue (topics.json): every writer goes through here, so the dashboard, autopilot and the growth agent cannot lose each other's changes."""
import json

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
