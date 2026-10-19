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
