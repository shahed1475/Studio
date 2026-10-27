import json

import agentlog
import config
import topicqueue
import topicrank

LONG = "The Jersey Devil is a legend of the Pine Barrens. " * 60


def queue(tmp_path, monkeypatch, items):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    config.TOPICS_FILE.write_text(json.dumps(items))


def test_a_topic_whose_words_appear_in_popular_titles_scores_higher():
    sig = [(topicrank.words("Cicada 3301: An Internet Mystery"), 7.6), (topicrank.words("The Jersey Devil of New Jersey"), 5.0)]
    assert topicrank.score("The Jersey Devil", sig) > topicrank.score("The Talking Drum", sig) == 0
    assert topicrank.score("Cicada 3301", sig) > topicrank.score("The Jersey Devil", sig)


def test_viability_needs_an_article_that_names_the_subject_and_a_legend_for_a_legend():
    assert topicrank.viable("The Jersey Devil", LONG) == (True, "")
    assert not topicrank.viable("The Jersey Devil", "short")[0]
    assert "does not mention" in topicrank.viable("The Mary Celeste", LONG)[1]
    town = "Tuckahoe is a town in Westchester. The railroad ran through it. Marble was quarried here. " * 40
    ok, why = topicrank.viable("The Legend of Tuckahoe", town)
    assert not ok and "no legend" in why


