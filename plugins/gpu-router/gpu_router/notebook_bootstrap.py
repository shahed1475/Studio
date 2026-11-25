"""Copy-paste this into the first cell of the Kaggle notebook.

It does three things that decide whether a long render survives:

1. Skips shards that are already done, so a restarted session doesn't redo
   finished work. Resume has to be idempotent or the 12-hour cap beats you.
2. Stops admitting new shards near the session cap. A shard killed mid-render
   costs its whole GPU time with nothing to show, and that time is gone from
   your weekly quota -- so it is better to stop early with work banked.
3. Pushes every finished artifact off-box immediately, because /kaggle/working
   only persists with a notebook version.

Sharding is per shot and per stage (embed -> draft -> refine -> decode -> encode).
Latents are small -- a few tens of MB -- so persisting between stages is cheap,
and a crash in decode or encode then costs minutes, not the whole denoise.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Iterable

WORKING = Path("/kaggle/working")
SESSION_CAP_HOURS = float(os.environ.get("SESSION_CAP_HOURS", 12.0))
# Stop taking work this long before the cap. 45 min is the research-backed
# default: long enough to finish a shard and flush uploads.
RESERVE_MINUTES = float(os.environ.get("RESERVE_MINUTES", 45.0))

_START = time.time()


def elapsed_hours() -> float:
    return (time.time() - _START) / 3600.0


def time_left_hours() -> float:
    return SESSION_CAP_HOURS - (RESERVE_MINUTES / 60.0) - elapsed_hours()


def can_admit(expected_hours: float) -> bool:
    """Only start a shard we can realistically finish."""
    return time_left_hours() >= expected_hours


def artifact_path(job_id: str, stage: str, ext: str = "bin") -> Path:
    path = WORKING / "artifacts" / job_id / f"{stage}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def done(job_id: str, stage: str, ext: str = "bin") -> bool:
    marker = artifact_path(job_id, stage, ext).with_suffix(f".{ext}.done")
    return marker.exists()


def write_atomic(path: Path, write: Callable[[Path], None]) -> Path:
    """Write to .tmp then rename, so a half-written file is never mistaken for done."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    write(tmp)
    tmp.replace(path)
    path.with_suffix(path.suffix + ".done").write_text(str(time.time()))
    return path


def run_stage(
    job_id: str,
    stage: str,
    fn: Callable[[Path], None],
    expected_hours: float,
    ext: str = "bin",
    push: Callable[[Path, str], str] | None = None,
) -> Path | None:
    """Run one stage of one shard, unless it's done or we're out of session time."""
    path = artifact_path(job_id, stage, ext)
    if done(job_id, stage, ext):
        print(f"  skip  {job_id}/{stage} (already done)")
        return path
    if not can_admit(expected_hours):
        print(f"  defer {job_id}/{stage} -- {time_left_hours():.2f} h left, needs {expected_hours:.2f} h")
        return None
    started = time.time()
    write_atomic(path, fn)
    took = (time.time() - started) / 60.0
    print(f"  done  {job_id}/{stage} in {took:.1f} min")
    if push:
        key = f"artifacts/{job_id}/{stage}.{ext}"
        print(f"  push  {push(path, key)}")
    return path


def load_manifest(path: str | Path = "/kaggle/input/render-manifest/manifest.json") -> list[dict]:
    """Work comes in as a Dataset input, not from polling your server.

    A notebook that polls an external queue looks like a distributed worker,
    which Kaggle's acceptable-use policy treats as resource abuse. Passing the
    manifest in as a Dataset keeps the notebook a notebook.
    """
    return json.loads(Path(path).read_text())["shots"]


def summary(shots: Iterable[dict], stages: list[str]) -> str:
    total = 0
    complete = 0
    for shot in shots:
        for stage in stages:
            total += 1
            complete += int(done(shot["id"], stage))
    return f"{complete}/{total} stage-artifacts complete; {time_left_hours():.2f} h of session left"
