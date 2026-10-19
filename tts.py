"""US-English neural voice (free, edge-tts) plus word-timed captions."""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

import config


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


def _ass(words: list[tuple[float, float, str]]) -> str:
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {config.WIDTH}\nPlayResY: {config.HEIGHT}\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,"
        "BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV\n"
        "Style: Cap,DejaVu Sans,96,&H00FFFFFF,&H00000000,&H64000000,1,1,8,2,5,80,80,0\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Text\n"
    )
    rows = []
    for i in range(0, len(words), 3):  # three words at a time reads well on a phone
        chunk = words[i : i + 3]
        end = words[i + 3][0] if i + 3 < len(words) else chunk[-1][1] + 0.15
        text = " ".join(w[2] for w in chunk).upper()
        rows.append(f"Dialogue: 0,{_ts(chunk[0][0])},{_ts(end)},Cap,{text}")
    return head + "\n".join(rows) + "\n"


def narrate(lines: list[str], work: Path, pause: float = 0.12) -> tuple[Path, Path, list[float]]:
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
    ass.write_text(_ass(all_words))
    return narration, ass, durations
