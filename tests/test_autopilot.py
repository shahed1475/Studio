import json
from datetime import datetime, timedelta, timezone

import autopilot

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True, "prepare_hours": 72,  # four documentary slots are due at the fixed test time
       "slots": [{"day": d, "time": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]}


def vid(slug="v", **kw):
    base = {"slug": slug, "source": None, "approved": False, "approved_by": None, "verdict": None, "hold": False,
            "video_id": None, "publish_at": None, "fails": 0, "prelaunch_ok": True}
    return {**base, **kw}


def state(videos=(), **kw):
    return {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "news_pending": 0, "videos": list(videos), **kw}


def plan(st, cfg=None, now=NOW):
    return [(a["do"], a.get("slug")) for a in autopilot.plan_actions(st, cfg or CFG, now)]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_disabled_plans_nothing():
    assert plan(state([vid()]), {**CFG, "enabled": False}) == []


def test_unreviewed_video_gets_review():
    assert ("review", "v") in plan(state([vid()]))


def test_pass_is_scheduled_unless_news():
    assert ("schedule", "v") in plan(state([vid(verdict="pass", approved=True)]))
    assert ("schedule", "n") not in plan(state([vid("n", verdict="needs_human", source="news", approved=False)]))


def test_news_never_scheduled_even_if_pass():
    assert ("schedule", "n") not in plan(state([vid("n", verdict="pass", source="news")]))


def test_upload_only_inside_lead_window():
    far = vid(verdict="pass", approved=True, publish_at=iso(NOW + timedelta(hours=3)))
    near = vid(verdict="pass", approved=True, publish_at=iso(NOW + timedelta(hours=1)))
    assert ("upload", "v") not in plan(state([far]))
    assert ("upload", "v") in plan(state([near]))


def test_past_publish_time_is_rescheduled_not_uploaded():
    late = vid(verdict="pass", approved=True, publish_at=iso(NOW - timedelta(hours=1)))
    acts = plan(state([late]))
    assert ("schedule", "v") in acts and ("upload", "v") not in acts


def test_no_upload_when_cap_reached_or_not_connected():
    near = vid(verdict="pass", approved=True, publish_at=iso(NOW + timedelta(hours=1)))
    assert ("upload", "v") not in plan(state([near], uploads_today=1))
    assert ("upload", "v") not in plan(state([near], connected=False))


def test_held_and_failed_videos_are_skipped():
    assert plan(state([vid(hold=True)], queue_len=5, busy=True)) == []
    assert ("review", "v") not in plan(state([vid(fails=3)]))


def test_refill_ideas_when_queue_low():
    assert ("ideas", None) in plan(state(queue_len=1))
    assert ("ideas", None) not in plan(state(queue_len=5))


def test_make_when_few_waiting_and_not_when_busy_or_enough():
    assert ("make", None) in plan(state([]))
    assert ("make", None) not in plan(state([], busy=True))
    two = [vid("a", verdict="pass", approved=True), vid("b")]
    assert ("make", None) in plan(state(two))  # three slots are kept covered and only two videos are on their way
    three = [*two, vid("c", verdict="fail", fix_attempts=1)]
    assert ("make", None) not in plan(state(three))


def test_news_video_made_when_pending_and_enabled():
    assert ("make_news", None) in plan(state([], news_pending=1))
    assert ("make_news", None) not in plan(state([], news_pending=1), {**CFG, "news_videos": False})


