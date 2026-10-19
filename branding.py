"""Channel look: profile picture, banner and description, drawn from the channel name (one soft-moon accent on night blue)."""
import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

SAFE = (507, 508, 2053, 931)  # the part of a 2560x1440 banner that every device shows
BG_TOP, BG_BOTTOM = (11, 18, 32), (18, 29, 50)
MOON, MUTED = (240, 234, 220), (154, 166, 191)
FONTS = Path(__file__).parent / "static" / "fonts"  # Noto Sans (SIL Open Font License), shipped with the project
BOLD, REGULAR = str(FONTS / "NotoSans-ExtraBold.ttf"), str(FONTS / "NotoSans-Regular.ttf")


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default(size)


def _gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    return col.resize((w, h))


def _stars(im: Image.Image, seed: str, count: int, avoid: tuple[int, int, int, int] | None = None) -> None:
    rnd = random.Random(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16))
    d = ImageDraw.Draw(im)
    w, h = im.size
    for _ in range(count):
        x, y, r = rnd.randrange(w), rnd.randrange(h), rnd.choice([2, 2, 3, 4])
        glow = rnd.uniform(0.45, 0.9)
        if avoid and avoid[0] - 40 <= x <= avoid[2] + 40 and avoid[1] - 40 <= y <= avoid[3] + 40:
            continue
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(c * glow) for c in MOON))


def _crescent(size: int) -> Image.Image:
    """A moon as an RGBA tile: full circle minus an offset circle."""
    s = size * 4  # draw large, shrink for smooth edges
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, s - 1, s - 1), fill=255)
    d.ellipse((int(s * 0.26), -int(s * 0.04), int(s * 1.16), int(s * 0.88)), fill=0)
    tile = Image.new("RGBA", (s, s), MOON + (0,))
    tile.putalpha(mask)
    return tile.resize((size, size), Image.LANCZOS)


def avatar(name: str) -> Image.Image:
    im = _gradient((800, 800))
    _stars(im, name, 26, avoid=(190, 190, 610, 610))
    moon = _crescent(420)
    im.paste(moon, (190, 190), moon)
    return im


def _fit_lines(text: str, path: str, max_w: int, start: int, min_size: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    words = text.split()
    for size in range(start, min_size - 1, -4):
        f = _font(path, size)
        if f.getlength(text) <= max_w:
            return f, [text]
        if len(words) > 1:
            k = min(range(1, len(words)), key=lambda i: max(f.getlength(" ".join(words[:i])), f.getlength(" ".join(words[i:]))))
            two = [" ".join(words[:k]), " ".join(words[k:])]
            if max(f.getlength(l) for l in two) <= max_w:
                return f, two
    return f, [" ".join(words[: len(words) // 2]), " ".join(words[len(words) // 2:])] if len(words) > 1 else [text]


def _layout(name: str, tagline: str):
    x0, y0, x1, y1 = SAFE
    moon, gap = 300, 56
    avail = (x1 - x0) - moon - gap
    nf, nlines = _fit_lines(name, BOLD, avail, 120, 44)
    tf, tlines = _fit_lines(tagline, REGULAR, avail, 56, 30)
    nh, th = round(nf.size * 1.15) * len(nlines), round(tf.size * 1.3) * len(tlines)
    block = nh + 24 + th
    top = (y0 + y1) // 2 - block // 2
    tx = x0 + moon + gap
    boxes = {
        "moon": (x0, (y0 + y1) // 2 - moon // 2, x0 + moon, (y0 + y1) // 2 + moon // 2),
        "name": (tx, top, tx + round(max(nf.getlength(l) for l in nlines)), top + nh),
        "tagline": (tx, top + nh + 24, tx + round(max(tf.getlength(l) for l in tlines)), top + nh + 24 + th),
    }
    return boxes, (nf, nlines), (tf, tlines)


def layout_banner(name: str, tagline: str) -> dict[str, tuple[int, int, int, int]]:
    return _layout(name, tagline)[0]


def banner(name: str, tagline: str) -> Image.Image:
    boxes, (nf, nlines), (tf, tlines) = _layout(name, tagline)
    im = _gradient((2560, 1440))
    _stars(im, name, 120, avoid=SAFE)
    d = ImageDraw.Draw(im)
    mx, my, _, _ = boxes["moon"]
    moon = _crescent(300)
    im.paste(moon, (mx, my), moon)
    for lines, font, key, color, step in ((nlines, nf, "name", MOON, 1.15), (tlines, tf, "tagline", MUTED, 1.3)):
        x, y = boxes[key][0], boxes[key][1]
        for line in lines:
            d.text((x, y), line, font=font, fill=color)
            y += round(font.size * step)
    return im


def channel_description(name: str, tagline: str) -> str:
    niche = config.niche()
    return (f"{tagline}.\n\n{name} tells {niche.get('name', 'legends, mysteries and strange true history').lower()}: old legends, "
            "unsolved mysteries and the surprising true stories behind them, retold slowly in our own words from public-domain "
            "tales and documented history.\n\nNarration is AI-generated. Where history is uncertain, we say so.\n\n"
            "Subscribe for new stories.")


def write_kit(out_dir: Path, name: str, tagline: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"avatar": out_dir / "avatar.png", "banner": out_dir / "banner.png", "description": out_dir / "description.txt"}
    avatar(name).save(paths["avatar"], optimize=True)
    banner(name, tagline).save(paths["banner"], optimize=True)
    paths["description"].write_text(channel_description(name, tagline))
    return paths
