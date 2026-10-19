"""US-English neural voice (free, edge-tts) plus word-timed captions."""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

import config
import keywords


def _duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out.decode().strip())


async def _synth_line(text: str, mp3: Path) -> list[tuple[float, float, str]]:
    """The voice service sometimes returns no audio for a line. Try again with a growing wait before giving up."""
    for attempt, wait in enumerate((1, 3, 8, 0)):
        try:
            return await _synth_once(text, mp3)
        except Exception:
            if not wait:
                raise
            await asyncio.sleep(wait)


async def _synth_once(text: str, mp3: Path) -> list[tuple[float, float, str]]:
    comm = edge_tts.Communicate(text, config.VOICE, rate=config.VOICE_RATE, pitch=config.VOICE_PITCH, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ev in comm.stream():
            if ev["type"] == "audio":
                f.write(ev["data"])
            elif ev["type"] == "WordBoundary":
                start = ev["offset"] / 1e7
                words.append((start, start + ev["duration"] / 1e7, ev["text"]))
    return words


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def words_to_json(words: list[tuple], path: Path) -> None:
    """Word timings for subtitles: start, end, text and the narration line each word belongs to."""
    path.write_text(json.dumps([{"s": round(s, 3), "e": round(e, 3), "w": w, "i": i} for s, e, w, i in words]))


def timings(lines: list[str], work: Path) -> list[dict]:
    """Word timings only (no concatenated narration): used to add subtitles to a video that already exists."""
    work.mkdir(parents=True, exist_ok=True)
    words, offset = [], 0.0
    for i, text in enumerate(lines):
        mp3 = work / f"t{i:02d}.mp3"
        got = asyncio.run(_synth_line(text, mp3))
        words += [(s + offset, e + offset, w, i) for s, e, w in got]
        offset += _duration(mp3) + 0.12
    words_to_json(words, work / "words.json")
    return json.loads((work / "words.json").read_text())


ACCENT = "&H28C8FF&"  # the thumbnail accent colour (255, 200, 40) in ASS order


def _wrap_hook(words: list[str], max_chars: int = 16) -> str:
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "\\N".join([*lines, cur] if cur else lines)


def _ass(words: list[tuple], motion: int = 0, pos: str = "bottom") -> str:
    """Captions for a Short. motion 0: three words at a time in the middle. motion 1 and up: the first line (the hook) as a big title,
    then a lower-third caption where the word being spoken is highlighted and pops."""
    words = [(w[0], w[1], keywords.clean(w[2]), *w[3:]) for w in words]
    return _ass_rich(words, pos) if motion >= 1 else _ass_plain(words)


MAX_CAPTION_CHARS = 16  # about 55 px a letter at the caption size: more than this runs off the sides of a 1080 px wide Short


def caption_spans(texts: list[str], limit: int = MAX_CAPTION_CHARS) -> list[tuple[int, int]]:
    """Groups of up to three words that fit the screen width: (start, end) indexes. A single long word stays alone."""
    spans, i = [], 0
    while i < len(texts):
        j, n = i + 1, len(texts[i])
        while j < len(texts) and j - i < 3 and n + 1 + len(texts[j]) <= limit:
            n += 1 + len(texts[j])
            j += 1
        spans.append((i, j))
        i = j
    return spans


def _ass_rich(words: list[tuple], pos: str = "bottom") -> str:
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {config.WIDTH}\nPlayResY: {config.HEIGHT}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV\n"
        f"Style: Cap,DejaVu Sans,92,&H00FFFFFF,&H00000000,&H64000000,1,1,8,2,{8 if pos == 'top' else 2},110,110,{250 if pos == 'top' else 380}\n"
        f"Style: Hook,DejaVu Sans,104,{ACCENT.replace('&H', '&H00', 1)},&H00000000,&H64000000,1,1,9,3,8,70,70,330\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Text\n"
    )
    numbered = bool(words) and len(words[0]) > 3
    line_of = (lambda w: w[3]) if numbered else (lambda w: 1)
    rows, caps = [], list(words)
    first = [w for w in words if line_of(w) == 0]
    if numbered and first and len(first) < len(words):
        end = first[-1][1] + 0.15
        text = _wrap_hook([w[2].upper() for w in first])
        rows.append(f"Dialogue: 1,{_ts(first[0][0])},{_ts(end)},Hook,{{\\fad(250,300)\\fscx85\\fscy85\\t(0,300,\\fscx100\\fscy100)}}{text}")
        caps = [w for w in words if line_of(w) != 0]
    by_line: dict = {}
    for w in caps:
        by_line.setdefault(line_of(w), []).append(w)
    for ws in by_line.values():
        found = keywords.kinds([w[2] for w in ws])  # judged on the whole line, so "Hamelin" at the start is not mistaken for a name
        for i, j in caption_spans([w[2] for w in ws]):
            chunk, mark = ws[i:j], keywords.limit(found[i:j], 2)
            for k, w in enumerate(chunk):
                nxt = chunk[k + 1][0] if k + 1 < len(chunk) else w[1] + 0.15
                shown = []
                for j, c in enumerate(chunk):
                    col = f"\\c{keywords.color(mark[j])}" if mark[j] else ""
                    pop = "\\fscx115\\fscy115\\t(0,110,\\fscx100\\fscy100)" if j == k else ""  # the word being spoken pops
                    shown.append(f"{{{pop}{col}}}{c[2].upper()}{{\\r}}" if (pop or col) else c[2].upper())
                rows.append(f"Dialogue: 0,{_ts(w[0])},{_ts(nxt)},Cap,{' '.join(shown)}")
    return head + "\n".join(rows) + "\n"