def test_tick_runs_actions_records_errors_and_respects_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(autopilot, "CONFIG_FILE", tmp_path / "cfg.json")
    autopilot.save_config({**CFG})
    calls = []
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: state([vid()]))
    monkeypatch.setattr(autopilot, "EXECUTORS", {
        "review": lambda slug, cfg, now: calls.append(("review", slug)),
        "make": lambda slug, cfg, now: (_ for _ in ()).throw(RuntimeError("ollama down")),
        "ideas": lambda slug, cfg, now: calls.append(("ideas", slug)),
    })
    res = autopilot.tick(NOW)
    assert ("review", "v") in calls
    assert any("ollama down" in e for e in res["errors"])
    assert json.loads((tmp_path / "state.json").read_text())["errors"]
    import fcntl
    with open(tmp_path / "lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert autopilot.tick(NOW) == {"skipped": "locked"}


def test_do_make_finishes_video_with_thumbnails_and_seo_title(tmp_path, monkeypatch):
    import run, seo, thumbnail
    folder = tmp_path / "doc-x"
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"title": "Old title", "format": "doc"}))
    order = []
    monkeypatch.setattr(run, "cmd_doc", lambda *a: order.append("doc") or folder)
    monkeypatch.setattr(thumbnail, "make", lambda f: order.append("thumbs"))
    def fake_seo(f):
        order.append("seo")
        m = json.loads((f / "meta.json").read_text())
        m["seo"] = {"titles": ["Better Title: What Happened?"]}
        (f / "meta.json").write_text(json.dumps(m))
    monkeypatch.setattr(seo, "make", fake_seo)
    autopilot.do_make(None, CFG, NOW)
    assert order == ["doc", "thumbs", "seo"]
    assert json.loads((folder / "meta.json").read_text())["title"] == "Better Title: What Happened?"


def test_human_approved_flagged_video_is_scheduled():
    flagged = vid("f", verdict="needs_human", approved=True, approved_by="you")
    news = vid("n", verdict="needs_human", source="news", approved=True, approved_by="you")
    unapproved = vid("u", verdict="needs_human", approved=False)
    acts = plan(state([flagged, news, unapproved]))
    assert ("schedule", "f") in acts and ("schedule", "n") in acts and ("schedule", "u") not in acts


def test_reviewer_approval_alone_never_schedules_news():
    assert ("schedule", "n") not in plan(state([vid("n", verdict="pass", source="news", approved=True, approved_by="reviewer-agent")]))


def test_clip_short_comes_before_a_fresh_short():
    got = plan(state(clippable=2, queue_len=5))
    assert ("make_clip", None) in got and ("make_short", None) not in got


def test_clip_works_even_with_an_empty_topic_queue():
    assert ("make_clip", None) in plan(state(clippable=1, queue_len=0))


def test_without_clippable_docs_a_fresh_short_is_made_as_before():
    got = plan(state(clippable=0, queue_len=5))
    assert ("make_short", None) in got and ("make_clip", None) not in got
    assert ("make_short", None) in plan(state(queue_len=5))  # state without the key


def test_clips_respect_the_waiting_shorts_limit_and_the_shorts_switch():
    waiting = [vid(f"s{i}", format="short", verdict="pass") for i in range(CFG["max_waiting_shorts"])]
    assert ("make_clip", None) not in plan(state(waiting, clippable=2))
    assert ("make_clip", None) not in plan(state(clippable=2), {**CFG, "shorts": False})


def test_build_state_counts_clippable_docs(tmp_path, monkeypatch):
    import clipper
    import config

    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(clipper, "clippable", lambda: 3)
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "t.json")
    assert autopilot.build_state(NOW, CFG)["clippable"] == 3


def test_make_clip_executor_finishes_the_short(monkeypatch):
    import clipper

    calls = []
    monkeypatch.setattr(clipper, "make_next", lambda: "folder")
    monkeypatch.setattr(autopilot, "finish_video", lambda f: calls.append(f))
    autopilot.do_make_clip(None, CFG, NOW)
    assert calls == ["folder"]
    monkeypatch.setattr(clipper, "make_next", lambda: None)
    autopilot.do_make_clip(None, CFG, NOW)
    assert calls == ["folder"]  # nothing made, nothing finished


def test_blocked_or_human_check_videos_go_to_the_fixer_first():
    fixable = vid("a", verdict="fail") , vid("b", verdict="needs_human")
    assert [p for p in plan(state(fixable)) if p[0] == "fix"] == [("fix", "a")]  # one video at a time


