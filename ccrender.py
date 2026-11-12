"""Pictures from Blender for a video made in a Claude Code session (1 Nov 2026): one call turns a scene spec into a picture and its exact depth map.

Everything is free and local: Blender (~/tools/blender, or $BLENDER) and the CC0 files in assets/cc0 (LEDGER.md). A picture is cached by the hash of its spec, so the same scene is never drawn twice.
The depth map is written to cache/depth/ under the picture's own key, so parallax.py moves the picture with the real depth instead of an estimate. Haze (distance fog) is added afterwards from that same depth,
because Blender's world fog blacks out Cycles frames. Usage: python ccrender.py spec.json   |   from code: ccrender.render(spec)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

import config
import depth

BLENDER = Path(os.environ.get("BLENDER") or Path.home() / "tools" / "blender" / "blender")
HAZE = {"dunes": ((0.93, 0.80, 0.64), 0.55), "temple": ((0.88, 0.72, 0.62), 0.4), "stones": ((0.82, 0.84, 0.92), 0.5)}  # colour and strength per scene; spec "haze" overrides
SIZES = {"short": (1080, 1920), "film": (1920, 1080)}


def cache_dir() -> Path:
    d = Path(config.CACHE) / "cc"
    d.mkdir(parents=True, exist_ok=True)
    return d


def spec_key(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


def with_haze(img: Image.Image, dmap: Image.Image, color, amount: float) -> Image.Image:
    """Mix the haze colour in by distance: the far parts take most, the near parts none. dmap is white = near."""
    far = ImageChops.invert(dmap.convert("L").resize(img.size, Image.BILINEAR)).filter(ImageFilter.GaussianBlur(1.5))
    mask = far.point(lambda v: int(255 * amount * (v / 255) ** 1.4))
    return Image.composite(Image.new("RGB", img.size, tuple(int(c * 255) for c in color)), img.convert("RGB"), mask)


def render(spec: dict, force: bool = False) -> Path:
    """spec: scene, params, format ('short' or 'film') or width and height, samples, engine, ev, haze (optional {color, amount}). Returns the picture's path."""
    if not BLENDER.exists():
        raise FileNotFoundError(f"Blender not found at {BLENDER}; set BLENDER or install it in ~/tools/blender")
    spec = dict(spec)
    if "format" in spec:
        spec["width"], spec["height"] = SIZES[spec.pop("format")]
    spec.setdefault("samples", 96)
    out = cache_dir() / f"{spec['scene']}-{spec_key(spec)}.png"
    if out.exists() and not force:
        return out
    with tempfile.TemporaryDirectory() as t:
        raw, dep, js = Path(t) / "raw.png", Path(t) / "depth.png", Path(t) / "spec.json"
        job = {k: v for k, v in spec.items() if k != "haze"} | {"out": str(raw), "depth_out": str(dep)}
        js.write_text(json.dumps(job))
        p = subprocess.run([str(BLENDER), "-b", "-P", str(Path(__file__).parent / "scenes" / "run_scene.py"), "--", str(js)], capture_output=True, text=True, timeout=1800)
        if "SCENE_DONE" not in p.stdout or not raw.exists():
            raise RuntimeError("Blender failed: " + (p.stdout + p.stderr)[-1200:])
        img, dmap = Image.open(raw).convert("RGB"), Image.open(dep).convert("L")
        h = spec.get("haze") or {}
        col, amt = h.get("color") or HAZE.get(spec["scene"], ((0.85, 0.85, 0.9), 0.4))[0], h.get("amount", HAZE.get(spec["scene"], ((0), 0.4))[1])
        if amt > 0:
            img = with_haze(img, dmap, col, amt)
        img.save(out)
        small = dmap.resize((depth.MAP_WIDTH, max(1, round(depth.MAP_WIDTH * dmap.height / dmap.width))), Image.LANCZOS)
        d = depth.depth_dir()
        d.mkdir(parents=True, exist_ok=True)
        small.save(d / f"{depth.depth_key(out)}.png")
    return out


if __name__ == "__main__":
    print(render(json.loads(Path(sys.argv[1]).read_text()), force="--force" in sys.argv))