def _ass_plain(words: list[tuple[float, float, str]]) -> str:
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {config.WIDTH}\nPlayResY: {config.HEIGHT}\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV\n"
        "Style: Cap,DejaVu Sans,96,&H00FFFFFF,&H00000000,&H64000000,1,1,8,2,5,80,80,0\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Text\n"
    )
    rows = []
    for i, j in caption_spans([w[2] for w in words]):  # up to three words at a time reads well on a phone
        chunk = words[i:j]
        end = words[j][0] if j < len(words) else chunk[-1][1] + 0.15
        text = " ".join(w[2] for w in chunk).upper()
        rows.append(f"Dialogue: 0,{_ts(chunk[0][0])},{_ts(end)},Cap,{text}")
    return head + "\n".join(rows) + "\n"


def narrate(lines: list[str], work: Path, pause: float = 0.12, motion: int = 0, pos: str = "bottom") -> tuple[Path, Path, list[float]]:
    """Return (narration.mp3, captions.ass, per-line durations in seconds)."""
    work.mkdir(parents=True, exist_ok=True)
    all_words, durations, parts = [], [], []
    offset = 0.0
    for i, text in enumerate(lines):
        mp3 = work / f"line{i:02d}.mp3"
        words = asyncio.run(_synth_line(text, mp3))
        d = _duration(mp3) + pause  # small breath between lines
        all_words += [(s + offset, e + offset, w, i) for s, e, w in words]
        durations.append(d)
        offset += d
        parts.append(mp3)
    # concat with a bit of silence after each line so audio and clip timing stay aligned
    inputs, filt = [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filt.append(f"[{i}:a]aresample=44100,apad=pad_dur={pause},atrim=0:{durations[i]:.3f}[a{i}]")
    chain = "".join(f"[a{i}]" for i in range(len(parts)))
    narration = work / "narration.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
         ";".join(filt) + f";{chain}concat=n={len(parts)}:v=0:a=1[out]", "-map", "[out]", str(narration)],
        check=True,
    )
    words_to_json(all_words, work / "words.json")
    ass = work / "captions.ass"
    ass.write_text(_ass(all_words, motion, pos))
    return narration, ass, durations
