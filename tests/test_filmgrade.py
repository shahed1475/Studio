import numpy as np
import pytest
from PIL import Image

import ccbuild
import filmgrade as grade


def flat(rgb, size=101):
    return Image.new("RGB", (size, size), rgb)


def centre(im):
    return im.getpixel((im.width // 2, im.height // 2))


def test_the_grade_keeps_size_and_mode():
    out = grade.apply(flat((90, 120, 150), 64), "cinema")
    assert out.size == (64, 64) and out.mode == "RGB"


def test_shadows_lean_teal_and_highlights_lean_warm():
    r, g, b = centre(grade.apply(flat((40, 40, 40)), "cinema"))
    assert b > r, "a dark grey should move toward teal"
    r, g, b = centre(grade.apply(flat((225, 225, 225)), "cinema"))
    assert r > b, "a bright grey should move toward orange"


def test_blacks_are_lifted_a_little_and_whites_are_not_clipped():
    assert 2 <= max(centre(grade.apply(flat((0, 0, 0)), "cinema"))) <= 25
    assert max(centre(grade.apply(flat((255, 255, 255)), "cinema"))) <= 252


def test_the_edges_are_darker_than_the_centre():
    out = np.asarray(grade.apply(flat((128, 128, 128), 201), "cinema"), dtype=float)
    assert out[0, 0].mean() < out[100, 100].mean() - 8


def test_the_grade_is_deterministic():
    im = Image.effect_noise((48, 48), 40).convert("RGB")
    assert list(grade.apply(im, "cinema").getdata()) == list(grade.apply(im, "cinema").getdata())


def test_an_unknown_look_is_refused():
    with pytest.raises(ValueError):
        grade.apply(flat((1, 2, 3), 8), "no-such-look")


def test_a_graded_picture_is_cached_apart_from_the_plain_one(tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    src = tmp_path / "a.png"
    Image.new("RGB", (64, 64), (60, 90, 120)).save(src)
    plain, graded = ccbuild.fitted(src), ccbuild.fitted(src, False, "cinema")
    assert plain != graded and graded.exists() and ccbuild.fitted(src, False, "cinema") == graded
    assert Image.open(graded).size == ccbuild.SIZE and Image.open(graded).tobytes() != Image.open(plain).tobytes()
