import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


import pytest


@pytest.fixture(autouse=True)
def _isolate_autopilot_log(tmp_path, monkeypatch):
    import autopilot

    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")


@pytest.fixture(autouse=True)
def _isolate_agent_files(tmp_path, monkeypatch):
    """No test may write the owner's real activity feed, inbox or lessons (tests/test_duplicates.py once filled the local feed with 34 invented 'Roswell Incident' events)."""
    import agentbus
    import agentlog
    import lessons

    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentbus, "FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(lessons, "FILE", tmp_path / "lessons.jsonl")


@pytest.fixture(autouse=True)
def _isolate_growth_files(tmp_path, monkeypatch):
    """No test may write the shipped rules file (a fake policy change once left a pending change in config/rules.json) or the growth, policy-hold and action files."""
    import shutil

    import actionlog
    import diagnose
    import drift
    import growthdata
    import policyclass
    import rulesfile

    import newswatch

    monkeypatch.setattr(newswatch, "_staff_service", lambda: None)  # no test builds a real YouTube client from a login that happens to be on this machine
    shipped = rulesfile.FILE
    iso = tmp_path / "_growth_isolated"
    iso.mkdir()
    private = iso / "rules.json"
    shutil.copy(shipped, private)
    monkeypatch.setattr(rulesfile, "FILE", private)
    monkeypatch.setattr(rulesfile, "STATE", iso / "rules_state.json")
    monkeypatch.setattr(policyclass, "CLASS_FILE", iso / "policy_class.json")
    monkeypatch.setattr(policyclass, "HOLD_FILE", iso / "policy_hold.json")
    monkeypatch.setattr(actionlog, "ACTIONS", iso / "actions.json")
    monkeypatch.setattr(actionlog, "EDITS", iso / "edits.json")
    monkeypatch.setattr(growthdata, "FILE", iso / "metrics_videos.json")
    monkeypatch.setattr(growthdata, "DAILY", iso / "metrics_daily.json")
    monkeypatch.setattr(drift, "FILE", iso / "metrics_daily.json")
    monkeypatch.setattr(diagnose, "FILE", iso / "diagnoses.json")
    import learner

    monkeypatch.setattr(learner, "WEEKLY", iso / "weekly.json")
    monkeypatch.setattr(learner, "QUEUED", iso / "queued_longs.json")
    monkeypatch.setattr(learner, "REPORTS", iso / "reports")


@pytest.fixture(autouse=True)
def _isolate_trend_inbox(tmp_path, monkeypatch):
    """Trends typed in by a person are the owner's data: no test may read or write the real file."""
    import trendinbox

    monkeypatch.setattr(trendinbox, "FILE", tmp_path / "trend_inbox.json")


@pytest.fixture(autouse=True)
def _isolate_scriptreview(tmp_path, monkeypatch):
    """The script reviewer keeps results and held scripts under data/agent: a test that goes through the gate must never write the real ones."""
    import scriptreview

    monkeypatch.setattr(scriptreview, "FILE", tmp_path / "scriptreview.json")
    monkeypatch.setattr(scriptreview, "HELD", tmp_path / "scriptreview_held")


@pytest.fixture(autouse=True)
def _local_fallback_for_old_tests(monkeypatch):
    """The production default is no local model; most older tests exercise the fallback path, so they opt in here."""
    import llm

    monkeypatch.setitem(llm.DEFAULTS, "local_fallback", True)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    import freemodels

    monkeypatch.setattr(freemodels, "quota", lambda *a, **k: None)  # tests never ask the real OpenRouter
    import risk

    real = risk.credit_left
    monkeypatch.setattr(risk, "credit_left", lambda key, get=None, now=None: real(key, get, now) if get else None)  # only an injected fake reaches the code


@pytest.fixture(autouse=True)
def _no_listening_in_tests(monkeypatch):
    """The studio listens to the narration of a video it approves (a model call). No test may do that by accident; the tests of the check itself switch it on and use a fake model."""
    import voicecheck

    monkeypatch.setattr(voicecheck, "ENABLED", False)
