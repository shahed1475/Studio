"""Depth maps for a picture's camera motion (2.5D parallax, see parallax.py).

A depth map is a small grey picture: white is near, black is far. It is made once by tools/make_depth.py (Depth Anything V2 Small, Apache-2.0, on a machine that
has onnxruntime and numpy; the studio server has neither) and kept in cache/depth/, named after the picture's own bytes so a copy of a picture has the same map.
A picture with no map gets an approximate one (the ground near, the sky far, a soft nearer middle) and says so: the motion still works, it is just less exact."""
import hashlib
from pathlib import Path

from PIL import Image

import config

MAP_WIDTH = 192  # a map is read at the size of a mesh of warp cells, so it stays small (about 10 KB)


def depth_dir() -> Path:
    return Path(config.CACHE) / "depth"


def depth_key(path) -> str:
    """The first 16 hex digits of the md5 of the picture's bytes."""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()[:16]


def load_depth(path) -> Image.Image | None:
    """The stored map for this picture as a grey picture, or None when there is none or the file cannot be read."""
    f = depth_dir() / f"{depth_key(path)}.png"
    try:
        return Image.open(f).convert("L") if f.exists() else None
    except Exception:
        return None


def approximate_depth(size: tuple[int, int] = (MAP_WIDTH, 108)) -> Image.Image:
    """No model: far at the top, near at the bottom, and a gentle nearer patch in the middle where the subject usually is."""
    w, h = size
    im = Image.new("L", size)
    px = im.load()
    for y in range(h):
        ramp = 40 + 150 * (y / max(1, h - 1)) ** 1.2
        for x in range(w):
            cx = 1 - abs(x / max(1, w - 1) - 0.5) * 2  # 1 in the middle, 0 at the sides
            cy = 1 - abs(y / max(1, h - 1) - 0.55) * 2
            px[x, y] = min(255, int(ramp + 45 * max(0, cx) * max(0, cy)))
    return im


def depth_for(path) -> tuple[Image.Image, str]:
    """(map, "model" or "approximate")."""
    got = load_depth(path)
    if got is not None:
        return got, "model"
    with Image.open(path) as im:
        w, h = im.size
    return approximate_depth((MAP_WIDTH, max(8, round(MAP_WIDTH * h / w)))), "approximate"
