import datetime as dt
import json

import autopilot
import planner
import serverstate

NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True, "prepare_hours": 72, "slots": [{"day": d, "time": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]}


def v(slug, at, fmt="doc"):
    return {"slug": slug, "format": fmt, "publish_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "hold": False, "approved": True, "verdict": "pass", "video_id": "x", "title": slug}


def test_with_no_weekly_cap_the_planner_behaves_as_before():
    assert planner.needs({**CFG, "max_videos_per_week": 0}, [], NOW)["doc"] >= 1


def test_a_full_week_makes_no_new_video_for_a_slot_inside_it():
    week = [v(f"s{i}", NOW - dt.timedelta(days=i % 5, hours=-1 * (i % 3))) for i in range(6)]
    free = planner.needs({**CFG, "max_videos_per_week": 0, "slots": CFG["slots"]}, week, NOW)
    capped = planner.needs({**CFG, "max_videos_per_week": 3}, week, NOW)
    assert sum(free.values()) > 0 and sum(capped.values()) == 0


def test_a_cap_above_the_week_count_changes_nothing():
    week = [v("a", NOW - dt.timedelta(days=1)), v("b", NOW - dt.timedelta(days=2))]
    assert planner.needs({**CFG, "max_videos_per_week": 10}, week, NOW) == planner.needs({**CFG, "max_videos_per_week": 0}, week, NOW)


def test_the_server_snapshot_hides_every_secret(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "llm.json").write_text(json.dumps({"enabled": True, "api_key": "sk-123", "daily_budget_usd": 3.0}))
    (tmp_path / "autopilot.json").write_text(json.dumps({"enabled": True, "review_window_hours": 2}))
    (tmp_path / "data" / "titletest.json").write_text('{"mode": "apply"}')
    (tmp_path / "data" / "playlists.json").write_text(json.dumps({"doc": ["PL1"], "cta": "More: https://x"}))
    snap = serverstate.snapshot(tmp_path)
    text = json.dumps(snap)
    assert "sk-123" not in text and snap["llm.json"]["api_key"] == "[hidden]" and snap["llm.json"]["daily_budget_usd"] == 3.0
    assert snap["data/titletest.json"] == {"mode": "apply"} and snap["autopilot.json"]["review_window_hours"] == 2


def test_the_snapshot_renders_as_markdown(tmp_path):
    (tmp_path / "autopilot.json").write_text('{"enabled": true}')
    md = serverstate.markdown(serverstate.snapshot(tmp_path))
    assert md.startswith("# Server-only settings") and "autopilot.json" in md and "enabled" in md
