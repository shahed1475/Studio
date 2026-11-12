"""A film-style colour grade for the studio's own (AI-drawn) pictures (1 Nov 2026, owner: "I saw over colour and it looks like AI generation; make it cinematic, a Hollywood colour grade").
What makes a picture look AI-made is mostly over-saturated colour, flat digital contrast, clean plastic noise-free skin and an even light. This grade, in plain steps:
  1. saturation down about 18 percent, protecting colours that are already muted;
  2. a gentle S-curve on brightness with a soft roll-off above 0.82 (highlights do not clip to a hard digital white);
  3. split-toning: shadows pushed toward teal, highlights toward warm amber (the classic cinema look), small amounts;
  4. a subtle vignette (about 14 percent darker in the corners);
  5. fine film grain, stronger in the mid-tones, seeded from the picture so the same picture always gets the same grain.
`strength` (0 to 1) scales every step. Pure numpy and Pillow, no model, no cost. `graded(path)` keeps the result in cache/cc (where animate.own_picture lets it have camera motion)
and never changes the source file. It does not change what a picture shows: it only changes how it looks."""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

import config

VERSION = 2
SAT, CONTRAST, TEAL, AMBER, VIGNETTE, GRAIN = 0.82, 0.16, 0.045, 0.05, 0.14, 0.011


def cinematic(img: Image.Image, strength: float = 1.0) -> Image.Image:
    s = float(strength)
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    src = a.copy()
    y = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    a = y + (a - y) * (1 - (1 - SAT) * s)  # 1. desaturate toward the brightness
    y = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    curve = y + CONTRAST * s * (y - 0.5) * (1 - np.abs(2 * y - 1) ** 2)  # 2. S-curve: lifts contrast in the middle, leaves the ends alone
    roll = np.where(curve > 0.82, 0.82 + (curve - 0.82) * 0.55, curve)  # soft highlight roll-off
    a = a * (roll / np.maximum(y, 1e-4))
    y2 = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]
    y0 = float((0.2126 * src[..., 0] + 0.7152 * src[..., 1] + 0.0722 * src[..., 2]).mean())
    gain = 1 + s * (np.clip(y0 * 1.02 / max(float(y2.mean()), 1e-4), 0.9, 1.35) - 1)  # keep the picture's average brightness (the curve and the vignette would darken it)
    a, y2 = a * gain, y2 * gain
    shadow, light = np.clip(1 - 2 * y2, 0, 1), np.clip(2 * y2 - 1, 0, 1)  # 3. split tone
    a = a + s * (shadow * np.array([-TEAL, TEAL * 0.35, TEAL]) + light * np.array([AMBER, AMBER * 0.35, -AMBER]))
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    a = a * (1 - VIGNETTE * s * np.clip(d, 0, 1) ** 2.2)[..., None]  # 4. vignette
    seed = int(hashlib.sha256(np.asarray(img.convert("RGB").resize((16, 16))).tobytes()).hexdigest()[:8], 16)
    g = np.random.default_rng(seed).normal(0, GRAIN * s, (h, w, 1)).astype(np.float32)
    a = a + g * (0.6 + 0.8 * np.clip(1 - np.abs(2 * y2 - 1), 0, 1))  # 5. grain
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def graded(src, strength: float = 1.0) -> Path:
    """The graded copy of a picture in cache/cc (made once)."""
    src = Path(src)
    key = hashlib.sha256(src.read_bytes() + repr((VERSION, round(float(strength), 3))).encode()).hexdigest()[:16]
    out = Path(config.CACHE) / "cc" / f"grade-{key}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        part = Path(str(out) + ".part.jpg")
        cinematic(Image.open(src), strength).save(part, quality=95, subsampling=0)
        part.rename(out)
    return out
