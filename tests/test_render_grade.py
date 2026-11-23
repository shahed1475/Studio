"""Colour and finish of every studio video (23 Nov 2026). Measured on the Maximilian film: no colour tags, the BT.601 matrix where players assume BT.709
(a red 200,60,40 played as 212,72,36), about 1.5 Mb/s for 1080p, and a 'grade' (eq=brightness=-0.05:saturation=0.85) that crushed up to 21% of a picture
to black and raised its saturation. These tests run the real ffmpeg."""
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import render

ff = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="no ffmpeg")


def test_every_encode_is_tagged_bt709_and_the_old_grade_is_gone():
    v = render._venc("18", "veryfast")
    for flag, val in (("-colorspace", "bt709"), ("-color_primaries", "bt709"), ("-color_trc", "bt709"), ("-color_range", "tv")):
        assert v[v.index(flag) + 1] == val
    pf = render._picture_filter(640, 360, 30, None, 0)
    assert render.GRADE in pf and "brightness=-0.05" not in pf
    assert "render.GRADE" in (Path(render.__file__).parent / "parallax.py").read_text()  # motion clips get the same grade
    assert render.AUDIO[render.AUDIO.index("-ar") + 1] == "48000" and render.AUDIO[render.AUDIO.index("-c:a") + 1] == "aac"


def _rgb(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:in_range=tv,format=rgb24",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(int)


@ff
def test_a_colour_plays_back_as_it_was_drawn_when_read_as_bt709(tmp_path):
    src = tmp_path / "red.png"
    Image.new("RGB", (64, 64), (200, 60, 40)).save(src)
    out = tmp_path / "red.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(src), "-t", "0.5", "-vf", "format=yuv420p", *render._venc("10", "veryfast"), str(out)],
                   check=True)
    px = _rgb(out)[64 * 32 + 32]
    assert np.abs(px - np.array([200, 60, 40])).max() <= 4, px  # untagged it was 212,72,36
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_primaries,color_transfer,color_space",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert probe.split(",") == ["bt709", "bt709", "bt709"], probe


@ff
def test_the_grade_clips_no_highlight_crushes_no_shadow_and_does_not_raise_saturation(tmp_path):
    w, h = 512, 256
    ramp = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    img = np.stack([ramp, (ramp * 0.6).astype(np.uint8), (ramp * 0.3).astype(np.uint8)], -1)  # a warm ramp from pure black to full red
    src = tmp_path / "ramp.png"
    Image.fromarray(img).save(src)
    out = tmp_path / "graded.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", render.GRADE, str(out)], check=True)
    a = np.asarray(Image.open(out).convert("RGB")).astype(int)
    centre = a[h // 4: 3 * h // 4, w // 8: 7 * w // 8]  # inside the vignette's soft edge
    assert centre.max() < 254 and centre.max(-1).min() > 2  # highlights rolled off, blacks lifted a little, nothing clipped or crushed
    sat = lambda x: ((x.max(-1) - x.min(-1)) / np.maximum(x.max(-1), 1)).mean()
    assert sat(centre) <= sat(img[h // 4: 3 * h // 4, w // 8: 7 * w // 8].astype(int)) * 1.02
