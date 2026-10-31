"""A number Short drawn entirely by code (31 Oct 2026, owner's order: football Shorts for a new channel, built from sources we may use).

A spec (see examples/numbershort/) holds a title, 5 to 9 narration lines with one picture card each, and the sources that carry the facts. The pictures are drawn here
with Pillow; the voice, word-timed captions and render are the studio's own (tts, render). Nothing third-party goes in: no match footage, no film clip, no download,
no AI picture of a person. A spec with such a key is refused (FORBIDDEN), and a spec without two sources, each with an address and the passage that carries the claim,
is refused too. The result is a held draft: `hold` is true and only the owner releases it."""
import contextlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config
import records

FONTS = Path(__file__).parent / "static" / "fonts"  # Noto Sans (SIL Open Font License), shipped with the project
FONT_FILES = (FONTS / "NotoSans-Black.ttf", FONTS / "NotoSans-ExtraCondensedBlack.ttf")
YEL, WHITE, DIM, RING = (250, 204, 21), (248, 250, 252), (148, 163, 184), (60, 100, 75)
MAX_TEXT = 30       # characters on one card line: cards use big type
MAX_WORDS = 80      # a Short of about 30 s; the studio's own check allows 20 to 180 s
MAX_TITLE = 70      # YouTube cuts a title near 70 characters on a phone
RUN_TO = 0.82       # the counter reaches its number at 82 percent of its line, then holds
FORBIDDEN = ("video", "clip", "clips", "footage", "source_video", "youtube_url", "download", "image", "images", "face", "person")
CARDS = {  # card type -> its required text fields
    "stopwatch": ("value", "label"),
    "versus": ("a", "b", "note", "detail"),
    "name": ("first", "last", "small"),
    "counter": ("to", "label"),
    "record": ("head", "sub", "by", "note"),
    "big": ("number", "unit"),
    "end": ("text", "small"),
}


def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_FILES:
        if f.exists():
            return ImageFont.truetype(str(f), size)
    raise FileNotFoundError("the Noto Sans fonts are missing from static/fonts")


def fit(draw, text: str, size: int, max_w: int):
    """The largest font up to `size` whose text is no wider than max_w (the camera zoom crops the edges a little, so cards keep clear of them)."""
    while size > 40 and draw.textlength(text, font=font(size)) > max_w:
        size -= 4
    return font(size)


# ---- the spec ----
def sources_ok(sources: list) -> bool:
    """At least two sources, each with a title, an https address, the passage that carries the claim and the date it was read (CLAUDE.md A and B)."""
    good = [x for x in sources if str(x.get("url", "")).startswith("https://") and (x.get("passage") or "").strip() and (x.get("title") or "").strip() and x.get("read")]
    return len(good) >= 2


