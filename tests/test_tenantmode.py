import datetime as dt
import json
import threading
import time

import agentlog
import pytest

import tenantmode

NOW = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    return tmp_path


def test_is_tenant_only_when_the_mode_is_set(monkeypatch):
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    assert tenantmode.is_tenant() is False
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    assert tenantmode.is_tenant() is True


def test_first_run_writes_safe_defaults_once_and_never_overwrites_later_choices(root):
    tenantmode.apply_defaults(root)
    ap = json.loads((root / "autopilot.json").read_text())
    assert ap["enabled"] is False and ap["auto_approve"] is False
    llm = json.loads((root / "llm.json").read_text())
    assert llm["enabled"] is False and llm["daily_budget_usd"] == 1.5 and llm["ai_art"] is False
    assert json.loads((root / "agent.json").read_text())["mode"] == "handoff"
    (root / "autopilot.json").write_text(json.dumps({"enabled": True}))  # the user turned Autopilot on later
    tenantmode.apply_defaults(root)
    assert json.loads((root / "autopilot.json").read_text()) == {"enabled": True}


def test_quota_levels_ok_warn_full(root):
    (root / "output").mkdir()
    (root / "output" / "v.mp4").write_bytes(b"x" * 1_000_000)
    assert tenantmode.usage_gb(root) == pytest.approx(0.001, abs=1e-5)
    assert tenantmode.quota_state(root, limit_gb=0.01)["state"] == "ok"
    assert tenantmode.quota_state(root, limit_gb=0.00125)["state"] == "warn"  # 80%
    got = tenantmode.quota_state(root, limit_gb=0.001)
    assert got["state"] == "full" and got["pct"] == 100


def test_a_full_disk_pauses_new_videos_once_and_the_pause_is_lifted_below_ninety_percent(root):
    (root / "output").mkdir()
    (root / "output" / "v.mp4").write_bytes(b"x" * 1_000_000)
    (root / "autopilot.json").write_text(json.dumps({"enabled": True, "make_videos": True}))
    tenantmode.enforce_quota(root, NOW, limit_gb=0.001)
    assert json.loads((root / "autopilot.json").read_text())["make_videos"] is False
    tenantmode.enforce_quota(root, NOW, limit_gb=0.001)
    assert len([e for e in agentlog.recent() if "storage" in e["title"].lower()]) == 1  # one message, not one an hour
    (root / "output" / "v.mp4").write_bytes(b"x" * 100_000)
    tenantmode.enforce_quota(root, NOW + dt.timedelta(hours=1), limit_gb=0.001)  # 10%
    assert json.loads((root / "autopilot.json").read_text())["make_videos"] is True


def test_a_pause_the_user_set_themselves_is_not_lifted(root):
    (root / "autopilot.json").write_text(json.dumps({"enabled": True, "make_videos": False}))
    tenantmode.enforce_quota(root, NOW, limit_gb=10)
    assert json.loads((root / "autopilot.json").read_text())["make_videos"] is False


def test_render_gate_is_a_no_op_without_a_gate_folder_and_limits_parallel_renders_with_one(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_RENDER_GATE", raising=False)
    with tenantmode.render_gate():
        pass
    monkeypatch.setenv("STUDIO_RENDER_GATE", str(tmp_path / "gate"))
    running, peak, lock = [0], [0], threading.Lock()

    def job():
        with tenantmode.render_gate(slots=1, poll=0.01):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.05)
            with lock:
                running[0] -= 1

    threads = [threading.Thread(target=job) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 1


def test_rendering_goes_through_the_gate(monkeypatch, tmp_path):
    import contextlib

    import render
    entered = []

    @contextlib.contextmanager
    def fake_gate(*a, **k):
        entered.append(1)
        yield

    monkeypatch.setattr(tenantmode, "render_gate", fake_gate)
    monkeypatch.setattr(render, "_render_ungated", lambda *a, **k: "done")
    assert render.render([], [], tmp_path / "n.mp3", None, tmp_path, tmp_path / "o.mp4") == "done" and entered == [1]


def test_the_worker_checks_storage_hourly_only_for_a_user_studio(monkeypatch):
    import importlib

    import worker
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    importlib.reload(worker)
    assert "quota" not in [j["name"] for j in worker.JOBS]
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    importlib.reload(worker)
    assert any(j["name"] == "quota" and j["every"] == 3600 and j["cmds"] == [["tenant-quota"]] for j in worker.JOBS)
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    importlib.reload(worker)


def test_a_user_who_turns_new_videos_back_on_while_storage_is_still_full_is_stopped_again(root):
    (root / "output").mkdir()
    (root / "output" / "v.mp4").write_bytes(b"x" * 1_000_000)
    (root / "autopilot.json").write_text(json.dumps({"enabled": True, "make_videos": True}))
    tenantmode.enforce_quota(root, NOW, limit_gb=0.001)
    (root / "autopilot.json").write_text(json.dumps({"enabled": True, "make_videos": True}))  # switched back on in the dashboard
    tenantmode.enforce_quota(root, NOW + dt.timedelta(hours=1), limit_gb=0.001)
    assert json.loads((root / "autopilot.json").read_text())["make_videos"] is False
    assert len([e for e in agentlog.recent() if "storage" in e["title"].lower()]) == 1  # still one message


def test_an_unreadable_settings_file_is_left_alone_not_replaced(root):
    (root / "output").mkdir()
    (root / "output" / "v.mp4").write_bytes(b"x" * 1_000_000)
    (root / "autopilot.json").write_text("{ broken")
    tenantmode.enforce_quota(root, NOW, limit_gb=0.001)
    assert (root / "autopilot.json").read_text() == "{ broken"


def test_a_video_started_by_hand_is_refused_when_storage_is_full(root, monkeypatch):
    import run
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    monkeypatch.setattr(tenantmode, "quota_state", lambda *a, **k: {"state": "full", "used_gb": 10.2, "limit_gb": 10.0, "pct": 102})
    with pytest.raises(SystemExit, match="storage is full"):
        run._charged(lambda topic: root / "doc-x", "A topic")
    monkeypatch.setenv("STUDIO_MODE", "")
    assert run._charged(lambda topic: root / "doc-x", "A topic") == root / "doc-x"  # the owner's studio has no such limit
