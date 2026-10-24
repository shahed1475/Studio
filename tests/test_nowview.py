import datetime as dt
import json

import autopilot
import config
import llm
import nowview

NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)


def make(out, name, files=(), **meta):
    d = out / name
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps(meta))
    for f in files:
        (d / f).write_bytes(b"x")
    return d


def test_each_stage_is_said_in_plain_words(tmp_path):
    cases = [({}, (), "being made"), ({"review": {"verdict": "fail"}}, ("video.mp4",), "waiting for a repair"), ({"review": {"verdict": "needs_human"}}, ("video.mp4",), "needs your attention"),
             ({"review": {"verdict": "pass"}}, ("video.mp4",), "waiting for approval"), ({"review": {"verdict": "pass"}, "approved": True, "publish_at": "T"}, ("video.mp4",), "waiting for its upload time"),
             ({"video_id": "v", "publish_at": "T"}, ("video.mp4",), "on YouTube, private until T"), ({}, ("video.mp4",), "waiting for the review")]
    for i, (meta, files, want) in enumerate(cases):
        d = make(tmp_path, f"v{i}", files, **meta)
        assert want in nowview.stage(d, meta), (meta, nowview.stage(d, meta))
    past = make(tmp_path, "p", ("video.mp4",), video_id="v", publish_at="2026-10-01T10:00:00Z")
    assert "has passed" in nowview.stage(past, {"video_id": "v", "publish_at": "2026-10-01T10:00:00Z"}, NOW)
    assert nowview.stage(past, {"video_id": "v", "hold": True, "publish_at": "2026-10-01T10:00:00Z"}, NOW) == "ON HOLD · on YouTube, kept private"
    held = make(tmp_path, "h", ("video.mp4",), hold=True, review={"verdict": "pass"})
    assert nowview.stage(held, {"hold": True, "review": {"verdict": "pass"}}).startswith("ON HOLD")


def test_build_reports_videos_money_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    make(tmp_path / "out", "a", ("video.mp4",), title="Alpha", format="doc", review={"verdict": "pass"})
    log = tmp_path / "autopilot.log"
    log.write_text("\n".join(f"line {i}" for i in range(40)))
    monkeypatch.setattr(autopilot, "LOG", log)
    monkeypatch.setattr(autopilot, "JOB_FILE", tmp_path / "job.pid")
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "ap.lock")
    monkeypatch.setattr(autopilot, "focus_view", lambda now=None: None)
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.4)
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 1.5})
    r = nowview.build(NOW)
    assert r["videos"][0]["title"] == "Alpha" and "waiting for approval" in r["videos"][0]["stage"]
    assert r["money"] == {"spent_today": 0.4, "cap": 1.5, "left": 1.1}
    assert r["log"][-1] == "line 39" and len(r["log"]) == nowview.LOG_LINES
    assert r["pass_running"] is False and r["dashboard_job"] is False
