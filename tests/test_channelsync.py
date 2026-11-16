"""channelsync: the server's upload records were lost with the VPS (17 Nov 2026). Before the worker may upload anything, every local video
that is already on the channel must carry its YouTube id, or Autopilot would send it a second time. Read-only towards YouTube."""
import json

import channelsync
import compliance
import records


RETRIES_SEEN = []


class _Call:
    def __init__(self, result):
        self.result = result

    def execute(self, num_retries=0):
        RETRIES_SEEN.append(num_retries)
        return self.result


class FakeYT:
    """Answers the three read calls channelsync makes, with the uploads split over pages of `page` items, like the real API."""

    def __init__(self, videos, page=50):
        self.videos_by_id = {v["id"]: v for v in videos}
        self.order = [v["id"] for v in videos]
        self.page = page
        self.pages_read = 0

    def channels(self):
        return self

    def playlistItems(self):
        return _Items(self)

    def videos(self):
        return _Videos(self)

    def list(self, **kw):  # channels().list
        assert kw.get("mine") is True
        return _Call({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})


class _Items:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part, playlistId, maxResults, pageToken=None):
        assert playlistId == "UU1" and maxResults <= 50
        start = int(pageToken or 0)
        ids = self.yt.order[start:start + self.yt.page]
        self.yt.pages_read += 1
        res = {"items": [{"contentDetails": {"videoId": i}} for i in ids]}
        if start + self.yt.page < len(self.yt.order):
            res["nextPageToken"] = str(start + self.yt.page)
        return _Call(res)


class _Videos:
    def __init__(self, yt):
        self.yt = yt

    def list(self, part, id):
        ids = id.split(",")
        assert len(ids) <= 50, "videos.list takes at most 50 ids"
        return _Call({"items": [self.yt.videos_by_id[i] for i in ids if i in self.yt.videos_by_id]})


def yt_video(vid, title, description="", published="2026-11-10T10:00:00Z", privacy="private", publish_at=None):
    st = {"privacyStatus": privacy}
    if publish_at:
        st["publishAt"] = publish_at
    return {"id": vid, "snippet": {"title": title, "description": description, "publishedAt": published}, "status": st}


def test_channel_videos_follows_every_page():
    vids = [yt_video(f"v{i}", f"title {i}") for i in range(120)]
    yt = FakeYT(vids, page=50)
    got = channelsync.channel_videos(yt)
    assert [v["id"] for v in got] == [f"v{i}" for i in range(120)]
    assert yt.pages_read == 3
    assert got[0] == {"id": "v0", "title": "title 0", "description": "", "publishedAt": "2026-11-10T10:00:00Z", "privacyStatus": "private", "publishAt": None}


def test_channel_videos_of_an_empty_channel_is_empty():
    assert channelsync.channel_videos(FakeYT([])) == []


def test_channel_videos_at_exact_page_boundaries():
    for n in (50, 100):
        yt = FakeYT([yt_video(f"v{i}", "t") for i in range(n)], page=50)
        assert len(channelsync.channel_videos(yt)) == n
        assert yt.pages_read == n // 50


def test_channel_videos_tolerates_missing_fields():
    yt = FakeYT([{"id": "bare", "snippet": {}, "status": {}}])
    assert channelsync.channel_videos(yt) == [{"id": "bare", "title": "", "description": "", "publishedAt": "", "privacyStatus": "", "publishAt": None}]


def test_match_adopts_a_video_with_the_same_title():
    metas = [{"slug": "a", "title": "The Lost Army", "approved": True}]
    plan = channelsync.match(metas, [{"id": "YT1", "title": "The Lost Army", "description": "", "publishedAt": "2026-11-12T08:00:00Z", "privacyStatus": "private", "publishAt": "2026-11-20T14:00:00Z"}])
    assert plan["adopt"] == [{"slug": "a", "video_id": "YT1", "by": "title", "publishedAt": "2026-11-12T08:00:00Z", "publishAt": "2026-11-20T14:00:00Z"}]
    assert plan["unmatched_local"] == [] and plan["conflicts"] == []


def test_match_finds_a_retitled_video_by_its_description():
    meta = {"slug": "b", "title": "New title after a fix", "description": "Fifty thousand Persian soldiers marched into the desert and were never seen again.", "tags": [], "approved": True}
    on_yt = compliance.final_description(meta)
    plan = channelsync.match([meta], [{"id": "YT2", "title": "Old title", "description": on_yt, "publishedAt": "x", "privacyStatus": "private", "publishAt": None}])
    assert [(r["slug"], r["video_id"], r["by"]) for r in plan["adopt"]] == [("b", "YT2", "description")]


def test_match_never_touches_a_folder_that_already_has_an_id():
    metas = [{"slug": "c", "title": "Same", "video_id": "OLD"}, {"slug": "d", "title": "Other"}]
    plan = channelsync.match(metas, [{"id": "NEW", "title": "Same", "description": "", "publishedAt": "x", "privacyStatus": "private", "publishAt": None},
                                     {"id": "OLD", "title": "Same", "description": "", "publishedAt": "x", "privacyStatus": "public", "publishAt": None}])
    assert plan["adopt"] == []
    assert plan["already"] == 1