def test_pop_best_takes_the_best_viable_topic_and_drops_the_ones_that_cannot_be_made(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Talking Drum", "The Legend of Tuckahoe", "The Jersey Devil"])
    sig = [(topicrank.words("The Jersey Devil of New Jersey"), 5.0), (topicrank.words("Tuckahoe legend"), 9.0)]
    article = {"The Talking Drum": "x" * 100, "The Legend of Tuckahoe": "Tuckahoe is a town. " * 200, "The Jersey Devil": LONG}
    assert topicrank.pop_best("doc", sig, article.get) == "The Jersey Devil"
    assert topicqueue.items() == ["The Talking Drum"]  # the unviable Tuckahoe was dropped, the unranked one waits
    assert any("Dropped a topic" in e["title"] for e in agentlog.recent())
    assert topicrank.pop_best("doc", sig, article.get) is None and topicqueue.items() == []


def test_an_outage_is_not_a_reason_to_drop_topics(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Jersey Devil"])
    import pytest

    def down(t):
        raise ConnectionError("no network")
    with pytest.raises(ConnectionError):
        topicrank.pop_best("doc", [], down)
    assert topicqueue.items() == ["The Jersey Devil"]


def test_pop_best_drops_a_topic_the_premise_screen_refuses_and_takes_the_next(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Jersey Devil", "The Jersey Devil Mystery"])
    sig = [(topicrank.words("The Jersey Devil of New Jersey"), 5.0)]
    article = {"The Jersey Devil": LONG, "The Jersey Devil Mystery": LONG}
    refuse_first = lambda topic, art: (False, "same story as one already made") if topic == "The Jersey Devil" else (True, "")
    assert topicrank.pop_best("doc", sig, article.get, premise_of=refuse_first) == "The Jersey Devil Mystery"
    events = [e for e in agentlog.recent() if "Dropped a topic" in e["title"]]
    assert events and "screened out: same story" in events[0]["detail"] and topicqueue.items() == []


def test_premise_check_reads_the_answer_and_lets_a_topic_through_when_the_model_cannot_answer():
    assert topicrank.premise_check("A", "article", [], chat=lambda p: {"ok": False, "reason": "invented link"}) == (False, "invented link")
    assert topicrank.premise_check("A", "article", [], chat=lambda p: {"ok": True}) == (True, "")

    def boom(p):
        raise RuntimeError("down")

    assert topicrank.premise_check("A", "article", [], chat=boom) == (True, "")
    seen = []
    topicrank.premise_check("Bell Witch", "x", ["What Do the 1817 Bell Farm Accounts Actually Describe?"], chat=lambda p: seen.append(p) or {"ok": True})
    assert "ALREADY MADE: What Do the 1817 Bell Farm" in seen[0]


def test_audit_queue_removes_refused_topics_and_keeps_them_in_a_file(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Jersey Devil", "The Tale of the Nuremberg Trials", "The Talking Drum"])
    monkeypatch.setattr(config, "ROOT", tmp_path)
    article = {"The Jersey Devil": LONG, "The Tale of the Nuremberg Trials": "The Nuremberg Trials legend. " * 80, "The Talking Drum": "x" * 50}
    got = topicrank.audit_queue(article_of=article.get, premise_of=lambda t, a: (False, "a real trial") if "Nuremberg" in t else (True, ""))
    assert [r["topic"] for r in got] == ["The Tale of the Nuremberg Trials", "The Talking Drum"]
    assert topicqueue.items() == ["The Jersey Devil"]
    kept = json.loads((tmp_path / "data" / "removed_topics.json").read_text())
    assert kept[0]["why"].startswith("screened out") and "no source article" in kept[1]["why"]


def test_the_choice_of_a_topic_is_written_to_the_activity_feed_with_its_reason(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Jersey Devil"])
    sig = [(topicrank.words("The Jersey Devil of New Jersey"), 5.0)]
    topicrank.pop_best("doc", sig, {"The Jersey Devil": LONG}.get, premise_of=lambda t, a: (True, ""))
    chose = [e for e in agentlog.recent() if e["title"].startswith("Chose a topic")]
    assert chose and "research score" in chose[0]["detail"] and "premise screen" in chose[0]["detail"]


def test_audit_queue_keeps_a_topic_whose_article_cannot_be_read_and_retries_before_judging(tmp_path, monkeypatch):
    queue(tmp_path, monkeypatch, ["The Jersey Devil", "The Legend of the Wendigo"])
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(topicrank.time, "sleep", lambda s: None)
    calls = {"The Jersey Devil": 0}

    def flaky(topic):
        if topic == "The Jersey Devil":  # a rate-limited first answer, then the article
            calls[topic] += 1
            return None if calls[topic] == 1 else LONG
        return None  # never readable: unknown, not "has no article"

    got = topicrank.audit_queue(article_of=flaky, premise_of=lambda t, a: (True, ""))
    assert got == [] and topicqueue.items() == ["The Jersey Devil", "The Legend of the Wendigo"] and calls["The Jersey Devil"] == 2


def test_the_premise_screen_judges_fit_by_the_channels_own_niche(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "NICHE_FILE", tmp_path / "niche.json")
    seen = []
    (tmp_path / "niche.json").write_text(json.dumps({"id": "space_history", "name": "Space", "audience": "a", "style": "s", "hashtags": ["#a"],
                                                      "channel_angle": "Missions and discoveries from Sputnik to Voyager, told from documented sources"}))
    topicrank.premise_check("Apollo 13", "article", [], chat=lambda p: seen.append(p) or {"ok": True})
    assert "Missions and discoveries from Sputnik to Voyager" in seen[0] and "neither a legend" not in seen[0]  # a space mission is not refused for being no legend
    (tmp_path / "niche.json").write_text(json.dumps({"name": "Mystery, history and folklore stories", "audience": "a", "style": "s", "channel_angle": "Folk tales", "hashtags": ["#a"]}))
    topicrank.premise_check("The Bell Witch", "article", [], chat=lambda p: seen.append(p) or {"ok": True})
    assert "neither a legend, myth, folktale nor a well-documented historical mystery" in seen[1]  # the owner's studio keeps its wording


def test_signals_weight_a_video_taking_off_now_above_an_old_one_with_the_same_views(monkeypatch):
    import channelwatch
    import trendwatch

    old = {"title": "Old Bell Legend", "views": 100_000}
    now_ = {"title": "Fresh Lantern Legend", "views": 100_000, "score": 99.0}
    monkeypatch.setattr(trendwatch, "latest", lambda: {"videos": [old], "fresh": {"docs": [now_], "shorts": [{"title": "Quick Mirror Tale", "views": 50_000, "score": 0.0}]}})
    monkeypatch.setattr(channelwatch, "latest", lambda: None)
    sig = dict((tuple(sorted(w)), wt) for w, wt in topicrank.signals())
    heavy, light = sig[tuple(sorted(topicrank.words("Fresh Lantern Legend")))], sig[tuple(sorted(topicrank.words("Old Bell Legend")))]
    assert heavy > light * 1.5 and heavy <= light * 2.01  # up to double, never more
    assert sig[tuple(sorted(topicrank.words("Quick Mirror Tale")))] > 0  # a Short with no outlier score still counts, unboosted


def test_a_digest_without_fresh_data_still_gives_the_old_signals(monkeypatch):
    import channelwatch
    import trendwatch

    monkeypatch.setattr(trendwatch, "latest", lambda: {"videos": [{"title": "Old Bell Legend", "views": 1000}]})
    monkeypatch.setattr(channelwatch, "latest", lambda: None)
    assert len(topicrank.signals()) == 1


def test_a_reference_channels_fresh_hit_counts_once_and_weighs_more_than_a_plain_top_video_with_the_same_views(monkeypatch):
    import channelwatch
    import trendwatch

    monkeypatch.setattr(trendwatch, "latest", lambda: None)
    hit = {"title": "Fresh Lantern Legend", "views": 50_000, "score": 9.0}
    plain = {"title": "Old Bell Legend", "views": 50_000}
    only_fresh = {"title": "Newest Mirror Tale", "views": 8_000, "score": 3.0}
    monkeypatch.setattr(channelwatch, "latest", lambda: {"channels": [{"top": [hit, plain], "fresh": [hit, only_fresh]}]})
    sig = topicrank.signals()
    by = {tuple(sorted(w)): wt for w, wt in sig}
    assert len(sig) == 3  # the hit that is also in `top` is not counted twice
    assert by[tuple(sorted(topicrank.words("Fresh Lantern Legend")))] > by[tuple(sorted(topicrank.words("Old Bell Legend")))] * 1.5
    assert by[tuple(sorted(topicrank.words("Newest Mirror Tale")))] > 0
