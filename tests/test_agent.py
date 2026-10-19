import datetime as dt
import fcntl
import json

import agent
import agentlog
import channelwatch
import config
import discover
import editprofile
import growth
import pytest
import strategy
from test_discover import Req

NOW = dt.datetime(2026, 10, 19, 6, 30, tzinfo=dt.timezone.utc)
IDS = [f"UC{i:022d}" for i in range(4)]
EDIT = {"kind": "edit", "text": "Make narration a little louder", "why": "w", "evidence": ["e"], "profile": {"target_lufs": -15}}
TOPIC = {"kind": "topic", "text": "The vanishing village of Hoia Baciu", "why": "w", "evidence": []}
TITLE = {"kind": "title", "text": "Put a number in the title", "why": "w", "evidence": []}
SCHED = {"kind": "schedule", "text": "Publish on Fridays at six", "why": "w", "evidence": []}


class FakeYT:
    def search(self):
        class S:
            def list(self, **kw):
                return Req({"items": [{"id": {"channelId": i}} for i in IDS[1:]]})
        return S()

    def channels(self):
        class C:
            def list(self, **kw):
                if kw.get("mine"):
                    return Req({"items": [{"id": IDS[0], "snippet": {"title": "Mine"}, "statistics": {"subscriberCount": "12", "viewCount": "900", "videoCount": "1"},
                                           "contentDetails": {"relatedPlaylists": {"uploads": "UU0"}}}]})
                ids = kw["id"].split(",")
                return Req({"items": [{"id": i, "snippet": {"title": f"T-{i}"}, "statistics": {"subscriberCount": "50000", "viewCount": "5000000", "videoCount": "50"},
                                       "contentDetails": {"relatedPlaylists": {"uploads": f"UU-{i}"}}} for i in ids]})
        return C()

    def playlistItems(self):
        class P:
            def list(self, **kw):
                return Req({"items": [{"contentDetails": {"videoId": "v1"}}]})
        return P()

    def videos(self):
        class V:
            def list(self, **kw):
                return Req({"items": [{"id": "v1", "snippet": {"title": "A big story", "channelTitle": "Ch", "channelId": IDS[1], "publishedAt": "2026-10-10T00:00:00Z"},
                                       "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT10M"}}]})
        return V()


class BrokenYT:
    def __getattr__(self, name):
        raise RuntimeError("quota exceeded")


def chat_with(*strategies):
    return lambda p: {"strategies": list(strategies)} if "advise" in p else {"fits": IDS}


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    d = tmp_path / "agent"
    monkeypatch.setattr(agentlog, "FILE", d / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(discover, "FILE", d / "discovered.json")
    monkeypatch.setattr(growth, "DIR", d / "own")
    monkeypatch.setattr(strategy, "FILE", d / "strategies.json")
    monkeypatch.setattr(agent, "REPORTS", d / "reports")
    monkeypatch.setattr(agent, "CONFIG_FILE", tmp_path / "agent.json")
    monkeypatch.setattr(agent, "LOCK_FILE", tmp_path / "agent.lock")
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "profile.json")
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    (tmp_path / "topics.json").write_text("[]")
    (tmp_path / "refs.json").write_text(json.dumps([IDS[1]]))


def set_mode(mode):
    agent.save_config({**agent.load_config(), "mode": mode})


def test_default_mode_is_handoff_and_bad_mode_rejected():
    assert agent.load_config()["mode"] == "handoff"
    with pytest.raises(ValueError):
        agent.save_config({"mode": "yolo"})


def test_off_does_nothing():
    set_mode("off")
    assert agent.run(NOW, FakeYT(), chat_with(EDIT)) == {"skipped": "off"}
    assert agent.latest_report() is None and agentlog.recent() == []


def test_handoff_adds_strategies_applies_none(tmp_path):
    got = agent.run(NOW, FakeYT(), chat_with(EDIT, TOPIC))
    assert got["mode"] == "handoff" and got["strategies_added"] == 2 and got["applied"] == 0 and got["errors"] == []
    assert {s["status"] for s in strategy.load()} == {"proposed"}
    assert editprofile.load()["target_lufs"] == -16.0 and json.loads((tmp_path / "topics.json").read_text()) == []
    assert agent.latest_report()["date"] == "2026-10-19"
    assert discover.load() and growth.load_snapshots()[-1]["subscribers"] == 12


def test_automatic_applies_only_edit_and_topic(tmp_path):
    set_mode("automatic")
    got = agent.run(NOW, FakeYT(), chat_with(EDIT, TOPIC, TITLE, SCHED))
    assert got["strategies_added"] == 4 and got["applied"] == 2
    status = {s["kind"]: s["status"] for s in strategy.load()}
    assert status == {"edit": "applied", "topic": "applied", "title": "proposed", "schedule": "proposed"}
    assert editprofile.load()["target_lufs"] == -15.0
    assert json.loads((tmp_path / "topics.json").read_text()) == [TOPIC["text"]]
    assert any(e["kind"] == "applied" for e in agentlog.recent())


def test_second_run_same_day_skipped_and_force_runs_again():
    agent.run(NOW, FakeYT(), chat_with(TITLE))
    assert agent.run(NOW, FakeYT(), chat_with(TITLE)) == {"skipped": "already ran today"}
    assert "skipped" not in agent.run(NOW, FakeYT(), chat_with(TITLE), force=True)


def test_api_failure_recorded_not_raised():
    got = agent.run(NOW, BrokenYT(), chat_with(TITLE))
    assert got["errors"] and got["strategies_added"] == 1  # the model step still ran on empty data
    assert any(e["kind"] == "error" for e in agentlog.recent())


def test_lock_held_returns_locked(tmp_path):
    with open(tmp_path / "agent.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert agent.run(NOW, FakeYT(), chat_with(TITLE)) == {"skipped": "locked"}
