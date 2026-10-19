import json
from datetime import datetime, timezone

import pytest

import channelwatch
import config
import scriptgen

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


class Call:
    def __init__(self, res):
        self.res = res

    def execute(self):
        return self.res


class FakeYT:
    """Just enough of the YouTube client: channels, playlistItems, videos."""
    def __init__(self, videos, fail=False):
        self.vids, self.fail, self.calls = videos, fail, []

    def channels(self):
        outer = self
        class C:
            def list(self, **kw):
                outer.calls.append(("channels", kw))
                if outer.fail:
                    raise RuntimeError("quotaExceeded")
                return Call({"items": [{"id": "UC123", "snippet": {"title": "Legend Lab"}, "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]})
        return C()

    def playlistItems(self):
        outer = self
        class P:
            def list(self, **kw):
                return Call({"items": [{"contentDetails": {"videoId": v["id"]}} for v in outer.vids]})
        return P()

    def videos(self):
        outer = self
        class V:
            def list(self, **kw):
                return Call({"items": [{"id": v["id"], "snippet": {"title": v["title"], "channelTitle": "Legend Lab", "channelId": "UC123", "publishedAt": "2026-01-01T00:00:00Z"},
                                         "statistics": {"viewCount": str(v["views"])}, "contentDetails": {"duration": f"PT{v['sec']}S"}} for v in outer.vids]})
        return V()


VIDS = [{"id": f"v{i}", "title": f"Story {i}?", "views": (i + 1) * 1000, "sec": 40 + i} for i in range(8)]


@pytest.mark.parametrize("ref,expected", [
    ("@LegendLab", {"handle": "@LegendLab"}),
    ("https://www.youtube.com/@LegendLab", {"handle": "@LegendLab"}),
    ("https://youtube.com/@LegendLab/shorts?si=abc", {"handle": "@LegendLab"}),
    ("UC1234567890abcdefghijkl", {"id": "UC1234567890abcdefghijkl"}),
    ("https://www.youtube.com/channel/UC1234567890abcdefghijkl", {"id": "UC1234567890abcdefghijkl"}),
])
def test_parse_ref(ref, expected):
    assert channelwatch.parse_ref(ref) == expected


@pytest.mark.parametrize("bad", ["", "hello world", "https://example.com/@x", "@", "javascript:alert(1)"])
def test_parse_ref_rejects(bad):
    with pytest.raises(ValueError):
        channelwatch.parse_ref(bad)


def test_breakdown_returns_top_five_by_views_with_summary():
    out = channelwatch.breakdown(FakeYT(VIDS), "@LegendLab")
    assert out["channel"] == "Legend Lab" and [v["views"] for v in out["top"]] == [8000, 7000, 6000, 5000, 4000]
    assert out["summary"]["median_views"] == 4500 and out["scanned"] == 8


def test_refs_add_remove_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    for i in range(channelwatch.MAX_REFS):
        channelwatch.add_ref(f"@chan{i:02d}")
    channelwatch.add_ref("@chan00")  # duplicate ignored
    assert len(channelwatch.load_refs()) == 40
    with pytest.raises(ValueError, match="at most 40"):
        channelwatch.add_ref("@chan99")
    channelwatch.remove_ref("@chan00")
    assert "@chan00" not in channelwatch.load_refs() and "@chan00" not in channelwatch.load_meta()


def test_run_writes_digest_with_original_proposals(tmp_path, monkeypatch):
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(channelwatch, "DATA_DIR", tmp_path / "ch")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    channelwatch.add_ref("@LegendLab")
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": ["Story 7?", "The Bell That Rang Under the Sea", "Why Sailors Feared the Green Flash"]})
    path = channelwatch.run(NOW, FakeYT(VIDS))
    d = json.loads(path.read_text())
    assert path.name == "2026-W43.json" and d["channels"][0]["channel"] == "Legend Lab"
    assert d["ideas"] == ["The Bell That Rang Under the Sea", "Why Sailors Feared the Green Flash"]  # a copied title is dropped
    assert not (tmp_path / "topics.json").exists()  # proposals only


def test_run_without_channels_and_with_api_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(channelwatch, "DATA_DIR", tmp_path / "ch")
    d = json.loads(channelwatch.run(NOW, FakeYT(VIDS)).read_text())
    assert d["channels"] == [] and "no reference channels" in d["note"]
    channelwatch.add_ref("@LegendLab")
    (tmp_path / "ch" / "2026-W43.json").unlink()
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": []})
    d = json.loads(channelwatch.run(NOW, FakeYT(VIDS, fail=True)).read_text())
    assert d["channels"][0]["error"].startswith("RuntimeError") and d["ideas"] == []


def test_suggest_channels_from_trends():
    trends = {"videos": [{"channel": "A", "channel_id": "UCa", "views": 5}, {"channel": "A", "channel_id": "UCa", "views": 9},
                         {"channel": "B", "channel_id": "UCb", "views": 100}, {"channel": "C", "channel_id": "UCc", "views": 1}, {"channel": "C", "channel_id": "UCc", "views": 2}]}
    got = channelwatch.suggest(trends)
    assert [g["channel_id"] for g in got] == ["UCa", "UCc"]  # seen at least twice, most views first


def test_empty_digest_from_before_channels_were_added_is_redone_the_same_day(tmp_path, monkeypatch):
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(channelwatch, "DATA_DIR", tmp_path / "ch")
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": []})
    assert json.loads(channelwatch.run(NOW, FakeYT(VIDS)).read_text())["channels"] == []
    channelwatch.add_ref("@LegendLab")
    assert json.loads(channelwatch.run(NOW, FakeYT(VIDS)).read_text())["channels"][0]["channel"] == "Legend Lab"
    calls = FakeYT(VIDS)
    channelwatch.run(NOW, calls)  # a filled digest is kept: still once a day
    assert calls.calls == []


def test_meta_records_who_added_a_channel_and_counts_the_agents(tmp_path, monkeypatch):
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    channelwatch.add_ref("@mine")
    channelwatch.add_ref("UC" + "a" * 22, source="agent", info={"title": "Found one", "why": "fits"})
    meta = channelwatch.load_meta()
    assert meta["@mine"]["source"] == "user" and meta["UC" + "a" * 22]["source"] == "agent" and meta["UC" + "a" * 22]["title"] == "Found one"
    assert channelwatch.auto_count() == 1
    channelwatch.remove_ref("UC" + "a" * 22)
    assert channelwatch.auto_count() == 0


def test_breakdown_reports_latest_upload_and_videos_in_the_last_year():
    out = channelwatch.breakdown(FakeYT(VIDS), "@LegendLab", now=NOW)
    assert out["latest"] == "2026-01-01T00:00:00Z" and out["recent_year"] == 8
    later = datetime(2028, 1, 1, tzinfo=timezone.utc)
    assert channelwatch.breakdown(FakeYT(VIDS), "@LegendLab", now=later)["recent_year"] == 0
    assert channelwatch.is_active({"recent_year": 3}) and not channelwatch.is_active({"recent_year": 2})
