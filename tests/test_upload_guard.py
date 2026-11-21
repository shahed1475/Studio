import json
from datetime import datetime, timezone

import pytest

import config
import upload


def make(out, name, **meta):
    d = out / name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps(meta))
    (d / "video.mp4").write_bytes(b"x")
    return d


def test_uploads_today_counts_only_today(tmp_path):
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    make(tmp_path, "a", uploaded_at="2026-10-19T03:00:00Z")
    make(tmp_path, "b", uploaded_at="2026-10-18T23:59:00Z")
    make(tmp_path, "c")
    assert upload.uploads_today(tmp_path, now) == 1


def test_upload_refuses_when_held(tmp_path):
    d = make(tmp_path, "h", approved=True, hold=True, title="t", description="d", tags=[])
    with pytest.raises(SystemExit, match="hold"):
        upload.upload(d)


def test_upload_refuses_at_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(config, "MAX_UPLOADS_PER_DAY", 1)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    make(tmp_path, "done", uploaded_at=today)
    d = make(tmp_path, "next", approved=True, title="t", description="d", tags=[])
    with pytest.raises(SystemExit, match="daily"):
        upload.upload(d)


def test_a_record_without_tags_reaches_the_send_instead_of_crashing(tmp_path, monkeypatch):
    """A meta.json with no tags used to raise KeyError after every approval check had passed (found 19 Nov 2026): the body now uses an empty list."""
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = make(tmp_path, "no-tags", title="A story", approved=True)
    (d / "meta.json").write_text(json.dumps({"title": "A story", "approved": True}))
    monkeypatch.setattr(upload.compliance, "metadata_problems", lambda m: [])
    monkeypatch.setattr(upload.compliance, "final_description", lambda m: "d")

    class Stop(Exception):
        pass

    def reached():
        raise Stop("reached the send")

    monkeypatch.setattr(upload, "_service", reached)
    with pytest.raises(Stop):
        upload.upload(d)
