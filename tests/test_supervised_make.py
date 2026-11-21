"""autopilot.make_one (20 Nov 2026): one supervised make by Autopilot's own executors, then the reviewer's review. It never approves, schedules or uploads, even with
auto_approve on and a passing review; it respects the weekly cap, the pace guard and full storage."""
import datetime as dt
import json

import pytest

import autopilot


@pytest.fixture
def studio(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(autopilot.config, "OUT", out)
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "autopilot.lock")
    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")
    monkeypatch.setattr(autopilot, "load_config", lambda: {**autopilot.DEFAULTS, "enabled": False, "auto_approve": True, "pause_scheduling": False})
    monkeypatch.setattr(autopilot, "governed", lambda cfg, now: {**cfg, "_caps": {"doc": 4, "short": 7, "level": "ok", "why": []}})
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: {"videos": [], "busy": False, "storage_full": False, "platform_level": "ok"})
    made, calls = out / "a-new-short", []

    def make(slug, cfg, now):
        made.mkdir()
        (made / "meta.json").write_text(json.dumps({"title": "A new Short", "format": "short", "approved": False}))
        calls.append("make")
        return made

    monkeypatch.setitem(autopilot.EXECUTORS, "make_short", make)
    for name in ("approve", "schedule", "upload"):
        monkeypatch.setitem(autopilot.EXECUTORS, name, lambda *a, n=name: calls.append(n))
    monkeypatch.setattr(autopilot, "_approve", lambda slug: calls.append("approve"))
    import reviewer

    def passing(folder):
        meta = json.loads((folder / "meta.json").read_text())
        meta["review"] = {"verdict": "pass"}
        (folder / "meta.json").write_text(json.dumps(meta))
        calls.append("review")
        return meta["review"]

    monkeypatch.setattr(reviewer, "review", passing)
    return out, calls


def test_a_supervised_make_reviews_but_never_approves_schedules_or_uploads(studio):
    out, calls = studio
    got = autopilot.make_one("short")
    assert got == {"made": "a-new-short", "format": "short", "verdict": "pass", "approved": False}
    assert calls == ["make", "review"]  # auto_approve is on and the review passed: still no approval, no slot, no upload
    assert not json.loads((out / "a-new-short" / "meta.json").read_text()).get("approved")


def test_the_weekly_cap_the_pace_guard_and_full_storage_are_respected(studio, monkeypatch):
    out, calls = studio
    monkeypatch.setattr(autopilot, "governed", lambda cfg, now: {**cfg, "_caps": {"doc": 4, "short": 0, "level": "act", "why": ["repeated openings"]}})
    with pytest.raises(RuntimeError, match="cap"):
        autopilot.make_one("short")
    monkeypatch.setattr(autopilot, "governed", lambda cfg, now: {**cfg, "_caps": {"doc": 4, "short": 7}})
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: {"videos": [], "busy": False, "storage_full": False, "platform_level": "watch", "platform_why": "11 videos in 7 days"})
    with pytest.raises(RuntimeError, match="pace guard"):
        autopilot.make_one("short")
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: {"videos": [], "busy": False, "storage_full": True})
    with pytest.raises(RuntimeError, match="storage"):
        autopilot.make_one("short")
    assert calls == []


def test_a_second_copy_is_refused_while_one_runs(studio):
    with autopilot.exclusive():
        with pytest.raises(autopilot.Busy):
            autopilot.make_one("short")
