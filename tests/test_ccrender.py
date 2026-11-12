"""ccrender.py (1 Nov 2026): the parts that need no Blender, and one real render when Blender is installed."""
import pytest
from PIL import Image

import ccrender


def test_spec_key_is_stable_and_changes_with_any_field():
    a = {"scene": "dunes", "width": 320, "height": 180, "params": {"seed": 1}}
    assert ccrender.spec_key(a) == ccrender.spec_key(dict(reversed(list(a.items()))))
    assert ccrender.spec_key(a) != ccrender.spec_key({**a, "params": {"seed": 2}})


def test_haze_touches_far_pixels_more_than_near_ones():
    img = Image.new("RGB", (4, 1), (10, 10, 10))
    dmap = Image.new("L", (4, 1))
    dmap.putdata([255, 255, 0, 0])  # white = near, black = far
    out = ccrender.with_haze(img, dmap, (1.0, 1.0, 1.0), 0.8)
    near, far = out.getpixel((0, 0)), out.getpixel((3, 0))
    assert far[0] > near[0] + 100


def test_zero_amount_leaves_the_picture_alone():
    img = Image.new("RGB", (4, 1), (10, 20, 30))
    assert ccrender.with_haze(img, Image.new("L", (4, 1), 0), (1, 1, 1), 0.0).getpixel((2, 0)) == (10, 20, 30)


def test_missing_blender_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(ccrender, "BLENDER", tmp_path / "nope")
    with pytest.raises(FileNotFoundError, match="Blender not found"):
        ccrender.render({"scene": "dunes", "width": 64, "height": 64})


@pytest.mark.skipif(not ccrender.BLENDER.exists(), reason="Blender is not installed here")
def test_real_render_writes_picture_and_depth(monkeypatch, tmp_path):
    import config
    import depth

    monkeypatch.setattr(config, "CACHE", tmp_path)
    p = ccrender.render({"scene": "dunes", "width": 160, "height": 90, "samples": 4, "engine": "EEVEE"})
    assert p.exists() and Image.open(p).size == (160, 90)
    assert depth.load_depth(p) is not None
    assert ccrender.render({"scene": "dunes", "width": 160, "height": 90, "samples": 4, "engine": "EEVEE"}) == p  # cached
