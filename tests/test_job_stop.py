"""Stopping a job the dashboard started (29 Oct 2026): the owner clicked 'Make documentary' and had no way to stop it."""
import json
import os
import subprocess
import time
from time import sleep as real_sleep  # the shared test setup replaces time.sleep

import pytest

import autopilot
import config
import dashboard


def process_alive(marker: bytes) -> bool:
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                if marker in open(f"/proc/{pid}/cmdline", "rb").read():
                    return True
            except OSError:
                pass
    return False


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(config, "OUT", out)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(dashboard, "LOGS", tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(autopilot, "JOB_FILE", tmp_path / "job.pid")
    monkeypatch.setattr(dashboard, "JOBS", {})
    started = []

    def fake(cmd="sh -c 'sleep 71 & wait'", before=()):
        proc = subprocess.Popen(["sh", "-c", "sleep 71 & wait"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started.append(proc)
        log = tmp_path / "logs" / "123456-doc.log"
        log.write_text("Documentary: A test\n")
        autopilot.JOB_FILE.write_text(str(proc.pid))
        dashboard.JOBS["123456-doc"] = {"id": "123456-doc", "cmd": "doc", "status": "running", "started": time.time(), "ended": None, "proc": proc, "before": list(before)}
        return proc

    yield fake, out, tmp_path
    for p in started:
        try:
            os.killpg(os.getpgid(p.pid), 9)
        except OSError:
            pass


def test_stop_ends_the_job_and_the_programs_it_started(jobs):
    fake, out, root = jobs
    proc = fake()
    real_sleep(0.4)
    assert process_alive(b"sleep\x0071")  # the render's child (ffmpeg, in real life)
    res = dashboard.stop_job("123456-doc")
    assert res["ok"] is True
    assert dashboard.JOBS["123456-doc"]["status"] == "stopped" and dashboard.JOBS["123456-doc"]["ended"]
    assert proc.poll() is not None and not process_alive(b"sleep\x0071")  # nothing left running or burning money
    assert not autopilot.JOB_FILE.exists()  # Autopilot may work again
    assert "Stopped by you" in (root / "logs" / "123456-doc.log").read_text()


def test_a_half_built_video_is_set_aside_not_deleted_and_finished_or_older_ones_are_left_alone(jobs):
    fake, out, root = jobs
    old = out / "older-video"
    old.mkdir()
    (old / "meta.json").write_text("{}")
    fake(before=["older-video"])
    half = out / "doc-a-test"
    half.mkdir()
    (half / "meta.json").write_text(json.dumps({"title": "A test"}))
    done = out / "doc-finished-meanwhile"
    done.mkdir()
    (done / "meta.json").write_text("{}")
    (done / "video.mp4").write_bytes(b"x")
    res = dashboard.stop_job("123456-doc")
    assert res["archived"] == ["doc-a-test"]
    assert not half.exists() and (root / "output_old" / "doc-a-test" / "meta.json").exists()  # moved, never deleted
    assert old.exists() and done.exists()


def test_a_job_in_the_dashboards_own_process_group_is_stopped_alone_never_with_the_dashboard(jobs, monkeypatch):
    fake, out, root = jobs
    proc = subprocess.Popen(["sleep", "71"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # no new session: same group as this process
    try:
        autopilot.JOB_FILE.write_text(str(proc.pid))
        dashboard.JOBS["123456-doc"] = {"id": "123456-doc", "cmd": "doc", "status": "running", "started": time.time(), "ended": None, "proc": proc, "before": []}
        groups = []
        monkeypatch.setattr(dashboard.os, "killpg", lambda *a: groups.append(a))  # a real killpg here would end the test run itself
        assert dashboard.stop_job("123456-doc")["ok"] is True
        assert groups == [] and proc.poll() is not None  # the process was signalled on its own
    finally:
        proc.kill()


def test_only_a_running_job_can_be_stopped(jobs):
    fake, out, root = jobs
    with pytest.raises(ValueError):
        dashboard.stop_job("nope")
    fake()
    dashboard.stop_job("123456-doc")
    with pytest.raises(ValueError):
        dashboard.stop_job("123456-doc")  # already stopped


def test_a_job_runs_in_its_own_process_group_so_that_stop_reaches_its_children(monkeypatch, tmp_path):
    seen = {}

    class P:
        pid = 4242

        def wait(self, *a):
            return 0

    def popen(cmd, **k):
        seen.update(k)
        return P()

    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(dashboard, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dashboard, "JOBS", {})
    monkeypatch.setattr(autopilot, "JOB_FILE", tmp_path / "job.pid")
    monkeypatch.setattr(autopilot, "is_running", lambda: False)
    monkeypatch.setattr(dashboard.subprocess, "Popen", popen)
    jid = dashboard.start_job("doc", [])
    for _ in range(50):  # the watcher thread notes the end of the (fake) process; let it finish before the test's setup is undone
        if dashboard.JOBS[jid]["status"] != "running":
            break
        real_sleep(0.05)
    assert seen.get("start_new_session") is True
    assert "proc" not in next(iter(dashboard.state_jobs()))  # the process object never reaches the page


def test_the_stop_route_answers_with_what_was_set_aside(jobs):
    fake, out, root = jobs
    fake()
    assert dashboard.H.route(None, "/api/job/stop", {"id": "123456-doc"})["ok"] is True
