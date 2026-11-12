"""Thumbnails that are not all the same.

30 Oct 2026: every documentary thumbnail on the channel shared one template (a white line over a yellow line at the bottom left on a dark fade), so none stood out from the
next. Research record: docs/studio/THUMBNAIL_CURIOSITY_RESEARCH_2026-10-30.md. Curiosity needs one concrete anchor and one gap the viewer can almost close (a number without its
story, a choice between two answers, a detail marked with a ring), so each composition below carries a device, and the chooser gives a video compositions that differ from the
channel's recent thumbnails. The type family and a colour family per kind of video stay as the brand; everything else varies.

Pillow only, fonts already in static/fonts. A composition is rendered in two steps (`base` without words, then the words) so the checks can measure text against what is behind it.
Nothing is invented: the words, the number and the labels all come from the hook the caller gives."""
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
SAFE = (int(W * 0.84), int(H * 0.84), W, H)  # the corner where YouTube writes the video's length
FONTS = Path(__file__).parent / "static" / "fonts"
CONDENSED, BLACK = FONTS / "NotoSans-ExtraCondensedBlack.ttf", FONTS / "NotoSans-Black.ttf"
WHITE, INK = (255, 255, 255), (10, 10, 12)
FAMILIES = {  # (accent, second colour) per kind of video: the colour family that stays the same from video to video of a kind
    "default": ((255, 200, 40), WHITE), "mystery": ((80, 205, 235), (255, 200, 40)), "legend": ((255, 150, 50), (255, 225, 140)),
    "event": ((255, 90, 70), (255, 225, 140)), "person": ((245, 235, 210), (255, 190, 60)), "place": ((120, 225, 170), (255, 210, 90)),
}
STOP = {"the", "of", "a", "an", "and", "in", "on", "to", "or", "is", "was", "for", "at", "it", "he", "she", "they", "what", "who", "why", "how", "did", "do", "does"}
NEW = ("foreground", "bignumber", "split", "pointer", "redacted", "corner")
CLASSIC = ("classic_a", "classic_b", "classic_c")


def family(kind: str | None) -> tuple:
    return FAMILIES.get(kind or "default", FAMILIES["default"])


@dataclass
class Thumb:
    image: Image.Image
    archetype: str
    boxes: list
    plan: list
    base: Image.Image | None = None  # the picture before any words, so the checks can measure what the words sit on
    spec: dict = field(default_factory=dict)


# ---- drawing helpers ----
def _font(size: int, path: Path = CONDENSED) -> ImageFont.FreeTypeFont:
    for f in (path, BLACK):
        if Path(f).exists():
            return ImageFont.truetype(str(f), size)
    return ImageFont.load_default(size)


