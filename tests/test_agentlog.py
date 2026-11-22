import datetime as dt
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


T0 = dt.datetime(2026, 11, 22, 6, 0, tzinfo=dt.timezone.utc)


def test_an_unchanged_routine_report_is_logged_once_a_day(tmp_path, monkeypatch):
    """22 Nov 2026: "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing" was logged 25 times in a week with nothing changed, each one in the bell."""
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    title = "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing"
    first = agentlog.event("info", title, "same", now=T0)
    again = agentlog.event("info", title, "same", now=T0 + dt.timedelta(hours=6))
    assert again.get("repeat") and again["at"] == first["at"] and len(agentlog.recent()) == 1
    agentlog.event("info", title, "something changed", now=T0 + dt.timedelta(hours=7))  # a changed detail is news
    agentlog.event("found", title, "same", now=T0 + dt.timedelta(hours=8))  # another kind is another event
    agentlog.event("info", title, "same", now=T0 + dt.timedelta(hours=25))  # a day later it is said again
    got = [(e["kind"], e["detail"]) for e in agentlog.recent()]
    assert got == [("info", "same"), ("found", "same"), ("info", "something changed"), ("info", "same")]


def test_errors_actions_strategies_and_alerts_are_always_logged_even_when_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    for kind in ("error", "applied", "strategy"):
        for _ in range(2):
            agentlog.event(kind, f"{kind} twice", "x", now=T0)
    for _ in range(2):
        agentlog.event("found", "Possible algorithm change", "x", notify=True, now=T0)
    titles = [e["title"] for e in agentlog.recent()]
    assert all(titles.count(t) == 2 for t in ("error twice", "applied twice", "strategy twice", "Possible algorithm change"))


def test_an_important_event_carries_an_alert_and_the_menu_count_takes_only_errors_and_alerts(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    agentlog.event("info", "Daily research finished", now=T0)
    agentlog.event("applied", "Repaired a title", now=T0)
    agentlog.event("applied", "Credit is low: paid models off", notify=True, now=T0)
    agentlog.event("error", "A render failed", now=T0)
    by = {e["title"]: e for e in agentlog.recent()}
    assert by["Credit is low: paid models off"]["alert"] is True and "alert" not in by["Repaired a title"] and "alert" not in by["A render failed"]
    assert agentlog.unread() == 4 and agentlog.unread(attention_only=True) == 2
    assert agentlog.record("found", "x", notify=True, now=T0)["alert"] is True and "alert" not in agentlog.record("found", "x", now=T0)


def test_a_feed_with_an_odd_line_still_finds_the_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    agentlog.event("info", "Checked", "fine", now=T0)
    with agentlog.FILE.open("a") as f:
        f.write("{half a line\n")
    assert agentlog.event("info", "Checked", "fine", now=T0 + dt.timedelta(hours=1)).get("repeat")
