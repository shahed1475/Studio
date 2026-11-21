"""The background music under a video's narration (20 Nov 2026, owner's order: suitable music, mixed correctly, for Shorts and documentaries).

The tracks are public-domain or CC0 recordings from Wikimedia Commons in music/ (LEDGER.json: file page, licence, performer, checksums; LICENSE.txt for the licence check).
Before this, a film looped one random track under the whole narration (a 22-minute film would hear a three-minute nocturne seven times) and no record said which track
was used. Now a video gets a bed as long as itself: different tracks one after another with a 4-second crossfade, never the same track twice until every track has played,
in an order fixed by the video's topic (a re-render hears the same music), faded out at the end. The renderer mixes it about 23 dB under the voice (render.py volume 0.07 on a
-16 LUFS track). A track whose file no longer matches its ledger checksum is left out. No music at all is a valid result: the video is made without it, never stopped."""
import hashlib
import json
import random
import subprocess
from pathlib import Path

import config

DIR = config.ROOT / "music"
FADE = 4.0


def tracks() -> list[dict]:
    """The ledger's tracks whose file is present and unchanged, with an approved licence."""
    try:
        ledger = json.loads((DIR / "LEDGER.json").read_text())
    except (OSError, ValueError):
        return []
    if not (DIR / "LICENSE.txt").exists():
        return []
    out = []
    for t in ledger if isinstance(ledger, list) else []:
        f = DIR / str(t.get("file", ""))
        if f.suffix != ".mp3" or not f.is_file() or str(t.get("licence", "")).lower() not in ("cc0", "public domain"):
            continue
        if t.get("sha256_mp3") and hashlib.sha256(f.read_bytes()).hexdigest() != t["sha256_mp3"]:
            continue
        out.append({**t, "path": f})
    return out


def order(items: list[dict], seed: str) -> list[dict]:
    """The tracks in an order fixed by the seed (the video's topic)."""
    items = sorted(items, key=lambda t: t["file"])
    random.Random(hashlib.sha256(seed.encode()).hexdigest()).shuffle(items)
    return items


def plan(seconds: float, seed: str, items: list[dict] | None = None) -> list[dict]:
    """Enough tracks to cover `seconds` plus the crossfades: each track once before any repeats."""
    items = order(tracks() if items is None else items, seed)
    if not items:
        return []
    picked, total, i = [], 0.0, 0
    while total < seconds + FADE and i < 50:
        t = items[i % len(items)]
        picked.append(t)
        total += float(t.get("seconds") or 0) - (FADE if picked[1:] else 0.0)
        i += 1
    return picked


def bed(seconds: float, work: Path, seed: str) -> tuple[Path | None, list[dict]]:
    """(an mp3 as long as the video, the tracks it holds as ledger records without paths). (None, []) when there is no usable music or ffmpeg fails."""
    picked = plan(seconds, seed)
    if not picked or seconds <= 0:
        return None, []
    out = Path(work) / "music_bed.mp3"
    args, graph = [], []
    for t in picked:
        args += ["-i", str(t["path"])]
    prev = "[0:a]"
    for k in range(1, len(picked)):
        graph.append(f"{prev}[{k}:a]acrossfade=d={FADE:g}:c1=tri:c2=tri[x{k}]")
        prev = f"[x{k}]"
    graph.append(f"{prev}atrim=0:{seconds:.3f},afade=t=in:d=2,afade=t=out:st={max(0.0, seconds - 3):.3f}:d=3[m]")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(graph), "-map", "[m]", "-c:a", "libmp3lame", "-b:a", "160k", str(out)],
                       check=True, capture_output=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return None, []
    used = [{k: v for k, v in t.items() if k != "path"} for t in picked]
    return out, used


def record(used: list[dict]) -> dict:
    """What a video's record keeps about its music: each track's file page and licence (no credit is required for CC0 or public domain; it is recorded anyway)."""
    return {"tracks": [{"title": t.get("title"), "licence": t.get("licence"), "page": t.get("page"), "performer": t.get("performer_or_author")} for t in used],
            "mix": "about 23 dB under the narration"} if used else {"tracks": [], "mix": "none"}
