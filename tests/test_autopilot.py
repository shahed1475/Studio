import json
from datetime import datetime, timedelta, timezone

import autopilot

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True}


def vid(slug="v", **kw):
    base = {"slug": slug, "source": None, "approved": False, "approved_by": None, "verdict": None, "hold": False,
            "video_id": None, "publish_at": None, "fails": 0}
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
    two = [vid("a", verdict="pass", approved=True, publish_at=iso(NOW + timedelta(days=2))), vid("b")]
    assert ("make", None) not in plan(state(two))


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
    assert [p for p in plan(state(fixable)) if p[0] == "fix"] == [("fix", "a"), ("fix", "b")]


def test_the_fixer_leaves_alone_what_it_already_tried_twice_news_drafts_and_videos_you_approved():
    st = state([vid("tried", verdict="fail", fix_attempts=2), vid("gave", verdict="fail", gave_up=True), vid("news", verdict="needs_human", source="news"),
                vid("mine", verdict="needs_human", approved=True, approved_by="you"), vid("fine", verdict="pass")])
    assert not [p for p in plan(st) if p[0] == "fix"]


def test_a_passing_video_is_never_sent_to_the_fixer():
    assert ("fix", "ok") not in plan(state([vid("ok", verdict="pass", approved=True)]))