def _cover(path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((max(W, round(im.width * s)), max(H, round(im.height * s))), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def _ramp(axis: int, a0: float, a1: float, p0: float = 0.0, p1: float = 1.0) -> Image.Image:
    """An 'L' mask over the whole frame: a0 until p0, then a straight ramp to a1 at p1, along x (axis 0) or y (axis 1)."""
    n = (W, H)[axis]
    line = Image.new("L", (n, 1) if axis == 0 else (1, n))
    for i in range(n):
        t = i / max(1, n - 1)
        v = a0 if t <= p0 else a1 if t >= p1 else a0 + (a1 - a0) * (t - p0) / (p1 - p0)
        line.putpixel((i, 0) if axis == 0 else (0, i), int(v))
    return line.resize((W, H))


def _darken(im: Image.Image, mask: Image.Image) -> Image.Image:
    out = im.copy()
    out.paste(Image.new("RGB", (W, H), (0, 0, 0)), mask=mask)
    return out


def _measure(text: str, font) -> tuple[int, int, int, int]:
    return font.getbbox(text)


def _fit(text: str, max_w: int, max_h: int, path: Path = CONDENSED, start: int = 320) -> ImageFont.FreeTypeFont:
    size = start
    while size > 28:
        f = _font(size, path)
        bb = _measure(text, f)
        if bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
            return f
        size -= 4
    return _font(28, path)


def _words_line(img: Image.Image, tokens: list[str], fills: list, font, x: int, bottom: int, stroke: int | None = None) -> tuple:
    """Draw the tokens left to right on one line whose lowest letter sits at `bottom`; returns the line's box. A soft shadow goes under it."""
    d = ImageDraw.Draw(img)
    sp = font.getlength(" ")
    sw = stroke if stroke is not None else max(3, font.size // 38)
    bb = [_measure(t, font) for t in tokens]
    y = bottom - max(b[3] for b in bb)
    xs, cx = [], x
    for t in tokens:
        xs.append(cx)
        cx += font.getlength(t) + sp
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for t, tx in zip(tokens, xs):
        sd.text((tx + 4, y + 6), t, font=font, fill=(0, 0, 0, 190), stroke_width=sw, stroke_fill=(0, 0, 0, 190))
    img.paste(Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(6))).convert("RGB"))
    d = ImageDraw.Draw(img)
    for t, tx, fill in zip(tokens, xs, fills):
        d.text((tx, y), t, font=font, fill=fill, stroke_width=sw, stroke_fill=INK)
    top = y + min(b[1] for b in bb)
    return (int(x), int(top - sw), int(cx - sp + sw), int(bottom + sw))


def _chip(img: Image.Image, text: str, xy: tuple, fill: tuple, ink=(15, 15, 18), size: int = 62, pad: int = 16) -> tuple:
    """A small rounded label with a solid colour behind dark letters."""
    f = _font(size, BLACK)
    bb = _measure(text, f)
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((xy[0], xy[1], xy[0] + w, xy[1] + h), radius=14, fill=fill)
    d.text((xy[0] + pad - bb[0], xy[1] + pad - bb[1]), text, font=f, fill=ink)
    return (xy[0], xy[1], xy[0] + w, xy[1] + h)


def _last_accent(tokens: list[str], accent) -> list:
    return [WHITE] * (len(tokens) - 1) + [accent] if len(tokens) > 1 else [accent]


def _item(kind: str, role: str, box: tuple, fill=WHITE, text: str = "", backdrop=None) -> dict:
    return {"kind": kind, "role": role, "box": box, "fill": fill, "text": text, "backdrop": backdrop}


# ---- the compositions: each returns the picture with the words on it ----
def _foreground(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    base = _darken(_cover(pics[0]), _ramp(1, 0, 235, 0.5, 1.0))
    img, plan, boxes = base.copy(), [], []
    if spec.get("badge"):
        box = _chip(img, spec["badge"], (44, 36), accent)
        plan.append(_item("badge", "badge", box, (15, 15, 18), spec["badge"], accent)); boxes.append(box)
    tokens = spec["text"].split()
    f = _fit(spec["text"], int(W * 0.82) - 60, int(H * 0.2))
    box = _words_line(img, tokens, _last_accent(tokens, accent), f, 60, H - 44)
    plan.append(_item("text", "line", box, WHITE, spec["text"])); boxes.append(box)
    return Thumb(img, "foreground", boxes, plan, base, spec)


def _bignumber(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    base = _darken(_cover(pics[0]), _ramp(0, 235, 0, 0.0, 0.78))
    img, plan, boxes = base.copy(), [], []
    badge = spec.get("badge")  # says what the figure counts ("THE BONES"), so it cannot be read as being about the picture's subject
    big = _fit(spec["big"], int(W * 0.6), int(H * (0.42 if badge else 0.5)), BLACK)
    if badge:
        box = _chip(img, badge, (44, 36), accent)
        plan.append(_item("badge", "badge", box, (15, 15, 18), badge, accent)); boxes.append(box)
    box_b = _words_line(img, [spec["big"]], [accent], big, 56, int(H * (0.66 if badge else 0.62)), stroke=max(4, big.size // 30))
    plan.append(_item("text", "big", box_b, accent, spec["big"])); boxes.append(box_b)
    if spec.get("caption"):
        cap = _fit(spec["caption"], int(W * 0.6), int(H * 0.15))
        box_c = _words_line(img, spec["caption"].split(), [WHITE] * len(spec["caption"].split()), cap, 60, box_b[3] + 12 + (_measure(spec["caption"], cap)[3] - _measure(spec["caption"], cap)[1]))
        plan.append(_item("text", "caption", box_c, WHITE, spec["caption"])); boxes.append(box_c)
    return Thumb(img, "bignumber", boxes, plan, base, spec)


def _split(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    right, left = _cover(pics[1]), _cover(pics[0])
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (int(W * 0.56), 0), (int(W * 0.44), H), (0, H)], fill=255)
    base = right.copy()
    base.paste(left, mask=mask)
    d = ImageDraw.Draw(base)
    d.line([(int(W * 0.56), 0), (int(W * 0.44), H)], fill=WHITE, width=10)
    img, plan, boxes = base.copy(), [], []
    cx, cy, r = W // 2, H // 2, 58
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent, outline=WHITE, width=6)
    f = _font(86, BLACK)
    bb = _measure(spec.get("center", "?"), f)
    d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), spec.get("center", "?"), font=f, fill=(15, 15, 18))
    for role, label, x in (("left", spec["left"], 40), ("right", spec["right"], None)):
        f = _font(74, BLACK)
        bb = _measure(label, f)
        w = bb[2] - bb[0] + 36
        x0 = x if x is not None else W - 40 - w
        box = _chip(img, label, (x0, 40), (15, 15, 18), ink=WHITE if role == "left" else accent, size=74, pad=18)
        plan.append(_item("badge", role, box, WHITE if role == "left" else accent, label, (15, 15, 18))); boxes.append(box)
    return Thumb(img, "split", boxes, plan, base, spec)


def _pointer(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    px, py = spec["point"]
    base = _darken(_cover(pics[0]), _radial(0, 0, 0.62))
    img, plan, boxes = base.copy(), [], []
    tokens = spec["text"].split()
    f = _fit(spec["text"], int(W * 0.46), int(H * 0.17))
    box = _words_line(img, tokens, _last_accent(tokens, accent), f, 52, 48 + (_measure(spec["text"], f)[3]))
    plan.append(_item("text", "line", box, WHITE, spec["text"])); boxes.append(box)
    cx, cy, r = int(W * px), int(H * py), int(H * 0.125)
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5), outline=INK, width=5)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=accent, width=9)
    ang = math.atan2(cy - (box[3] + 10), cx - (box[0] + 80))
    sx, sy = box[0] + 80, box[3] + 10
    ex, ey = cx - math.cos(ang) * (r + 8), cy - math.sin(ang) * (r + 8)
    d.line([(sx, sy), (ex, ey)], fill=accent, width=9)
    for side in (-0.5, 0.5):
        d.line([(ex, ey), (ex - 34 * math.cos(ang + side), ey - 34 * math.sin(ang + side))], fill=accent, width=9)
    plan.append(_item("shape", "ring", (cx - r, cy - r, cx + r, cy + r), accent)); boxes.append((cx - r, cy - r, cx + r, cy + r))
    return Thumb(img, "pointer", boxes, plan, base, spec)