def test_the_fixer_leaves_alone_what_it_already_tried_twice_news_drafts_and_videos_you_approved():
    st = state([vid("tried", verdict="fail", fix_attempts=2), vid("gave", verdict="fail", gave_up=True), vid("news", verdict="needs_human", source="news"),
                vid("mine", verdict="needs_human", approved=True, approved_by="you"), vid("fine", verdict="pass")])
    assert not [p for p in plan(st) if p[0] == "fix"]


def test_a_passing_video_is_never_sent_to_the_fixer():
    assert ("fix", "ok") not in plan(state([vid("ok", verdict="pass", approved=True)]))


def test_a_video_the_reviewer_passed_earlier_but_nobody_approved_gets_the_reviewers_approval():
    assert ("approve", "p") in plan(state([vid("p", verdict="pass")]))
    assert ("approve", "p") not in plan(state([vid("p", verdict="pass", approved=True)]))
    assert ("approve", "p") not in plan(state([vid("p", verdict="pass")]), {**CFG, "auto_approve": False})
    assert ("approve", "n") not in plan(state([vid("n", verdict="needs_human")]))


def test_a_clearly_bad_picture_set_is_not_auto_approved_but_a_few_warnings_are(tmp_path, monkeypatch):
    import config, videoinspect
    monkeypatch.setattr(config, "OUT", tmp_path)

    def video(name):
        d = tmp_path / name
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"review": {"verdict": "pass", "checks": []}}))
    rows = lambda pics, cap="fine": [{"name": "pictures_fit_story", "ok": not pics, "severity": "warn", "detail": "; ".join(f"{i} s: bad" for i in pics) or "ok"},
                                      {"name": "captions_readable", "ok": cap == "fine", "severity": "warn", "detail": cap}]
    video("bad")
    monkeypatch.setattr(videoinspect, "visual_review", lambda folder: rows([1, 2]))
    assert autopilot.visually_ok("bad") is False
    meta = json.loads((tmp_path / "bad" / "meta.json").read_text())
    assert meta["review"]["verdict"] == "needs_human" and meta["approved"] is False and meta["review"]["checks"][-1]["name"] == "visual_review"
    video("garbled")
    monkeypatch.setattr(videoinspect, "visual_review", lambda folder: rows([], "caption reads TOF LOST TALESR, garbled"))
    assert autopilot.visually_ok("garbled") is False
    video("ok")
    monkeypatch.setattr(videoinspect, "visual_review", lambda folder: rows([1]))
    assert autopilot.visually_ok("ok") is True
    monkeypatch.setattr(videoinspect, "visual_review", lambda folder: (_ for _ in ()).throw(RuntimeError("no model")))
    assert autopilot.visually_ok("ok") is True  # a reading that cannot run never blocks


def test_no_new_videos_while_three_of_that_kind_are_stuck_failed():
    st = state([vid(f"s{i}", format="short", verdict="fail", fix_attempts=2) for i in range(3)], queue_len=5)
    assert "make_short" not in [d for d, _ in plan(st)]
    st["videos"] = st["videos"][:2]
    assert "make_short" in [d for d, _ in plan(st)]
    docs = state([vid(f"d{i}", format="doc", verdict="needs_human") for i in range(3)], queue_len=5)
    assert "make" not in [d for d, _ in plan(docs)]


def test_make_videos_off_plans_repairs_and_uploads_but_no_new_video_or_research():
    st = state([vid("a", verdict="fail", fix_attempts=0), vid("b")], queue_len=0)
    acts = [d for d, _ in plan(st, {**CFG, "make_videos": False})]
    assert "fix" in acts and "review" in acts
    assert not {"ideas", "make", "make_short", "make_clip", "make_news"} & set(acts)
    assert "ideas" in [d for d, _ in plan(state([vid("b")], queue_len=0))]


