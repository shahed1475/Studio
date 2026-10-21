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


def test_a_passed_video_with_a_facts_warning_is_polished_before_it_is_approved_or_scheduled():
    acts = plan(state([vid(verdict="pass", polish_wanted=True)]))
    assert ("polish", "v") in acts and ("approve", "v") not in acts and ("schedule", "v") not in acts
    acts = plan(state([vid(verdict="pass", approved=True, polish_wanted=True, publish_at=iso(NOW + timedelta(hours=60)))]))
    assert ("polish", "v") in acts and ("schedule", "v") not in acts


def test_only_one_polish_per_tick_the_soonest_slot_first():
    soon = vid("soon", verdict="pass", approved=True, polish_wanted=True, publish_at=iso(NOW + timedelta(hours=40)))
    later = vid("later", verdict="pass", approved=True, polish_wanted=True, publish_at=iso(NOW + timedelta(hours=90)))
    unslotted = vid("none", verdict="pass", polish_wanted=True)
    assert [a for a in plan(state([unslotted, later, soon])) if a[0] == "polish"] == [("polish", "soon")]


def test_no_polish_close_to_the_slot_without_a_warning_or_when_the_daily_cap_is_spent():
    close = vid(verdict="pass", approved=True, polish_wanted=True, prelaunch_ok=False, publish_at=iso(NOW + timedelta(hours=20)))
    assert not [a for a in plan(state([close])) if a[0] == "polish"]
    assert not [a for a in plan(state([vid(verdict="pass", polish_wanted=False)])) if a[0] == "polish"]
    assert not [a for a in plan(state([vid(verdict="pass", polish_wanted=True)], spend_ok=False)) if a[0] == "polish"]
    assert ("schedule", "v") not in plan(state([vid(verdict="pass", approved=True, polish_wanted=True)], spend_ok=False))  # nothing with an open facts warning is scheduled, even when the cap is spent


def test_a_video_with_an_open_facts_warning_is_never_approved_scheduled_prechecked_or_uploaded():
    for pub in (None, iso(NOW + timedelta(hours=20)), iso(NOW + timedelta(hours=10))):
        acts = plan(state([vid(verdict="pass", approved=True, polish_wanted=False, facts_open=True, prelaunch_ok=True, publish_at=pub)]))  # already polished, still warned
        assert not [a for a in acts if a[0] in ("approve", "schedule", "prelaunch", "upload", "polish")]
    assert ("approve", "v") in plan(state([vid(verdict="pass", approved=False, facts_open=False)]))  # a clean pass goes on as before




def test_build_state_marks_only_passed_unpolished_videos_with_a_facts_warning(tmp_path, monkeypatch):
    import clipper
    import config
    import llm

    warn = [{"name": "invented_facts", "ok": True, "severity": "block", "detail": "risk 4/10. x", "issues": ["x"]}, {"name": "invented_facts_watch", "ok": False, "severity": "warn", "detail": "moderate"}]
    metas = {"warned": {"review": {"verdict": "pass", "checks": warn}}, "yours": {"approved_by": "you", "review": {"verdict": "pass", "checks": warn}},
             "done": {"polish_done": {"result": "x"}, "review": {"verdict": "pass", "checks": warn}}, "clean": {"review": {"verdict": "pass", "checks": []}}}
    for name, m in metas.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "meta.json").write_text(json.dumps({"format": "doc", **m}))
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "t.json")
    monkeypatch.setattr(clipper, "clippable", lambda: 0)
    monkeypatch.setattr(llm, "spent_today", lambda now: 0.2)
    st = autopilot.build_state(NOW, {**CFG, "daily_budget_usd": 1.5})
    assert {v["slug"]: v["polish_wanted"] for v in st["videos"]} == {"warned": True, "yours": False, "done": False, "clean": False}
    assert {v["slug"]: v["facts_open"] for v in st["videos"]} == {"warned": True, "yours": False, "done": True, "clean": False}  # a warning that survived its polish still holds the video
    monkeypatch.setattr(llm, "spent_today", lambda now: 9.0)
    assert autopilot.build_state(NOW, CFG)["spend_ok"] is False


