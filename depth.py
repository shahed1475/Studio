"""Depth maps for a picture's camera motion (2.5D parallax, see parallax.py).

A depth map is a small grey picture: white is near, black is far, kept in cache/depth/ and named after the picture's own bytes so a copy of a picture has the same map.
It is made by Depth Anything V2 Small (Apache-2.0) when this machine has numpy and onnxruntime and the model file (data/models/, fetched once by `run.py depth-setup` and refused
unless its SHA-256 is the checked one), or earlier by tools/make_depth.py on another machine. A picture with no map and no model gets an approximate one (the ground near, the
sky far, a soft nearer middle) and says so: the motion still works, it is just less exact."""
import functools
import hashlib
from pathlib import Path

from PIL import Image, ImageFilter

import config

MAP_WIDTH = 192  # a map is read at the size of a mesh of warp cells, so it stays small (about 10 KB)
# The model: Depth Anything V2 Small (Apache-2.0), the uint8 ONNX export of onnx-community/depth-anything-v2-small, 27,258,801 bytes. ONNX is data, not code.
MODEL_URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_uint8.onnx"
MODEL_SHA256 = "fcf51f1b230362b28690bb9d1809bf0431f29cad20534e3f589bd7285547f20d"  # checked on 29 Oct 2026; a file with any other hash is never loaded
SIDE = 518  # the model reads multiples of 14 pixels; 518 on the long edge is its native size


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


def model_path() -> Path:
    return Path(config.ROOT) / "data" / "models" / "depth_anything_v2_small_uint8.onnx"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    """Fetch the model from the one host it was checked on (https only)."""
    import requests

    if not url.startswith("https://huggingface.co/onnx-community/depth-anything-v2-small/"):
        raise RuntimeError(f"not downloading from {url.split('/')[2] if '//' in url else url}: that host is not the one the model was checked on")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def ensure_model() -> Path:
    """The model file, downloaded once. It is kept only when its SHA-256 is the checked one: anything else is removed and refused."""
    f = model_path()
    if f.exists() and sha256_of(f) == MODEL_SHA256:
        return f
    f.parent.mkdir(parents=True, exist_ok=True)
    part = f.with_name(f.name + ".part")
    try:
        _download(MODEL_URL, part)
        if sha256_of(part) != MODEL_SHA256:
            raise RuntimeError("the downloaded model's SHA-256 is not the checked one: refused and removed")
        part.replace(f)
    finally:
        part.unlink(missing_ok=True)
    return f


def _runtime():
    """(numpy, onnxruntime) when both are installed, else None."""
    try:
        import numpy
        import onnxruntime
    except Exception:
        return None
    return numpy, onnxruntime


@functools.lru_cache(maxsize=1)
def _session():
    """The model's session, or None when there is no runtime, no model file, or a model file that is not the checked one."""
    rt = _runtime()
    f = model_path()
    if rt is None or not f.exists() or sha256_of(f) != MODEL_SHA256:
        return None
    return rt[1].InferenceSession(str(f), providers=["CPUExecutionProvider"])


def make_map(session, picture) -> Image.Image:
    """The depth map of one picture (white is near). Stretched between the 2nd and 98th percentile so one stray pixel cannot flatten the rest, and softened a little so the
    warp in parallax.py has no hard steps."""
    import numpy as np

    img = Image.open(picture).convert("RGB")
    W, H = img.size
    w, h = (SIDE, int(round(SIDE * H / W / 14)) * 14) if W >= H else (int(round(SIDE * W / H / 14)) * 14, SIDE)
    x = np.asarray(img.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    x = ((x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)).transpose(2, 0, 1)[None]
    d = session.run(None, {session.get_inputs()[0].name: x})[0][0]
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    small = Image.fromarray((d * 255).astype(np.uint8)).resize((MAP_WIDTH, max(8, round(MAP_WIDTH * H / W))), Image.LANCZOS)
    return small.filter(ImageFilter.GaussianBlur(1.2))


def make_and_store(path) -> Image.Image | None:
    """Make the picture's map with the model and keep it in cache/depth/; None when the model cannot run here or fails (the caller then uses the approximate map)."""
    try:
        session = _session()
        if session is None:
            return None
        m = make_map(session, path)
        depth_dir().mkdir(parents=True, exist_ok=True)
        tmp = depth_dir() / f"{depth_key(path)}.part.png"
        m.save(tmp)
        tmp.replace(depth_dir() / f"{depth_key(path)}.png")
        return m
    except Exception:
        return None


def depth_for(path) -> tuple[Image.Image, str]:
    """(map, "model" or "approximate"). A picture with no stored map is given one by the model when this machine can run it."""
    got = load_depth(path)
    if got is None:
        got = make_and_store(path)
    if got is not None:
        return got, "model"
    with Image.open(path) as im:
        w, h = im.size
    return approximate_depth((MAP_WIDTH, max(8, round(MAP_WIDTH * h / w)))), "approximate"
