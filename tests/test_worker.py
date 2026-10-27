import datetime as dt
import json
import os
import time

import worker

UTC = dt.timezone.utc


def t(*a):
    return dt.datetime(*a, tzinfo=UTC)


def names(jobs):
    return [j["name"] for j in jobs]


def test_interval_job_due_when_never_run_or_old():
    job = {"name": "tick", "every": 1800}
    assert names(worker.due(t(2026, 10, 19, 10, 0), {}, [job])) == ["tick"]
    assert worker.due(t(2026, 10, 19, 10, 0), {"tick": "2026-10-19T09:50:00Z"}, [job]) == []
    assert names(worker.due(t(2026, 10, 19, 10, 21), {"tick": "2026-10-19T09:50:00Z"}, [job])) == ["tick"]


def test_daily_job_runs_once_per_day_after_its_time():
    job = {"name": "agent", "at": "06:30"}
    yesterday = {"agent": "2026-10-18T06:31:00Z"}
    assert worker.due(t(2026, 10, 19, 6, 0), yesterday, [job]) == []
    assert names(worker.due(t(2026, 10, 19, 6, 31), yesterday, [job])) == ["agent"]
    assert worker.due(t(2026, 10, 19, 23, 0), {"agent": "2026-10-19T06:35:00Z"}, [job]) == []


def test_weekly_job_uses_most_recent_slot():
    job = {"name": "weekly", "at": "09:00", "weekday": 0}  # Monday
    assert names(worker.due(t(2026, 10, 20, 12, 0), {"weekly": "2026-10-12T09:05:00Z"}, [job])) == ["weekly"]  # Tue, last was last Monday
    assert worker.due(t(2026, 10, 20, 12, 0), {"weekly": "2026-10-19T09:05:00Z"}, [job]) == []
    assert worker.due(t(2026, 10, 19, 8, 0), {"weekly": "2026-10-12T09:05:00Z"}, [job]) == []


def test_missed_slots_run_once_not_many():
    job = {"name": "agent", "at": "06:30"}
    got = worker.due(t(2026, 10, 25, 12, 0), {"agent": "2026-10-19T06:31:00Z"}, [job])
    assert names(got) == ["agent"]  # six days missed, one run


def test_state_roundtrip_and_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "STATE", tmp_path / "w.json")
    assert worker.load_state() == {}
    worker.save_state({"a": "2026-10-19T00:00:00Z"})
    assert worker.load_state() == {"a": "2026-10-19T00:00:00Z"}
    (tmp_path / "w.json").write_text("{not json")
    assert worker.load_state() == {}


def test_run_job_runs_commands_in_order_and_survives_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "LOG", tmp_path / "worker.log")
    calls = []

    class R:
        def __init__(self, rc):
            self.returncode = rc

    def fake(cmd, **kw):
        calls.append(cmd[2:])
        return R(1 if cmd[2] == "bad" else 0)

    monkeypatch.setattr(worker.subprocess, "run", fake)
    rc = worker.run_job({"name": "x", "cmds": [["bad"], ["good"]], "timeout": 5})
    assert calls == [["bad"], ["good"]] and rc == 1
    assert "bad" in (tmp_path / "worker.log").read_text()


def test_run_job_timeout_is_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "LOG", tmp_path / "worker.log")

    def boom(cmd, **kw):
        raise worker.subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(worker.subprocess, "run", boom)
    assert worker.run_job({"name": "x", "cmds": [["slow"]], "timeout": 1}) == 1
    assert "timed out" in (tmp_path / "worker.log").read_text()


def test_prune_cache_removes_only_old_files(tmp_path):
    old, new = tmp_path / "old.mp4", tmp_path / "new.mp4"
    old.write_bytes(b"x" * 10)
    new.write_bytes(b"y")
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))
    freed = worker.prune_cache(tmp_path, 21, dt.datetime.now(UTC))
    assert freed == 10 and not old.exists() and new.exists()
    assert worker.prune_cache(tmp_path / "missing", 21, dt.datetime.now(UTC)) == 0


def test_alive_depends_on_fresh_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "HEARTBEAT", tmp_path / "hb")
    assert worker.alive() is False
    (tmp_path / "hb").write_text("1")
    assert worker.alive() is True
    old = time.time() - 600
    os.utime(tmp_path / "hb", (old, old))
    assert worker.alive() is False


def test_trend_and_reference_channel_jobs_run_daily_before_the_research_agent_so_autopilot_sees_what_is_taking_off_now():
    by = {j["name"]: j for j in worker.JOBS}
    assert by["trendwatch"]["cmds"] == [["trends"], ["channels"]] and "weekday" not in by["trendwatch"]
    assert by["trendwatch"]["at"] < by["agent"]["at"]  # 06:00 before 06:30
    weekly_cmds = [c[0] for c in by["weekly"]["cmds"]]
    assert "trends" not in weekly_cmds and "channels" not in weekly_cmds and "newswatch" in weekly_cmds
