"""The Gloamtale mark, small in a corner of every video of the owner's channel (30 Oct 2026, owner's request: "with logo and brand").

It is laid over the finished video in the same ffmpeg pass as the subscribe pop-up (`subscribe.apply`), so it adds no second re-encode. It fades in after the cold open (the first 4 s
belong to the hook), stays at partial opacity so it never fights the picture or the captions, and fades out with the video. A documentary carries it bottom left (chapter cards sit top
left, date badges and the pop-up top right, captions in the middle below); a vertical Short carries it top left, under the phone's status bar and clear of the pop-up.
It is not YouTube's channel watermark (the owner sets that in Studio) and it is the owner's mark: a user studio on this server never shows it.
The record's switch `brand_mark`: absent or true shows it, false turns it off."""
from pathlib import Path

import config

MARK = Path(config.ROOT) / "branding" / "gloamtale" / "watermark-150.png"
APPEAR, FADE_IN, FADE_OUT, OPACITY = 4.0, 1.0, 1.5, 0.75
SHARE = {False: 0.06, True: 0.12}   # width of the mark as a share of the video's width: landscape, vertical


def spec(size: tuple[int, int], vertical: bool, seconds: float, mark: Path = MARK) -> dict | None:
    """Where and when the mark shows on a video of this size and length, or None when it cannot (no file, or a video too short to show it)."""
    w, h = size
    if not Path(mark).exists() or seconds < APPEAR + FADE_IN + FADE_OUT:
        return None
    tw = round(SHARE[bool(vertical)] * w)
    margin = round(0.025 * w) if not vertical else round(0.04 * w)
    return {"file": str(mark), "width": tw, "x": margin, "y": round(0.07 * h) if vertical else h - tw - round(0.025 * w),
            "start": APPEAR, "seconds": round(seconds, 3)}


def corner(vertical: bool) -> str:
    """Which corner the mark sits in, for the video's record."""
    return "top left" if vertical else "bottom left"


def chain(m: dict, index: int, prev: str) -> tuple[list[str], list[str], str]:
    """(ffmpeg input arguments, filter-graph parts, the label of the result) that lay the mark over `prev`. `index` is the mark's input number."""
    end = max(m["start"] + FADE_IN, m["seconds"] - FADE_OUT)
    inputs = ["-loop", "1", "-framerate", "30", "-t", f"{m['seconds'] + 1:.3f}", "-i", m["file"]]
    graph = [f"[{index}:v]scale={m['width']}:-1,format=rgba,colorchannelmixer=aa={OPACITY},fade=t=in:st={m['start']}:d={FADE_IN}:alpha=1,fade=t=out:st={end:.3f}:d={FADE_OUT}:alpha=1[mk]",
             f"{prev}[mk]overlay=x={m['x']}:y={m['y']}:eof_action=pass[vm]"]
    return inputs, graph, "[vm]"
