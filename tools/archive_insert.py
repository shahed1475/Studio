"""A real archive scan as a 16:9 insert shot for a documentary (1 Nov 2026).
The scan sits at the centre on a darkened, blurred copy of itself (so a portrait page fills a wide frame), with a soft shadow and the cinematic grade at half strength.
It is saved as cache/archive/insert-<name>.jpg, NOT in cache/cc: animate.own_picture is false for it, so the studio gives it only a plain camera move, never depth motion (a real
picture must not be bent). The source file is never changed. Licence of the scans used is recorded in the spec's credits (Beinecke MS 408 pages are public domain on Wikimedia Commons)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import config
import grade

SIZE = (1920, 1080)


def compose(src, name: str) -> Path:
    out = Path(config.CACHE) / "archive" / f"insert-{name}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    im = Image.open(src).convert("RGB")
    w, h = SIZE
    back = im.copy()
    scale = max(w / back.width, h / back.height)
    back = back.resize((round(back.width * scale), round(back.height * scale)), Image.LANCZOS)
    back = back.crop(((back.width - w) // 2, (back.height - h) // 2, (back.width - w) // 2 + w, (back.height - h) // 2 + h)).filter(ImageFilter.GaussianBlur(38))
    back = Image.fromarray((np.asarray(back, dtype=np.float32) * 0.38).astype(np.uint8))
    fit = min((w - 160) / im.width, (h - 100) / im.height)
    page = im.resize((round(im.width * fit), round(im.height * fit)), Image.LANCZOS)
    x, y = (w - page.width) // 2, (h - page.height) // 2
    shadow = Image.new("L", (page.width + 80, page.height + 80), 0)
    shadow.paste(180, (40, 40, 40 + page.width, 40 + page.height))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    back.paste(Image.new("RGB", shadow.size, (0, 0, 0)), (x - 40, y - 28), shadow)
    back.paste(page, (x, y))
    part = Path(str(out) + ".part.jpg")
    grade.cinematic(back, 0.5).save(part, quality=94, subsampling=0)
    part.rename(out)
    return out
