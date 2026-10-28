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


def test_the_footage_block_reports_the_newest_run_and_todays_count(tmp_path, monkeypatch):
    import footagestore
    monkeypatch.setattr(footagestore, "ROOT", tmp_path / "store")
    assert nowview.footage_status(NOW) == {"last_status": None, "last_at": None, "runs_today": 0, "runs_total": 0}
    r = footagestore.create("footage-test")
    r.update(status="failed")
    got = nowview.footage_status(dt.datetime.now(dt.timezone.utc))
    assert got["last_status"] == "failed" and got["runs_today"] == 1 and got["runs_total"] == 1


def test_an_unreadable_footage_store_is_none_not_an_error(monkeypatch):
    import footagestore
    monkeypatch.setattr(footagestore, "runs", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    assert nowview.footage_status(NOW) is None


# ---- the live view (29 Oct 2026) ----
def test_the_station_is_the_newest_log_line_that_names_one_and_a_finished_or_quiet_build_is_idle():
    lines = ["Documentary: The Lost Army", "  source articles: 2", "Voice...", "Archival images (only pictures that name the subject)...", "Rendering (48/48 scenes have footage)..."]
    s = nowview.stage_now(lines, 5, True)
    assert (s["key"], s["index"], s["of"], s["idle"]) == ("render", 3, 5, False) and s["last_line"].startswith("Rendering")
    assert s["topic"] == "The Lost Army"
    assert nowview.stage_now(lines[:3], 5, True)["key"] == "voice" and nowview.stage_now(lines[:1], 5, True)["key"] == "plan"
    assert nowview.stage_now(lines + ["Done: /app/output/x/video.mp4"], 5, True)["idle"] is True  # finished
    assert nowview.stage_now(lines, 5, False)["idle"] is True  # nothing holds the lock or a job
    assert nowview.stage_now(lines, nowview.LIVE_SECONDS + 1, True)["idle"] is True  # a quiet log is not progress
    assert nowview.stage_now([], None, True)["idle"] is True and nowview.stage_now(["no stage here"], 1, True)["key"] is None


def test_the_live_log_is_the_newest_build_log_never_the_action_summary(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "logs").mkdir()
    old, new, quiet = (tmp_path / "logs" / n for n in ("a-doc.log", "b-doc.log", "autopilot.log"))
    old.write_text("Voice...\n"), new.write_text("Rendering...\n"), quiet.write_text("ok approve x\n")
    os.utime(old, (1, 1)), os.utime(new, (100, 100))  # the quiet file is the newest by time and must still be skipped
    path, lines, age = nowview.live_log()
    assert path.name == "b-doc.log" and lines == ["Rendering..."] and age > 0
    (tmp_path / "logs" / "b-doc.log").unlink(), old.unlink()
    assert nowview.live_log()[0] is None


def test_build_carries_the_live_fields_and_a_failing_source_does_not_break_the_page(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(nowview, "_plan_cache", {})
    monkeypatch.setattr(nowview, "events", lambda n=8: [{"at": "T", "kind": "info", "title": "t", "detail": ""}])
    import autopilot
    monkeypatch.setattr(autopilot, "plan_view", lambda now: (_ for _ in ()).throw(RuntimeError("planner down")))
    d = nowview.build(NOW)
    assert {"stage", "busy", "build_log", "next", "events", "credit"} <= set(d) and d["next"] == [] and d["events"][0]["title"] == "t"
    assert d["stage"]["of"] == 5 and isinstance(d["stage"]["steps"], list)
