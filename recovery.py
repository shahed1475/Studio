"""What a power cut left behind (20 Nov 2026, load-shedding): every unfinished job folder in output/, what of it is finished and checked, what is missing or broken,
and the one safe step that continues it. Read-only: it never renders, deletes or approves anything. Used by the doctor (doctor.production_status) and by
`python run.py recover`.

A folder is unfinished when it has a work/ folder and no meta.json (a finished video's record is saved before its work folder is removed)."""
from __future__ import annotations

import json
from pathlib import Path

import checkpoint
import config

RESUME_DOC = "python run.py autopilot make doc   (continues the saved film from data/pending_doc.json; finished voice lines, scenes and pictures are kept)"
RESUME_SHORT = "python run.py autopilot make short   (continues the saved Short from data/pending_short.json in its own folder; finished voice lines and scenes are kept)"


def _pending_folder(pending: Path) -> str:
    return str(checkpoint.read_json(pending).get("folder") or "")


def inspect(folder: Path, thorough: bool = False) -> dict:
    """One unfinished job: stages, scenes kept and broken, voice lines kept, a leftover half-written final file. thorough re-hashes every scene (slow on a long film)."""
    work = folder / "work"
    state = checkpoint.read_json(work / checkpoint.MANIFEST)
    segs = checkpoint.read_json(work / "segments.json")
    rec = segs.get("segments") or {}
    ok, bad = 0, []
    for name, r in sorted(rec.items()):
        p = work / name
        good = checkpoint.still_valid(p, r, r.get("key")) if thorough else (p.is_file() and p.stat().st_size == r.get("bytes"))
        if good:
            ok += 1
        else:
            bad.append(name)
    voice = 0
    for side in work.glob("line*.json"):
        r = checkpoint.read_json(side)
        mp3 = side.with_suffix(".mp3")
        if mp3.is_file() and mp3.stat().st_size == r.get("bytes"):
            voice += 1
    parts = segs.get("parts") or {}
    parts_ok = sum(1 for name, r in parts.items() if (work / name).is_file() and (work / name).stat().st_size == r.get("bytes"))
    halves = sorted(p.name for p in [*work.glob("*.part.*"), *folder.glob("*.part.*")])
    run = state.get("run") or {}
    return {"folder": folder.name, "job": state.get("job", ""), "interrupted": checkpoint.was_interrupted(work), "last_start": run.get("started"),
            "last_outcome": run.get("outcome"), "stages": sorted((state.get("stages") or {}).keys()),
            "scenes_kept": ok, "scenes_total": segs.get("total"), "scenes_broken": bad, "voice_lines_kept": voice,
            "final_parts_kept": parts_ok, "sound_kept": bool(segs.get("sound")) and (work / "sound.m4a").is_file(),
            "half_written": halves, "interruptions": sum(1 for h in state.get("history") or [] if h.get("interrupted")) + (1 if checkpoint.was_interrupted(work) else 0)}


def scan(out: Path | None = None, pending: Path | None = None, thorough: bool = False) -> list[dict]:
    out = out or config.OUT
    pending = pending or config.ROOT / "data" / "pending_doc.json"
    mine = _pending_folder(pending)
    short = _pending_folder(pending.with_name("pending_short.json"))  # 21 Nov 2026: a cut Short resumes in its own folder too
    found = []
    try:
        folders = sorted(p for p in out.iterdir() if p.is_dir())
    except OSError:
        return []
    for f in folders:
        if not (f / "work").is_dir() or (f / "meta.json").exists():
            continue
        if not (f / "work" / checkpoint.MANIFEST).exists() and not (f / "work" / "segments.json").exists():
            continue  # an older unfinished folder made before checkpoints existed: not this module's to judge
        info = inspect(f, thorough)
        if f.name == mine:
            info["resume"] = RESUME_DOC
        elif f.name == short:
            info["resume"] = RESUME_SHORT
        elif info["job"] == "doc":
            info["resume"] = "its saved script is no longer in data/pending_doc.json: the folder is kept as it is; ask the owner before making it again"
        else:
            info["resume"] = "the folder is kept; making the same video again starts a new folder"
        found.append(info)
    return found


def report(items: list[dict]) -> str:
    if not items:
        return "No unfinished render found."
    rows = []
    for i in items:
        rows.append(f"{i['folder']}: {'INTERRUPTED' if i['interrupted'] else 'unfinished'} (last start {i['last_start'] or '?'}, outcome {i['last_outcome'] or 'none recorded'})\n"
                    f"  stages done: {', '.join(i['stages']) or 'none'}; voice lines kept: {i['voice_lines_kept']}; scenes kept: {i['scenes_kept']} of {i['scenes_total'] or '?'}"
                    + (f"; final-video parts kept: {i['final_parts_kept']}" if i.get("final_parts_kept") else "")
                    + (f"; broken scenes (made again): {', '.join(i['scenes_broken'])}" if i["scenes_broken"] else "")
                    + (f"; half-written files (never used): {', '.join(i['half_written'])}" if i["half_written"] else "")
                    + f"\n  next: {i['resume']}")
    return "\n".join(rows)


if __name__ == "__main__":
    import sys

    items = scan(thorough="--thorough" in sys.argv)
    print(json.dumps(items, indent=1) if "--json" in sys.argv else report(items))
