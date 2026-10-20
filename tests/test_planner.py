import datetime as dt

import config
import planner

NOW = dt.datetime(2026, 10, 20, 14, 0, tzinfo=dt.timezone.utc)  # Tuesday
CFG = {"slots": [{"day": d, "time": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")],
       "short_slots": [{"day": d, "time": "12:30"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")],
       "review_window_hours": 24, "plan_ahead": 3}


def vid(slug, fmt="doc", **kw):
    return {"slug": slug, "format": fmt, "verdict": None, "approved": False, "hold": False, "video_id": None, "publish_at": None, "fix_attempts": 0, "title": slug, **kw}


def test_slot_times_are_in_the_audience_time_zone_and_in_order():
    s = planner.slot_times(CFG["slots"], NOW, 3)
    assert [a.strftime("%a %H:%M") for a in s] == ["Tue 22:00", "Wed 22:00", "Thu 22:00"]  # 18:00 in New York in October is 22:00 UTC


def test_rows_show_what_fills_each_slot_and_a_slot_too_close_to_fill_says_so():
    vs = [vid("up", video_id="X", publish_at="2026-10-21T22:00:00Z", verdict="pass", approved=True),
          vid("ready", verdict="pass", approved=True), vid("fixing", verdict="fail", fix_attempts=1)]
    docs = [r for r in planner.rows(CFG, vs, NOW) if r["format"] == "doc"][:5]
    assert [r["status"] for r in docs] == ["too_soon", "uploaded", "ready", "repairing", "empty"]
    assert docs[1]["slug"] == "up" and docs[2]["slug"] == "ready" and docs[3]["slug"] == "fixing"
    assert "Wed" in docs[1]["us"] and "Thu" in docs[2]["us"]


def test_needs_counts_only_the_slots_nothing_covers():
    assert planner.needs(CFG, [], NOW) == {"doc": 3, "short": 3}
    vs = [vid("a", verdict="pass", approved=True), vid("b", verdict="fail", fix_attempts=1), vid("s1", "short", verdict="pass", approved=True)]
    assert planner.needs(CFG, vs, NOW) == {"doc": 1, "short": 2}
    vs.append(vid("gave", verdict="fail", fix_attempts=2, gave_up=True))  # a video the fixer gave up on covers nothing
    assert planner.needs(CFG, vs, NOW) == {"doc": 1, "short": 2}
    assert planner.needs({**CFG, "plan_ahead": 1}, vs, NOW) == {"doc": 0, "short": 0}


def test_a_held_news_or_uploaded_video_covers_no_future_slot():
    vs = [vid("h", verdict="pass", hold=True), vid("n", verdict="needs_human", source="news"), vid("u", verdict="pass", video_id="X", publish_at="2026-10-19T22:00:00Z")]
    assert planner.needs(CFG, vs, NOW)["doc"] == 3


def test_ready_folder_links_are_named_by_post_time_and_stale_links_go(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    (config.OUT / "a-doc").mkdir(parents=True)
    root = tmp_path / "ready"
    (root).mkdir()
    (root / "old-link").symlink_to(tmp_path)  # a link of ours that is no longer wanted
    (root / "keep.txt").write_text("not a link")
    vs = [vid("a-doc", publish_at="2026-10-22T22:00:00Z", approved=True, verdict="pass"), vid("b", verdict="pass", approved=True)]
    names = planner.sync_ready_folder(vs, root)
    assert names == ["2026-10-22_2200Z_doc_a-doc"] and (root / names[0]).resolve() == (config.OUT / "a-doc").resolve()
    assert not (root / "old-link").exists() and (root / "keep.txt").exists()
    assert planner.sync_ready_folder(vs, root) == names  # running it again changes nothing


def test_plan_view_lists_the_next_videos_and_what_is_still_to_make(monkeypatch):
    import autopilot
    cfg = {**autopilot.DEFAULTS, **CFG}
    st = {"videos": [vid("a", verdict="pass", approved=True)]}
    monkeypatch.setattr(autopilot, "load_config", lambda: cfg)
    monkeypatch.setattr(autopilot, "build_state", lambda now, c: st)
    v = autopilot.plan_view(NOW)
    assert v["needs"] == {"doc": 2, "short": 3} and v["plan_ahead"] == 3 and v["per_day"] == {"doc": 1, "short": 1}
    assert {r["status"] for r in v["rows"]} >= {"ready", "empty", "too_soon"} and all(r["at"] <= "2026-10-29T14:00:00Z" for r in v["rows"])