def test_the_next_video_to_repair_is_a_documentary_then_one_already_in_progress_then_the_closest_to_passing():
    st = state([vid("s1", format="short", verdict="fail", blocking=1), vid("d9", format="doc", verdict="fail", blocking=3),
                vid("d2", format="doc", verdict="fail", blocking=1), vid("d5", format="doc", verdict="fail", blocking=4, fix_attempts=1)])
    assert [p for p in plan(st) if p[0] == "fix"] == [("fix", "d5")]
    st["videos"] = [v for v in st["videos"] if v["slug"] != "d5"]
    assert [p for p in plan(st) if p[0] == "fix"] == [("fix", "d2")]
    st["videos"] = [v for v in st["videos"] if v["slug"].startswith("s")]
    assert [p for p in plan(st) if p[0] == "fix"] == [("fix", "s1")]


def test_nothing_new_is_made_while_a_broken_video_can_still_be_repaired_but_it_is_once_none_can():
    broken = state([vid("d", format="doc", verdict="fail")], queue_len=5)
    assert not {"make", "make_short", "make_clip", "make_news", "ideas"} & {d for d, _ in plan(broken)}
    done = state([vid("d", format="doc", verdict="fail", fix_attempts=2)], queue_len=5)
    assert "make" in [d for d, _ in plan(done)]


def test_a_tick_finishes_quick_repairs_then_stops_after_a_re_render(tmp_path, monkeypatch):
    import config
    for name in ("t1", "t2", "v1", "v2"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "meta.json").write_text("{}")
    monkeypatch.setattr(config, "OUT", tmp_path)
    videos = {n: vid(n, format="doc", verdict="fail") for n in ("t1", "t2", "v1", "v2")}
    ran = []

    def fix(slug, cfg, now):
        ran.append(slug)
        videos[slug]["verdict"] = "pass"  # repaired
        return {"rerendered": slug.startswith("v")}
    monkeypatch.setattr(autopilot, "load_config", lambda: {**CFG})
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: state(list(videos.values())))
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(autopilot, "LOG", tmp_path / "log")
    monkeypatch.setattr(autopilot, "EXECUTORS", {**{k: (lambda slug, cfg, now: None) for k in autopilot.EXECUTORS}, "fix": fix})
    autopilot.tick(NOW)
    assert ran == ["t1", "t2", "v1"]  # the two quick ones, then the re-render ends the tick; v2 waits for the next one


def test_status_names_the_video_autopilot_is_working_on(monkeypatch):
    st = state([vid("d1", format="doc", verdict="fail", blocking=2, problems=["title_matches", "visual_review"], title="The Pied Piper", fix_attempts=1), vid("ok", verdict="pass")])
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: st)
    monkeypatch.setattr(autopilot, "load_config", lambda: {**CFG})
    assert autopilot.focus_view(NOW) == {"slug": "d1", "title": "The Pied Piper", "problems": ["title_matches", "visual_review"], "tries": 1}
    st["videos"] = [vid("ok", verdict="pass")]
    assert autopilot.focus_view(NOW) is None


