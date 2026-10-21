import datetime as dt

import config
import planner

NOW = dt.datetime(2026, 10, 20, 14, 0, tzinfo=dt.timezone.utc)  # Tuesday
CFG = {"slots": [{"day": d, "time": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")],
       "short_slots": [{"day": d, "time": "12:30"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")],
       "review_window_hours": 24, "prepare_hours": 12}


def vid(slug, fmt="doc", **kw):
    return {"slug": slug, "format": fmt, "verdict": None, "approved": False, "hold": False, "video_id": None, "publish_at": None, "fix_attempts": 0, "title": slug, **kw}


def test_slot_times_are_in_the_audience_time_zone_and_in_order():
    s = planner.slot_times(CFG["slots"], NOW, 3)
    assert [a.strftime("%a %H:%M") for a in s] == ["Tue 22:00", "Wed 22:00", "Thu 22:00"]  # 18:00 in New York in October is 22:00 UTC


def test_rows_say_what_fills_each_slot_and_only_due_slots_take_drafts():
    vs = [vid("up", video_id="X", publish_at="2026-10-21T22:00:00Z", verdict="pass", approved=True),
          vid("ready", verdict="pass", approved=True), vid("fixing", verdict="fail", fix_attempts=1)]
    docs = [r for r in planner.rows(CFG, vs, NOW) if r["format"] == "doc"][:5]
    # now is Tue 14:00 UTC: Tue's slot is under 24 h away, Wed's is due (inside 36 h), everything after is later
    assert [r["status"] for r in docs] == ["too_soon", "uploaded", "ready", "later", "later"]
    assert docs[2]["slug"] == "ready" and docs[3]["slug"] is None and "Thu" in docs[2]["us"]
    assert docs[3]["starts_us"].startswith("Thu") and docs[4]["starts_us"].startswith("Fri")  # Autopilot starts on Friday's slot on Thursday evening (36 h before)


def test_a_due_slot_takes_the_best_draft_else_a_new_video_and_ready_videos_take_it_first():
    assert planner.needs(CFG, [], NOW) == {"doc": 1, "short": 1}
    draft = [vid("d", verdict="fail", fix_attempts=1), vid("s", "short", verdict="needs_human")]
    assert planner.needs(CFG, draft, NOW) == {"doc": 0, "short": 0} and planner.repair_targets(CFG, draft, NOW) == {"d", "s"}
    ready = [vid("r", verdict="pass", approved=True), vid("d", verdict="fail")]
    assert planner.needs(CFG, ready, NOW)["doc"] == 0 and planner.repair_targets(CFG, ready, NOW) == set()  # the ready one took Wednesday; the draft is parked
    assert planner.needs({**CFG, "prepare_hours": 60}, [], NOW)["doc"] == 3  # a longer head start makes more slots due


def test_parked_drafts_and_unfixable_ones_cover_nothing_that_is_not_due():
    vs = [vid("gave", verdict="fail", fix_attempts=2, gave_up=True), vid("h", verdict="pass", hold=True), vid("n", verdict="needs_human", source="news")]
    assert planner.needs(CFG, vs, NOW)["doc"] == 1  # none of them covers the due slot
    vs2 = [vid(f"d{i}", verdict="fail") for i in range(5)]
    assert planner.repair_targets(CFG, vs2, NOW) == {"d0"}  # five drafts, one due slot: the best one only, the rest stay parked


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
    assert v["needs"] == {"doc": 0, "short": 1} and v["prepare_hours"] == 12 and v["per_day"] == {"doc": 1, "short": 1}
    assert {r["status"] for r in v["rows"]} >= {"ready", "empty", "too_soon", "later"} and all(r["at"] <= "2026-10-29T14:00:00Z" for r in v["rows"])


def test_a_failed_video_that_still_holds_a_slot_inside_the_window_is_repaired_even_when_the_slot_is_too_soon_for_a_new_video():
    held = vid("k", "short", verdict="fail", fix_attempts=1, publish_at="2026-10-21T16:30:00Z")  # Wed 16:30 UTC is under 24 h away
    assert planner.repair_targets(CFG, [held], NOW) == {"k"}
    far = vid("f", "short", verdict="fail", publish_at="2026-10-25T16:30:00Z")
    others = [vid("a", "short", verdict="fail", approved=True, publish_at="2026-10-21T16:30:00Z"), vid("h", "short", verdict="fail", hold=True, publish_at="2026-10-21T16:30:00Z"),
              vid("u", "short", verdict="fail", video_id="X", publish_at="2026-10-21T16:30:00Z"), vid("p", "short", verdict="pass", publish_at="2026-10-21T16:30:00Z")]
    assert planner.repair_targets(CFG, [far, *others], NOW) == set()


def test_a_passed_video_with_an_open_facts_warning_is_a_draft_not_ready():
    vs = [vid("warned", verdict="pass", approved=True, facts_open=True), vid("clean", verdict="pass", approved=True)]
    docs = [r for r in planner.rows(CFG, vs, NOW) if r["format"] == "doc"][:3]
    assert [(r["status"], r["slug"]) for r in docs[1:3]] == [("ready", "clean"), ("repairing", "warned")] or [r["status"] for r in docs[1:3]] == ["ready", "later"]
    assert not [r for r in docs if r["status"] == "ready" and r["slug"] == "warned"]
