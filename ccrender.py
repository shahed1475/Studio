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
HAZE = {"dunes": ((0.93, 0.80, 0.64), 0.55), "temple": ((0.88, 0.72, 0.62), 0.4), "stones": ((0.82, 0.84, 0.92), 0.5), "sea": ((0.80, 0.85, 0.92), 0.45), "night": ((0.05, 0.06, 0.1), 0.0)}  # colour and strength per scene; spec "haze" overrides
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


CLIP_FPS, OUT_FPS = 12, 24  # a moving Blender clip is rendered at 12 frames a second and half size on the CPU, then blended to 24 (ffmpeg framerate: minterpolate dropped the last frames) and scaled up (20 Nov 2026: 4 to 5 s a frame at 960x540 against 35 to 65 s at 1920x1080)


def _frames_ok(d: Path, frames: int) -> bool:
    return all((d / f"f_{i:04d}.png").is_file() and (d / f"f_{i:04d}.png").stat().st_size > 0 for i in range(1, frames + 1))


def clip_seconds(path) -> float:
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60).stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def clip_job(spec: dict, seconds: float, size: tuple[int, int]) -> dict:
    """What Blender is asked to draw for a clip: half the size, 12 frames a second, one frame more than the length needs (blending to 24 frames a second ends half a
    frame early, and a clip of exactly the length was measured 0.1 s short)."""
    import math

    w, h = size
    return {"scene": spec["scene"], "params": spec.get("params", {}), "width": (w // 2) // 2 * 2, "height": (h // 2) // 2 * 2, "samples": spec.get("samples", 4),
            "frames": max(2, math.ceil(seconds * CLIP_FPS) + 1), "fps": CLIP_FPS}


def render_clip(spec: dict, seconds: float, size: tuple[int, int] = (1920, 1080), force: bool = False) -> Path:
    """A moving clip of an animated scene (scenes.library.ANIMATED) about `seconds` long, as an H.264 MP4 at `size` and 24 frames a second. Cached by the hash of its spec;
    the frames go to their own folder first, so a render that was stopped continues with the frames it has (an empty placeholder frame from a killed render is redone).
    Raises when Blender fails or the clip is not as long as asked (it is checked before anything uses it)."""
    if not BLENDER.exists():
        raise FileNotFoundError(f"Blender not found at {BLENDER}; set BLENDER or install it in ~/tools/blender")
    w, h = size
    job = clip_job(spec, seconds, size)
    frames = job["frames"]
    key = spec_key(job)
    out = cache_dir() / f"clip-{spec['scene']}-{key}.mp4"
    if out.exists() and not force and clip_seconds(out) >= seconds * 0.95:
        return out
    fdir = cache_dir() / f"frames-{key}"
    fdir.mkdir(parents=True, exist_ok=True)
    for f in fdir.glob("f_*.png"):
        if f.stat().st_size == 0:  # the placeholder of a frame that was being drawn when the render was stopped
            f.unlink()
    js = fdir / "spec.json"
    js.write_text(json.dumps({**job, "out_dir": str(fdir)}))
    if not _frames_ok(fdir, frames):
        p = subprocess.run([str(BLENDER), "-b", "-P", str(Path(__file__).parent / "scenes" / "run_anim.py"), "--", str(js)], capture_output=True, text=True, timeout=7200)
        if "ANIM_DONE" not in p.stdout or not _frames_ok(fdir, frames):
            raise RuntimeError("Blender clip failed: " + (p.stdout + p.stderr)[-1200:])
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(CLIP_FPS), "-i", str(fdir / "f_%04d.png"),
                    "-vf", f"framerate=fps={OUT_FPS},scale={w}:{h}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-movflags", "+faststart", str(tmp)], check=True, capture_output=True, timeout=1800)
    got = clip_seconds(tmp)
    if got < seconds * 0.95:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Blender clip is {got:.1f} s, {seconds:.1f} s was asked")
    os.replace(tmp, out)
    import shutil

    shutil.rmtree(fdir, ignore_errors=True)  # this clip's own frame folder, named by its key; the finished clip is kept
    return out


def version() -> str:
    """The Blender version line, or '' when Blender cannot run."""
    try:
        return subprocess.run([str(BLENDER), "-b", "--version"], capture_output=True, text=True, timeout=120).stdout.splitlines()[0].strip()
    except (OSError, IndexError, subprocess.SubprocessError):
        return ""


if __name__ == "__main__":
    print(render(json.loads(Path(sys.argv[1]).read_text()), force="--force" in sys.argv))