def test_the_tick_ends_with_a_finishing_pass_so_a_repaired_video_is_scheduled_at_once(tmp_path, monkeypatch):
    import config
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "meta.json").write_text("{}")
    monkeypatch.setattr(config, "OUT", tmp_path)
    videos = {"f": vid("f", format="doc", verdict="fail")}
    ran = []

    def fix(slug, cfg, now):
        ran.append(("fix", slug))
        videos["f"].update(verdict="pass", approved=True, approved_by="reviewer-agent")  # the repair passed and approved it
        return {"rerendered": True}
    monkeypatch.setattr(autopilot, "MAX_ROUNDS", 1)
    monkeypatch.setattr(autopilot, "load_config", lambda: {**CFG})
    monkeypatch.setattr(autopilot, "build_state", lambda now, cfg: state(list(videos.values())))
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "lock")
    monkeypatch.setattr(autopilot, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(autopilot, "LOG", tmp_path / "log")
    monkeypatch.setattr(autopilot, "EXECUTORS", {**{k: (lambda slug, cfg, now, k=k: ran.append((k, slug))) for k in autopilot.EXECUTORS}, "fix": fix})
    autopilot.tick(NOW)
    assert ran == [("fix", "f"), ("schedule", "f")]


def test_nothing_is_made_or_repaired_for_slots_that_are_not_due_yet():
    cfg = {**CFG, "prepare_hours": 0}  # only slots inside the 24 hour window plus zero hours: none is due at the fixed test time
    draft = state([vid("d", format="doc", verdict="fail")], queue_len=5)
    acts = [d for d, _ in plan(draft, cfg)]
    assert "fix" not in acts and "make" not in acts and "make_short" not in acts  # the draft is parked, nothing new is started
    later = [d for d, _ in plan(draft, {**cfg, "prepare_hours": 40})]
    assert "fix" in later  # the same draft is worked on once its slot is due


def test_a_due_slot_with_no_draft_gets_a_new_video_but_a_ready_video_is_used_first():
    cfg = {**CFG, "prepare_hours": 10}
    assert ("make", None) in plan(state([], queue_len=5), cfg)
    assert ("make", None) not in plan(state([vid("r", format="doc", verdict="pass", approved=True)], queue_len=5), cfg)


def test_a_scheduled_video_gets_its_final_check_when_the_review_window_opens_and_only_then_uploads():
    near = iso(NOW + timedelta(hours=26))
    far = iso(NOW + timedelta(days=4))
    due = vid("due", verdict="pass", approved=True, approved_by="reviewer-agent", publish_at=near, prelaunch_ok=False)
    later = vid("later", verdict="pass", approved=True, approved_by="reviewer-agent", publish_at=far, prelaunch_ok=False)
    acts = plan(state([due, later]))
    assert ("prelaunch", "due") in acts and ("prelaunch", "later") not in acts and ("upload", "due") not in acts
    checked = {**due, "prelaunch_ok": True, "publish_at": iso(NOW + timedelta(hours=1))}
    assert ("upload", "due") in plan(state([checked])) and ("prelaunch", "due") not in plan(state([checked]))
    soon_unchecked = {**due, "publish_at": iso(NOW + timedelta(hours=1))}
    acts = plan(state([soon_unchecked]))
    assert ("prelaunch", "due") in acts and ("upload", "due") not in acts  # no upload without a passed final check


def test_a_failed_final_check_pulls_a_reviewer_approved_video_back_but_never_one_you_approved(tmp_path, monkeypatch):
    import agentlog, config, prelaunch
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(prelaunch, "check", lambda slug, now=None: {"at": "2026-10-20T00:00:00Z", "ok": False, "problems": ["video: audio: no audio stream"]})
    for name, by in (("agent", "reviewer-agent"), ("mine", "you")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "meta.json").write_text(json.dumps({"title": name, "approved": True, "approved_by": by, "publish_at": "2026-10-21T16:30:00Z", "fix_attempts": 2, "review": {"verdict": "pass", "checks": []}}))
        autopilot.do_prelaunch(name, CFG, NOW)
    a = json.loads((tmp_path / "agent" / "meta.json").read_text())
    assert a["approved"] is False and "publish_at" not in a and a["review"]["verdict"] == "fail" and a["fix_attempts"] == 0
    assert a["review"]["checks"][-1]["name"] == "prelaunch" and a["prelaunch"]["ok"] is False
    m = json.loads((tmp_path / "mine" / "meta.json").read_text())
    assert m["approved"] is True and m["publish_at"] and m["review"]["verdict"] == "pass" and m["prelaunch"]["ok"] is False  # told, not withdrawn
    assert {e["title"][:6] for e in agentlog.recent()} >= {"Pulled", "Final "}
