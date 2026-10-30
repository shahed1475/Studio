"""US-English neural voice (free, edge-tts) plus word-timed captions."""
import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts

import audiofinish

import config
import keywords


def _duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out.decode().strip())


# An opt-in delivery for a Short (a video's `voice_style`): quicker, brighter, with the hook, the questions and the closing invitation lifted and the payoff settled.
# The default voice (Andrew, -6% speed, -3 Hz) is a calm bedtime reader. Measured 29 Oct 2026 on the same two lines: rate and pitch change the delivery (+8% rate made the
# line 15% faster, +2 Hz raised its median pitch), while the `volume` setting only moves the raw level, which the renderer's loudness target replaces; so loudness is set
# there (editprofile.lufs_for), not here. Judged by measurement, not by ear.
FINISH_LUFS = -14.5  # the narration alone; the render's own target (editprofile, -14) then trims the last half decibel with the music in
VOICE_STYLES = {
    "energetic": {"voice": "en-US-AndrewMultilingualNeural", "rate": "+10%", "pitch": "+2Hz",  # 30 Oct 2026: one voice for the channel (the owner chose Andrew Multilingual); the style lifts it with rate and pitch
                  "hook": {"rate": "+14%", "pitch": "+6Hz"}, "question": {"rate": "+8%", "pitch": "+7Hz"},
                  "payoff": {"rate": "+3%", "pitch": "+0Hz"}, "invite": {"rate": "+12%", "pitch": "+5Hz"},
                  # The service ends every line with silence after its last word: 0.83 s for this voice (29 Oct 2026: the last word ends at 4.66 s, the file runs to 5.52 s). With the
                  # renderer's own breath that was 1.1 to 1.2 s of no voice, no caption and a still picture before every line. Keep only this much after the last word.
                  "tail": 0.15},
}
INVITE = re.compile(r"\bfollow\b|subscribe|next story", re.I)


# How a name is SAID, for names the voice gets wrong. 30 Oct 2026: the voice read "Amun" as "ah-mo-nee-us"; a Gemini model listened to four spellings and heard "ah-moon" only for
# "Ahmoon". Only the text sent to the voice changes: the script, the captions (matched to the script word by word) and the description keep the real spelling, so a respelling
# must stay ONE word.
PRONUNCIATION = {"Amun": "Ahmoon"}


def spoken(text: str) -> str:
    for word, said in PRONUNCIATION.items():
        text = re.sub(rf"(?<![\w]){re.escape(word)}(?![\w])", said, text)
    return text


def line_length(duration: float, words: list[tuple], pause: float, tail: float | None) -> float:
    """Seconds one narration line takes, breath included. With a `tail` the silence the service leaves after the last spoken word is cut to that length (the file
    is never padded, and a line with no word timings keeps the whole file); with None the whole file is kept."""
    if tail is not None and words:
        duration = min(duration, words[-1][1] + tail)
    return duration + pause


def voice_used(style: str | None = None) -> dict:
    """Which voice made a video's narration, for its record (the record did not say, so 'what voice did we use' needed the git history). A styled voice keeps its base
    rate and pitch; each line then lifts them a little."""
    spec = VOICE_STYLES.get(style or "")
    return {"voice": spec["voice"] if spec else config.VOICE, "rate": spec["rate"] if spec else config.VOICE_RATE, "pitch": spec["pitch"] if spec else config.VOICE_PITCH,
            "style": style or None, "finish_lufs": FINISH_LUFS}


def line_prosody(style: str | None, text: str, index: int, total: int) -> dict | None:
    """{voice, rate, pitch} for one narration line of a styled video, or None for the studio's default voice. The hook is line 0, the invitation is a closing line that
    asks to follow, the payoff is the line before it, and any other question rises."""
    spec = VOICE_STYLES.get(style or "")
    if not spec:
        return None
    last_is_invite = total > 1 and bool(INVITE.search(text if index == total - 1 else ""))
    if index == 0:
        part = spec["hook"]
    elif last_is_invite:
        part = spec["invite"]
    elif index == total - 2:
        part = spec["payoff"]
    elif text.rstrip().endswith("?"):
        part = spec["question"]
    else:
        part = spec
    return {"voice": spec["voice"], "rate": part["rate"], "pitch": part["pitch"]}


async def _synth_line(text: str, mp3: Path, prosody: dict | None = None) -> list[tuple[float, float, str]]:
    """The voice service sometimes returns no audio for a line. Try again with a growing wait before giving up."""
    for attempt, wait in enumerate((1, 3, 8, 0)):
        try:
            return await (_synth_once(text, mp3) if prosody is None else _synth_once(text, mp3, prosody))
        except Exception:
            if not wait:
                raise
            await asyncio.sleep(wait)


async def _synth_once(text: str, mp3: Path, prosody: dict | None = None) -> list[tuple[float, float, str]]:
    voice, rate, pitch = (prosody["voice"], prosody["rate"], prosody["pitch"]) if prosody else (config.VOICE, config.VOICE_RATE, config.VOICE_PITCH)
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
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
        got = asyncio.run(_synth_line(spoken(text), mp3))
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
    cap_rows: list[list] = []
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
                cap_rows.append([w[0], nxt, " ".join(shown)])
    cap_rows.sort(key=lambda r: r[0])
    for a, b in zip(cap_rows, cap_rows[1:]):  # the last word of a group is held 0.15 s past its end: never into the next group, or the two lines print over each other
        a[1] = min(a[1], b[0])
    rows += [f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,{text}" for a, b, text in cap_rows]
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


def narrate(lines: list[str], work: Path, pause: float = 0.12, motion: int = 0, pos: str = "bottom", style: str | None = None, tail: float | None = None) -> tuple[Path, Path, list[float]]:
    """Return (narration.mp3, captions.ass, per-line durations in seconds). style: an opt-in delivery from VOICE_STYLES, else the default voice. tail: seconds of the
    service's silence kept after each line's last word (a video's own `voice_tail`); None keeps the style's tail, or the whole file when the voice has no style."""
    work.mkdir(parents=True, exist_ok=True)
    all_words, durations, parts = [], [], []
    offset = 0.0
    if tail is None:
        tail = (VOICE_STYLES.get(style or "") or {}).get("tail")  # only a styled voice, or a video that asks, trims the service's silent tail; the default voice is made exactly as before
    for i, text in enumerate(lines):
        mp3 = work / f"line{i:02d}.mp3"
        pros = line_prosody(style, text, i, len(lines))
        said = spoken(text)
        words = asyncio.run(_synth_line(said, mp3) if pros is None else _synth_line(said, mp3, pros))
        d = line_length(_duration(mp3), words, pause, tail)  # small breath between lines
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
    audiofinish.finish(narration, lufs=FINISH_LUFS)  # a steadier, louder voice (two-pass, gentle compressor); False leaves the file as it was
    words_to_json(all_words, work / "words.json")
    ass = work / "captions.ass"
    ass.write_text(_ass(all_words, motion, pos))
    return narration, ass, durations
