"""30 Oct 2026, the owner: every video needs changes and no schedule may be created until they say so. `pause_scheduling` in autopilot.json stops Autopilot from giving a video a slot or
sending it to YouTube. Making, reviewing, fixing and approving go on (the owner tests by generating videos); only the two steps that put a video on a clock stop."""
from datetime import datetime, timezone

import autopilot

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True, "prepare_hours": 72}
PAUSED = {**CFG, "pause_scheduling": True}


def vid(slug="v", **kw):
    base = {"slug": slug, "source": None, "approved": False, "approved_by": None, "verdict": None, "hold": False, "video_id": None, "publish_at": None, "fails": 0, "prelaunch_ok": True}
    return {**base, **kw}


def plan(cfg, *videos):
    st = {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "news_pending": 0, "videos": list(videos)}
    return [(a["do"], a.get("slug")) for a in autopilot.plan_actions(st, cfg, NOW)]


def test_a_ready_video_is_scheduled_normally_and_not_when_the_owner_paused_scheduling():
    ready = vid("ready-short", format="short", verdict="pass", approved=True)
    assert ("schedule", "ready-short") in plan(CFG, ready)
    assert not {"schedule", "upload"} & {a for a, _ in plan(PAUSED, ready)}


def test_a_video_that_already_has_a_time_is_not_uploaded_while_paused():
    planned = vid("planned", format="doc", verdict="pass", approved=True, publish_at="2026-10-19T14:00:00Z")
    assert ("upload", "planned") in plan(CFG, planned)
    assert ("upload", "planned") not in plan(PAUSED, planned)


def test_the_executors_refuse_too_in_case_something_else_calls_them():
    assert "paused" in autopilot.do_schedule("s1", PAUSED, NOW)["skipped"]
    assert "paused" in autopilot.do_upload("s1", PAUSED, NOW)["skipped"]


def test_the_default_is_off_so_nothing_changes_for_a_studio_that_never_sets_it():
    assert autopilot.DEFAULTS["pause_scheduling"] is False


def test_a_broken_draft_is_still_repaired_while_scheduling_is_paused():
    broken = vid("d", format="doc", verdict="fail", fix_attempts=0, blocking=1)
    assert ("fix", "d") in plan(PAUSED, broken)
