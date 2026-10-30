"""The owner's weekly programme (30 Oct 2026): four films a week, day 1 a mystery from history, day 2 an unsolved crime or case, day 3 a famous person, day 4 what is trending on the channel's
subject; six Shorts, five from those films and the sixth copying what our best Short did. The studio keeps the rotation by looking at its last three films, not at the calendar, so a late
film or a skipped day does not break it. It PREFERS the wanted kind: if none is queued the best topic is made instead and the feed says so."""
import json
from datetime import datetime, timezone

import agentlog
import config
import topicqueue
import topicrank
import weekplan

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
ART = "The case of the murder is described here. " * 80


def test_the_rotation_is_mystery_then_case_then_person_then_trending_then_again():
    assert weekplan.next_long_kind([]) == "mystery"
    assert weekplan.next_long_kind(["mystery"]) == "case"
    assert weekplan.next_long_kind(["case", "mystery"]) == "person"
    assert weekplan.next_long_kind(["person", "case", "mystery"]) == "trending"
    assert weekplan.next_long_kind(["event", "person", "legend"]) == "mystery"   # what the last three were not is wanted next, in the owner's order
    assert weekplan.next_long_kind(["trending", "legend", "event"]) == "mystery"


def test_the_last_three_films_are_read_from_the_records_newest_first_ignoring_held_ones_and_shorts():
    metas = [{"format": "doc", "made_at": "2026-10-20T00:00:00Z", "topic": "Cleopatra queen pharaoh"},
             {"format": "doc", "made_at": "2026-10-25T00:00:00Z", "topic": "The Zodiac Killer unsolved murders"},
             {"format": "doc", "made_at": "2026-10-28T00:00:00Z", "topic": "The Lost Army vanished", "hold": True},
             {"format": "short", "made_at": "2026-10-29T00:00:00Z", "topic": "The Voynich manuscript mystery"},
             {"format": "doc", "made_at": "2026-10-27T00:00:00Z", "topic": "The Voynich manuscript mystery cipher"}]
    assert weekplan.recent_doc_kinds(metas) == ["mystery", "case", "person"]


def queue(tmp_path, monkeypatch, items):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    config.TOPICS_FILE.write_text(json.dumps(items))


def article(topic):
    return (f"{topic}. " + "Mystery and the vanished army of the desert, the lost city, and the unsolved murder case, the investigation and the killer. " * 40)


