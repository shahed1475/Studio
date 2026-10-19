import subprocess

import agentlog


def test_event_roundtrip_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    agentlog.event("info", "first")
    agentlog.event("found", "second", "detail")
    got = agentlog.recent()
    assert [e["title"] for e in got] == ["second", "first"]
    assert got[0]["kind"] == "found" and got[0]["detail"] == "detail" and got[0]["read"] is False


def test_unread_and_mark_read(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    agentlog.event("info", "a")
    agentlog.event("info", "b")
    assert agentlog.unread() == 2
    agentlog.mark_read()
    assert agentlog.unread() == 0
    assert all(e["read"] for e in agentlog.recent())


def test_notify_failure_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")

    def boom(*a, **k):
        raise FileNotFoundError("notify-send")

    monkeypatch.setattr(subprocess, "run", boom)
    e = agentlog.event("strategy", "new", notify=True)
    assert e["title"] == "new" and agentlog.recent()[0]["title"] == "new"


def test_notify_called_only_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a[0]))
    agentlog.event("info", "quiet")
    assert calls == []
    agentlog.event("strategy", "loud", "x", notify=True)
    assert calls and calls[0][0] == "notify-send" and "loud" in calls[0]