def validate(spec: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings). An error stops the build; a warning is told to the owner."""
    errors, warns = [], []
    for k in spec:
        if k.lower() in FORBIDDEN:
            errors.append(f"'{k}': a number Short takes no third-party footage, picture or download")
    title = spec.get("title") or ""
    if not title or len(title) > MAX_TITLE:
        errors.append(f"the title must be 1 to {MAX_TITLE} characters")
    lines = spec.get("lines") or []
    if not 5 <= len(lines) <= 9:
        errors.append(f"a number Short has 5 to 9 lines, this has {len(lines)}")
    words = sum(len((l.get("text") or "").split()) for l in lines)
    if words > MAX_WORDS:
        errors.append(f"{words} words is too many for one Short (limit {MAX_WORDS})")
    counters = 0
    for i, l in enumerate(lines):
        card = l.get("card") or {}
        kind = card.get("type")
        if not (l.get("text") or "").strip():
            errors.append(f"line {i}: no text")
        if kind not in CARDS:
            errors.append(f"line {i}: unknown card '{kind}'")
            continue
        counters += kind == "counter"
        for f in CARDS[kind]:
            v = card.get(f)
            if v is None or str(v).strip() == "":
                errors.append(f"line {i}: card '{kind}' needs '{f}'")
            elif len(str(v)) > MAX_TEXT:
                errors.append(f"line {i}: '{f}' is longer than {MAX_TEXT} characters")
        if kind == "counter" and not isinstance(card.get("to"), (int, float)):
            errors.append(f"line {i}: the counter's 'to' must be a number")
    if counters > 1:
        errors.append("at most one counter card")
    if not sources_ok(spec.get("sources") or []):
        errors.append("at least two sources, each with title, https address, the passage that carries the claim and the date it was read")
    if lines and not (lines[0].get("text") or "").strip().endswith("?"):
        warns.append("the hook is not a question (the studio's taste is an open who, what, where, why or how question)")
    if lines and "subscribe" not in (lines[-1].get("text") or "").lower():
        warns.append("the last line does not invite a subscribe")
    return errors, warns


# ---- the pictures ----
def base(size=(1080, 1920)) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    top, bot = (4, 40, 22), (20, 83, 45)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    o = ImageDraw.Draw(ov)
    line = (255, 255, 255, 38)
    o.rectangle((90, 200, w - 90, h - 200), outline=line, width=6)
    o.line((90, h // 2, w - 90, h // 2), fill=line, width=6)
    o.ellipse((w // 2 - 220, h // 2 - 220, w // 2 + 220, h // 2 + 220), outline=line, width=6)
    o.rectangle((w // 2 - 300, 200, w // 2 + 300, 470), outline=line, width=6)
    o.rectangle((w // 2 - 300, h - 470, w // 2 + 300, h - 200), outline=line, width=6)
    img.paste(ov, (0, 0), ov)
    return img


def put(d, cx: int, y: int, text: str, size: int, fill=WHITE, max_w: int = 800) -> None:
    d.text((cx, y), text, font=fit(d, text, size, max_w), fill=fill, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))


def ball(d, cx: int, cy: int, r: int) -> None:
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE, outline=(0, 0, 0), width=8)
    pent = [(cx + r * 0.42 * math.cos(math.radians(a)), cy + r * 0.42 * math.sin(math.radians(a))) for a in range(-90, 270, 72)]
    d.polygon(pent, fill=(20, 20, 20))
    for px, py in pent:
        d.line((px, py, cx + (px - cx) * 1.9, cy + (py - cy) * 1.9), fill=(20, 20, 20), width=8)


def ring(d, cx: int, cy: int, r: int, p: float, width: int = 30) -> None:
    d.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=RING, width=width)
    if p > 0:
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * min(p, 1.0), fill=YEL, width=width)


def draw_card(card: dict, size=(1080, 1920), progress: float = 0.0) -> Image.Image:
    """One picture. The lower third stays empty: the captions live there. `progress` (0 to 1) only matters to a counter card."""
    img = base(size)
    d = ImageDraw.Draw(img)
    cx = size[0] // 2
    kind = card["type"]
    if kind == "stopwatch":
        ring(d, cx, 1010, 280, 0.0)
        put(d, cx, 1010, str(card["value"]), 200)
        put(d, cx, 1330, str(card["label"]).upper(), 70, DIM)
    elif kind == "versus":
        put(d, cx, 560, str(card["a"]).upper(), 170)
        put(d, cx, 760, "v", 100, DIM)
        put(d, cx, 950, str(card["b"]).upper(), 130)
        put(d, cx, 1130, str(card["note"]).upper(), 64, YEL)
        put(d, cx, 1215, str(card["detail"]).upper(), 60, DIM)
    elif kind == "name":
        ball(d, cx, 540, 170)
        put(d, cx, 850, str(card["first"]).upper(), 190)
        put(d, cx, 1040, str(card["last"]).upper(), 210, YEL)
        put(d, cx, 1190, str(card["small"]).upper(), 70, DIM)
    elif kind == "counter":
        p = min(max(progress, 0.0), 1.0)
        done = p >= 1.0
        ring(d, cx, 1010, 280, p)
        put(d, cx, 1010, f"{float(card['to']) * p:05.2f}", 200, YEL if done else WHITE)
        put(d, cx, 1330, str(card["label"]).upper(), 56, DIM)
    elif kind == "record":
        d.rounded_rectangle((90, 400, size[0] - 90, 1170), radius=40, outline=YEL, width=10)
        put(d, cx, 560, str(card["head"]).upper(), 150, WHITE, 700)
        put(d, cx, 720, str(card["sub"]).upper(), 100, YEL, 700)
        d.line((220, 820, size[0] - 220, 820), fill=DIM, width=4)
        put(d, cx, 920, str(card["by"]).upper(), 70, WHITE, 700)
        put(d, cx, 1030, str(card["note"]), 60, DIM, 700)
    elif kind == "big":
        put(d, cx, 700, str(card["number"]), 620, YEL, 900)
        put(d, cx, 1130, str(card["unit"]).upper(), 140)
    elif kind == "end":
        ball(d, cx, 500, 140)
        put(d, cx, 790, str(card["text"]).upper(), 160, YEL)
        put(d, cx, 960, str(card["small"]), 60, DIM)
    return img


def counter_frames(card: dict, n: int):
    """n frames of a counter card: the number runs from 0 to its target at RUN_TO of the line, then holds."""
    for k in range(n):
        t = k / max(n - 1, 1)
        yield draw_card(card, progress=min(t / RUN_TO, 1.0))


def counter_clip(card: dict, seconds: float, folder: Path, work: Path) -> Path:
    import render

    frames = work / "counter_frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    n = int(seconds * config.FPS) + 1
    for k, img in enumerate(counter_frames(card, n)):
        img.save(frames / f"f{k:04d}.png")
    out = folder / "anim" / "counter.mp4"  # a clip inside a folder called anim plays once and is not looped or darkened (render.py)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(config.FPS), "-i", str(frames / "f%04d.png"), *render._venc("18", "veryfast"), str(out)], check=True)
    shutil.rmtree(frames, ignore_errors=True)
    return out


# ---- the voice ----
@contextlib.contextmanager
def respelled(say: dict):
    """How a name is SAID (tts.PRONUNCIATION) for the length of one build."""
    import tts

    old = dict(tts.PRONUNCIATION)
    tts.PRONUNCIATION.update(say or {})
    try:
        yield
    finally:
        tts.PRONUNCIATION.clear()
        tts.PRONUNCIATION.update(old)


def restore_spelling(ass_text: str, say: dict) -> str:
    """The burned captions are built from the text the voice was given, so a respelled name shows as its respelling: put the real spelling back (any case)."""
    for real, said in (say or {}).items():
        for form_said, form_real in ((said, real), (said.upper(), real.upper()), (said.lower(), real.lower())):
            ass_text = ass_text.replace(form_said, form_real)
    return ass_text


# ---- the build ----
def slug_of(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]


def build(spec: dict, out_root: Path | None = None, replace: bool = False) -> Path:
    """Voice, pictures, render and a held record for one spec. Returns the folder. Raises ValueError for a spec that breaks the rules above."""
    import editprofile
    import render
    import subtitles
    import tts

    errors, warns = validate(spec)
    if errors:
        raise ValueError("; ".join(errors))
    folder = (out_root or config.OUT) / (spec.get("slug") or slug_of(spec["title"]))
    if folder.exists():
        try:
            mine = records.read(folder).get("built_by") == "numbershort"
        except (OSError, ValueError, records.RecordError):
            mine = False
        if not (replace and mine):
            raise FileExistsError(f"{folder.name} exists" + (" and was not made by this tool" if replace and not mine else " (pass replace=True to rebuild a folder this tool made)"))
        shutil.rmtree(folder)
    work = folder / "work"
    work.mkdir(parents=True)
    lines = [l["text"] for l in spec["lines"]]
    prof = editprofile.load()
    say = spec.get("say") or {}
    with respelled(say):
        narration, ass, durations = tts.narrate(lines, work, editprofile.short_pause(prof), prof["motion"], prof["caption_pos"], style=spec.get("voice_style", "energetic"))
    ass.write_text(restore_spelling(ass.read_text(), say))
    clips = []
    for i, l in enumerate(spec["lines"]):
        if l["card"]["type"] == "counter":
            clips.append(counter_clip(l["card"], durations[i], folder, work))
        else:
            p = folder / f"card{i}.png"
            draw_card(l["card"]).save(p)
            clips.append(p)
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=editprofile.lufs_for({}, prof), shots=True, crossfade=0.0, grain=False)
    words = subtitles.load_words(work / "words.json")
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.with_punctuation(words, lines))
    meta = {
        "title": spec["title"], "format": "short", "kind": spec.get("kind", "number"), "built_by": "numbershort", "voice_style": spec.get("voice_style", "energetic"),
        "hold": True, "hold_reason": "a number Short built by numbershort.py: the owner watches it and releases it", "lines": [{"text": t, "visual": ""} for t in lines],
        "description": (spec.get("description") or "").rstrip() + "\n\nPictures: drawn by code for this video. Voice: synthetic.\n\nSources:\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in spec["sources"]),
        "tags": spec.get("tags", []), "sources": spec["sources"], "credits": ["Pictures drawn by code (original work)"], "limits": spec.get("limits", []),
        "warnings": warns, "durations": [round(x, 2) for x in durations],
    }
    records.create(folder, meta)
    return folder


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python numbershort.py SPEC.json [--check] [--replace]")
        return 2
    spec = json.loads(Path(argv[0]).read_text())
    errors, warns = validate(spec)
    for w in warns:
        print("warn:", w)
    for e in errors:
        print("ERROR:", e)
    if errors or "--check" in argv:
        return 1 if errors else 0
    print("built:", build(spec, replace="--replace" in argv))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