def test_the_wanted_kind_is_taken_first_even_when_another_kind_scores_higher(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Lost Army vanished mystery", "The Zodiac Killer unsolved murders"])
    sig = [(topicrank.words("Lost Army vanished mystery"), 9.0)]
    assert topicrank.pop_best("doc", sig, article, want_kind="case") == "The Zodiac Killer unsolved murders"
    assert topicqueue.items() == ["The Lost Army vanished mystery"]


def test_when_no_topic_of_the_wanted_kind_is_queued_the_best_topic_is_made_and_the_feed_says_so(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Lost Army vanished mystery"])
    assert topicrank.pop_best("doc", [], article, want_kind="person") == "The Lost Army vanished mystery"
    assert any("wanted" in e["detail"] and "person" in e["detail"] for e in agentlog.recent(5))


def test_trending_and_no_wish_mean_the_plain_ranking(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Zodiac Killer unsolved murders", "The Lost Army vanished mystery"])
    sig = [(topicrank.words("Lost Army vanished mystery"), 9.0)]
    assert topicrank.pop_best("doc", sig, article, want_kind="trending") == "The Lost Army vanished mystery"
    queue(tmp_path, monkeypatch, ["The Zodiac Killer unsolved murders", "The Lost Army vanished mystery"])
    assert topicrank.pop_best("doc", sig, article) == "The Lost Army vanished mystery"


def test_the_sixth_short_of_the_week_is_the_winner_copy_once_five_are_made():
    cfg = {"weekly": {"enabled": True, "short_from_long": 5}}
    week = lambda n, held=0: [{"format": "short", "made_at": f"2026-10-{24 + i}T00:00:00Z"} for i in range(n)] + [{"format": "short", "made_at": "2026-10-28T00:00:00Z", "hold": True}] * held
    assert weekplan.winner_due(week(4), cfg, NOW) is False
    assert weekplan.winner_due(week(5), cfg, NOW) is True
    assert weekplan.winner_due(week(5, held=3), cfg, NOW) is True     # held Shorts do not count
    assert weekplan.winner_due(week(6), cfg, NOW) is False             # the week's six are made
    assert weekplan.winner_due(week(5), {"weekly": {"enabled": False}}, NOW) is False and weekplan.winner_due(week(5), {}, NOW) is False
    old = [{"format": "short", "made_at": "2026-10-01T00:00:00Z"}] * 5
    assert weekplan.winner_due(old, cfg, NOW) is False                  # last month's Shorts are not this week's


# ---- Autopilot: the sixth Short is a standalone copy of the winner, not another clip ----
import autopilot
import run
import shortpick

A_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
A_CFG = {**autopilot.DEFAULTS, "enabled": True, "prepare_hours": 72}


def plan(**state):
    st = {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "news_pending": 0, "videos": [], **state}
    return [a["do"] for a in autopilot.plan_actions(st, A_CFG, A_NOW)]


def test_normally_a_short_is_clipped_from_our_own_film_and_the_sixth_is_made_standalone_from_the_winner():
    assert "make_clip" in plan(clippable=2) and "make_short" not in plan(clippable=2)
    due = plan(clippable=2, winner_due=True)
    assert "make_short" in due and "make_clip" not in due
    assert "make_short" in plan(clippable=0)  # no film to clip: a standalone Short as before


def test_the_state_carries_the_winner_flag_from_the_records(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    for i in range(5):
        d = tmp_path / f"s{i}"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"format": "short", "made_at": f"2026-10-{24 + i}T00:00:00Z"}))
    on = {**A_CFG, "weekly": {"enabled": True, "short_from_long": 5}}
    assert autopilot._winner_due(on, NOW) is True and autopilot._winner_due(A_CFG, NOW) is False


# ---- shortpick: what our best Short did ----
ROWS = {"a": {"kind": "short", "views_90d": 329, "avg_pct_viewed": 54.0, "retention_at_30s": 54.5, "title": "The Voynich Manuscript: Dates, Owners and Failed Codebreakers", "seconds": 78},
        "b": {"kind": "short", "views_90d": 265, "avg_pct_viewed": 58.0, "retention_at_30s": 53.4, "title": "Thunderbird Mythology: Who Makes the Thunder Roll?", "seconds": 79},
        "c": {"kind": "short", "views_90d": 12, "avg_pct_viewed": 99.0, "title": "A tiny Short", "seconds": 40},
        "d": {"kind": "doc", "views_90d": 999, "avg_pct_viewed": 20.0, "title": "A big film about a king", "seconds": 460}}


def test_the_winner_is_our_best_short_by_views_weighted_by_how_much_was_watched_and_never_a_film_or_a_tiny_sample():
    w = shortpick.winner(ROWS)
    assert w["title"].startswith("The Voynich") and w["kind"] == "mystery" and w["views"] == 329
    assert shortpick.winner({"d": ROWS["d"], "c": ROWS["c"]}) is None  # a film is not a Short; 12 views is not a pattern
    assert shortpick.winner({}) is None


def test_the_topic_the_winner_asks_for_is_its_kind_and_a_missing_or_unreadable_file_asks_for_nothing(tmp_path, monkeypatch):
    import growthdata

    monkeypatch.setattr(growthdata, "FILE", tmp_path / "videos.json")
    assert shortpick.winner() is None  # no file
    (tmp_path / "videos.json").write_text(json.dumps({"videos": ROWS}))
    assert shortpick.winner()["kind"] == "mystery"
    (tmp_path / "videos.json").write_text("not json")
    assert shortpick.winner() is None


def test_the_producer_asks_the_weekly_programme_which_kind_to_make(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUT", tmp_path)
    cfg = {**autopilot.DEFAULTS, "weekly": {"enabled": True, "short_from_long": 5}}
    monkeypatch.setattr(autopilot, "load_config", lambda: cfg)
    assert run._weekly_kind("doc") == "mystery"           # no films yet: day 1 is a mystery
    assert run._weekly_kind("short") is None              # not the sixth yet
    monkeypatch.setattr(autopilot, "load_config", lambda: {**autopilot.DEFAULTS})
    assert run._weekly_kind("doc") is None                # switched off: the plain ranking
