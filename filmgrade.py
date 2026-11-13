"""Named film looks for a still picture (14 Nov 2026, owner's request: realistic, film colour). Separate from grade.py (the 1 Nov grade ccdoc uses); ccbuild picks this one with the spec key `grade`.

A filmic S-curve with slightly lifted blacks and soft highlights, teal in the shadows, orange in the highlights, a little more colour and a gentle vignette.
Applied to each picture before the camera move, so burned-in captions stay clean white. Pure numpy and Pillow: free, deterministic, no model."""
import numpy as np
from PIL import Image

LOOKS = {
    # lift/roll-off keep blacks off zero and whites under 255; shadow and highlight tints are added in 0 to 1 colour units; vignette is the corner darkening
    "cinema": {"black": 0.035, "white": 0.975, "curve": 0.65, "shadow": (-0.035, 0.0, 0.05), "highlight": (0.055, 0.02, -0.045), "saturation": 1.10, "vignette": 0.30},
}


def apply(im: Image.Image, look: str = "cinema") -> Image.Image:
    """The picture graded with the named look, same size, RGB. Raises ValueError for an unknown look."""
    if look not in LOOKS:
        raise ValueError(f"unknown grade look: {look!r}")
    p = LOOKS[look]
    x = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    s = x * x * (3.0 - 2.0 * x)  # smoothstep: darker darks, brighter lights
    x = x + p["curve"] * (s - x)
    x = p["black"] + (p["white"] - p["black"]) * x
    luma = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x = x + (1.0 - luma) ** 2 * np.array(p["shadow"], dtype=np.float32) + luma ** 2 * np.array(p["highlight"], dtype=np.float32)
    luma = (0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2])[..., None]
    x = luma + (x - luma) * p["saturation"]
    x = np.where(x > 0.9, 0.9 + 0.1 * np.tanh((x - 0.9) / 0.1), x)  # a soft shoulder: warm highlights roll off instead of clipping
    h, w = x.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = (((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2) / 2.0  # 0 at the centre, 1 in the corners
    x = x * (1.0 - p["vignette"] * r2)[..., None]
    return Image.fromarray(np.clip(x * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGB")
