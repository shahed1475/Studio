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