def test_match_reports_two_folders_claiming_one_video_and_adopts_neither():
    metas = [{"slug": "e1", "title": "Twin", "approved": True}, {"slug": "e2", "title": "Twin", "approved": True}]
    plan = channelsync.match(metas, [{"id": "YT3", "title": "Twin", "description": "", "publishedAt": "x", "privacyStatus": "private", "publishAt": None}])
    assert plan["adopt"] == []
    assert plan["conflicts"] == [{"video_id": "YT3", "slugs": ["e1", "e2"]}]


def test_match_lists_approved_videos_that_are_not_on_the_channel():
    metas = [{"slug": "f", "title": "Never sent", "approved": True}, {"slug": "g", "title": "Draft", "approved": False}]
    plan = channelsync.match(metas, [])
    assert plan["unmatched_local"] == ["f"]


def test_apply_writes_only_the_adopt_rows(tmp_path):
    for slug, meta in {"a": {"title": "A", "approved": True}, "z": {"title": "Z"}}.items():
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "meta.json").write_text(json.dumps(meta))
    plan = {"adopt": [{"slug": "a", "video_id": "YT1", "by": "title", "publishedAt": "2026-11-12T08:00:00Z", "publishAt": "2026-11-20T14:00:00Z"}], "conflicts": [], "unmatched_local": [], "already": 0}
    assert channelsync.apply(tmp_path, plan) == 1
    a = records.read(tmp_path / "a")
    assert a["video_id"] == "YT1" and a["uploaded_at"] == "2026-11-12T08:00:00Z" and a["publish_at"] == "2026-11-20T14:00:00Z" and a["adopted_from_channel"] is True
    assert "video_id" not in records.read(tmp_path / "z")


def test_apply_skips_a_folder_that_got_an_id_in_the_meantime(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "meta.json").write_text(json.dumps({"title": "A", "video_id": "MINE"}))
    plan = {"adopt": [{"slug": "a", "video_id": "YT1", "by": "title", "publishedAt": "x", "publishAt": None}]}
    assert channelsync.apply(tmp_path, plan) == 0
    assert records.read(tmp_path / "a")["video_id"] == "MINE"


def test_a_broken_record_is_listed_and_every_other_video_is_still_checked(tmp_path):
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "meta.json").write_text(json.dumps({"title": "A", "approved": True}))
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "meta.json").write_text("{not json")
    metas = channelsync.local_metas(tmp_path)
    plan = channelsync.match(metas, [{"id": "YT1", "title": "A", "description": "", "publishedAt": "x", "privacyStatus": "private", "publishAt": None}])
    assert plan["unreadable"] == ["bad"]
    assert [r["slug"] for r in plan["adopt"]] == ["good"]
    assert (tmp_path / "bad" / "meta.json").read_text() == "{not json"  # a broken record is reported, never rewritten

def test_apply_run_twice_writes_once(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "meta.json").write_text(json.dumps({"title": "A"}))
    plan = {"adopt": [{"slug": "a", "video_id": "YT1", "by": "title", "publishedAt": "x", "publishAt": None}]}
    assert channelsync.apply(tmp_path, plan) == 1
    assert channelsync.apply(tmp_path, plan) == 0
    assert records.read(tmp_path / "a")["video_id"] == "YT1"


def test_channel_sync_command_reports_a_refused_login_and_writes_nothing(tmp_path, monkeypatch, capsys):
    import pytest

    import config
    import run
    import upload

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "meta.json").write_text(json.dumps({"title": "A", "approved": True}))
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(upload, "_service", lambda: (_ for _ in ()).throw(RuntimeError("invalid_grant")))
    monkeypatch.setattr("sys.argv", ["run.py", "channel-sync", "--apply"])
    with pytest.raises(SystemExit) as e:
        run.main()
    assert e.value.code == 2
    assert "login expired or refused" in capsys.readouterr().out
    assert "video_id" not in records.read(tmp_path / "a")


def test_apply_keeps_going_when_one_record_cannot_be_written(tmp_path, monkeypatch):
    for slug in ("a", "b"):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "meta.json").write_text(json.dumps({"title": slug}))
    real = records.merge

    def merge(folder, changes):
        if folder.name == "a":
            raise OSError("disk full")
        return real(folder, changes)

    monkeypatch.setattr(records, "merge", merge)
    plan = {"adopt": [{"slug": s, "video_id": "YT" + s, "by": "title", "publishedAt": "x", "publishAt": None} for s in ("a", "b")]}
    assert channelsync.apply(tmp_path, plan) == 1
    assert plan["failed"] == [{"slug": "a", "error": "OSError: disk full"}]
    assert records.read(tmp_path / "b")["video_id"] == "YTb"


def test_every_youtube_read_retries_with_the_librarys_backoff():
    """google-api-python-client retries 5xx, 429 and rate-limit 403s with exponential backoff only when execute() gets num_retries; the default is 0."""
    RETRIES_SEEN.clear()
    channelsync.channel_videos(FakeYT([yt_video(f"v{i}", "t") for i in range(60)], page=50))  # 1 channel + 2 list pages + 2 detail batches
    assert len(RETRIES_SEEN) == 5 and set(RETRIES_SEEN) == {channelsync.RETRIES} and channelsync.RETRIES >= 3
