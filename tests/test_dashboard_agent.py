import json

import agent
import agentlog
import channelwatch
import config
import dashboard
import discover
import editprofile
import growth
import pytest
import strategy


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    d = tmp_path / "agent"
    monkeypatch.setattr(agentlog, "FILE", d / "events.jsonl")
    monkeypatch.setattr(discover, "FILE", d / "discovered.json")
    monkeypatch.setattr(growth, "DIR", d / "own")
    monkeypatch.setattr(strategy, "FILE", d / "strategies.json")
    monkeypatch.setattr(agent, "REPORTS", d / "reports")
    monkeypatch.setattr(agent, "CONFIG_FILE", tmp_path / "agent.json")
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "profile.json")
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")


def test_agent_view_shape_when_nothing_has_run():
    v = dashboard.agent_view()
    assert v["config"]["mode"] == "handoff" and v["events"] == [] and v["unread"] == 0
    assert v["strategies"] == [] and v["report"] is None and v["own"] is None and v["discovered"] == []
    assert set(v) >= {"timer_installed", "refs", "profile"}


def test_config_rejects_unknown_mode_and_saves_valid():
    with pytest.raises(ValueError):
        dashboard.agent_config({"mode": "yolo"})
    assert dashboard.agent_config({"mode": "automatic"})["mode"] == "automatic"
    assert agent.load_config()["mode"] == "automatic"


def test_strategy_apply_edit_changes_profile():
    sid = strategy.add([{"kind": "edit", "text": "Make narration a little louder", "why": "w", "evidence": [], "profile": {"target_lufs": -15}}])[0]["id"]
    row = dashboard.agent_strategy({"id": sid, "action": "apply"})
    assert row["status"] == "applied" and editprofile.load()["target_lufs"] == -15.0


def test_strategy_apply_advice_kind_returns_error_and_dismiss_restore():
    sid = strategy.add([{"kind": "title", "text": "Use a number in the title", "why": "w", "evidence": []}])[0]["id"]
    with pytest.raises(ValueError, match="advice only"):
        dashboard.agent_strategy({"id": sid, "action": "apply"})
    assert dashboard.agent_strategy({"id": sid, "action": "dismiss"})["status"] == "dismissed"
    assert dashboard.agent_strategy({"id": sid, "action": "restore"})["status"] == "proposed"
    with pytest.raises(ValueError):
        dashboard.agent_strategy({"id": sid, "action": "explode"})


def test_read_marks_events_read():
    agentlog.event("info", "x")
    assert dashboard.state()["agent"]["unread"] == 1
    dashboard.agent_read()
    assert dashboard.state()["agent"]["unread"] == 0


def test_agent_is_an_allowed_job():
    assert "agent" in dashboard.ALLOWED_JOBS


def test_timer_counts_as_installed_when_worker_is_alive(monkeypatch):
    import worker

    monkeypatch.setattr(worker, "alive", lambda: True)
    assert dashboard.agent_view()["timer_installed"] is True
    assert dashboard.timer_installed("story-autopilot.timer") is True


def test_profile_update_validates_and_saves():
    got = dashboard.agent_profile({"caption_pos": "top", "motion": 1})
    assert got["caption_pos"] == "top" and got["motion"] == 1 and editprofile.load()["caption_pos"] == "top"
    for bad in ({"caption_pos": "middle"}, {"motion": 7}, {"evil": 1}, {"motion": 1, "evil": 1}, {}):
        with pytest.raises(ValueError):
            dashboard.agent_profile(bad)
