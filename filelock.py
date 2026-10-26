"""Small helpers for files that several processes write (dashboard, worker, agent): a lock around read-modify-write, and atomic writes."""
import contextlib
import fcntl
import os
from pathlib import Path


@contextlib.contextmanager
def locked(path: Path):
    """Hold an exclusive lock for `path` (kept in a neighbouring .lock file) while the caller reads, changes and writes it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


class Busy(Exception):
    """Another process holds this lock."""


@contextlib.contextmanager
def try_locked(path: Path):
    """Like `locked`, but never waits: raises Busy when another process holds the lock (for work that must not run twice at once, such as sending a video)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy(str(path)) from None
        yield


def write_atomic(path: Path, text: str) -> None:
    """Write to a temporary file and rename it over `path`, so a reader never sees half a file and a crash never truncates it."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
