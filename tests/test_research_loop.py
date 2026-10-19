import datetime as dt
import json

import agent
import agentlog
import channelwatch
import config
import pytest
import topicqueue
import trendwatch

NOW = dt.datetime(2026, 10, 20, 6, 30, tzinfo=dt.timezone.utc)
CFG = {"auto_topics": True, "topics_per_day": 3}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(channelwatch, "DATA_DIR", tmp_path / "ch")
    monkeypatch.setattr(trendwatch, "DATA_DIR", tmp_path / "tr")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "output").mkdir()
    topicqueue._write([])
    (tmp_path / "ch").mkdir()
    (tmp_path / "tr").mkdir()


def digests(tmp_path, channel_ideas=(), trend_ideas=()):
    (tmp_path / "ch" / "2026-W43.json").write_text(json.dumps({"ideas": list(channel_ideas)}))
    (tmp_path / "tr" / "2026-W43.json").write_text(json.dumps({"ideas": list(trend_ideas)}))


def test_new_ideas_join_the_queue_a_few_a_day(tmp_path):
    digests(tmp_path, ["The Bell That Rang Under the Sea", "The Lost Garden of Babylon Explained"], ["Why Sailors Feared the Green Flash at Dusk", "The Silent Village of Hoia Baciu"])
    added = agent.queue_ideas(CFG, NOW)
    assert len(added) == 3 and topicqueue.items() == added
    assert any("Added 3 story ideas" in e["title"] for e in agentlog.recent())


def test_an_idea_already_queued_made_or_given_up_on_is_not_added_again(tmp_path):
    topicqueue._write(["The Bell That Rang Under the Sea"])
    old = tmp_path / "output_old" / "x"
    old.mkdir(parents=True)
    (old / "meta.json").write_text(json.dumps({"topic": "The Lost Garden of Babylon Explained", "title": "Babylon"}))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "topic_fails.json").write_text(json.dumps({"The Silent Village of Hoia Baciu": 2}))
    digests(tmp_path, ["The Bell That Rang Under the Sea!", "The Lost Garden of Babylon: Explained", "The Silent Village of Hoia Baciu"], ["A brand new idea about the Roanoke Colony"])
    assert agent.queue_ideas(CFG, NOW) == ["A brand new idea about the Roanoke Colony"]


def test_off_switch_and_a_full_queue_add_nothing(tmp_path):
    digests(tmp_path, ["Some fresh idea about the Library of Alexandria"])
    assert agent.queue_ideas({**CFG, "auto_topics": False}, NOW) == []
    topicqueue._write([f"topic number {i} here" for i in range(agent.MAX_QUEUE)])
    assert agent.queue_ideas(CFG, NOW) == []


def test_briefing_sums_up_videos_queue_and_what_needs_you(tmp_path):
    def vid(name, **m):
        d = tmp_path / "output" / name
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"title": name, **m}))
    vid("live", video_id="abc")
    vid("sched", approved=True, publish_at="2026-10-22T16:30:00Z", title="The Minotaur Legend")
    vid("wait")
    topicqueue._write(["a", "b"])
    agentlog.event("applied", "Fixed: Delphi", "x", now=NOW)
    agentlog.event("error", "Needs your eyes: Titanic", "y", now=NOW)
    text = agent.briefing(NOW, ["c1"], [], ["t1"])
    assert "1 videos live, 1 approved" in text and "1 waiting for a decision" in text
    assert "The Minotaur Legend at 2026-10-22 16:30 UTC" in text and "2 topics queued (1 added today)" in text
    assert "reference channels: 1 added" in text and "fixer: 1 video" in text and "needs you: Needs your eyes: Titanic" in text
    assert agentlog.recent(1)[0]["title"] == "Daily briefing"


def test_topic_settings_are_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "CONFIG_FILE", tmp_path / "agent.json")
    assert agent.load_config()["auto_topics"] is True and agent.load_config()["topics_per_day"] == 3
    assert agent.save_config({**agent.load_config(), "topics_per_day": 5, "auto_topics": False})["topics_per_day"] == 5
    for bad in ({"topics_per_day": 0}, {"topics_per_day": 11}, {"auto_topics": "yes"}):
        with pytest.raises(ValueError):
            agent.save_config({**agent.load_config(), **bad})
