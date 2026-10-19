import datetime as dt
import json

import growth
from test_discover import Req


def vid(i, views, seconds, day):
    return {"id": i, "title": f"t{i}", "views": views, "seconds": seconds, "published": f"2026-10-{day:02d}T10:00:00Z"}


def snap(date, subs, views, recent=()):
    return {"date": date, "subscribers": subs, "views": views, "videos": len(recent), "recent": list(recent)}


def test_analyze_deltas_over_seven_days():
    got = growth.analyze([snap("2026-10-01", 10, 100), snap("2026-10-04", 15, 200), snap("2026-10-08", 25, 400)], [])
    assert got["subs"] == 25 and got["subs_delta_7d"] == 15 and got["views_delta_7d"] == 300


def test_analyze_empty_channel_is_zeros():
    got = growth.analyze([], [])
    assert got["subs"] == 0 and got["best"] == [] and got["uploads_per_week"] == 0 and got["gap_ratio"] == 0
    got = growth.analyze([snap("2026-10-08", 0, 0)], [])
    assert got["shorts_median_views"] == 0 and got["long_median_views"] == 0


def test_analyze_splits_shorts_and_long_and_best():
    recent = [vid("a", 100, 60, 7), vid("b", 300, 59, 6), vid("c", 5000, 600, 5), vid("d", 40, 61, 4)]
    got = growth.analyze([snap("2026-10-08", 5, 9, recent)], [])
    assert got["shorts_median_views"] == 200 and got["long_median_views"] == 2520
    assert [v["id"] for v in got["best"]] == ["c", "b", "a"]
    assert got["uploads_per_week"] == 1.0  # 4 videos in the last 28 days


def test_gap_ratio_unknown_is_zero_and_known_is_ratio():
    s = [snap("2026-10-08", 5, 9, [vid("a", 100, 600, 7)])]
    assert growth.analyze(s, [])["gap_ratio"] == 0
    got = growth.analyze(s, [{"summary": {"median_views": 1000}}, {"summary": {"median_views": 0}}])
    assert got["competitor_median_views"] == 1000 and got["gap_ratio"] == 0.1


def test_snapshot_writes_file_with_fake_yt(tmp_path, monkeypatch):
    monkeypatch.setattr(growth, "DIR", tmp_path)

    class YT:
        def channels(self):
            class C:
                def list(self, **kw):
                    assert kw["mine"] is True
                    return Req({"items": [{"id": "UCx", "snippet": {"title": "Mine"}, "statistics": {"subscriberCount": "7", "viewCount": "70", "videoCount": "2"},
                                           "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]})
            return C()

        def playlistItems(self):
            class P:
                def list(self, **kw):
                    return Req({"items": [{"contentDetails": {"videoId": "v1"}}]})
            return P()

        def videos(self):
            class V:
                def list(self, **kw):
                    return Req({"items": [{"id": "v1", "snippet": {"title": "One", "publishedAt": "2026-10-01T00:00:00Z"},
                                           "statistics": {"viewCount": "33"}, "contentDetails": {"duration": "PT45S"}}]})
            return V()

    now = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)
    got = growth.snapshot(YT(), now)
    assert got["subscribers"] == 7 and got["recent"] == [{"id": "v1", "title": "One", "views": 33, "seconds": 45, "published": "2026-10-01T00:00:00Z"}]
    assert json.loads((tmp_path / "2026-10-19.json").read_text())["channel_id"] == "UCx"
    assert growth.load_snapshots()[-1]["date"] == "2026-10-19"


def test_snapshot_hidden_subscribers_and_no_videos(tmp_path, monkeypatch):
    monkeypatch.setattr(growth, "DIR", tmp_path)

    class YT:
        def channels(self):
            class C:
                def list(self, **kw):
                    return Req({"items": [{"id": "UCx", "snippet": {"title": "Mine"}, "statistics": {"hiddenSubscriberCount": True, "viewCount": "0", "videoCount": "0"},
                                           "contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]})
            return C()

        def playlistItems(self):
            class P:
                def list(self, **kw):
                    return Req({"items": []})
            return P()

    got = growth.snapshot(YT(), dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc))
    assert got["subscribers"] == 0 and got["recent"] == []
