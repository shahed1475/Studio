import json
from datetime import datetime, timezone

import config
import scriptgen
import trendwatch

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
ITEMS = [
    {"id": "a", "title": "The Pied Piper: What Really Happened?", "channel": "C1", "views": 1_000_000, "seconds": 600, "published": "2026-01-01T00:00:00Z", "url": "u1"},
    {"id": "b", "title": "5 Legends That Were True", "channel": "C2", "views": 3_000_000, "seconds": 40, "published": "2026-02-01T00:00:00Z", "url": "u2"},
    {"id": "c", "title": "Hamelin: the real story", "channel": "C3", "views": 200_000, "seconds": 900, "published": "2026-03-01T00:00:00Z", "url": "u3"},
]


def test_iso_seconds():
    assert trendwatch.iso_seconds("PT43S") == 43
    assert trendwatch.iso_seconds("PT10M13S") == 613
    assert trendwatch.iso_seconds("PT1H2M") == 3720
    assert trendwatch.iso_seconds("P0D") == 0


def test_summarize_videos_numbers_and_patterns():
    s = trendwatch.summarize_videos(ITEMS)
    assert s["median_views"] == 1_000_000
    assert round(s["short_share"], 2) == 0.33
    assert s["avg_minutes"] == 12.5  # mean of the two long videos: (600 + 900) / 2 / 60
    assert s["patterns"] == {"question": 1, "real_story": 2, "number": 1, "colon": 2}


def test_summarize_empty():
    s = trendwatch.summarize_videos([])
    assert s["median_views"] == 0 and s["short_share"] == 0 and s["patterns"]["question"] == 0


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(trendwatch, "DATA_DIR", tmp_path / "trends")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(trendwatch, "search_niche", lambda queries, yt=None: ITEMS)
    monkeypatch.setattr(trendwatch, "search_fresh", lambda *a, **k: [])  # no network in tests


