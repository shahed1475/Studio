from pathlib import Path

import config
import footage


def test_clip_for_falls_back_to_archive_image_without_pexels_key(monkeypatch):
    monkeypatch.setattr(config, "PEXELS_KEY", "")
    monkeypatch.setattr(footage.archive_video, "fetch_clip", lambda q, s=10.0: None)
    monkeypatch.setattr(footage, "image_for", lambda q: (Path("/tmp/x.jpg"), "credit") if q == "old castle" else None)
    assert footage.clip_for("old castle") == Path("/tmp/x.jpg")
    assert footage.clip_for("nothing found") is None
    assert footage.clip_for("") is None


def test_enough_footage_ratio():
    assert footage.enough_footage([Path("a"), Path("b"), None]) is True       # 2 of 3
    assert footage.enough_footage([Path("a"), None, None, None]) is False     # 1 of 4
    assert footage.enough_footage([]) is False


def test_collect_credits_dedupes_and_skips_missing(tmp_path):
    a, b, c = tmp_path / "a.mp4", tmp_path / "b.jpg", tmp_path / "c.jpg"
    for f in (a, b, c):
        f.write_bytes(b"x")
    (tmp_path / "a.txt").write_text("Film A (Internet Archive, CC0)")
    (tmp_path / "b.txt").write_text("Film A (Internet Archive, CC0)")
    assert footage.collect_credits([a, None, b, c]) == ["Film A (Internet Archive, CC0)"]
