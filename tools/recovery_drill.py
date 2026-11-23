"""Controlled interruption drill for load-shedding recovery (20 Nov 2026). Disposable: everything is made in a new folder given on the command line, never in
output/ or data/. The render runs in its own process and is killed with SIGKILL (no clean-up, no end record: the same as a power cut for this process).

  python tools/recovery_drill.py <empty folder> [1 2 3]      -> prints a JSON report

Drill 1: kill after at least two scenes are checked; the doctor's scan must see the interrupted job; resume; only the missing scenes are made.
Drill 2: kill during the final assembly; resume; no scene is made again, the half-written final file is never used, the final video decodes in full.
Drill 3 (21 Nov 2026): a 5 minute film with burned captions, assembled in parts; kill while the second part is written; resume; the first part and every
scene are kept, only the missing parts are made, the final video decodes in full.
Drill 4 (23 Nov 2026): the whole worker CONTAINER dies, not only the render (the host OOM of 22 Nov 2026 killed the container's pid 1):
  python tools/recovery_drill.py /tmp/<new folder> container-start    (inside the worker; returns with the render still running)
  kill -9 $(docker inspect -f '{{.State.Pid}}' studio-worker)         (on the host; Docker restarts the container)
  python tools/recovery_drill.py /tmp/<same folder> container-after   (inside the restarted worker: scan, doctor, resume, checks)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import checkpoint  # noqa: E402

SCENES, SECONDS, SIZE = 8, 4.0, (1280, 720)
CHILD = r'''
import sys, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import checkpoint, render
folder = Path(sys.argv[2]); work = folder / "work"
spec = json.loads((folder / "spec.json").read_text())
checkpoint.start_run(work, "doc")
render._render_ungated([Path(p) for p in spec["pics"]], spec["durs"], work / "narration.wav", work / spec["ass"] if spec.get("ass") else None, work, folder / "video.mp4",
                       size=tuple(spec["size"]), shots=True, loudness=spec.get("loudness"))
checkpoint.end_run(work, "done")
print("CHILD_DONE")
'''


def _ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)


LONG_SCENES, LONG_SECONDS = 10, 30.0  # drill 3: 300 s, over render.PARTS_FROM, so the final pass is made in parts


def _captions(seconds: float) -> str:
    rows = "".join(f"Dialogue: 0,0:{int(t // 60):02d}:{t % 60:05.2f},0:{int((t + 2) // 60):02d}:{(t + 2) % 60:05.2f},Default,,0,0,0,,Caption at {t:.0f} seconds\n"
                   for t in range(1, int(seconds) - 2, 5))
    return ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
            "MarginV, Encoding\nStyle: Default,DejaVu Sans,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,40,1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + rows)


def make_job(folder: Path, scenes: int = SCENES, seconds: float = SECONDS, captions: bool = False) -> None:
    work = folder / "work"
    work.mkdir(parents=True)
    _ff("-f", "lavfi", "-i", f"sine=frequency=330:duration={scenes * seconds}", "-ar", "44100", str(work / "narration.wav"))
    if captions:
        (work / "captions.ass").write_text(_captions(scenes * seconds))
    pics = []
    for i in range(scenes):
        p = folder / f"pic{i}.png"
        _ff("-f", "lavfi", "-i", f"testsrc2=s=1920x1080:r=1", "-vf", f"hue=h={i * 40}", "-frames:v", "1", str(p))
        pics.append(str(p))
    (folder / "spec.json").write_text(json.dumps({"pics": pics, "durs": [seconds] * scenes, "size": list(SIZE), "ass": "captions.ass" if captions else None,
                                                  "loudness": -16 if captions else None}))


def stamps(work: Path) -> dict:
    return {p.name: [p.stat().st_ino, p.stat().st_mtime_ns] for p in sorted([*work.glob("seg??.mp4"), *work.glob("part??.mp4")])}


def start(folder: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", CHILD, str(ROOT), str(folder)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)


def kill_when(proc: subprocess.Popen, cond, timeout: float = 900) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if proc.poll() is not None:
            return False
        if cond():
            os.killpg(proc.pid, signal.SIGKILL)  # the render and its ffmpeg child die at once, like a power cut
            proc.wait()
            return True
        time.sleep(0.05)
    return False


def recorded(work: Path) -> int:
    return len(checkpoint.read_json(work / "segments.json").get("segments") or {})


def drill(base: Path, n: int) -> dict:
    import doctor
    import recovery

    out = base / "output"
    folder = out / f"doc-drill-{n}"
    scenes, seconds = (LONG_SCENES, LONG_SECONDS) if n == 3 else (SCENES, SECONDS)
    make_job(folder, scenes, seconds, captions=n == 3)
    work = folder / "work"
    pend = base / "pending_doc.json"
    checkpoint.write_json(pend, {"folder": folder.name, "data": {"title": f"drill {n}"}, "tries": 0})
    p = start(folder)
    t0 = time.monotonic()
    if n == 1:
        killed = kill_when(p, lambda: recorded(work) >= 2)
    elif n == 2:
        killed = kill_when(p, lambda: (folder / "video.part.mp4").exists() and (folder / "video.part.mp4").stat().st_size > 50_000)
    else:
        killed = kill_when(p, lambda: (work / "part01.part.mp4").exists() and (work / "part01.part.mp4").stat().st_size > 50_000, timeout=1800)
    cut_after = round(time.monotonic() - t0, 1)
    before = stamps(work)
    rec = checkpoint.read_json(work / "segments.json").get("segments") or {}
    rec_parts = checkpoint.read_json(work / "segments.json").get("parts") or {}
    checked = {k: checkpoint.still_valid(work / k, r, r["key"]) for k, r in rec.items()}
    scan = [i for i in recovery.scan(out, pend, thorough=True) if i["folder"] == folder.name]
    doc = doctor.production_status(dt.datetime.now(dt.timezone.utc), pend)
    half = sorted(x.name for x in [*folder.glob("*.part.*"), *work.glob("*.part.*")])
    final_before = (folder / "video.mp4").exists()
    t1 = time.monotonic()
    p2 = start(folder)
    log = p2.communicate(timeout=1800)[0]
    resume_s = round(time.monotonic() - t1, 1)
    after = stamps(work)
    rerendered = sorted(k for k in after if k in before and after[k] != before[k])
    newly = sorted(k for k in after if k not in before)
    final = folder / "video.mp4"
    return {
        "drill": n, "interruption": "SIGKILL of the render's process group " + ("after two checked scenes" if n == 1 else "during the final assembly"),
        "killed": killed, "cut_after_s": cut_after, "scenes_checked_before_cut": len(rec), "checked_scenes_valid_after_cut": all(checked.values()) and bool(checked),
        "half_written_files_after_cut": half, "final_video_existed_after_cut": final_before,
        "scan_saw_interrupted": bool(scan and scan[0]["interrupted"]), "scan_resume_step": scan[0]["resume"] if scan else None,
        "doctor_listed_it": [i["folder"] for i in doc.get("interrupted", [])],
        "resume_exit": p2.returncode, "resume_s": resume_s, "resume_said": [l for l in log.splitlines() if l.strip()][-3:],
        "scenes_kept_unchanged": sorted(k for k in before if before[k] == after.get(k)), "scenes_rerendered": rerendered, "scenes_rendered_on_resume": newly,
        "parts_recorded_before_cut": sorted(rec_parts),
        "final_check": checkpoint.check_media(final, seconds=scenes * seconds, need=("video", "audio"), tol=1.0, full=True) or "complete, decodes in full",
        "final_seconds": round(checkpoint.media_seconds(final), 2), "part_files_left": sorted(x.name for x in [*folder.glob("*.part.*"), *work.glob("*.part.*")]),
        "run_history": checkpoint.read_json(work / checkpoint.MANIFEST).get("history"),
    }


def container_start(base: Path) -> dict:
    """Drill 4, first half (23 Nov 2026): run INSIDE the worker container. Makes the drill-1 job, starts its render detached and returns once two scenes are
    checked. The operator then kills the container's pid 1 from the host (`kill -9 $(docker inspect -f '{{.State.Pid}}' studio-worker)`): every process in the
    container dies at once, as in the host OOM of 22 Nov 2026, and Docker restarts the container. `container-after` checks and resumes."""
    out = base / "output"
    folder = out / "doc-drill-4"
    make_job(folder)
    work = folder / "work"
    checkpoint.write_json(base / "pending_doc.json", {"folder": folder.name, "data": {"title": "drill 4"}, "tries": 0})
    p = start(folder)
    t0 = time.monotonic()
    while recorded(work) < 2 and p.poll() is None and time.monotonic() - t0 < 600:
        time.sleep(0.05)
    facts = {"drill": 4, "render_pid": p.pid, "render_started": checkpoint.proc_start(p.pid), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "scenes_checked_at_handover": recorded(work), "render_still_running": p.poll() is None, "after_s": round(time.monotonic() - t0, 1)}
    checkpoint.write_json(base / "drill4_start.json", facts)
    return facts


def container_after(base: Path) -> dict:
    """Drill 4, second half: run inside the RESTARTED worker container. Nothing has touched the folder since the kill, so its state is the state at the cut."""
    import doctor
    import recovery

    out = base / "output"
    folder = out / "doc-drill-4"
    work = folder / "work"
    pend = base / "pending_doc.json"
    facts = checkpoint.read_json(base / "drill4_start.json")
    before = stamps(work)
    rec = checkpoint.read_json(work / "segments.json").get("segments") or {}
    checked = {k: checkpoint.still_valid(work / k, r, r["key"]) for k, r in rec.items()}
    cut_run = checkpoint.read_json(work / checkpoint.MANIFEST).get("run") or {}
    scan = [i for i in recovery.scan(out, pend, thorough=True) if i["folder"] == folder.name]
    doc = doctor.production_status(dt.datetime.now(dt.timezone.utc), pend)
    half = sorted(x.name for x in [*folder.glob("*.part.*"), *work.glob("*.part.*")])
    old = Path(f"/proc/{facts.get('render_pid')}")
    old_now = old.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")[:80] if old.exists() else "no such process"
    t1 = time.monotonic()
    p2 = start(folder)
    log = p2.communicate(timeout=1800)[0]
    after = stamps(work)
    final = folder / "video.mp4"
    return {
        **facts, "interruption": "kill -9 of the worker container's pid 1 from the host; Docker restarted the container",
        "boot_id_unchanged": Path("/proc/sys/kernel/random/boot_id").read_text().strip() == facts.get("boot_id"),
        "old_render_pid_now": old_now, "cut_run_judged_alive": checkpoint._run_alive(cut_run) if cut_run else None,
        "scenes_checked_before_cut": len(rec), "checked_scenes_valid_after_cut": all(checked.values()) and bool(checked),
        "half_written_files_after_cut": half, "scan_saw_interrupted": bool(scan and scan[0]["interrupted"]), "scan_resume_step": scan[0]["resume"] if scan else None,
        "doctor_listed_it": [i["folder"] for i in doc.get("interrupted", [])],
        "resume_exit": p2.returncode, "resume_s": round(time.monotonic() - t1, 1), "resume_said": [l for l in log.splitlines() if l.strip()][-3:],
        "scenes_kept_unchanged": sorted(k for k in before if before[k] == after.get(k)),
        "scenes_rerendered": sorted(k for k in after if k in before and after[k] != before[k]), "scenes_rendered_on_resume": sorted(k for k in after if k not in before),
        "final_check": checkpoint.check_media(final, seconds=SCENES * SECONDS, need=("video", "audio"), tol=1.0, full=True) or "complete, decodes in full",
        "final_seconds": round(checkpoint.media_seconds(final), 2), "part_files_left": sorted(x.name for x in [*folder.glob("*.part.*"), *work.glob("*.part.*")]),
        "run_history": checkpoint.read_json(work / checkpoint.MANIFEST).get("history"),
    }


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] in ("container-start", "container-after"):
        base = Path(sys.argv[1]).resolve()
        if sys.argv[2] == "container-start":
            if base.exists() and any(base.iterdir()):
                raise SystemExit(f"{base} is not empty: the drill only runs in a new, empty folder")
            base.mkdir(parents=True, exist_ok=True)
            print(json.dumps(container_start(base), indent=1))
        else:
            print(json.dumps(container_after(base), indent=1))
        raise SystemExit(0)
    base = Path(sys.argv[1]).resolve()
    if base.exists() and any(base.iterdir()):
        raise SystemExit(f"{base} is not empty: the drill only runs in a new, empty folder")
    base.mkdir(parents=True, exist_ok=True)
    which = [int(x) for x in sys.argv[2:]] or [1, 2, 3]
    print(json.dumps([drill(base, n) for n in which], indent=1))
