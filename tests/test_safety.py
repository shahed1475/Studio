import json
import os
from datetime import datetime, timedelta, timezone

import agentlog
import autopilot
import config
import safety

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def make(out, name, **meta):
    d = out / name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps(meta))
    return d


class FakeYT:
    def __init__(self, items):
        self.items, self.asked = items, []

    def videos(self):
        return self

    def list(self, part, id):
        self.asked.append(id)
        return self

    def execute(self):
        return {"items": self.items}


def item(vid, privacy="public", upload="processed", **extra):
    status = {"privacyStatus": privacy, "uploadStatus": upload, **extra.pop("status", {})}
    return {"id": vid, "status": status, "contentDetails": extra.get("contentDetails", {})}


def test_judge_ok_when_public_and_processed():
    assert safety.judge(item("a"), published=True) == []


def test_judge_flags_private_after_publish_time_but_not_before():
    assert any("private" in p for p in safety.judge(item("a", privacy="private"), published=True))
    assert safety.judge(item("a", privacy="private"), published=False) == []


def test_judge_flags_rejection_and_failure_in_plain_english():
    p = safety.judge(item("a", upload="rejected", status={"rejectionReason": "copyright"}), published=True)
    assert p and "copyright" in p[0].lower()
    assert safety.judge(item("a", upload="failed", status={"failureReason": "codec"}), published=True)


def test_judge_flags_region_block_and_missing_video():
    blocked = item("a", contentDetails={"regionRestriction": {"blocked": ["US"]}})
    assert any("blocked" in p for p in safety.judge(blocked, published=True))
    assert any("removed" in p for p in safety.judge(None, published=True))


def test_check_marks_healthy_video_and_leaves_autopilot_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make(tmp_path, "good", video_id="v1", publish_at=iso(NOW - timedelta(hours=2)), uploaded_at=iso(NOW - timedelta(hours=5)))
    called = []
    monkeypatch.setattr(autopilot, "save_config", lambda c: called.append(c))
    r = safety.check(NOW, yt=FakeYT([item("v1")]))
    assert r["problems"] == [] and r["checked"] == 1 and not called
    assert json.loads((tmp_path / "good" / "meta.json").read_text())["health"]["ok"] is True


def test_check_pauses_autopilot_and_reports_when_a_video_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog, "subprocess", __import__("types").SimpleNamespace(run=lambda *a, **k: None))
    make(tmp_path, "bad", video_id="v2", publish_at=iso(NOW - timedelta(hours=2)), uploaded_at=iso(NOW - timedelta(hours=5)))
    saved = []
    monkeypatch.setattr(autopilot, "load_config", lambda: {"enabled": True, "x": 1})
    monkeypatch.setattr(autopilot, "save_config", lambda c: saved.append(c))
    r = safety.check(NOW, yt=FakeYT([item("v2", privacy="private")]))
    assert r["problems"] and r["paused"] is True and saved[0]["enabled"] is False
    ev = agentlog.recent(1)[0]
    assert ev["kind"] == "error" and "paused" in ev["title"].lower()


def test_check_skips_videos_not_due_and_already_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make(tmp_path, "future", video_id="f", publish_at=iso(NOW + timedelta(hours=5)), uploaded_at=iso(NOW))
    make(tmp_path, "done", video_id="d", publish_at=iso(NOW - timedelta(hours=9)), health={"ok": True, "checked_at": iso(NOW - timedelta(hours=1))})
    make(tmp_path, "old", video_id="o", publish_at=iso(NOW - timedelta(days=9)))
    make(tmp_path, "noid", publish_at=iso(NOW - timedelta(hours=9)))
    yt = FakeYT([])
    assert safety.check(NOW, yt=yt)["checked"] == 0 and yt.asked == []


def test_check_reports_expired_login(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog, "subprocess", __import__("types").SimpleNamespace(run=lambda *a, **k: None))
    make(tmp_path, "v", video_id="v1", publish_at=iso(NOW - timedelta(hours=2)))

    class RefreshError(Exception):
        pass

    def boom():
        raise RefreshError("expired")
    monkeypatch.setattr(safety, "_service", boom)
    r = safety.check(NOW)
    assert "login" in r["error"].lower()
    assert "7 days" in agentlog.recent(1)[0]["detail"] or "production" in agentlog.recent(1)[0]["detail"].lower()


def test_audit_flags_open_permissions_and_fix_repairs(tmp_path):
    f = tmp_path / "token.json"
    f.write_text(json.dumps({"refresh_token": "r", "scopes": ["https://www.googleapis.com/auth/youtube.upload"]}))
    os.chmod(f, 0o644)
    by = {c["name"]: c for c in safety.local_audit(tmp_path, use_git=False)}
    assert not by["file_modes"]["ok"] and "token.json" in by["file_modes"]["detail"]
    assert safety.fix_permissions(tmp_path) == ["token.json"]
    assert safety.local_audit(tmp_path, use_git=False)[0]["ok"]


def test_audit_flags_wide_scopes_and_missing_refresh_token(tmp_path):
    (tmp_path / "token.json").write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/youtube"]}))
    os.chmod(tmp_path / "token.json", 0o600)
    by = {c["name"]: c for c in safety.local_audit(tmp_path, use_git=False)}
    assert not by["token_scopes"]["ok"] and not by["refresh_token"]["ok"]


def test_pace_settings_match_the_research():
    import dashboard
    import scheduler
    import worker
    assert config.MAX_UPLOADS_PER_DAY == 2
    assert len({s["day"] for s in scheduler.SHORT_SLOTS_DEFAULT}) == 7  # a Short every day
    assert {"uploads_per_day": 2} == dashboard.validate_autopilot_config({"uploads_per_day": 2})
    for bad in ({"uploads_per_day": 3}, {"shorts_per_day": 3}):
        try:
            dashboard.validate_autopilot_config(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    names = {j["name"] for j in worker.JOBS}
    assert {"health", "policywatch"} <= names
