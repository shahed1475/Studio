"""Sound cues of the studio's own making (30 Oct 2026, owner's order: hook and curiosity from the first second with voice, sound effects and a question).

Four effects are synthesised with ffmpeg once and kept in cache/sfx, so no licence question exists: a riser that swells into the first word, a low hit on the reveal (the start of the
second line), a soft whoosh at each chapter change and a quiet swell when the last chapter starts (the payoff). They are laid under the finished narration in an audio-only pass: the
picture is copied, the length is checked, any failure leaves the video exactly as it was. They are quiet on purpose, so the loudness target does not move.
No study shows that sound effects raise retention (research of 30 Oct 2026, docs/superpowers/plans/2026-10-30-content-system-v2.md): this is a design choice, off with `sfx: false`
in the video's record, and never added in a user studio (the cues are part of the owner's channel style, like the pop-up)."""
import os
import subprocess
from pathlib import Path

import config

CACHE_DIR = Path(config.CACHE) / "sfx"
LENGTHS = {"riser": 1.8, "hit": 1.2, "whoosh": 0.9, "swell": 3.0}
GAIN_DB = {"riser": -20, "hit": -13, "whoosh": -22, "swell": -26}  # under the voice: a hit is short, so it barely moves the integrated loudness
MIN_GAP = 3.0       # cues closer than this are dropped: a cue is an event, not a texture
MAX_CUES = 14
SPEC = {
    "riser": "aevalsrc='0.6*sin(2*PI*(90*t+240*t*t))*min(t/1.6,1)':d=1.8:s=44100,afade=t=out:st=1.6:d=0.2",
    "hit": "aevalsrc='0.9*sin(2*PI*52*t)*exp(-5*t)+0.3*sin(2*PI*104*t)*exp(-9*t)':d=1.2:s=44100",
    "whoosh": "anoisesrc=d=0.9:c=pink:a=0.5:r=44100,highpass=f=500,lowpass=f=6000,afade=t=in:d=0.4,afade=t=out:st=0.4:d=0.5",
    "swell": "aevalsrc='0.18*(sin(2*PI*110*t)+sin(2*PI*164.81*t)+sin(2*PI*220*t))*sin(PI*t/3)':d=3:s=44100",
}


def line_starts(durations: list[float]) -> list[float]:
    out, t = [], 0.0
    for d in durations:
        out.append(t)
        t += d
    return out


def cues(kind: str, durations: list[float], chapters: list[dict] | None = None) -> list[tuple[float, str]]:
    """[(second, effect)] in time order. A Short: a riser at 0 and a hit on its second line. A film adds a whoosh at every chapter after the first and a swell at the last chapter."""
    if not durations:
        return []
    starts, total = line_starts(durations), sum(durations)
    out = [(0.0, "riser")]
    if len(starts) > 1 and starts[1] + LENGTHS["hit"] <= total:
        out.append((round(starts[1], 3), "hit"))
    if kind == "doc":
        lines = [int(c.get("start_line", 0)) for c in (chapters or [])]
        for i in lines[1:-1]:
            if 0 < i < len(starts) and starts[i] + LENGTHS["whoosh"] <= total:
                out.append((round(starts[i], 3), "whoosh"))
        if len(lines) > 2 and 0 < lines[-1] < len(starts) and starts[lines[-1]] + LENGTHS["swell"] <= total:
            out.append((round(starts[lines[-1]], 3), "swell"))
    out.sort()
    kept: list[tuple[float, str]] = []
    for t, name in out:
        if not kept or t - kept[-1][0] >= MIN_GAP:
            kept.append((t, name))
    return kept[:MAX_CUES]


def _effect(name: str, cache: Path) -> Path:
    """The wav of one effect, made once."""
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / f"{name}.wav"
    if not dest.exists():
        tmp = dest.with_suffix(".tmp.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", SPEC[name], "-t", str(LENGTHS[name]), "-ac", "1", str(tmp)], check=True, capture_output=True, timeout=120)
        os.replace(tmp, dest)
    return dest


def _seconds(path) -> float:
    import render

    return render._clip_seconds(path)


def apply(video: Path, plan: list[tuple[float, str]], cache: Path | None = None) -> bool:
    """Lay the cues under the narration of `video` in place. False (video untouched) when ffmpeg fails or the new file's length is not the old one's."""
    video, cache = Path(video), Path(cache or CACHE_DIR)
    tmp = video.with_name(video.stem + ".sfx.tmp.mp4")
    try:
        before = _seconds(video)
        cmd, parts, labels = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)], [], []
        for i, (t, name) in enumerate(plan, 1):
            cmd += ["-i", str(_effect(name, cache))]
            ms = round(t * 1000)
            parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay={ms}:all=1,volume={GAIN_DB[name]}dB[c{i}]")
            labels.append(f"[c{i}]")
        graph = ";".join(parts) + f";[0:a]aformat=sample_rates=44100:channel_layouts=stereo[v];[v]{''.join(labels)}amix=inputs={len(plan) + 1}:duration=first:normalize=0:dropout_transition=0[a]"
        subprocess.run([*cmd, "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(tmp)],
                       check=True, capture_output=True, timeout=3600)
        after = _seconds(tmp)
        if before <= 0 or abs(after - before) > 0.5:
            raise ValueError("the length changed")
        os.replace(tmp, video)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


def add_to(video: Path, data: dict, kind: str, durations: list[float], chapters: list[dict] | None = None, cache: Path | None = None) -> bool:
    """The record's switch `sfx`: absent or True lays the cues, False turns them off. Notes what was laid in data['sfx_shown']. Never in a user studio."""
    import tenantmode

    if tenantmode.is_tenant() or data.get("sfx") is False:
        return False
    plan = cues(kind, durations, chapters)
    if not plan:
        return False
    ok = apply(video, plan, cache)
    if ok:
        data["sfx_shown"] = {"cues": len(plan), "names": sorted({n for _, n in plan})}
        print(f"  sound cues: {', '.join(n for _, n in plan[:6])}{'...' if len(plan) > 6 else ''} ({len(plan)})")
    else:
        print("  sound cues skipped (the mix failed); the video is unchanged")
    return ok
