"""Power-cut safe state for long renders (20 Nov 2026, owner's order on load-shedding).

Load-shedding cuts the PC's power while a 20 to 26 minute film renders. Nothing here guesses that a file is good because it exists or because a process
exited: a finished unit is checked (ffprobe, a decode of its last second), its size and SHA-256 are written into a manifest, and the manifest itself is
written atomically (a temporary file, flushed to disk, checked, then renamed over the old one; the old one is kept as .prev). A later run trusts a unit only
when its recorded size and hash still match the file and its inputs are the same.

No network, no model, no cost. Used by render.py (segments and the final assembly), tts.py (one voice line at a time) and run._produce_doc (stages).
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

MANIFEST = "checkpoint.json"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, data: dict) -> None:
    """Atomic: a reader sees the old file or the new one, never half of one. The previous version is kept as <name>.prev."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(data, indent=1, sort_keys=True)
    json.loads(text)  # the structure is checked before it can replace anything
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        try:
            shutil.copy2(path, path.with_name(path.name + ".prev"))
        except OSError:
            pass
    os.replace(tmp, path)
    try:  # the rename itself reaches the disk
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def read_json(path: Path) -> dict:
    """The manifest, or its previous version when the current one is unreadable (a cut during a write on a file system that lost the rename), or {}."""
    path = Path(path)
    if not path.exists():  # deleted on purpose (a finished job): never brought back from .prev (the rename is atomic, so a cut never leaves it missing)
        return {}
    for p in (path, path.with_name(path.name + ".prev")):
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def key_of(*parts) -> str:
    """A stable hash of a unit's inputs (arguments, input file sizes and times)."""
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:24]


def file_stamp(path) -> list:
    """What identifies an input file without reading it: path, size, modification time."""
    try:
        st = Path(path).stat()
        return [str(path), st.st_size, st.st_mtime_ns]
    except OSError:
        return [str(path), None, None]


def media_seconds(path: Path) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _streams(path: Path) -> set[str]:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=120).stdout
        return {s.strip() for s in out.split() if s.strip()}
    except (OSError, subprocess.SubprocessError):
        return set()


def decodes(path: Path, tail: float | None = 1.0, timeout: int = 3600) -> bool:
    """True when ffmpeg decodes the file without an error: the last `tail` seconds, or the whole file when tail is None."""
    seek = ["-sseof", f"-{tail:g}"] if tail else []
    try:
        p = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(path), "-f", "null", "-"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0 and not p.stderr.strip()


