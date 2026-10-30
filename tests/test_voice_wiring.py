"""The narration listening check is wired in three places and is a WARNING everywhere: the quality gate (--listen), Autopilot's approval step (after the picture check), and a command
(run.py listen <slug>). A model failure, a missing audio model or an empty budget never stops a video."""
import inspect
import json

import pytest

import agentlog
import autopilot
import config
import records
import studiochecks
import voicecheck

GOOD = {"ok": True, "match": 0.99, "words": 1300, "gaps": [], "heard_as": [["chafetz", "chafitz"]], "model": "m", "at": "2026-10-30T15:00:00Z", "parts": 4, "failed_parts": [], "cost": 0.006,
        "coverage": "Listened to 8.4 of 8.4 minutes."}
BAD = {**GOOD, "ok": False, "match": 0.8, "gaps": [{"kind": "missing", "words": 12, "script": "the legend says cambyses sent them", "heard": ""}], "heard_as": []}


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "doc-x"
    d.mkdir()
    records.save(d, {"title": "A Film", "format": "doc", "lines": [{"text": "a line"}]})
    monkeypatch.setattr(voicecheck, "ENABLED", True)
    return d


def test_the_rows_say_what_was_heard_and_only_warn(folder, monkeypatch):
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: GOOD)
    rows = voicecheck.rows(folder)
    assert [r["name"] for r in rows] == ["transcript_matches_script", "names_heard_differently", "listening_coverage"]
    assert all(r["severity"] == "warn" for r in rows) and rows[0]["ok"] and "99" in rows[0]["detail"]
    assert "chafetz" in rows[1]["detail"] and rows[2]["ok"]
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: BAD)
    bad = voicecheck.rows(folder)
    assert not bad[0]["ok"] and "missing" in bad[0]["detail"] and "legend says" in bad[0]["detail"]
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: {"error": "no audio model"})
    err = voicecheck.rows(folder)
    assert len(err) == 1 and err[0]["name"] == "voice_listen" and not err[0]["ok"] and err[0]["severity"] == "warn" and "could not run" in err[0]["detail"]


def test_the_gate_adds_the_listening_rows_only_when_asked(folder, monkeypatch):
    import reviewer

    monkeypatch.setattr(reviewer, "review", lambda f, **k: {"checks": [], "verdict": "pass"})
    for name in ("check_script", "check_sources", "check_licenses", "check_video"):
        monkeypatch.setattr(studiochecks, name, lambda *a, **k: [])
    monkeypatch.setattr(reviewer, "source_text", lambda m: "")
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: BAD)
    without = studiochecks.quality_gate("doc-x")
    with_it = studiochecks.quality_gate("doc-x", listen=True)
    assert not any(r["name"].startswith("voice:") for r in without["rows"])
    assert any(r["name"] == "voice: transcript_matches_script" and not r["ok"] for r in with_it["rows"])
    assert with_it["verdict"] == "PASS" and with_it["blocking"] == 0  # a warning never blocks


def test_approval_listens_records_the_result_and_never_blocks(folder, monkeypatch):
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: BAD)
    autopilot.listened("doc-x")
    saved = json.loads((folder / "meta.json").read_text())["voice_check"]
    assert saved["ok"] is False and saved["match"] == 0.8 and saved["gaps"][0]["words"] == 12
    assert any("Narration" in e["title"] and "A Film" in e["title"] for e in agentlog.recent(5))


def test_a_good_listening_is_recorded_quietly_and_a_failed_one_is_simply_skipped(folder, monkeypatch):
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: GOOD)
    autopilot.listened("doc-x")
    assert json.loads((folder / "meta.json").read_text())["voice_check"]["ok"] is True and not agentlog.recent(5)
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: {"error": "no audio model"})
    records.merge(folder, {"voice_check": None})
    autopilot.listened("doc-x")
    assert json.loads((folder / "meta.json").read_text())["voice_check"] is None
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    autopilot.listened("doc-x")  # nothing raised


def test_tests_never_call_a_model_the_switch_is_off_by_default_under_pytest(folder, monkeypatch):
    monkeypatch.setattr(voicecheck, "ENABLED", False)
    monkeypatch.setattr(voicecheck, "listen", lambda f, **k: pytest.fail("must not listen"))
    autopilot.listened("doc-x")


def test_approval_goes_through_the_listening_step_and_the_command_exists():
    assert "listened(slug)" in inspect.getsource(autopilot._approve)
    import run

    src = inspect.getsource(run.main)
    assert 'a[0] == "listen"' in src and "voicecheck" in src.split('a[0] == "listen"')[1][:700]
