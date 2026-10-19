import json
from datetime import datetime, timedelta, timezone

import pytest

import autopilot
import config
import dashboard
import run

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def vid(slug="v", fmt="short", **kw):
    base = {"slug": slug, "format": fmt, "source": None, "approved": True, "approved_by": "reviewer-agent", "verdict": "pass",
            "hold": False, "video_id": None, "publish_at": None, "fails": 0}
    return {**base, **kw}


def state(videos=(), **kw):
    return {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "uploads_by_format": {}, "news_pending": 0,
            "videos": list(videos), **kw}


def plan(st, cfg=None):
    return [(a["do"], a.get("slug")) for a in autopilot.plan_actions(st, cfg or CFG, NOW)]


def test_defaults_have_us_short_slots_and_are_valid():
    d = autopilot.DEFAULTS
    assert d["shorts"] is True and d["shorts_per_day"] == 1 and d["max_waiting_shorts"] == 3
    assert {"day": "fri", "time": "16:00"} in d["short_slots"] and {"day": "tue", "time": "12:30"} in d["short_slots"]
    assert dashboard.validate_autopilot_config({k: d[k] for k in ("shorts", "shorts_per_day", "max_waiting_shorts", "short_slots")})


def test_short_made_when_enabled_and_few_waiting():
    assert ("make_short", None) in plan(state([]))
    assert ("make_short", None) not in plan(state([]), {**CFG, "shorts": False})


def test_short_waiting_limit_is_separate_from_doc_limit():
    three = [vid(f"s{i}", publish_at=iso(NOW + timedelta(days=2 + i))) for i in range(3)]
    assert ("make_short", None) not in plan(state(three))
    assert ("make", None) in plan(state(three))  # shorts waiting do not block documentaries


def test_upload_caps_are_per_format():
    near = iso(NOW + timedelta(hours=1))
    s, d = vid("s", publish_at=near), vid("d", fmt="doc", publish_at=near)
    acts = plan(state([s, d], uploads_today=1, uploads_by_format={"short": 1}))
    assert ("upload", "s") not in acts and ("upload", "d") in acts


def test_total_daily_cap_still_applies(monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOADS_PER_DAY", 1)
    near = iso(NOW + timedelta(hours=1))
    acts = plan(state([vid("s", publish_at=near), vid("d", fmt="doc", publish_at=near)], uploads_today=0), {**CFG, "uploads_per_day": 5, "shorts_per_day": 5})
    assert len([a for a in acts if a[0] == "upload"]) == 1


def test_short_scheduled_into_short_slots_and_only_against_same_format(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    for name, fmt, pub in (("doc1", "doc", "2026-10-23T20:00:00Z"), ("s1", "short", None)):
        d = tmp_path / name
        d.mkdir()
        meta = {"format": fmt}
        if pub:
            meta["publish_at"] = pub
        (d / "meta.json").write_text(json.dumps(meta))
    cfg = {**CFG, "short_slots": [{"day": "fri", "time": "16:00"}], "review_window_hours": 24}
    autopilot.do_schedule("s1", cfg, NOW)
    # Friday 16:00 ET = 20:00Z, same instant as the doc slot: allowed because only same-format videos block a slot
    assert json.loads((tmp_path / "s1" / "meta.json").read_text())["publish_at"] == "2026-10-23T20:00:00Z"


def test_finish_short_skips_thumbnail_but_sets_seo_title(tmp_path, monkeypatch):
    import seo, thumbnail
    f = tmp_path / "s"
    f.mkdir()
    (f / "meta.json").write_text(json.dumps({"title": "Old", "format": "short"}))
    calls = []
    monkeypatch.setattr(thumbnail, "make", lambda x: calls.append("thumb"))
    def fake_seo(x):
        calls.append("seo")
        m = json.loads((x / "meta.json").read_text()); m["seo"] = {"titles": ["Where Did They Go?"]}; (x / "meta.json").write_text(json.dumps(m))
    monkeypatch.setattr(seo, "make", fake_seo)
    autopilot.finish_video(f)
    assert calls == ["seo"] and json.loads((f / "meta.json").read_text())["title"] == "Where Did They Go?"


def test_do_make_short_runs_pipeline_then_finish(tmp_path, monkeypatch):
    f = tmp_path / "s"
    f.mkdir()
    (f / "meta.json").write_text(json.dumps({"title": "T"}))
    seen = []
    monkeypatch.setattr(run, "cmd_make", lambda *a: seen.append("make") or f)
    monkeypatch.setattr(autopilot, "finish_video", lambda p, *a, **k: seen.append("finish"))
    autopilot.do_make_short(None, CFG, NOW)
    assert seen == ["make", "finish"]


def test_tick_makes_short_and_doc_but_only_one_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "s.json")
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "l")
    monkeypatch.setattr(autopilot, "CONFIG_FILE", tmp_path / "c.json")
    autopilot.save_config({**CFG})
    calls = []
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: state([], news_pending=1))
    monkeypatch.setattr(autopilot, "EXECUTORS", {k: (lambda k: lambda slug, cfg, now: calls.append(k))(k) for k in ("make_short", "make", "make_news", "ideas")})
    autopilot.tick(NOW)
    assert calls.count("make_short") == 1 and (calls.count("make") + calls.count("make_news")) == 1
