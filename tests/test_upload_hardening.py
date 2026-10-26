import datetime as dt
import json

import config
import pytest
import upload


class Exec:
    def __init__(self, data=None, chunk=None):
        self.data, self.chunk = data, chunk

    def execute(self):
        return self.data

    def next_chunk(self):
        return None, self.chunk


class FakeYT:
    """What YouTube stores is configurable, so the read-back can be right or wrong."""

    def __init__(self, stored=None, existing=None):
        self.inserted, self.stored, self.existing = [], stored, existing or []

    def videos(self):
        outer = self

        class V:
            def insert(self, part, body, media_body):
                outer.inserted.append(body)
                return Exec(chunk={"id": "NEWID"})

            def list(self, part, id):
                if outer.existing and "," in id or (outer.existing and id == outer.existing[0]["id"]):
                    return Exec({"items": outer.existing})
                if outer.stored is None:
                    return Exec({"items": []})
                return Exec({"items": [{"id": id, "snippet": {"title": outer.stored["title"]},
                                        "status": {"privacyStatus": outer.stored["privacy"], "publishAt": outer.stored.get("publish_at"), "uploadStatus": "uploaded"}}]})
        return V()

    def channels(self):
        return type("C", (), {"list": lambda s, **k: Exec({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})})()

    def playlistItems(self):
        outer = self
        return type("P", (), {"list": lambda s, **k: Exec({"items": [{"contentDetails": {"videoId": e["id"]}} for e in outer.existing]})})()

    def thumbnails(self):
        return type("T", (), {"set": lambda s, **k: Exec({})})()