def test_do_polish_approves_a_pass_and_never_raises(tmp_path, monkeypatch):
    import config
    import fixer

    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "meta.json").write_text("{}")
    monkeypatch.setattr(config, "OUT", tmp_path)
    approved = []
    monkeypatch.setattr(autopilot, "_approve", lambda slug: approved.append(slug))
    monkeypatch.setattr(fixer, "polish", lambda slug, now=None: {"verdict": "pass", "rerendered": True})
    assert autopilot.do_polish("v", {**CFG, "auto_approve": True}, NOW)["rerendered"] is True and approved == ["v"]
    monkeypatch.setattr(fixer, "polish", lambda slug, now=None: {"verdict": "fail", "rerendered": True})
    autopilot.do_polish("v", {**CFG, "auto_approve": True}, NOW)
    assert approved == ["v"]
    monkeypatch.setattr(fixer, "polish", lambda slug, now=None: (_ for _ in ()).throw(RuntimeError("render broke")))
    assert autopilot.do_polish("v", CFG, NOW) == {"skipped": "error"}
    assert "render broke" in json.loads((tmp_path / "v" / "meta.json").read_text())["polish_done"]["result"]


def test_a_video_you_approved_gets_a_picture_reading_at_the_final_check_and_you_are_told_never_overruled(tmp_path, monkeypatch):
    import agentlog, config, prelaunch, videoinspect
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(prelaunch, "check", lambda slug, now=None: {"at": "2026-10-20T00:00:00Z", "ok": True, "problems": []})
    rows = lambda pics: [{"name": "pictures_fit_story", "ok": not pics, "severity": "warn", "times": pics, "detail": "; ".join(f"{t} s: wrong place" for t in pics) or "ok"},
                         {"name": "captions_readable", "ok": True, "severity": "warn", "detail": "fine"}]
    for name, pics in (("bad", [4.0, 9.0]), ("fine", []), ("seen", None)):
        (tmp_path / name).mkdir()
        meta = {"title": name, "approved": True, "approved_by": "you", "publish_at": "2026-10-21T16:30:00Z", "review": {"verdict": "pass", "checks": []}}
        if pics is None:
            meta["visual_check"] = {"ok": True, "rows": []}
        (tmp_path / name / "meta.json").write_text(json.dumps(meta))

        def reading(folder, pics=pics):
            assert pics is not None, "a video with a passed picture check is not read again"
            return rows(pics)
        monkeypatch.setattr(videoinspect, "visual_review", reading)
        autopilot.do_prelaunch(name, CFG, NOW)
    bad = json.loads((tmp_path / "bad" / "meta.json").read_text())
    assert bad["approved"] is True and bad["publish_at"] and bad["review"]["verdict"] == "pass"  # told, not withdrawn
    assert bad["visual_check"]["ok"] is False and bad["visual_check"]["wrong_at"] == [4.0, 9.0] and bad["prelaunch"]["ok"] is True
    assert json.loads((tmp_path / "fine" / "meta.json").read_text())["visual_check"]["ok"] is True
    assert [e["title"] for e in agentlog.recent() if e["title"].startswith("Pictures")] == ["Pictures may not fit: bad"]


def test_a_repair_waits_for_the_daily_cap_because_a_videos_two_tries_are_not_spent_on_weak_free_models():
    broken = vid("b", format="doc", verdict="fail", fix_attempts=1, publish_at=iso(NOW + timedelta(hours=10)))
    assert ("fix", "b") in plan(state([broken]))
    assert ("fix", "b") not in plan(state([broken], spend_ok=False))


def test_a_video_that_gave_up_after_two_tries_is_repaired_again_only_when_it_has_a_third_try():
    done = dict(verdict="needs_human", fix_attempts=2, gave_up=True, publish_at=iso(NOW + timedelta(hours=10)))
    assert not [a for a in plan(state([vid(**done, fix_limit=2)])) if a[0] == "fix"]
    assert [a for a in plan(state([vid(**done, fix_limit=3)])) if a[0] == "fix"]
    assert not [a for a in plan(state([vid(**{**done, "fix_attempts": 3}, fix_limit=3)])) if a[0] == "fix"]


