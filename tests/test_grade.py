"""grade.py (1 Nov 2026): a film-style colour grade for the studio's own pictures, to take away the over-saturated 'AI' look. Deterministic, size-preserving, cached in cache/cc."""
import numpy as np
import pytest
from PIL import Image

import animate
import config
import grade


def sat(img):
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    return float(((a.max(2) - a.min(2)) / (a.max(2) + 1e-6)).mean())


def lum(img):
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    return float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean())


def vivid():
    a = np.zeros((90, 160, 3), np.uint8)
    a[:, :80] = (230, 60, 40)
    a[:, 80:] = (40, 190, 90)
    return Image.fromarray(a)


def flat(v):
    return Image.new("RGB", (160, 90), (v, v, v))


def test_the_grade_takes_saturation_down_without_moving_the_brightness_much():
    out = grade.cinematic(vivid())
    assert out.size == (160, 90) and out.mode == "RGB"
    assert sat(out) < 0.88 * sat(vivid()) and abs(lum(out) - lum(vivid())) < 0.08


def test_the_same_picture_always_gives_the_same_grade():
    assert grade.cinematic(vivid()).tobytes() == grade.cinematic(vivid()).tobytes()


def test_shadows_lean_teal_and_highlights_lean_warm():
    dark = np.asarray(grade.cinematic(flat(45)), dtype=np.float32)[30:60, 60:100].mean((0, 1))
    light = np.asarray(grade.cinematic(flat(215)), dtype=np.float32)[30:60, 60:100].mean((0, 1))
    assert dark[2] - dark[0] > 1.0 and light[0] - light[2] > 1.0


def test_the_corners_are_a_little_darker_than_the_middle():
    a = np.asarray(grade.cinematic(flat(128)).convert("L"), dtype=np.float32)
    assert a[:6, :6].mean() < a[40:50, 70:90].mean() - 3


def test_a_graded_file_is_cached_where_the_studio_may_animate_it_and_never_overwrites_the_source(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    src = tmp_path / "a.jpg"
    vivid().save(src)
    before = src.read_bytes()
    out = grade.graded(src)
    assert out.exists() and out.parent == tmp_path / "cache" / "cc" and out.name.startswith("grade-") and animate.own_picture(out)
    assert grade.graded(src) == out and src.read_bytes() == before
    assert grade.graded(src, strength=0.5) != out


def lowkey():
    g = np.linspace(20, 150, 160, dtype=np.float32)
    a = np.tile(g, (90, 1))
    return Image.fromarray(np.stack([a * 1.1, a, a * 0.8], 2).clip(0, 255).astype(np.uint8))


def test_the_grade_keeps_the_average_brightness_of_a_dark_scene_so_it_stays_readable_on_a_phone():
    src = lowkey()
    assert abs(lum(grade.cinematic(src)) - lum(src)) < 0.035
