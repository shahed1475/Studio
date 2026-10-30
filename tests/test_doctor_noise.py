"""Between 28 and 30 Oct the doctor drafted five skills for the same "Risks" status digest (one per 6-hour run, a new model-chosen name each time) and posted a task for each, and
triage tasks stayed open for days after their cause had stopped. A status digest is not a failure of an agent, a family gets one draft, and a quiet family's task closes."""
import datetime as dt
import json

import agentbus
import doctor
import tracetriage

NOW = dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.timezone.utc)
SKILL = {"name": "studio-fix-something", "description": "Use when X.", "steps": ["Do Y"]}


def families(tmp_path, signature="needs eyes", count=5):
    f = tmp_path / "triage.json"
    f.write_text(json.dumps({"families": [{"signature": signature, "state": "recurring", "count": count, "example": "Needs your eyes: A video", "detail": "d"}]}))
    return f


def run(tmp_path, now, chat):
    return doctor.run(now, chat=chat, get=lambda u: 200, state={}, lines=[], may_spend=True, busy=lambda: [], report=tmp_path / "doc.json", triage_file=families(tmp_path),
                      proposals=tmp_path / "proposals")


def drafts():
    return [t for t in agentbus.tasks() if t["kind"] == "skill_draft"]


def test_a_problem_family_gets_one_draft_not_one_every_six_hours(tmp_path):
    asked = []
    chat = lambda p, r: asked.append(1) or {**SKILL, "name": f"studio-fix-{len(asked)}"}
    assert run(tmp_path, NOW, chat)["drafts"] == ["studio-fix-1"]
    for hours in (6, 12, 24, 24 * 20):
        assert run(tmp_path, NOW + dt.timedelta(hours=hours), chat)["drafts"] == []
    assert len(asked) == 1 and len(drafts()) == 1


def test_after_thirty_days_a_family_that_is_still_there_may_be_drafted_again(tmp_path):
    chat = lambda p, r: SKILL
    run(tmp_path, NOW, chat)
    assert run(tmp_path, NOW + dt.timedelta(days=31), lambda p, r: {**SKILL, "name": "studio-fix-again"})["drafts"] == ["studio-fix-again"]


def test_a_draft_that_failed_is_tried_again_only_after_a_day(tmp_path):
    asked = []
    chat = lambda p, r: asked.append(1) or {}
    run(tmp_path, NOW, chat)
    run(tmp_path, NOW + dt.timedelta(hours=6), chat)
    assert len(asked) == 1
    run(tmp_path, NOW + dt.timedelta(hours=25), chat)
    assert len(asked) == 2 and not drafts()


def test_a_status_digest_is_not_a_problem_family():
    digest = [{"at": "2026-10-29T06:30:00Z", "kind": "error", "title": f"Risks: 1 need action, {n} to watch", "detail": "Running out of money"} for n in (1, 3, 4, 5)]
    briefing = [{"at": "2026-10-29T06:30:00Z", "kind": "error", "title": "Daily briefing", "detail": "x"}]
    assert not any(tracetriage.is_problem(e) for e in digest + briefing)
    real = {"at": "2026-10-29T06:30:00Z", "kind": "error", "title": "Autopilot paused: a published video has a problem", "detail": "d"}
    assert tracetriage.is_problem(real)


def test_a_triage_task_closes_when_its_family_has_been_quiet_for_three_days(tmp_path):
    old = {"at": "2026-10-26T00:00:00Z", "kind": "error", "title": "Agent evaluation failed", "detail": "a case"}
    new = {"at": "2026-10-30T10:00:00Z", "kind": "error", "title": "Thumbnail was not set", "detail": "x"}
    for e in (old, new):
        agentbus.post("triage_family", "triage", "trainer", tracetriage.signature(e["title"])[:60], reason=e["title"], now=NOW)
    tracetriage.triage(7, NOW, [old] * 3 + [new] * 3, report=tmp_path / "t.json")
    state = {t["slug"]: t["state"] for t in agentbus.tasks() if t["kind"] == "triage_family"}
    assert state[tracetriage.signature(old["title"])[:60]] == "done" and state[tracetriage.signature(new["title"])[:60]] == "open"
    assert any("quiet" in h or "no new" in h for t in agentbus.tasks() if t["state"] == "done" for h in t["history"])


def test_tasks_that_belong_to_a_person_or_a_video_are_never_closed_by_triage(tmp_path):
    agentbus.post("public_video_problem", "guardian", "owner", "some-video", reason="a public video has a problem", now=NOW)
    agentbus.post("triage_family", "triage", "trainer", "quiet family", reason="old", now=NOW)
    tracetriage.triage(7, NOW, [], report=tmp_path / "t.json")
    states = {t["kind"]: t["state"] for t in agentbus.tasks()}
    assert states["public_video_problem"] == "open" and states["triage_family"] == "done"
