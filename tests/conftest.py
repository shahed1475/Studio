import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


import pytest


@pytest.fixture(autouse=True)
def _isolate_autopilot_log(tmp_path, monkeypatch):
    import autopilot

    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")


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