def test_run_writes_digest_and_original_ideas(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": ["The Pied Piper: What Really Happened?", "The Lost Bells of a Drowned Village", "Why the Raven Guards the Tower"]})
    path = trendwatch.run(NOW)
    d = json.loads(path.read_text())
    assert path.name == "2026-W43.json" and d["summary"]["median_views"] == 1_000_000 and len(d["videos"]) == 3
    assert d["ideas"] == ["The Lost Bells of a Drowned Village", "Why the Raven Guards the Tower"]  # never a scraped title
    assert not (tmp_path / "topics.json").exists()  # proposals only: a person decides what enters the queue


def test_run_survives_api_failure(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    def boom(queries, yt=None):
        raise RuntimeError("quotaExceeded")
    monkeypatch.setattr(trendwatch, "search_niche", boom)
    path = trendwatch.run(NOW)
    d = json.loads(path.read_text())
    assert "quotaExceeded" in d["error"] and d["ideas"] == [] and not (tmp_path / "topics.json").exists()


def test_run_is_limited_to_once_a_day(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": []})
    trendwatch.run(NOW)
    calls = []
    monkeypatch.setattr(trendwatch, "search_niche", lambda q, yt=None: calls.append(1) or ITEMS)
    trendwatch.run(NOW.replace(hour=20))
    assert calls == []


# ---- fresh outliers: what is taking off now, judged against the size of the channel that made it
class _Call:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


class FakeYT:
    """search -> ids; videos -> stats; channels -> subscriber counts. Counts every search (100 quota units each)."""

    def __init__(self, videos, subs):
        self.videos_, self.subs, self.searches = videos, subs, []

    def search(self):
        outer = self
        return type("S", (), {"list": lambda s, **k: (outer.searches.append(k), _Call({"items": [{"id": {"videoId": v["id"]}} for v in outer.videos_]}))[1]})()

    def videos(self):
        outer = self
        return type("V", (), {"list": lambda s, part, id: _Call({"items": [
            {"id": v["id"], "snippet": {"title": v["title"], "channelTitle": v["channel"], "channelId": v["cid"], "publishedAt": v["at"]},
             "statistics": {"viewCount": str(v["views"])}, "contentDetails": {"duration": v["dur"]}} for v in outer.videos_ if v["id"] in id.split(",")]})})()

    def channels(self):
        outer = self
        return type("C", (), {"list": lambda s, part, id: _Call({"items": [
            {"id": c, "statistics": ({"hiddenSubscriberCount": True} if n is None else {"subscriberCount": str(n)})} for c, n in outer.subs.items() if c in id.split(",")]})})()


def _v(i, views, dur, days_ago, cid="c1", title=None):
    at = (NOW - __import__("datetime").timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": f"v{i}", "title": title or f"Video {i}", "channel": f"Ch {cid}", "cid": cid, "views": views, "dur": dur, "at": at}


def test_outlier_score_compares_views_per_day_with_channel_size_and_floors_tiny_channels():
    assert trendwatch.outlier_score(10_000, 1_000, 10) == 1.0
    assert trendwatch.outlier_score(10_000, 10, 10) == 2.0  # a 10-subscriber channel is treated as 500, so one lucky view count cannot explode the score
    assert trendwatch.outlier_score(100, 1_000, 0) == 0.1  # a video from today counts as one day old, never a division by zero


def test_search_fresh_ranks_small_channels_that_beat_their_size_above_big_channels_and_drops_old_and_wrong_length():
    yt = FakeYT([_v(1, 200_000, "PT9M", 3, "big"), _v(2, 60_000, "PT7M", 3, "small"), _v(3, 900_000, "PT8M", 40, "small"), _v(4, 50_000, "PT30S", 2, "small"), _v(5, 80_000, "PT6M", 2, "hid")],
                {"big": 2_000_000, "small": 3_000, "hid": None})
    got = trendwatch.search_fresh(["q"], yt, NOW, kind="doc")
    assert [g["id"] for g in got] == ["v2", "v5", "v1"]  # v3 is 40 days old, v4 is a Short
    assert got[0]["score"] > got[1]["score"] > got[2]["score"] and got[0]["subs"] == 3_000 and got[1]["subs"] is None
    assert len(yt.searches) == 1 and yt.searches[0]["order"] == "viewCount" and "publishedAfter" in yt.searches[0]


def test_search_fresh_for_shorts_keeps_only_vertical_length_videos_and_asks_for_short_ones():
    yt = FakeYT([_v(1, 90_000, "PT45S", 2, "a"), _v(2, 90_000, "PT8M", 2, "a")], {"a": 1_000})
    got = trendwatch.search_fresh(["q"], yt, NOW, kind="short")
    assert [g["id"] for g in got] == ["v1"] and yt.searches[0]["videoDuration"] == "short"


def test_search_fresh_never_spends_more_than_the_search_budget_and_survives_an_empty_answer():
    yt = FakeYT([], {})
    assert trendwatch.search_fresh(["a", "b", "c", "d", "e", "f"], yt, NOW, kind="doc") == [] and len(yt.searches) == trendwatch.FRESH_SEARCHES


def test_run_stores_fresh_outliers_with_a_length_hint_and_a_failure_there_keeps_the_rest(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": []})
    mk = lambda i, s, secs: {"id": f"f{i}", "title": f"T{i}", "score": s, "seconds": secs, "views": 1000, "subs": 100, "channel": "c", "url": "u"}
    monkeypatch.setattr(trendwatch, "search_fresh", lambda q, yt=None, now=None, kind="doc": [mk(1, 5, 480), mk(2, 4, 600), mk(3, 3, 720)] if kind == "doc" else [mk(4, 9, 40), mk(5, 8, 50)])
    d = json.loads(trendwatch.run(NOW).read_text())
    assert [v["id"] for v in d["fresh"]["docs"]] == ["f1", "f2", "f3"] and d["fresh"]["hint"] == {"doc_minutes": 10.0, "short_seconds": 45}
    monkeypatch.setattr(trendwatch, "DATA_DIR", tmp_path / "t2")
    monkeypatch.setattr(trendwatch, "search_fresh", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("quotaExceeded")))
    d2 = json.loads(trendwatch.run(NOW).read_text())
    assert len(d2["videos"]) == 3 and "quotaExceeded" in d2["fresh"]["error"] and d2["fresh"]["docs"] == []


def test_the_length_hint_ignores_multi_hour_sleep_videos_that_would_make_it_meaningless():
    docs = [{"seconds": 9000}, {"seconds": 10000}, {"seconds": 480}, {"seconds": 600}, {"seconds": 720}]
    assert trendwatch.fresh_hint({"docs": docs, "shorts": []}) == {"doc_minutes": 10.0, "short_seconds": 0}
    assert trendwatch.fresh_hint({"docs": [{"seconds": 9000}], "shorts": []})["doc_minutes"] == 0
