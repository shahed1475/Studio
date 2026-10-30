"""A branded subscribe reminder that pops up on screen (30 Oct 2026, owner's request).

The animation is drawn once (studio3d/src/SubscribePop.tsx, rendered to the transparent PNG sequence in branding/gloamtale/subscribe/) and laid over the finished video by ffmpeg,
so it costs nothing per video. It is our own gold button with the Gloamtale mark and a bell, not YouTube's button or logo. YouTube's spam policy allows asking viewers to subscribe; what it
forbids is incentives, sub-for-sub swaps and misleading elements, so the pop-up promises nothing and does not pretend to be clickable.
When: a Short pops it just before the narrator says 'subscribe' (the cursor clicks 1.9 s in, about on the word); a documentary ends on the story, so it gets one or two pops at high points
(about 40 and 82 percent in, on the start of a narration line, never in the first 45 s or the last 25 s, 120 s apart). The timing advice is creator practice, not a measured rule.
The overlay is a post-pass: any failure leaves the finished video exactly as it was."""
import os
import subprocess
from pathlib import Path

import config
import render

ASSETS = Path(config.ROOT) / "branding" / "gloamtale" / "subscribe"
POP_SECONDS = 3.6        # 86 frames at 24 fps
POP_FPS = 24
LEAD = 1.2               # a Short's pop starts this long before the spoken word (the click is 1.9 s in)
MIN_START, END_MARGIN, MIN_GAP = 45.0, 25.0, 120.0


def line_starts(durations: list[float]) -> list[float]:
    out, t = [], 0.0
    for d in durations:
        out.append(t)
        t += d
    return out


def _snap(target: float, starts: list[float]) -> float:
    return min(starts, key=lambda s: abs(s - target))


def moments(kind: str, durations: list[float], words: list[dict] | None = None) -> list[float]:
    """Seconds into the video where the pop-up starts."""
    total = sum(durations)
    if kind == "short":
        if total < POP_SECONDS + 1 or not durations:
            return []
        last = len(durations) - 1
        t = line_starts(durations)[last]
        spoken = [w["s"] for w in (words or []) if w.get("i") == last and str(w.get("w", "")).lower().startswith("subscribe")]
        if spoken:
            t = max(t, spoken[0] - LEAD)
        return [round(max(0.0, min(t, total - POP_SECONDS)), 1)]
    if kind == "doc":
        if total < 60:
            return []
        starts = line_starts(durations)
        lo, hi = MIN_START, total - POP_SECONDS - END_MARGIN
        targets = [0.50] if total < 150 else [0.40, 0.82]
        out = []
        for share in targets:
            t = _snap(share * total, starts)
            t = min(max(t, lo), hi)
            if not out or t - out[-1] >= MIN_GAP:
                out.append(t)
        return [round(t, 1) for t in out]
    return []


def _place(size: tuple[int, int], vertical: bool) -> tuple[int, int, int]:
    """(width of the picture, x, y): top right on a landscape video, centred and near the top on a vertical Short."""
    w, h = size
    if vertical:
        tw = round(0.70 * w)
        return tw, round((w - tw) / 2), round(0.14 * h)
    tw = round(0.22 * w)
    return tw, w - tw - round(0.025 * w), round(0.04 * h)


def command(video: Path, out: Path, times: list[float], size: tuple[int, int], vertical: bool, assets: Path = ASSETS) -> list[str]:
    tw, x, y = _place(size, vertical)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    graph, prev = [], "[0:v]"
    for i, t in enumerate(times):
        cmd += ["-framerate", str(POP_FPS), "-i", str(Path(assets) / "pop-%03d.png")]
        graph.append(f"[{i + 1}:v]scale={tw}:-1,format=rgba,setpts=PTS+{t:.3f}/TB[p{i}]")
        graph.append(f"{prev}[p{i}]overlay=x={x}:y={y}:eof_action=pass[v{i}]")
        prev = f"[v{i}]"
    return [*cmd, "-filter_complex", ";".join(graph), "-map", prev, "-map", "0:a?", *render._venc("19", "veryfast"), "-c:a", "copy", "-movflags", "+faststart", str(out)]


def _seconds(path) -> float:
    return render._clip_seconds(path)


def apply(video: Path, times: list[float], size: tuple[int, int], vertical: bool, assets: Path = ASSETS) -> bool:
    """Lay the pop-up over `video` in place. False (video untouched) when ffmpeg fails or the new file's length is not the old one's."""
    video = Path(video)
    tmp = video.with_name(video.stem + ".sub.tmp.mp4")
    try:
        before = _seconds(video)
        subprocess.run(command(video, tmp, times, size, vertical, assets), check=True, capture_output=True, timeout=3600)
        after = _seconds(tmp)
        if before <= 0 or abs(after - before) > 0.5:
            raise ValueError("the length changed")
        os.replace(tmp, video)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


def add_to(video: Path, data: dict, kind: str, durations: list[float], words: list[dict], size: tuple[int, int]) -> bool:
    """The record's switch `subscribe_pop`: absent or True picks the moments, False turns it off, a list gives exact seconds. Notes what was shown in data['subscribe_shown']."""
    switch = data.get("subscribe_pop", True)
    if switch is False:
        return False
    times = [float(t) for t in switch] if isinstance(switch, (list, tuple)) else moments(kind, durations, words)
    if not times:
        return False
    ok = apply(video, times, size, kind == "short")
    if ok:
        data["subscribe_shown"] = {"at": times, "seconds": POP_SECONDS}
        print(f"  subscribe pop-up at {', '.join(f'{t:.0f} s' for t in times)}")
    else:
        print("  subscribe pop-up skipped (the overlay failed); the video is unchanged")
    return ok
