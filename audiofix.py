"""Bring a finished video's loudness to its target without drawing or rendering anything again.

28 Oct 2026: three videos came out at -18 LUFS because the growth agent had lowered the loudness target (editprofile now stops that). Fixing them by a
re-render would have cost the pictures again. Here only the audio is measured and re-encoded (two passes of ffmpeg's loudnorm, linear, so the voice keeps its
shape) and the picture stream is copied untouched. A video that is already on YouTube is never touched: its copy there would not change anyway."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import config
import records
import reviewer

TARGET = -16.0  # the reviewer's accepted range is -17.5 to -12; our earlier renders sat at -16
TRUE_PEAK = -1.5
TOLERANCE = 1.0  # LUFS: the result must land this close to the target, or the original is kept


def _ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True)


def measure(path: Path, target: float = TARGET) -> dict | None:
    """The first pass: what loudnorm measured (input_i, input_tp, input_lra, input_thresh, target_offset), or None when ffmpeg gave no numbers."""
    r = _ffmpeg("-i", str(path), "-vn", "-af", f"loudnorm=I={target:g}:TP={TRUE_PEAK:g}:LRA=11:print_format=json", "-f", "null", "-")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


def normalize(folder: Path, target: float = TARGET) -> dict:
    """Make the folder's video.mp4 hit `target` LUFS. Returns {"changed": bool, "before": lufs, "after": lufs, "why": str}. The original goes to backups/ first."""
    video = folder / "video.mp4"
    meta = json.loads((folder / "meta.json").read_text()) if (folder / "meta.json").exists() else {}
    if meta.get("video_id"):
        return {"changed": False, "why": "already uploaded: not touched"}
    if not video.exists():
        return {"changed": False, "why": "no video.mp4"}
    first = measure(video, target)
    if not first:
        return {"changed": False, "why": "the loudness could not be measured"}
    before = float(first["input_i"])
    if abs(before - target) <= TOLERANCE:
        return {"changed": False, "before": before, "why": f"already within {TOLERANCE:g} LUFS of {target:g}"}
    tmp = folder / "video.loudfix.mp4"
    af = (f"loudnorm=I={target:g}:TP={TRUE_PEAK:g}:LRA=11:measured_I={first['input_i']}:measured_TP={first['input_tp']}:measured_LRA={first['input_lra']}:"
          f"measured_thresh={first['input_thresh']}:offset={first['target_offset']}:linear=true")
    r = _ffmpeg("-i", str(video), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp))
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return {"changed": False, "before": before, "why": "ffmpeg failed: " + r.stderr.strip()[-200:]}
    try:
        old, new = reviewer.probe_video(video), reviewer.probe_video(tmp)
    except Exception as e:  # a file ffprobe cannot read is not an improvement
        tmp.unlink(missing_ok=True)
        return {"changed": False, "before": before, "why": f"the new file could not be read: {type(e).__name__}"}
    after = new.get("lufs")
    if after is None or abs(after - target) > TOLERANCE or abs(new["duration"] - old["duration"]) > 0.3 or new["width"] != old["width"]:
        tmp.unlink(missing_ok=True)
        return {"changed": False, "before": before, "after": after, "why": "the result missed the target or changed the length, so the original is kept"}
    backups = config.ROOT / "backups"
    backups.mkdir(exist_ok=True)
    shutil.copy2(video, backups / f"{folder.name}.video.pre-loudness.mp4")
    tmp.replace(video)
    def apply(d):
        reviewer.invalidate(d)  # the old review measured the old file
        d["loudness_fixed"] = {"from": round(before, 1), "to": round(after, 1)}

    records.update(folder, apply)
    return {"changed": True, "before": before, "after": after, "why": "audio re-measured and re-encoded, picture copied"}
