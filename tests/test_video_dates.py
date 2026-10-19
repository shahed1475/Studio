import json
import os
import time

import config
import dashboard


def make(tmp_path, name, fmt="short", **meta):
    d = tmp_path / name
    d.mkdir()
    (d / "video.mp4").write_bytes(b"x" * 1000)
    (d / "meta.json").write_text(json.dumps({"title": name, "format": fmt, **meta}))
    return d


def test_every_video_has_a_made_time_in_utc_and_a_when(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = make(tmp_path, "a")
    t = time.mktime((2026, 10, 19, 10, 0, 0, 0, 0, -1))
    os.utime(d / "video.mp4", (t, t))
    v = dashboard.videos()[0]
    assert v["made_at"].endswith("Z") and len(v["made_at"]) == 20
    assert v["when"] == {"kind": "made", "at": v["made_at"]}


def test_uploaded_video_uses_its_upload_time(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make(tmp_path, "a", video_id="abc", uploaded_at="2026-10-20T08:30:00Z", publish_at="2026-10-22T19:00:00Z")
    v = dashboard.videos()[0]
    assert v["when"] == {"kind": "uploaded", "at": "2026-10-20T08:30:00Z"}
    assert v["publish_at"] == "2026-10-22T19:00:00Z" and v["uploaded_at"] == "2026-10-20T08:30:00Z"


def test_uploaded_without_a_recorded_time_falls_back_to_made_time(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make(tmp_path, "a", video_id="abc")
    v = dashboard.videos()[0]
    assert v["when"]["kind"] == "uploaded" and v["when"]["at"] == v["made_at"]


def test_scheduled_video_uses_its_public_time(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make(tmp_path, "a", publish_at="2026-10-24T19:00:00Z")
    assert dashboard.videos()[0]["when"] == {"kind": "scheduled", "at": "2026-10-24T19:00:00Z"}


def test_video_without_a_file_still_lists_with_an_empty_date(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "broken"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"title": "broken"}))
    v = dashboard.videos()[0]
    assert v["made_at"] == "" and v["when"] == {"kind": "made", "at": ""}
