import datetime as dt

import craftlearn

NOW = dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc)


def test_chapter_marks_need_a_real_chapter_list():
    ok = "Intro\n0:00 Start\n1:30 Middle\n12:05 End"
    assert craftlearn.chapter_marks(ok) == [0, 90, 725]
    assert craftlearn.chapter_marks("1:30 Middle\n2:00 B\n3:00 C") == []      # must start at 0:00
    assert craftlearn.chapter_marks("0:00 a\n1:00 b") == []                   # three or more
    assert craftlearn.chapter_marks("0:00 a\n5:00 b\n2:00 c") == []           # ascending
    assert craftlearn.chapter_marks("0:00 a\n1:00:10 b\n1:30:00 c") == [0, 3610, 5400]


def test_compact_keeps_pace_not_text():
    c = craftlearn.compact({"seconds": 600, "views": 5, "published": "2026-01-01T00:00:00Z", "description": "0:00 a\n2:00 b\n6:00 c"})
    assert c == {"s": 600, "v": 5, "p": "2026-01-01T00:00:00Z", "ch": 3, "gap": 240}


def _channel(kind_s, hot_s, n_hot=5, n_cold=6):
    old = (NOW - dt.timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan = [{"s": hot_s, "v": 100_000, "p": old, "ch": 6, "gap": 120} for _ in range(n_hot)]
    scan += [{"s": kind_s, "v": 1_000, "p": old, "ch": 0, "gap": 0} for _ in range(n_cold)]
    return {"scan": scan}


def test_learn_finds_the_length_of_outperformers_per_channel():
    d = {"channels": [_channel(300, 900), _channel(300, 1200)]}
    r = craftlearn.learn(d, NOW)
    b = r["bands"]["doc"]
    assert b["outperformers"] == 10 and 900 <= b["out_median_s"] <= 1200
    assert b["with_chapters_share"] == 1.0 and b["seconds_per_chapter_median"] == 120
    assert "NOT measured" in r["coverage"]


def test_too_few_outperformers_says_nothing():
    r = craftlearn.learn({"channels": [_channel(300, 900, n_hot=3)]}, NOW)
    assert "out_median_s" not in r["bands"]["doc"]


def test_young_and_old_videos_are_ignored():
    young = (NOW - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan = [{"s": 900, "v": 10**7, "p": young, "ch": 0, "gap": 0} for _ in range(20)]
    r = craftlearn.learn({"channels": [{"scan": scan}]}, NOW)
    assert r["videos_used"] == 0


def test_shorts_and_documentaries_are_judged_apart():
    old = (NOW - dt.timedelta(days=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan = [{"s": 45, "v": 500, "p": old, "ch": 0, "gap": 0} for _ in range(10)]
    scan += [{"s": 45, "v": 50_000, "p": old, "ch": 0, "gap": 0} for _ in range(8)]
    scan += [{"s": 1200, "v": 900, "p": old, "ch": 0, "gap": 0} for _ in range(6)]  # a long video must not be compared with the Shorts
    r = craftlearn.learn({"channels": [{"scan": scan}]}, NOW)
    assert r["bands"]["short"]["outperformers"] == 8
    assert r["bands"]["doc"]["outperformers"] == 0
