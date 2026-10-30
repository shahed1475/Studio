"""Draws the Gloamtale identity (30 Oct 2026): one mark (a gold G that is also a setting sun, its bar the horizon over a dune), profile picture, banner, watermark, lockup, SVG.
Only Pillow and the Cinzel font (SIL OFL) in fonts/. Run: python branding/gloamtale/make_brand.py"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
FONT = HERE / "fonts" / "Cinzel-Variable.ttf"
P = {"night": "#0b0f2a", "indigo": "#1b2150", "plum": "#3b2350", "dune_far": "#4a2a4a", "dune_mid": "#2a1a3a", "dune_near": "#140e2a", "ember": "#d7743a", "gold": "#f2c46d", "cream": "#fff1d4"}
RGB = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def font(size, weight=700):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_axes([weight])
    return f


def gradient(w, h, stops):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                d.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(RGB(c0), RGB(c1))))
                break
    return img


def mark(size, ring=P["gold"], far=P["ember"], near=P["plum"]):
    """RGBA mark in a size x size box. Geometry in a 1000 unit box: ring centre (500,470), outer radius 300, stroke 70, gap upper right, bar from the centre to the ring."""
    S = size * 4
    u = S / 1000
    cx, cy, R, t = 500 * u, 470 * u, 300 * u, 70 * u
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = R - t / 2
    d.arc([cx - r - t / 2, cy - r - t / 2, cx + r + t / 2, cy + r + t / 2], start=0, end=315, fill=ring, width=round(t))
    for a in (0, 315):
        x, y = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
        d.ellipse([x - t / 2, y - t / 2, x + t / 2, y + t / 2], fill=ring)
    d.rectangle([cx, cy - t / 2, cx + r, cy + t / 2], fill=ring)
    d.ellipse([cx - t / 2, cy - t / 2, cx + t / 2, cy + t / 2], fill=ring)
    inner = Image.new("L", (S, S), 0)
    ImageDraw.Draw(inner).ellipse([cx - (R - t), cy - (R - t), cx + (R - t), cy + (R - t)], fill=255)
    for col, amp, ph, lift in ((far, 0.16, 0.5, 0.85), (near, 0.12, 2.4, 1.55)):
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        pts = [(x, cy + t * lift + amp * R * math.sin((x - (cx - R)) / (2 * R) * math.pi * 1.6 + ph)) for x in range(int(cx - R), int(cx + R) + 1, 4)]
        ld.polygon(pts + [(cx + R, cy + R + t), (cx - R, cy + R + t)], fill=col)
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (S, S), 0), inner))
        img.alpha_composite(layer)
    return img.resize((size, size), Image.LANCZOS)


def stars(d, w, h, n, seed, avoid=None, ymax=0.55, big=4):
    rnd = random.Random(seed)
    for _ in range(n):
        x, y, s = rnd.randint(0, w), rnd.randint(0, int(h * ymax)), rnd.choice([2, 2, 3, big])
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        d.ellipse([x - s / 2, y - s / 2, x + s / 2, y + s / 2], fill=P["cream"])


def spaced(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track
    return x - track


def spaced_width(d, text, f, track):
    return sum(d.textlength(c, font=f) for c in text) + track * (len(text) - 1)


def avatar(out):
    S = 800
    bg = gradient(S, S, [(0, P["night"]), (0.55, P["indigo"]), (0.85, P["plum"]), (1, "#5a2c4a")]).convert("RGBA")
    d = ImageDraw.Draw(bg)
    stars(d, S, S, 12, 7, avoid=(120, 110, 680, 640), ymax=0.30, big=4)
    bg.alpha_composite(mark(690), (55, 60))
    bg.convert("RGB").save(out, quality=95)


def banner(out):
    W, H = 2560, 1440
    img = gradient(W, H, [(0, "#0b0f2a"), (0.45, P["indigo"]), (0.68, P["plum"]), (0.80, "#b5573a"), (0.86, P["ember"]), (1, "#7a3b3a")]).convert("RGBA")
    d = ImageDraw.Draw(img)
    safe = (662, 551, 1897, 889)
    stars(d, W, H, 120, 3, avoid=(safe[0] - 60, safe[1] - 60, safe[2] + 60, safe[3] + 60))
    for col, base, amp, f1, f2, ph in ((P["dune_far"], 1090, 70, 0.0021, 0.0053, 0.3), (P["dune_mid"], 1190, 85, 0.0017, 0.0041, 2.0), (P["dune_near"], 1300, 70, 0.0014, 0.0033, 4.1)):
        pts = [(x, base + amp * math.sin(x * f1 + ph) + amp * 0.45 * math.sin(x * f2 + ph * 2)) for x in range(0, W + 8, 8)]
        d.polygon(pts + [(W, H), (0, H)], fill=col)
    wm, tag = font(116), font(42, 500)
    track = 12
    word = "GLOAMTALE"
    ww = spaced_width(d, word, wm, track)
    mk = 232
    gap = 46
    total = mk + gap + ww
    x0 = (W - total) / 2
    img.alpha_composite(mark(mk), (round(x0), 720 - mk // 2 - 8))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    tx = x0 + mk + gap
    spaced(gd, (tx, 612), word, wm, (11, 15, 42, 200), track)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    spaced(d, (tx, 612), word, wm, P["cream"], track)
    spaced(d, (tx + 4, 612 + 150), "History & legends told at dusk", tag, P["gold"], 3)
    img.convert("RGB").save(out, quality=95)
    return safe, (x0, total)


def watermark(out):
    m = mark(150)
    shadow = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    shadow.putalpha(m.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(255, v * 2)))
    shadow = Image.composite(Image.new("RGBA", (150, 150), (11, 15, 42, 255)), shadow, shadow.getchannel("A"))
    shadow.putalpha(m.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(200, v)))
    shadow.alpha_composite(m)
    shadow.save(out)


def lockup(out):
    W, H = 1500, 300
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wm = font(150)
    ww = spaced_width(d, "GLOAMTALE", wm, 14)
    img.alpha_composite(mark(260), (0, 20))
    spaced(d, (310, 70), "GLOAMTALE", wm, P["cream"], 14)
    img.crop((0, 0, int(310 + ww + 20), H)).save(out)


def svg(out):
    cx, cy, R, t = 500, 470, 300, 70
    r = R - t / 2
    ex, ey = cx + r * math.cos(math.radians(315)), cy + r * math.sin(math.radians(315))
    out.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" role="img" aria-label="Gloamtale">
<defs><clipPath id="c"><circle cx="{cx}" cy="{cy}" r="{R - t}"/></clipPath></defs>
<g clip-path="url(#c)"><path d="M{cx - R} {cy + t * 0.85} Q{cx - R / 2} {cy - R * 0.1} {cx} {cy + t * 0.85} T{cx + R} {cy + t * 0.85} V{cy + R} H{cx - R}Z" fill="{P['ember']}"/>
<path d="M{cx - R} {cy + t * 1.55} Q{cx - R / 3} {cy + R * 0.12} {cx + R / 5} {cy + t * 1.55} T{cx + R} {cy + t * 1.6} V{cy + R} H{cx - R}Z" fill="{P['plum']}"/></g>
<path d="M{cx + r} {cy} A{r} {r} 0 1 1 {ex:.1f} {ey:.1f}" fill="none" stroke="{P['gold']}" stroke-width="{t}" stroke-linecap="round"/>
<path d="M{cx} {cy} H{cx + r}" stroke="{P['gold']}" stroke-width="{t}" stroke-linecap="round"/></svg>''')


if __name__ == "__main__":
    avatar(HERE / "avatar-800.png")
    safe, meta = banner(HERE / "banner-2560x1440.png")
    watermark(HERE / "watermark-150.png")
    lockup(HERE / "lockup.png")
    mark(1000).save(HERE / "mark-1000.png")
    svg(HERE / "mark.svg")
    (HERE / "brand.json").write_text(json.dumps({"name": "Gloamtale", "handle": "@Gloamtale", "tagline": "History & legends told at dusk", "about_line": "History and legends for the end of the day", "palette": P, "font": "Cinzel (SIL OFL), weights 500 and 700"}, indent=1))
    print("banner safe area", safe, "lockup x0, width", [round(v) for v in meta])
