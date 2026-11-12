"""tools/archive_insert.py (1 Nov 2026): a real archive scan as a 16:9 insert shot. It is saved in cache/archive, never in cache/cc, so the studio never gives a real picture fake depth motion."""
import config
import numpy as np
import pytest
from PIL import Image

import animate
import tools.archive_insert as ai


def test_a_portrait_scan_becomes_a_16_9_insert_with_the_page_in_the_middle_and_the_source_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    src = tmp_path / "page.jpg"
    Image.new("RGB", (600, 800), (230, 220, 190)).save(src)
    before = src.read_bytes()
    out = ai.compose(src, "page")
    im = Image.open(out)
    assert im.size == (1920, 1080) and out.parent == tmp_path / "cache" / "archive" and not animate.own_picture(out) and src.read_bytes() == before
    a = np.asarray(im.convert("L"), dtype=np.float32)
    assert a[500:580, 900:1020].mean() > a[500:580, 20:100].mean() + 40  # the pale page in the middle, a dark blurred backdrop at the sides
    assert ai.compose(src, "page") == out


def test_a_landscape_scan_fits_the_width_and_never_leaves_the_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    src = tmp_path / "wide.jpg"
    Image.new("RGB", (1536, 731), (200, 190, 160)).save(src)
    assert Image.open(ai.compose(src, "wide")).size == (1920, 1080)
