"""Thumbnail options for a finished documentary: picks the best frames, adds a short hook, writes 3 layouts (1280x720)."""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

import config
import reviewer

W, H = 1280, 720
FONTS = Path(__file__).parent / "static" / "fonts"  # Noto Sans (SIL Open Font License), shipped with the project
FONT = str(FONTS / "NotoSans-ExtraCondensedBlack.ttf")
FONT_FALLBACK = str(FONTS / "NotoSans-Black.ttf")
HIGHLIGHT = (255, 200, 40)  # one accent for every thumbnail
WHITE = (255, 255, 255)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in (FONT, FONT_FALLBACK):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def hook_for(meta: dict) -> str:
    """2 to 4 words that make someone curious; local model first, title words as fallback."""
    try:
        import scriptgen

        out = scriptgen._chat(
            f"Write the text for a YouTube thumbnail about: {meta['title']}.\n"
            "Rules: 2 to 4 words, ALL CAPS, creates curiosity, no clickbait lies, no punctuation except ? or !.\n"
            'Return JSON: {"hook": "..."}'
        )
        hook = re.sub(r"[^A-Za-z0-9?! ']", "", str(out["hook"])).strip().upper()
        if 1 <= len(hook.split()) <= 5:
            return hook
    except Exception:
        pass
    words = re.sub(r"[^A-Za-z0-9 ']", "", meta["title"]).upper().split()
    skip = {"THE", "OF", "A", "AN", "AND", "IN", "ON"}
    return " ".join([w for w in words if w not in skip][:3]) or "UNSOLVED"


def _frames(video: Path, work: Path, n: int = 14) -> list[Path]:
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], text=True))
    work.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(n):
        p = work / f"f{i:02d}.jpg"
        t = dur * (0.04 + 0.9 * i / (n - 1))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(p)], check=True)
        out.append(p)
    return out


def _score(p: Path) -> float:
    """Detail plus contrast; flat or dark frames score low."""
    im = Image.open(p).convert("L").resize((320, 180))
    edges = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).stddev[0]
    return edges + ImageStat.Stat(im).stddev[0] * 0.5


def _best(frames: list[Path], k: int = 3) -> list[Path]:
    ranked = sorted(range(len(frames)), key=lambda i: -_score(frames[i]))
    picked: list[int] = []
    for i in ranked:  # keep them spread out so the 3 options look different
        if all(abs(i - j) >= 3 for j in picked):
            picked.append(i)
        if len(picked) == k:
            break
    for i in ranked:
        if len(picked) == k:
            break
        if i not in picked:
            picked.append(i)
    return [frames[i] for i in picked]


def _gradient(size, direction="bottom", strength=235) -> Image.Image:
    w, h = size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y / h if direction == "bottom" else 1 - y / h
        g.putpixel((0, y), int(strength * max(0, (t - 0.25) / 0.75) ** 1.4))
    return g.resize((w, h))


def _fit(draw, lines, max_w, max_h, start=250):
    size = start
    while size > 40:
        f = _font(size)
        widths = [draw.textlength(l, font=f) for l in lines]
        if max(widths) <= max_w and size * 0.95 * len(lines) <= max_h:
            return f, size
        size -= 6
    return _font(40), 40


def _split(hook: str) -> list[str]:
    words = hook.split()
    if len(words) <= 2:
        return words
    mid = (len(words) + 1) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def _text(img: Image.Image, lines, box, anchor="left", highlight_last=True) -> None:
    """Text with a soft shadow; the last line is in the accent color."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f, size = _fit(d, lines, x1 - x0, y1 - y0)
    lh = int(size * 0.98)
    top = y1 - lh * len(lines) if anchor == "left" else y0 + (y1 - y0 - lh * len(lines)) // 2
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        x = x0 if anchor == "left" else x0 + (x1 - x0 - d.textlength(line, font=f)) // 2
        sd.text((x + 5, top + i * lh + 7), line, font=f, fill=(0, 0, 0, 200))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x = x0 if anchor == "left" else x0 + (x1 - x0 - d.textlength(line, font=f)) // 2
        color = HIGHLIGHT if (highlight_last and i == len(lines) - 1 and len(lines) > 1) else WHITE
        d.text((x, top + i * lh), line, font=f, fill=color, stroke_width=max(3, size // 40), stroke_fill=(10, 10, 12))


def _layout_a(frame: Path, hook: str) -> Image.Image:
    """Full image, hook bottom left."""
    im = Image.open(frame).convert("RGBA")
    im.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (W, H), (8, 8, 10)).split(), _gradient((W, H)))))
    _text(im, _split(hook), (60, 120, W - 60, H - 50))
    return im


def _layout_b(frame: Path, hook: str) -> Image.Image:
    """Vignette, hook centred, slightly desaturated image behind it."""
    im = Image.open(frame).convert("RGB")
    im = Image.blend(im, im.convert("L").convert("RGB"), 0.25).convert("RGBA")
    dark = Image.new("RGBA", (W, H), (6, 6, 8, 120))
    im.alpha_composite(dark)
    vign = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vign).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(120))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(vign.point(lambda v: 255 - v))
    im.alpha_composite(black)
    _text(im, _split(hook), (80, 80, W - 80, H - 80), anchor="center")
    return im


def _layout_c(frame: Path, hook: str) -> Image.Image:
    """Dark text panel on the left, image on the right."""
    base = Image.new("RGBA", (W, H), (14, 15, 18, 255))
    pic = Image.open(frame).convert("RGBA")
    cut = int(W * 0.46)
    base.alpha_composite(pic.crop((cut, 0, W, H)), (cut, 0))
    fade = Image.new("L", (160, H))
    ImageDraw.Draw(fade).rectangle((0, 0, 160, H), fill=0)
    for x in range(160):
        ImageDraw.Draw(fade).line((x, 0, x, H), fill=int(255 * (1 - x / 160)))
    edge = Image.new("RGBA", (160, H), (14, 15, 18, 255))
    edge.putalpha(fade)
    base.alpha_composite(edge, (cut, 0))
    ImageDraw.Draw(base).rectangle((0, H - 14, int(W * 0.46), H), fill=HIGHLIGHT)
    _text(base, _split(hook), (56, 70, cut + 40, H - 70), anchor="center")
    return base


def make(folder: Path, hook: str | None = None) -> list[str]:
    meta = json.loads((folder / "meta.json").read_text())
    if not (folder / "video.mp4").exists():
        raise SystemExit(f"{folder.name}: no video.mp4")
    hook = (hook or meta.get("thumb_hook") or hook_for(meta)).strip().upper()
    work = folder / "work_thumbs"
    best = _best(_frames(folder / "video.mp4", work))
    out = folder / "thumbs"
    out.mkdir(exist_ok=True)
    names = []
    for i, (layout, frame) in enumerate(zip((_layout_a, _layout_b, _layout_c), best), 1):
        img = layout(frame, hook).convert("RGB")
        path = out / f"thumb-{i}.jpg"
        q = 90
        img.save(path, quality=q, optimize=True)
        while path.stat().st_size > 1_900_000 and q > 60:  # YouTube limit is 2 MB
            q -= 8
            img.save(path, quality=q, optimize=True)
        names.append(f"thumbs/{path.name}")
    for p in work.glob("*"):
        p.unlink()
    work.rmdir()
    meta["thumb_hook"] = hook
    meta["thumbnails"] = names
    meta["thumbnail"] = names[0]
    reviewer.invalidate(meta)
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"hook: {hook}\n" + "\n".join(names))
    return names