def test_no_new_video_is_started_when_the_balance_cannot_pay_for_one_but_repairs_and_uploads_go_on():
    assert ("make", None) in plan(state([], credit_left=5.0)) and ("make", None) in plan(state([], credit_left=None))  # unknown balance: not blocked
    assert ("make", None) not in plan(state([], credit_left=autopilot.MIN_CREDIT_TO_MAKE - 0.01))
    assert ("make_short", None) not in plan(state([], credit_left=0.5)) and ("make_clip", None) not in plan(state([], credit_left=0.5, clippable=1))
    near = vid(verdict="pass", approved=True, publish_at=iso(NOW + timedelta(hours=1)))
    assert ("upload", "v") in plan(state([near], credit_left=0.2))  # an upload costs nothing


def test_a_video_that_has_cost_more_than_its_limit_is_not_repaired_again_and_the_owner_is_told_once():
    broke = vid("d", format="doc", verdict="fail", fix_attempts=1, cost=2.6, publish_at=iso(NOW + timedelta(hours=10)))
    acts = plan(state([broke]))
    assert ("fix", "d") not in acts and ("cost_stop", "d") in acts
    told = vid("d", format="doc", verdict="fail", fix_attempts=1, cost=2.6, cost_alerted=True, publish_at=iso(NOW + timedelta(hours=10)))
    assert ("cost_stop", "d") not in plan(state([told]))
    cheap = vid("d", format="doc", verdict="fail", fix_attempts=1, cost=1.2, publish_at=iso(NOW + timedelta(hours=10)))
    assert ("fix", "d") in plan(state([cheap])) and ("cost_stop", "d") not in plan(state([cheap]))
    short = vid("s", format="short", verdict="fail", fix_attempts=1, cost=0.8, publish_at=iso(NOW + timedelta(hours=10)))
    assert ("fix", "s") not in plan(state([short])) and ("cost_stop", "s") in plan(state([short]))  # a Short has a lower limit than a documentary


def test_do_cost_stop_tells_the_owner_once_and_marks_the_video(tmp_path, monkeypatch):
    import agentlog
    import config
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "meta.json").write_text(json.dumps({"title": "Delphi", "format": "doc"}))
    monkeypatch.setattr(autopilot.llm, "video_cost", lambda slug: 2.61)
    autopilot.do_cost_stop("d", CFG, NOW)
    assert json.loads((tmp_path / "d" / "meta.json").read_text())["cost_alerted"] is True
    assert any("Stopped spending" in e["title"] and "$2.61" in e["detail"] for e in agentlog.recent())


def test_workable_means_autopilot_can_still_review_repair_or_polish_the_video(monkeypatch):
    monkeypatch.setattr(autopilot.llm, "video_cost", lambda slug: 0.5)
    warn = [{"name": "invented_facts", "ok": True, "severity": "block", "detail": "risk 4/10. x", "issues": ["x"]}, {"name": "invented_facts_watch", "ok": False, "severity": "warn", "detail": "m"}]
    w = lambda d: autopilot._workable({"format": "doc", **d}, CFG, "s")
    assert w({}) and w({"review": {"verdict": None, "checks": []}})  # not reviewed yet
    assert w({"review": {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block"}]}, "fix_attempts": 1})
    assert not w({"review": {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block"}]}, "fix_attempts": 2})
    assert w({"review": {"verdict": "needs_human", "checks": [{"name": "visual_review", "ok": False, "severity": "human"}]}, "fix_attempts": 2, "fix_gave_up": True})  # a third try for pictures
    assert w({"review": {"verdict": "pass", "checks": warn}}) and not w({"review": {"verdict": "pass", "checks": warn}, "polish_done": {"round": 2}})
    assert not w({"review": {"verdict": "pass", "checks": []}}) and not w({"review": {"verdict": "fail", "checks": []}, "hold": True})
    monkeypatch.setattr(autopilot.llm, "video_cost", lambda slug: 9.0)
    assert not w({"review": {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block"}]}, "fix_attempts": 0})


def test_no_new_video_is_planned_while_a_user_studios_storage_is_full():
    assert ("make", None) in plan(state([], storage_full=False))
    assert ("make", None) not in plan(state([], storage_full=True)) and ("make_short", None) not in plan(state([], storage_full=True))
    near = vid(verdict="pass", approved=True, publish_at=iso(NOW + timedelta(hours=1)))
    assert ("upload", "v") in plan(state([near], storage_full=True))  # what exists still goes out