def check_media(path: Path, seconds: float | None = None, need: tuple[str, ...] = ("video",), tol: float | None = None, full: bool = False) -> str | None:
    """None when the file is a complete, readable video; otherwise the plain reason. `seconds` is the expected length; `full` decodes the whole file."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return "missing or empty"
    have = _streams(path)
    for kind in need:
        if kind not in have:
            return f"no {kind} stream (an interrupted write leaves an unreadable file)"
    secs = media_seconds(path)
    if seconds is not None:
        allow = tol if tol is not None else max(0.25, seconds * 0.01)
        if abs(secs - seconds) > allow:
            return f"{secs:.2f} s long, {seconds:.2f} s expected"
    if not decodes(path, None if full else 1.0):
        return "does not decode" + (" to the end" if full else " at its end")
    return None


def facts(path: Path) -> dict:
    path = Path(path)
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path), "seconds": round(media_seconds(path), 3)}


def still_valid(path: Path, rec: dict | None, key: str) -> bool:
    """A unit recorded as done is trusted only while its inputs are the same (key) and the file is the very one that was checked (size and hash)."""
    path = Path(path)
    if not rec or rec.get("key") != key or not path.is_file():
        return False
    try:
        return path.stat().st_size == rec.get("bytes") and sha256(path) == rec.get("sha256")
    except OSError:
        return False


# ---- run markers: was the last run of this job cut off? ----

def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return False


def proc_start(pid: int) -> str:
    """When the process with this pid started, in clock ticks since boot (/proc/<pid>/stat, field 22), or "" when it cannot be read. A pid alone is not
    enough to say a run is still alive: a restarted container numbers its processes from 1 again, so a new process can carry the old run's pid
    (21 Nov 2026 review)."""
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text()
        return stat[stat.rindex(")") + 2:].split()[19]  # after the command name, which may hold spaces and brackets; field 22 overall
    except (OSError, ValueError, IndexError, TypeError):
        return ""


def _run_alive(run: dict) -> bool:
    """True only while the very process that started this run is still running: same boot, the pid exists, and it started at the recorded moment."""
    if run.get("boot") != boot_id() or not _alive(int(run.get("pid") or 0)):
        return False
    then = run.get("pstart")
    return not then or proc_start(int(run.get("pid") or 0)) == then  # a record from before 21 Nov has no start time: pid and boot as before


def start_run(work: Path, job: str) -> dict:
    """Record that a run of this job started; returns what the previous run left (with 'interrupted' True when it never recorded its end)."""
    path = Path(work) / MANIFEST
    state = read_json(path)
    prev = state.get("run") or {}
    interrupted = bool(prev) and not prev.get("ended") and not _run_alive(prev)
    history = (state.get("history") or [])[-19:]
    if prev:
        history.append({**prev, "interrupted": interrupted})
    state.update(job=job, run={"pid": os.getpid(), "pstart": proc_start(os.getpid()), "boot": boot_id(), "started": _now()}, history=history)
    state.setdefault("stages", {})
    write_json(path, state)
    return {"previous": prev, "interrupted": interrupted, "stages": dict(state["stages"])}


def mark_stage(work: Path, stage: str, **info) -> None:
    path = Path(work) / MANIFEST
    state = read_json(path)
    state.setdefault("stages", {})[stage] = {"at": _now(), **info}
    write_json(path, state)


def end_run(work: Path, outcome: str) -> None:
    path = Path(work) / MANIFEST
    if not path.parent.is_dir():
        return
    state = read_json(path)
    if state.get("run"):
        state["run"]["ended"] = _now()
        state["run"]["outcome"] = outcome
        write_json(path, state)


def was_interrupted(work: Path) -> bool:
    """True when the last run of the job in this folder started and never recorded its end, and its process is gone (a power cut, a kill, a crash of the container)."""
    prev = read_json(Path(work) / MANIFEST).get("run") or {}
    return bool(prev) and not prev.get("ended") and not _run_alive(prev)


# ---- one render at a time per job, and room on the disk ----

class Busy(RuntimeError):
    pass


class lock:
    """An exclusive lock on a job's folder (fcntl, released by the kernel when the process dies, so a power cut never leaves a stale lock)."""

    def __init__(self, work: Path):
        self.path = Path(work) / "render.lock"
        self.f = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a+")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise Busy(f"another render of this job is running ({self.path.parent})")
        self.f.seek(0)
        self.f.truncate()
        self.f.write(str(os.getpid()))
        self.f.flush()
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        finally:
            self.f.close()
        return False


MIN_FREE_BYTES = 2 * 1024 ** 3  # always kept free for the final assembly and the system


def room(path: Path, need_bytes: int) -> str | None:
    """None when the disk under `path` has need_bytes plus a 2 GB margin free; otherwise the reason. Nothing is ever deleted to make room."""
    try:
        free = shutil.disk_usage(Path(path) if Path(path).exists() else Path(path).parent).free
    except OSError as e:
        return f"cannot read free disk space ({e})"
    if free < need_bytes + MIN_FREE_BYTES:
        return f"only {free / 1e9:.1f} GB free; this render needs about {need_bytes / 1e9:.1f} GB plus a {MIN_FREE_BYTES / 1e9:.0f} GB margin"
    return None


def memory_note() -> str | None:
    """A plain warning when available memory is low (renders are one ffmpeg at a time; this only explains a slow or killed render)."""
    try:
        info = dict(l.split(":", 1) for l in Path("/proc/meminfo").read_text().splitlines() if ":" in l)
        avail = int(info["MemAvailable"].split()[0]) * 1024
    except (OSError, KeyError, ValueError):
        return None
    return f"only {avail / 1e9:.1f} GB of memory available" if avail < 1.5e9 else None
