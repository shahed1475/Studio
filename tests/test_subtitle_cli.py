import json
import subprocess

import pytest

import subtitles
import tts

WORDS = [{"s": 0.0, "e": 0.5, "w": "Hello", "i": 0}, {"s": 0.5, "e": 100.0, "w": "there.", "i": 0}]


def folder(tmp_path, **meta):
    d = tmp_path / "doc-x"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"format": "doc", "lines": [{"text": "Hello there."}], **meta}))
    (d / "video.mp4").write_bytes(b"original")
    return d


def test_ensure_words_uses_saved_file(tmp_path, monkeypatch):
    d = folder(tmp_path)
    (d / "words.json").write_text(json.dumps(WORDS))
    monkeypatch.setattr(tts, "timings", lambda *a: pytest.fail("must not regenerate"))
    assert subtitles.ensure_words(d) == WORDS


def test_ensure_words_rejects_mismatched_duration(tmp_path, monkeypatch):
    d = folder(tmp_path)
    monkeypatch.setattr(tts, "timings", lambda lines, work: WORDS)
    monkeypatch.setattr(subtitles, "video_seconds", lambda p, *a, **k: 300.0)
    with pytest.raises(SystemExit, match="do not match"):
        subtitles.ensure_words(d)
    assert not (d / "words.json").exists()


def test_ensure_words_regenerates_and_saves(tmp_path, monkeypatch):
    d = folder(tmp_path)
    monkeypatch.setattr(tts, "timings", lambda lines, work: WORDS)
    monkeypatch.setattr(subtitles, "video_seconds", lambda p, *a, **k: 100.4)
    assert subtitles.ensure_words(d) == WORDS and json.loads((d / "words.json").read_text()) == WORDS


def test_burn_refuses_uploaded_and_shorts_and_already_burned(tmp_path):
    for meta, msg in (({"video_id": "abc"}, "uploaded"), ({"format": "short"}, "Shorts"), ({"subtitles": "burned"}, "already")):
        d = tmp_path / f"d{len(msg)}"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"format": "doc", **meta}))
        with pytest.raises(SystemExit, match=msg):
            subtitles.burn_into_video(d)


def test_burn_keeps_original_when_ffmpeg_fails(tmp_path, monkeypatch):
    d = folder(tmp_path)
    (d / "words.json").write_text(json.dumps(WORDS))
    monkeypatch.setattr(subtitles, "video_seconds", lambda p, *a, **k: 100.4)
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "ffmpeg")
    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(subprocess.CalledProcessError):
        subtitles.burn_into_video(d)
    assert (d / "video.mp4").read_bytes() == b"original" and not (d / "video.tmp.mp4").exists()
    assert "subtitles" not in json.loads((d / "meta.json").read_text())