def _radial(cx: float, cy: float, reach: float, strength: int = 215) -> Image.Image:
    """A dark patch centred at (cx, cy) as a fraction of the frame, fading to nothing at `reach` times the width."""
    m = Image.new("L", (W // 8, H // 8))
    px = m.load()
    for y in range(m.height):
        for x in range(m.width):
            dd = math.hypot(x / m.width - cx, (y / m.height - cy) * H / W) / reach
            px[x, y] = int(strength * max(0.0, 1 - dd) ** 1.2)
    return m.resize((W, H), Image.BILINEAR)


def _redacted(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    base = _darken(_cover(pics[0]), _ramp(1, 215, 0, 0.0, 0.5))
    img, plan, boxes = base.copy(), [], []
    words, hide = spec["text"].split(), spec["hide"].upper()
    f = _fit(spec["text"], int(W * 0.86), int(H * 0.2))
    sp = f.getlength(" ")
    total = sum(f.getlength(w) for w in words) + sp * (len(words) - 1)
    x, bottom = (W - total) / 2, int(H * 0.27)
    d = ImageDraw.Draw(img)
    for w in words:
        wl = f.getlength(w)
        bb = _measure(w, f)
        if w.upper().strip("?!.,") == hide.strip("?!.,"):
            top, bot = bottom - (bb[3] - bb[1]) - 6, bottom + 6
            box = (int(x - 8), int(top), int(x + wl + 8), int(bot))
            d.rectangle(box, fill=(0, 0, 0), outline=WHITE, width=4)
            q = _font(int((bot - top) * 0.8), BLACK)
            qb = _measure("?", q)
            d.text(((box[0] + box[2]) / 2 - (qb[0] + qb[2]) / 2, (top + bot) / 2 - (qb[1] + qb[3]) / 2), "?", font=q, fill=accent)
            plan.append(_item("shape", "bar", box, accent, "", (0, 0, 0))); boxes.append(box)
        else:
            box = _words_line(img, [w], [WHITE], f, int(x), bottom)
            plan.append(_item("text", "word", box, WHITE, w)); boxes.append(box)
            d = ImageDraw.Draw(img)
        x += wl + sp
    return Thumb(img, "redacted", boxes, plan, base, spec)


def _corner(pics, spec) -> Thumb:
    accent = spec.get("accent", family(None)[0])
    base = _cover(pics[0])
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((26, 26, int(W * 0.56), int(H * 0.52)), radius=30, fill=(0, 0, 0, 165))
    base = Image.alpha_composite(base.convert("RGBA"), panel).convert("RGB")
    img, plan, boxes = base.copy(), [], []
    y = 54
    if spec.get("badge"):
        box = _chip(img, spec["badge"], (54, y), accent)
        plan.append(_item("badge", "badge", box, (15, 15, 18), spec["badge"], accent)); boxes.append(box)
        y = box[3] + 18
    words = spec["text"].split()
    half = math.ceil(len(words) / 2)
    lines = [words[:half], words[half:]] if len(words) > 2 else [words]
    lines = [l for l in lines if l]
    maxw = int(W * 0.56) - 54 - 28
    size_font = min((_fit(" ".join(l), maxw, int(H * 0.15)) for l in lines), key=lambda f: f.size)
    for n, l in enumerate(lines):
        bb = _measure(" ".join(l), size_font)
        bottom = y + (bb[3] - bb[1]) + 8
        box = _words_line(img, l, _last_accent(l, accent) if n == len(lines) - 1 else [WHITE] * len(l), size_font, 54, bottom)
        plan.append(_item("text", "line", box, WHITE, " ".join(l))); boxes.append(box)
        y = box[3] + 10
    return Thumb(img, "corner", boxes, plan, base, spec)


def _classic_boxes(name: str, text: str) -> list[tuple]:
    """Where the old layouts really put each line of their words (the same fitting code): one box per line, so a long top line is not mistaken for a long bottom line."""
    import thumbnail

    d = ImageDraw.Draw(Image.new("RGB", (W, H)))
    lines = thumbnail._split(text)
    region, anchor = {"classic_a": ((60, 120, W - 60, H - 50), "left"), "classic_b": ((80, 80, W - 80, H - 80), "center"),
                      "classic_c": ((56, 70, int(W * 0.46) + 40, H - 70), "center")}[name]
    f, size = thumbnail._fit(d, lines, region[2] - region[0], region[3] - region[1])
    lh = int(size * 0.98)
    top = region[3] - lh * len(lines) if anchor == "left" else region[1] + (region[3] - region[1] - lh * len(lines)) // 2
    boxes = []
    for i, l in enumerate(lines):
        w = d.textlength(l, font=f)
        x0 = region[0] if anchor == "left" else region[0] + (region[2] - region[0] - w) / 2
        boxes.append((int(x0), int(top + i * lh), int(x0 + w), int(top + (i + 1) * lh)))
    return boxes


def _classic(name):
    def make(pics, spec) -> Thumb:
        import thumbnail

        layout = {"classic_a": thumbnail._layout_a, "classic_b": thumbnail._layout_b, "classic_c": thumbnail._layout_c}[name]
        img = layout(pics[0], spec["text"]).convert("RGB")
        boxes = _classic_boxes(name, spec["text"])
        return Thumb(img, name, boxes, [_item("text", "classic", b, WHITE, spec["text"]) for b in boxes], None, spec)
    return make


ARCHETYPES = {"foreground": _foreground, "bignumber": _bignumber, "split": _split, "pointer": _pointer, "redacted": _redacted, "corner": _corner,
              "classic_a": _classic("classic_a"), "classic_b": _classic("classic_b"), "classic_c": _classic("classic_c")}


def render(archetype: str, pictures: list, spec: dict) -> Thumb:
    return ARCHETYPES[archetype](pictures, spec)


# ---- checks ----
def _lum(c) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def contrast_ratio(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _overlap(box, region) -> bool:
    return box[0] < region[2] and box[2] > region[0] and box[1] < region[3] and box[3] > region[1]


def _content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 2 and w not in STOP}


def check(t: Thumb, hook: str, title: str) -> list[dict]:
    """The rows every candidate must pass: 2 to 5 words, not the title's own words, nothing in the video-length corner, and words that stand out from what is behind them
    (a contrast of 3 to 1 or more, the level WCAG asks of large text)."""
    n = len(hook.split())
    mine, theirs = _content_words(hook), _content_words(title)
    share = len(mine & theirs) / len(mine) if mine else 0.0
    rows = [{"name": "hook_words", "ok": 2 <= n <= 5, "detail": f"{n} words (2 to 5)"},
            {"name": "not_title", "ok": share < 0.5, "detail": f"{share:.0%} of the words are the title's own (under 50%)"},
            {"name": "safe_corner", "ok": not any(_overlap(b, SAFE) for b in t.boxes), "detail": "the video-length corner is clear" if not any(_overlap(b, SAFE) for b in t.boxes) else "words reach the video-length corner"}]
    worst = None
    if t.base is not None:
        px = t.base.convert("RGB")
        for item in t.plan:
            if item["kind"] not in ("text", "badge") or item["fill"] is None:
                continue
            x0, y0, x1, y1 = (max(0, item["box"][0]), max(0, item["box"][1]), min(W, item["box"][2]), min(H, item["box"][3]))
            if x1 <= x0 or y1 <= y0:
                continue
            behind = item["backdrop"] or tuple(int(v) for v in _mean(px.crop((x0, y0, x1, y1))))
            r = contrast_ratio(item["fill"], behind)
            worst = r if worst is None else min(worst, r)
    rows.append({"name": "contrast", "ok": worst is None or worst >= 3.0, "detail": "not measured" if worst is None else f"words against their background {worst:.1f} to 1 (3 or more)"})
    return rows


def _mean(im: Image.Image) -> tuple:
    small = im.resize((1, 1), Image.BOX)
    return small.getpixel((0, 0))


# ---- how different from the others ----
def signature(t: Thumb) -> dict:
    grid = list(t.image.convert("L").resize((8, 4), Image.BOX).tobytes())
    xs = [b for b in t.boxes] or [(0, 0, W, H)]
    cx = sum((b[0] + b[2]) / 2 for b in xs) / len(xs) / W
    cy = sum((b[1] + b[3]) / 2 for b in xs) / len(xs) / H
    return {"arch": t.archetype, "grid": [v / 255 for v in grid], "text": (cx, cy)}


def signature_of_image(img: Image.Image, archetype: str = "classic_a") -> dict:
    """A signature for a thumbnail made before this module existed (its words were bottom left)."""
    return {"arch": archetype, "grid": [v / 255 for v in img.convert("L").resize((8, 4), Image.BOX).tobytes()], "text": (0.4, 0.75)}


def distance(a: dict, b: dict) -> float:
    """0 for the same composition on the same picture, near 1 for a different composition with the words somewhere else on a different picture."""
    grid = sum(abs(x - y) for x, y in zip(a["grid"], b["grid"])) / len(a["grid"])
    pos = math.hypot(a["text"][0] - b["text"][0], a["text"][1] - b["text"][1])
    return min(1.0, 0.45 * (a["arch"] != b["arch"]) + 0.30 * min(1.0, pos / 0.5) + 0.25 * min(1.0, grid * 2.5))


# ---- choosing ----
def device_for(hook: str) -> str:
    if re.search(r"\d", hook):
        return "number"
    if re.search(r"\b(OR|VS\.?|VERSUS)\b", hook, re.I):
        return "choice"
    if hook.rstrip().endswith("?"):
        return "question"
    return "plain"


PREFER = {"number": ("bignumber", "foreground", "corner", "classic_a", "classic_b", "classic_c", "split"),
          "choice": ("split", "foreground", "corner", "classic_b", "classic_a", "classic_c"),
          "question": ("corner", "foreground", "classic_b", "classic_a", "classic_c", "split"),
          "plain": ("foreground", "corner", "classic_a", "classic_c", "classic_b", "split")}


def choose(hook: str, recent: list[str], pictures: int = 1, n: int = 3, also_avoid=()) -> list[str]:
    """Up to n different compositions that fit the hook's device, skipping the channel's two most recent ones (and any in also_avoid) when there is any other choice. The same input
    always gives the same answer."""
    pref = [a for a in PREFER[device_for(hook)] if not (a == "split" and pictures < 2)]
    avoid = set(recent[:2]) | set(also_avoid)
    return ([a for a in pref if a not in avoid] + [a for a in pref if a in avoid])[:n]


def recent_archetypes(out_dir: Path, exclude: Path | None = None, n: int = 6) -> list[str]:
    """The compositions of the channel's most recent documentary thumbnails, newest first. A thumbnail made before this module existed counts as the old template (classic_a)."""
    rows = []
    for f in Path(out_dir).glob("*/meta.json"):
        if exclude is not None and f.parent.resolve() == Path(exclude).resolve():
            continue
        try:
            m = json.loads(f.read_text())
            if m.get("format") != "doc":
                continue
            style = m.get("thumb_style") or ("classic_a" if m.get("thumbnail") else None)
            if style:
                rows.append((f.stat().st_mtime, style))
        except (OSError, ValueError):
            continue
    return [s for _, s in sorted(rows, reverse=True)][:n]


def spec_for(archetype: str, hook: str, kind: str | None, pictures: list, badge: str | None = None) -> dict:
    """What a composition needs, built only from the hook the caller gave."""
    accent, _ = family(kind)
    spec = {"text": hook, "accent": accent, "badge": badge}
    if archetype == "bignumber":
        m = re.search(r"\d[\d,]*(?:\s?(?:BC|BCE|AD|CE))?", hook)
        spec["big"] = m.group(0).strip()
        spec["caption"] = re.sub(r"\s+", " ", hook.replace(m.group(0), " ")).strip(" .,-")
    elif archetype == "split":
        parts = re.split(r"\s+(?:OR|VS\.?|VERSUS)\s+", hook, maxsplit=1, flags=re.I)
        spec["left"], spec["right"] = parts[0].strip(" ?!."), parts[1].strip(" ?!.")
    return spec


def variants(folder: Path, meta: dict, pictures: list, hook: str, kind: str | None = None, recent: list[str] | None = None, title: str | None = None,
             names: tuple = ("art-a.jpg", "art-b.jpg", "art-c.jpg"), badge: str | None = None, hooks: list[str] | None = None) -> list[dict]:
    """Up to three candidates for a video, each a different composition with its own words when `hooks` gives several. A candidate that fails a check (words that repeat the title,
    too few or too many, words in the video-length corner, words that do not stand out) is dropped and the next composition or hook takes its place. Writes folder/thumbs/<name> and
    folder/thumbs/variants.json; returns [{file, archetype, hook, checks, signature}]."""
    title = title or meta.get("title", "")
    queue = list(dict.fromkeys(hooks or [hook]))
    out, chosen = [], []
    out_dir = Path(folder) / "thumbs"
    out_dir.mkdir(exist_ok=True)

    def try_hook(h: str) -> bool:
        for arch in choose(h, recent or [], len(pictures), n=len(ARCHETYPES), also_avoid=chosen):
            if arch in chosen:  # one composition once per video: copies of a layout make Test & Compare run longer and give the owner nothing to choose between
                continue
            try:
                t = render(arch, pictures[:2] if arch == "split" else pictures[:1], spec_for(arch, h, kind or meta.get("kind"), pictures, badge))
            except Exception:
                continue
            rows = check(t, h, title)
            if not all(r["ok"] for r in rows):
                continue
            path = out_dir / names[len(out)]
            q = 90
            t.image.save(path, quality=q, optimize=True)
            while path.stat().st_size > 1_900_000 and q > 60:
                q -= 8
                t.image.save(path, quality=q, optimize=True)
            out.append({"file": f"thumbs/{path.name}", "archetype": arch, "hook": h, "checks": {r["name"]: r["ok"] for r in rows}, "signature": signature(t)})
            chosen.append(arch)
            return True
        return False

    passed = []
    for h in queue:
        if len(out) >= len(names):
            break
        if try_hook(h):
            passed.append(h)
    while passed and len(out) < len(names):  # fewer hooks than candidates: the hooks that worked are used again in other compositions
        before = len(out)
        for h in passed:
            if len(out) < len(names):
                try_hook(h)
        if len(out) == before:
            break
    (out_dir / "variants.json").write_text(json.dumps(out, indent=1))
    return out
