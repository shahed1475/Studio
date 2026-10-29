"""Depth maps for camera motion (29 Oct 2026). A depth map says how near each part of a picture is. It is made once, outside the server (the server has no numpy or onnxruntime),
and kept as a small grey picture in cache/depth/, named after the picture's own bytes. A picture with no map gets an approximate one that says so."""
import pytest
from PIL import Image

import config
import depth


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    (tmp_path / "cache" / "art").mkdir(parents=True)


def picture(tmp_path, colour=(200, 120, 60), name="a.jpg", size=(320, 180)):
    p = tmp_path / "cache" / "art" / name
    Image.new("RGB", size, colour).save(p, "JPEG")
    return p


def test_the_key_comes_from_the_pictures_bytes_so_a_copy_has_the_same_depth_and_a_change_does_not(tmp_path):
    a, b = picture(tmp_path), picture(tmp_path, name="copy.jpg")
    assert depth.depth_key(a) == depth.depth_key(b) and len(depth.depth_key(a)) == 16
    assert depth.depth_key(a) != depth.depth_key(picture(tmp_path, (10, 20, 30), "other.jpg"))


def test_a_stored_map_is_found_and_returned_as_a_grey_picture(tmp_path):
    p = picture(tmp_path)
    assert depth.load_depth(p) is None
    (config.CACHE / "depth").mkdir()
    Image.new("L", (192, 108), 90).save(config.CACHE / "depth" / f"{depth.depth_key(p)}.png")
    got = depth.load_depth(p)
    assert got.mode == "L" and got.size == (192, 108)
    m, how = depth.depth_for(p)
    assert how == "model" and m.getpixel((5, 5)) == 90


def test_a_picture_with_no_map_gets_an_approximate_one_and_says_so(tmp_path):
    p = picture(tmp_path)
    m, how = depth.depth_for(p)
    assert how == "approximate" and m.mode == "L"
    w, h = m.size
    assert m.getpixel((w // 2, h - 2)) > m.getpixel((w // 2, 2)) + 60  # the ground is near, the sky is far
    assert m.getpixel((w // 2, h // 2)) >= m.getpixel((2, h // 2))  # something in the middle stands a little nearer than the edge


def test_a_broken_map_file_is_ignored(tmp_path):
    p = picture(tmp_path)
    (config.CACHE / "depth").mkdir()
    (config.CACHE / "depth" / f"{depth.depth_key(p)}.png").write_bytes(b"not a picture")
    assert depth.load_depth(p) is None
    assert depth.depth_for(p)[1] == "approximate"
