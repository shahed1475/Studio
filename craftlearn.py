"""What the reference channels' own public numbers say about video length and chapter pace.

Input is the metadata the YouTube Data API already returns for each scanned video (length, views, publish date, and the chapter
timestamps creators write in the description). Nothing is watched or downloaded (rule B), so cuts, music and picture style are NOT measured:
the coverage text says so. A video "outperforms" when its views per day beat 1.5 times the median of its own channel and format, so a huge
channel does not drown a small one. The result is advice for a person and the writer; it never changes a rule by itself.
"""
import datetime as dt
import json
import re
import statistics
from pathlib import Path

import config

FILE = config.ROOT / "data" / "channels" / "craft.json"
STAMP = re.compile(r"(?m)^\s*(?:[-*•]\s*)?(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")
MIN_AGE_DAYS = 7        # a video younger than this has not had time to show what it can do
MAX_AGE_DAYS = 365
OUTPERFORM = 1.5
MIN_PER_KIND = 5        # videos of one format in one channel before its median means anything
MIN_OUTPERFORMERS = 8   # across all channels before a band is reported


def chapter_marks(description: str) -> list[int]:
    """Seconds of each chapter start, only when the description is a valid YouTube chapter list (starts at 0:00, three or more, ascending)."""
    marks = [int(h or 0) * 3600 + int(m) * 60 + int(s) for h, m, s in STAMP.findall(description or "")]
    if len(marks) < 3 or marks[0] != 0 or marks != sorted(marks):
        return []
    return marks


def compact(video: dict) -> dict:
    """The few fields kept per scanned video (the description itself is not stored)."""
    marks = chapter_marks(video.get("description", ""))
    gaps = [b - a for a, b in zip(marks, marks[1:])] + ([max(video["seconds"] - marks[-1], 0)] if marks else [])
    return {"s": video["seconds"], "v": video["views"], "p": video["published"], "ch": len(marks),
            "gap": int(statistics.median(gaps)) if gaps else 0}


def _quant(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    i = (len(xs) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def _kind(seconds: int) -> str | None:
    if seconds <= 60:
        return "short"
    return "doc" if 240 <= seconds <= 3600 else None


def _age_days(published: str, now: dt.datetime) -> int | None:
    try:
        return (now - dt.datetime.fromisoformat(published.replace("Z", "+00:00"))).days
    except ValueError:
        return None


def learn(digest: dict, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    pools: dict[str, list[dict]] = {"short": [], "doc": []}
    channels = scanned = 0
    for c in digest.get("channels", []):
        by_kind: dict[str, list[dict]] = {"short": [], "doc": []}
        for v in c.get("scan", []):
            age, kind = _age_days(v.get("p", ""), now), _kind(v.get("s", 0))
            if kind is None or age is None or age < MIN_AGE_DAYS or age > MAX_AGE_DAYS:
                continue
            by_kind[kind].append({**v, "vpd": v.get("v", 0) / max(age, 1)})
        used = False
        for kind, vs in by_kind.items():
            if len(vs) < MIN_PER_KIND:
                continue
            med = statistics.median(x["vpd"] for x in vs)
            if med <= 0:
                continue
            used = True
            scanned += len(vs)
            pools[kind] += [{**x, "rel": x["vpd"] / med} for x in vs]
        channels += used
    bands = {}
    for kind, vs in pools.items():
        out = [x for x in vs if x["rel"] >= OUTPERFORM]
        if len(out) < MIN_OUTPERFORMERS:
            bands[kind] = {"videos": len(vs), "outperformers": len(out), "note": "too few outperforming videos to say anything"}
            continue
        secs = [x["s"] for x in out]
        b = {"videos": len(vs), "outperformers": len(out), "all_median_s": int(statistics.median(x["s"] for x in vs)),
             "out_p25_s": int(_quant(secs, .25)), "out_median_s": int(_quant(secs, .5)), "out_p75_s": int(_quant(secs, .75))}
        if kind == "doc":
            chap = [x for x in out if x.get("ch", 0) >= 3]
            b["with_chapters_share"] = round(len(chap) / len(out), 2)
            if chap:
                b["chapters_per_10min_median"] = round(statistics.median(x["ch"] / (x["s"] / 600) for x in chap), 1)
                b["seconds_per_chapter_median"] = int(statistics.median(x["gap"] for x in chap if x.get("gap")) if any(x.get("gap") for x in chap) else 0)
        bands[kind] = b
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "channels_used": channels, "videos_used": scanned, "bands": bands,
            "versus_studio": _versus(bands),
            "coverage": (f"YouTube Data API numbers of {scanned} videos from {channels} reference channels: length, views, age, chapter timestamps in descriptions. "
                         "No video was watched or downloaded, so cuts, music, captions and picture style are NOT measured here.")}


def _versus(bands: dict) -> list[str]:
    notes = []
    try:
        import rulesfile

        lo, hi = rulesfile.get("benchmarks", "long_min_minutes"), rulesfile.get("benchmarks", "long_max_minutes")
        slo, shi = rulesfile.get("benchmarks", "shorts_min_seconds"), rulesfile.get("benchmarks", "shorts_max_seconds")
    except Exception:
        return notes
    d, s = bands.get("doc", {}), bands.get("short", {})
    if d.get("out_median_s"):
        notes.append(f"Outperforming long videos run {d['out_p25_s'] // 60} to {d['out_p75_s'] // 60} minutes (middle {d['out_median_s'] // 60}); the studio's target is {lo} to {hi}. "
                     "The target is the owner's choice and is not changed by this.")
    if s.get("out_median_s"):
        notes.append(f"Outperforming Shorts run {s['out_p25_s']} to {s['out_p75_s']} seconds (middle {s['out_median_s']}); the studio's range is {slo} to {shi}.")
    return notes


def save(result: dict, path: Path | None = None) -> Path:
    path = Path(path or FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return path


def latest(path: Path | None = None) -> dict | None:
    try:
        return json.loads(Path(path or FILE).read_text())
    except (OSError, ValueError):
        return None
