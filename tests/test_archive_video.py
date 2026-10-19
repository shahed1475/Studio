import json
from pathlib import Path

import pytest

import archive_video
import config
import footage


def test_build_query_is_public_domain_only():
    q = archive_video.build_query("foggy forest")
    assert "publicdomain/mark/1.0" in q and "zero/1.0" in q and "collection:(" in q and "NOT subject:" in q
    assert "mediatype:movies" in q and "foggy" in q and "forest" in q


def test_relevant_needs_a_keyword_in_title_or_subject():
    doc = {"title": "Castle on the Rhine", "subject": ["travel", "germany"], "description": "A trip"}
    assert archive_video.relevant(doc, "old castle") is True
    assert archive_video.relevant({"title": "Noggin recording", "subject": "tv"}, "old castle") is False
    assert archive_video.relevant({"title": "x"}, "the of and") is False


FILES = [
    {"name": "a.ogv", "format": "Ogg Video", "size": "3000000"},
    {"name": "big.mp4", "format": "h.264", "size": "200000000"},
    {"name": "ok.mp4", "format": "h.264", "size": "40000000", "length": "612.5"},
    {"name": "small.mp4", "format": "MPEG4", "size": "5000000"},
]


def test_pick_file_prefers_h264_mp4_under_cap():
    assert archive_video.pick_file(FILES)["name"] == "ok.mp4"


def test_pick_file_none_when_nothing_usable():
    assert archive_video.pick_file([FILES[0], FILES[1]]) is None
    assert archive_video.pick_file([]) is None


def test_clip_offset_inside_video():
    for seed in ("a", "b", "castle"):
        off = archive_video.clip_offset(600.0, 10.0, seed)
        assert 0.15 * 590 <= off <= 0.6 * 590
    assert archive_video.clip_offset(5.0, 10.0, "x") == 0.0


def test_credit_for_reads_sibling_txt(tmp_path):
    clip = tmp_path / "arch-1.mp4"
    clip.write_bytes(b"x")
    assert footage.credit_for(clip) is None
    (tmp_path / "arch-1.txt").write_text("Film (Internet Archive, Public Domain Mark)")
    assert footage.credit_for(clip) == "Film (Internet Archive, Public Domain Mark)"


def fake_net(monkeypatch, docs, files=FILES):
    def get_json(url, params=None):
        if "advancedsearch" in url:
            return {"response": {"docs": docs}}
        return {"files": files, "metadata": {"licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/"}}
    monkeypatch.setattr(archive_video, "_get_json", get_json)


def test_fetch_clip_none_when_nothing_relevant(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    fake_net(monkeypatch, [{"identifier": "n", "title": "Noggin", "subject": "tv", "licenseurl": "x"}])
    assert archive_video.fetch_clip("old castle") is None


def test_fetch_clip_writes_clip_and_credit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    fake_net(monkeypatch, [{"identifier": "castle1", "title": "The Old Castle", "subject": "castle", "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/"}])
    def fake_ffmpeg(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"clip")
        class R: returncode = 0
        return R()
    import render
    monkeypatch.setattr(render, "_venc", lambda *a: [])
    monkeypatch.setattr(archive_video.subprocess, "run", fake_ffmpeg)
    clip = archive_video.fetch_clip("old castle")
    assert clip and clip.read_bytes() == b"clip"
    assert footage.credit_for(clip) == "The Old Castle (Internet Archive, Public Domain Mark)"
    assert archive_video.fetch_clip("old castle") == clip  # cached


def test_fetch_clip_none_and_no_partial_file_when_ffmpeg_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    fake_net(monkeypatch, [{"identifier": "castle1", "title": "The Old Castle", "subject": "castle", "licenseurl": "x"}])
    def fail(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"partial")
        class R: returncode = 1
        return R()
    import render
    monkeypatch.setattr(render, "_venc", lambda *a: [])
    monkeypatch.setattr(archive_video.subprocess, "run", fail)
    assert archive_video.fetch_clip("old castle") is None
    assert not list(tmp_path.glob("arch-*.mp4"))


def test_clip_for_chain_order(monkeypatch):
    monkeypatch.setattr(config, "PEXELS_KEY", "")
    monkeypatch.setattr(config, "ARCHIVE_VIDEO", True)
    monkeypatch.setattr(footage, "image_for", lambda q: (Path("/tmp/img.jpg"), "c"))
    monkeypatch.setattr(archive_video, "fetch_clip", lambda q, s=10.0: Path("/tmp/v.mp4"))
    assert footage.clip_for("castle") == Path("/tmp/v.mp4")
    monkeypatch.setattr(archive_video, "fetch_clip", lambda q, s=10.0: None)
    assert footage.clip_for("castle") == Path("/tmp/img.jpg")
    monkeypatch.setattr(config, "ARCHIVE_VIDEO", False)
    monkeypatch.setattr(archive_video, "fetch_clip", lambda q, s=10.0: pytest.fail("archive disabled"))
    assert footage.clip_for("castle") == Path("/tmp/img.jpg")


def test_description_only_match_is_not_relevant():
    doc = {"title": "Crossroads", "subject": "Classic TV; Crime", "description": "An old flame tries to blackmail her."}
    assert archive_video.relevant(doc, "candle flame") is False


def test_collections_are_footage_not_tv_drama():
    assert set(archive_video.COLLECTIONS) == {"silent_films", "prelinger", "nasa"}
