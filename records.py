"""The one safe way to read and write a video's saved record (`output/<slug>/meta.json`).

`update` takes an exclusive lock, reads the CURRENT file, lets the caller change it, writes a temp file and swaps it in with os.replace, so a crash leaves the
old record whole and two writers cannot overwrite each other's keys. The file format is unchanged. Design: docs/architecture/05-target-design.md."""
import contextlib
import fcntl
import json
import os
import time
from pathlib import Path

LOCK_WAIT_SECONDS = 10.0
NAME = "meta.json"


class RecordError(Exception):
    pass


@contextlib.contextmanager
def _lock(folder: Path, shared: bool = False):
    fd = os.open(folder / ".meta.lock", os.O_CREAT | os.O_RDWR, 0o600)
    flag = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    try:
        while True:
            try:
                fcntl.flock(fd, flag)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RecordError(f"could not lock the record in {folder.name} within {LOCK_WAIT_SECONDS:.0f} s")
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)  # closing releases the lock


def read(folder) -> dict:
    folder = Path(folder)
    with _lock(folder, shared=True):
        return json.loads((folder / NAME).read_text())


def _write(folder: Path, data: dict) -> None:
    tmp = folder / (NAME + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(data, indent=2))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, folder / NAME)


def update(folder, fn) -> dict:
    """fn(record) changes the dict in place (or returns a new dict). The result is saved and returned."""
    folder = Path(folder)
    with _lock(folder):
        data = json.loads((folder / NAME).read_text())
        out = fn(data)
        data = data if out is None else out
        _write(folder, data)
        return data


def save(folder, data: dict) -> dict:
    """Replace the whole record atomically under the lock. Only for code that edits many keys across a long pass (the fixer): it still overwrites a key written
    meanwhile, so prefer merge/update everywhere else."""
    folder = Path(folder)
    with _lock(folder):
        _write(folder, data)
        return data


def merge(folder, changes: dict) -> dict:
    return update(folder, lambda d: d.update(changes))


def create(folder, data: dict) -> dict:
    """Make a new record; refuses when one exists (a folder that holds a video is never overwritten)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with _lock(folder):
        if (folder / NAME).exists():
            raise RecordError(f"{folder.name} already has a record")
        _write(folder, data)
        return data
