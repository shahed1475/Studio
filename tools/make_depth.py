"""Make depth maps for pictures (run on a machine that has onnxruntime, numpy and Pillow; the studio server has only Pillow).

    python tools/make_depth.py MODEL.onnx PICTURE_OR_FOLDER... [--out DIR]

The model is Depth Anything V2 Small (Apache-2.0), file onnx/model_uint8.onnx of onnx-community/depth-anything-v2-small. It is refused unless its SHA-256 is the one
that was checked on 29 Oct 2026. An ONNX file is data, not code. Each map is written as DIR/<depth.depth_key(picture)>.png (default cache/depth/): white is near.
The map is stretched between the 2nd and 98th percentile so one stray pixel cannot flatten the rest, and softened a little so the warp in parallax.py has no hard steps."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import depth

PINNED_SHA256 = depth.MODEL_SHA256
sha256 = depth.sha256_of


def make_map(session, picture: Path):
    return depth.make_map(session, picture)


def main(argv: list[str]) -> int:
    import onnxruntime as ort

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
