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


def write_atomic(path: Path, text: str) -> None:
    """Write to a temporary file and rename it over `path`, so a reader never sees half a file and a crash never truncates it."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
