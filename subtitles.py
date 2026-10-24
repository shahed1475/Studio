"""Subtitles from word timings: cues, SRT text and an ASS style for 16:9 documentaries."""
import json
import records
from pathlib import Path

import keywords

MAX_CUE_SECONDS = 6.0


def _wrap(words: list[str], max_chars: int) -> str:
    """One line if it fits, else two lines split where they are the most even."""
    text = " ".join(words)
    if len(text) <= max_chars or len(words) < 2:
        return text
    best = min(range(1, len(words)), key=lambda k: max(len(" ".join(words[:k])), len(" ".join(words[k:]))))
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


def _fits(words: list[str], max_chars: int) -> bool:
    return all(len(l) <= max_chars for l in _wrap(words, max_chars).split("\n"))


def with_punctuation(words: list[dict], lines: list[str]) -> list[dict]:
    """The voice's word timings carry no punctuation. Where a narration line has the same number of words as its timings, show the
    line's own words (commas, full stops, apostrophes) so captions read naturally and can break at clauses."""
    out = [dict(w) for w in words]
    by_line: dict[int, list[int]] = {}
    for k, w in enumerate(out):
        by_line.setdefault(w["i"], []).append(k)
    for i, idx in by_line.items():
        toks = lines[i].split() if 0 <= i < len(lines) else []
        if len(toks) == len(idx):
            for k, t in zip(idx, toks):
                out[k]["w"] = t
    return out


CLAUSE_END = ",.;:?!"


def build_cues(words: list[dict], max_chars: int = 42) -> list[dict]:
    """Words are {s, e, w, i}: start, end, text and narration line index. A cue never spans two narration lines."""
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur and (w["i"] != cur[-1]["i"] or w["e"] - cur[0]["s"] > MAX_CUE_SECONDS - 0.2
                    or not _fits([x["w"] for x in cur] + [w["w"]], max_chars)
                    or (len(cur) >= 3 and cur[-1]["w"][-1] in CLAUSE_END)):  # break after a clause, not in the middle of one
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    cues = [{"start": g[0]["s"], "end": g[-1]["e"] + 0.15, "text": _wrap([x["w"] for x in g], max_chars)} for g in groups]
    for k, c in enumerate(cues):
        nxt = cues[k + 1]["start"] if k + 1 < len(cues) else float("inf")
        c["end"] = min(max(c["end"], c["start"] + 1.0), nxt, c["start"] + MAX_CUE_SECONDS)
    return cues


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def to_srt(cues: list[dict]) -> str:
    return "".join(f"{n}\n{_srt_ts(c['start'])} --> {_srt_ts(c['end'])}\n{c['text']}\n\n" for n, c in enumerate(cues, 1))


def _ass_ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def to_ass(cues: list[dict], size: tuple[int, int] = (1920, 1080), pos: str = "bottom") -> str:
    w, h = size
    head = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV\n"
        f"Style: Sub,DejaVu Sans,{round(h * 0.06)},&H00FFFFFF,&H00000000,&H64000000,1,1,4,2,{8 if pos == 'top' else 2},{round(w * 0.08)},{round(w * 0.08)},{round(h * (0.07 if pos == 'top' else 0.06))}\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Text\n"
    )
    rows = [f"Dialogue: 0,{_ass_ts(c['start'])},{_ass_ts(c['end'])},Sub,{keywords.colorize(keywords.clean(c['text'])).replace(chr(10), chr(92) + 'N')}" for c in cues]
    return head + "\n".join(rows) + "\n"


def timings_match(words: list[dict], video_seconds: float, tol: float = 1.5) -> bool:
    return bool(words) and abs(words[-1]["e"] - video_seconds) <= tol


def load_words(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())


def write_files(folder: Path, words: list[dict]) -> Path:
    """captions.srt next to the video, for players, editors and a later caption upload."""
    srt = folder / "captions.srt"
    srt.write_text(to_srt(build_cues(words)))
    return srt


def video_seconds(path: Path) -> float:
    import subprocess

    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], text=True))


def ensure_words(folder: Path) -> list[dict]:
    """Saved word timings, or new ones from the saved script. Refuses when they do not fit the video's length."""
    saved = folder / "words.json"
    if saved.exists():
        return load_words(saved)
    import tts

    meta = json.loads((folder / "meta.json").read_text())
    work = folder / "work_subs"
    try:
        words = tts.timings([l["text"] for l in meta["lines"]], work)
    finally:
        if work.exists():
            for f in work.glob("*"):
                f.unlink()
            work.rmdir()
    seconds = video_seconds(folder / "video.mp4")
    if not timings_match(words, seconds):
        raise SystemExit(f"the voice timings do not match this video ({words[-1]['e']:.0f} s of speech vs {seconds:.0f} s); nothing was changed")
    saved.write_text(json.dumps(words))
    return words


def burn_into_video(folder: Path) -> None:
    """Burn subtitles into an existing documentary. The original stays untouched unless the encode succeeds."""
    import subprocess

    import render
    import reviewer

    meta_path = folder / "meta.json"
    meta = json.loads(meta_path.read_text())
    if meta.get("video_id"):
        raise SystemExit("this video is already uploaded; the file cannot be changed")
    if meta.get("format") != "doc":
        raise SystemExit("Shorts already have burned-in captions")
    if meta.get("subtitles") == "burned":
        raise SystemExit("this video already has burned-in subtitles")
    words = with_punctuation(ensure_words(folder), [l["text"] for l in meta["lines"]])
    ass = folder / "burn.ass"
    ass.write_text(to_ass(build_cues(words), (1920, 1080), __import__("editprofile").load()["caption_pos"]))
    tmp = folder / "video.tmp.mp4"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video.mp4", "-vf", f"subtitles={ass.name}",
                        *render._venc("21", "medium"), "-c:a", "copy", "-movflags", "+faststart", tmp.name], check=True, cwd=folder)
        tmp.replace(folder / "video.mp4")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        ass.unlink(missing_ok=True)
    write_files(folder, words)
    def apply(d):
        d["subtitles"] = "burned"
        reviewer.invalidate(d)

    records.update(folder, apply)