@pytest.fixture
def vid(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "v1"
    d.mkdir()
    (d / "video.mp4").write_bytes(b"x")
    meta = {"approved": True, "title": "The Title", "description": "d" * 100, "tags": ["a"], "format": "short"}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


def when():
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_upload_is_marked_before_sending_and_read_back_from_youtube_afterwards(vid, monkeypatch):
    pub = when()
    yt = FakeYT(stored={"title": "The Title", "privacy": "private", "publish_at": pub})
    monkeypatch.setattr(upload, "_service", lambda: yt)
    assert upload.upload(vid, "private", pub) == "NEWID"
    meta = json.loads((vid / "meta.json").read_text())
    assert meta["video_id"] == "NEWID" and meta["upload_started"] and meta["upload_check"]["ok"] is True and meta["upload_check"]["privacyStatus"] == "private"
    assert yt.inserted[0]["status"]["privacyStatus"] == "private" and yt.inserted[0]["status"]["containsSyntheticMedia"] is True


def test_a_retry_after_a_crash_finds_the_earlier_upload_and_never_sends_a_second_copy(vid, monkeypatch):
    meta = json.loads((vid / "meta.json").read_text())
    meta["upload_started"] = "2026-10-20T10:00:00Z"  # the earlier attempt began, no video id was written down
    (vid / "meta.json").write_text(json.dumps(meta))
    earlier = {"id": "OLDID", "snippet": {"title": "The Title", "publishedAt": "2026-10-20T10:03:00Z"}}
    yt = FakeYT(existing=[earlier])
    monkeypatch.setattr(upload, "_service", lambda: yt)
    assert upload.upload(vid, "private", when()) == "OLDID"
    assert yt.inserted == [] and json.loads((vid / "meta.json").read_text())["video_id"] == "OLDID"


def test_an_unrelated_older_video_with_the_same_title_does_not_stop_a_real_retry(vid, monkeypatch):
    meta = json.loads((vid / "meta.json").read_text())
    meta["upload_started"] = "2026-10-20T10:00:00Z"
    (vid / "meta.json").write_text(json.dumps(meta))
    old = {"id": "OLD", "snippet": {"title": "The Title", "publishedAt": "2026-09-01T10:00:00Z"}}
    pub = when()
    yt = FakeYT(existing=[old], stored={"title": "The Title", "privacy": "private", "publish_at": pub})
    monkeypatch.setattr(upload, "_service", lambda: yt)
    assert upload.upload(vid, "private", pub) == "NEWID" and len(yt.inserted) == 1


def test_a_mismatch_between_what_was_sent_and_what_youtube_stored_is_recorded_and_shown(vid, monkeypatch, capsys):
    pub = when()
    yt = FakeYT(stored={"title": "The Title", "privacy": "public", "publish_at": None})
    monkeypatch.setattr(upload, "_service", lambda: yt)
    upload.upload(vid, "private", pub)
    check = json.loads((vid / "meta.json").read_text())["upload_check"]
    assert check["ok"] is False and any("privacy is public" in p for p in check["problems"]) and "WARNING" in capsys.readouterr().out


def test_verify_upload_reports_a_video_the_api_does_not_return():
    assert upload.verify_upload(FakeYT(stored=None), "X", {"title": "t", "privacy": "private"})["ok"] is False


class RefusedThumbs(FakeYT):
    def thumbnails(self):
        def refuse(s, **k):
            raise RuntimeError("403 The authenticated user doesn't have permissions to upload and set custom video thumbnails")
        return type("T", (), {"set": refuse})()


def test_a_refused_thumbnail_is_recorded_and_the_owner_is_told_but_the_upload_stands(vid, monkeypatch, tmp_path):
    import agentlog

    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    meta = json.loads((vid / "meta.json").read_text())
    meta["thumbnail"] = "thumbs/thumb-1.jpg"
    (vid / "thumbs").mkdir()
    (vid / "thumbs" / "thumb-1.jpg").write_bytes(b"x")
    (vid / "meta.json").write_text(json.dumps(meta))
    pub = when()
    monkeypatch.setattr(upload, "_service", lambda: RefusedThumbs(stored={"title": "The Title", "privacy": "private", "publish_at": pub}))
    assert upload.upload(vid, "private", pub) == "NEWID"
    saved = json.loads((vid / "meta.json").read_text())
    assert "custom video thumbnails" in saved["thumbnail_error"] and not saved.get("thumbnail_uploaded")
    assert any(e["title"].startswith("Thumbnail was not set") for e in agentlog.recent())


def test_metadata_youtube_would_reject_is_never_sent(vid, monkeypatch):
    meta = json.loads((vid / "meta.json").read_text())
    meta["title"] = "A title with <b>tags</b>"
    (vid / "meta.json").write_text(json.dumps(meta))
    yt = FakeYT()
    monkeypatch.setattr(upload, "_service", lambda: yt)
    with pytest.raises(SystemExit, match="title contains"):
        upload.upload(vid, "private", when())
    assert yt.inserted == [] and "upload_started" not in json.loads((vid / "meta.json").read_text())


def test_a_retry_finds_the_earlier_copy_even_when_the_title_changed_since(vid, monkeypatch):
    import compliance

    meta = json.loads((vid / "meta.json").read_text())
    earlier_description = compliance.final_description(meta)
    meta.update(upload_started="2026-10-20T10:00:00Z", title="A Repaired Title")  # the fixer retitled the video between the crash and the retry
    (vid / "meta.json").write_text(json.dumps(meta))
    earlier = {"id": "OLDID", "snippet": {"title": "The Title", "description": earlier_description, "publishedAt": "2026-10-20T10:03:00Z"}}
    yt = FakeYT(existing=[earlier])
    monkeypatch.setattr(upload, "_service", lambda: yt)
    assert upload.upload(vid, "private", when()) == "OLDID"
    assert yt.inserted == []


def test_two_uploads_of_one_video_at_the_same_moment_send_only_one(vid, monkeypatch):
    import filelock

    yt = FakeYT()
    monkeypatch.setattr(upload, "_service", lambda: yt)
    with filelock.try_locked(vid / ".upload"):  # another process (the dashboard button, a manual command) is sending this video right now
        with pytest.raises(SystemExit, match="being uploaded"):
            upload.upload(vid, "private", when())
    assert yt.inserted == []


def test_the_upload_lock_is_free_again_after_a_refusal_or_a_finished_upload(vid, monkeypatch):
    pub = when()
    yt = FakeYT(stored={"title": "The Title", "privacy": "private", "publish_at": pub})
    monkeypatch.setattr(upload, "_service", lambda: yt)
    assert upload.upload(vid, "private", pub) == "NEWID"
    with pytest.raises(SystemExit, match="already uploaded"):  # not "being uploaded": the lock was released
        upload.upload(vid, "private", pub)
