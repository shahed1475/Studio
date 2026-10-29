"""Make depth maps for pictures (run on a machine that has onnxruntime, numpy and Pillow; the studio server has only Pillow).

    python tools/make_depth.py MODEL.onnx PICTURE_OR_FOLDER... [--out DIR]

The model is Depth Anything V2 Small (Apache-2.0), file onnx/model_uint8.onnx of onnx-community/depth-anything-v2-small. It is refused unless its SHA-256 is the one
that was checked on 29 Oct 2026. An ONNX file is data, not code. Each map is written as DIR/<depth.depth_key(picture)>.png (default cache/depth/): white is near.
The map is stretched between the 2nd and 98th percentile so one stray pixel cannot flatten the rest, and softened a little so the warp in parallax.py has no hard steps."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PINNED_SHA256 = "fcf51f1b230362b28690bb9d1809bf0431f29cad20534e3f589bd7285547f20d"
SIDE = 518  # the model reads a multiple of 14 pixels; 518 on the long edge is its native size


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_map(session, picture: Path):
    import numpy as np
    from PIL import Image, ImageFilter

    import depth

    img = Image.open(picture).convert("RGB")
    W, H = img.size
    w, h = (SIDE, int(round(SIDE * H / W / 14)) * 14) if W >= H else (int(round(SIDE * W / H / 14)) * 14, SIDE)
    x = np.asarray(img.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
    x = ((x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)).transpose(2, 0, 1)[None]
    d = session.run(None, {session.get_inputs()[0].name: x})[0][0]
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    small = Image.fromarray((d * 255).astype(np.uint8)).resize((depth.MAP_WIDTH, max(8, round(depth.MAP_WIDTH * H / W))), Image.LANCZOS)
    return small.filter(ImageFilter.GaussianBlur(1.2))


def main(argv: list[str]) -> int:
    import onnxruntime as ort

    import config
    import depth

    args = [a for a in argv if not a.startswith("--")]
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else depth.depth_dir()
    if "--out" in argv:
        args = [a for a in args if a != argv[argv.index("--out") + 1]]
    if len(args) < 2:
        print(__doc__)
        return 2
    model, sources = Path(args[0]), [Path(a) for a in args[1:]]
    if sha256(model) != PINNED_SHA256:
        print(f"refusing {model}: its SHA-256 is not the checked one ({PINNED_SHA256[:12]}...)")
        return 1
    pics = sorted(p for s in sources for p in ([s] if s.is_file() else s.glob("*.jpg")))
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    out.mkdir(parents=True, exist_ok=True)
    for p in pics:
        m = make_map(session, p)
        m.save(out / f"{depth.depth_key(p)}.png")
    print(f"{len(pics)} depth maps written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
