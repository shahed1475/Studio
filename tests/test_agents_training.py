import datetime as dt
import json

import agentbus
import agentlog
import agenteval
import escalate
import lessons
import playbook
import tracetriage
import unstick

NOW = agenteval.NOW


def test_every_behaviour_check_of_the_agents_passes():
    res = agenteval.run(write=False)
    assert res["failed"] == 0, [c for c in res["cases"] if not c["ok"]]
    assert res["passed"] >= 14


def test_each_playbook_is_complete_and_the_brief_is_capped_and_ordered():
    for a in agenteval.REQUIRED_AGENTS:
        assert playbook.problems(a) == [], a
    b = playbook.brief("seo", max_chars=400)
    assert b.startswith("Playbook of the seo agent") and len(b) <= 400
    assert playbook.model_role("guardian") == "review" and playbook.model_role("nobody") == "cheap"
    assert playbook.problems("nobody") == ["no playbook for nobody"]


def test_a_playbook_missing_a_section_or_with_a_bad_model_role_is_reported(tmp_path):
    (tmp_path / "x.md").write_text("model_role: gpt\n## Role\nr\n## Goal\ng\n")
    got = playbook.problems("x", tmp_path)
    assert any("model_role" in p for p in got) and any("When" in p for p in got)


def test_lessons_match_by_problem_shape_prefer_what_worked_and_prune_what_never_did():
    with agenteval.sandbox():
        lessons.record("fixer", "title_matches failed on video 12", "new_title", True, NOW)
        lessons.record("fixer", "description repair failed", "rewrite_description", False, NOW)
        for _ in range(3):
            lessons.record("fixer", "description repair failed", "rewrite_description", False, NOW)
        got = lessons.recall("fixer", "title_matches failed on video 99")
        assert got and got[0]["tried"] == "new_title"
        assert "worked 1x" in lessons.brief("fixer", "title_matches failed on video 7")
        assert "do not repeat" in lessons.brief("fixer", "description repair failed")
        assert lessons.recall("seo", "title_matches failed") == []  # another agent's notes are not used
        assert lessons.prune() == 1 and lessons.recall("fixer", "description repair failed") == []


def test_bus_task_lifecycle_and_owner_handoff():
    with agenteval.sandbox():
        t = agentbus.post("repair_video", "guardian", "autopilot", "s1", reason="r", now=NOW)
        assert [x["id"] for x in agentbus.open_for("autopilot")] == [t["id"]]
        agentbus.claim(t["id"], "autopilot", NOW)
        assert agentbus.open_for("autopilot") == [] and agentbus.summary()["working"] == 1
        assert agentbus.close_for("s1", "uploaded again", now=NOW) == 1
        o = agentbus.post("needs_owner", "fixer", "owner", "s2", now=NOW)
        agentbus.to_owner(o["id"], "tried two fixes", NOW)
        assert agentbus.summary() == {"open": 0, "working": 0, "done": 1, "failed": 0, "owner": 1}


def test_ladder_solves_by_a_remembered_fix_without_asking_a_model_and_learns_from_a_diagnosis():
    with agenteval.sandbox():
        lessons.record("fixer", "title keeps failing", "new_title", True, NOW)
        asked = []
        fixes = {"new_title": ("t", lambda: (True, "done")), "other": ("o", lambda: (True, "done"))}
        res = escalate.solve("fixer", "title keeps failing", "e", fixes, chat=lambda p, r: asked.append(r) or {}, now=NOW)
        assert res["solved"] and res["fix"] == "new_title" and asked == []
        seen = []
        res = escalate.solve("fixer", "a brand new problem", "e", fixes, chat=lambda p, r: seen.append((r, p)) or {"cause": "c", "fixes": ["other"]}, now=NOW)
        assert res["solved"] and res["fix"] == "other" and res["cause"] == "c"
        assert seen[0][0] == "review" and "Playbook of the fixer agent" in seen[0][1] and "untrusted" in seen[0][1] and "other: o" in seen[0][1]
        assert lessons.recall("fixer", "a brand new problem")[0]["tried"] == "other"


def test_a_second_role_gives_a_second_opinion_when_the_first_fix_fails():
    with agenteval.sandbox():
        roles = []

        def chat(p, role):
            roles.append(role)
            return {"cause": "x", "fixes": ["a"] if role == "review" else ["b"]}
        res = escalate.solve("fixer", "hard problem", "e", {"a": ("a", lambda: (False, "no")), "b": ("b", lambda: (True, "yes"))}, chat=chat, now=NOW)
        assert roles == ["review", "script"] and res["fix"] == "b" and [t["ok"] for t in res["tried"]] == [False, True]


def test_triage_groups_the_feed_marks_known_ones_and_posts_tasks_for_the_rest(tmp_path):
    ev = lambda title, day="2026-10-25": {"at": f"{day}T10:00:00Z", "kind": "found", "title": title, "detail": "d"}
    events = [ev("Re-check: a scheduled video has a problem (Alpha 1)"), ev("Re-check: a scheduled video has a problem (Beta 22)"),
              ev("Re-check: a scheduled video has a problem (Gamma)"), ev("Could not read the YouTube login"), ev("Old thing", "2026-09-01"),
              {"at": "2026-10-25T10:00:00Z", "kind": "info", "title": "fine"}]
    with agenteval.sandbox():
        rep = tracetriage.triage(7, NOW, events, report=tmp_path / "t.json")
        by = {f["example"]: f for f in rep["families"]}
        top = rep["families"][0]
        assert top["count"] == 3 and top["state"] == "recurring" and len(rep["families"]) == 2
        assert {t["kind"] for t in agentbus.tasks()} == {"triage_family"} and len(agentbus.tasks()) == 2
        lessons.record("guardian", "Could not read the YouTube login", "wait", True, NOW)
        again = tracetriage.triage(7, NOW, events, report=tmp_path / "t.json", post=False)
        assert {f["state"] for f in again["families"] if "login" in f["example"]} == {"known"}
    assert json.loads((tmp_path / "t.json").read_text())["events"] == 6


def test_unstick_gives_the_stuck_draft_to_the_ladder_and_reviews_the_result(tmp_path, monkeypatch):
    import fixer
    with agenteval.sandbox() as root:
        stuck = {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block", "detail": "title promises too much"}]}
        f = agenteval._video(root, "d1", review=stuck, fix_attempts=2, title="Old Title Here")
        monkeypatch.setattr(unstick, "affordable", lambda *a: True)
        monkeypatch.setattr(fixer, "pick_title", lambda meta, others, chat=None, *a, **k: "Mami Wata: The Honest Story")
        reviews = []
        res = unstick.run(NOW, out=root / "out", review=lambda folder: reviews.append(folder.name) or {"verdict": "pass"},
                          ladder_chat=lambda p, r: {"cause": "title", "fixes": ["new_title"]}, lock_file=root / "lock")
        m = agenteval._meta(f)
        assert res["solved"] and res["fix"] == "new_title" and m["title"] == "Mami Wata: The Honest Story" and m["fix_attempts"] == 0 and reviews == ["d1"]
        assert m["ladder"]["tries"] == 1 and "review" not in m  # the old review is dropped; Autopilot reviews again
        assert unstick.run(NOW, out=root / "out", lock_file=root / "lock") == {"skipped": "no stuck draft"}


def test_unstick_with_no_working_fix_hands_the_draft_to_the_owner_once(monkeypatch):
    with agenteval.sandbox() as root:
        stuck = {"verdict": "needs_human", "checks": [{"name": "facts", "ok": False, "severity": "human", "detail": "d"}]}
        f = agenteval._video(root, "d2", review=stuck, fix_attempts=2)
        monkeypatch.setattr(unstick, "affordable", lambda *a: False)  # the day's money is spent: no model is asked
        res = unstick.run(NOW, out=root / "out", ladder_chat=lambda p, r: 1 / 0, lock_file=root / "lock")
        assert not res["solved"] and res["owner"] and [t["state"] for t in agentbus.tasks()] == ["owner"]
        assert agenteval._meta(f)["ladder"]["tries"] == 1


def test_guardian_thumbnail_text_and_reissue_leave_the_old_video_alone(monkeypatch):
    import guardian
    import thumbnail
    with agenteval.sandbox() as root:
        f = agenteval._video(root, "t1", video_id="V9", publish_at=agenteval.FUTURE, title="Mami Wata: The Real Story", description="Mami Wata is a spirit of the sea.",
                             thumb_hook="MAMI WATA REAL STORY", thumbnail="thumb.jpg")
        made = []
        monkeypatch.setattr(thumbnail, "hook_for", lambda meta, avoid=(), chat=None: "SPIRIT OF THE SEA")
        monkeypatch.setattr(thumbnail, "make", lambda folder, hook=None: made.append(hook) or (folder / "thumb.jpg").write_bytes(b"x"))
        sent = []
        monkeypatch.setattr(guardian, "_set_thumbnail", lambda yt, vid, path: sent.append((vid, path.name)))
        res = agenteval._guard(root, agenteval.FakeYT())
        assert made == ["SPIRIT OF THE SEA"] and sent == [("V9", "thumb.jpg")] and res["actions"][0]["did"] == ["thumbnail text: SPIRIT OF THE SEA"]
        assert guardian.reissue(f, agenteval._meta(f), NOW) is False  # no hold, so not reissued


def test_the_risks_card_row_for_agents_follows_the_evaluation(tmp_path):
    import risk
    with agenteval.sandbox() as root:
        assert risk.agents_row(NOW, tmp_path / "none.json", None, tmp_path / "nodoc.json")["level"] == "watch"
        ok = tmp_path / "ev.json"
        ok.write_text(json.dumps({"at": "2026-10-26T06:00:00Z", "passed": 9, "failed": 0, "cases": []}))
        assert risk.agents_row(NOW, ok, None, tmp_path / "nodoc.json")["level"] == "ok"
        ok.write_text(json.dumps({"at": "2026-10-26T06:00:00Z", "passed": 8, "failed": 1, "cases": [{"case": "x", "ok": False}]}))
        assert risk.agents_row(NOW, ok, None, tmp_path / "nodoc.json")["level"] == "act"
        ok.write_text(json.dumps({"at": "2026-10-20T06:00:00Z", "passed": 9, "failed": 0, "cases": []}))
        assert risk.agents_row(NOW, ok, None, tmp_path / "nodoc.json")["level"] == "watch"


def test_the_worker_runs_the_guardian_unstick_and_the_daily_agent_review():
    import worker
    names = {j["name"]: j for j in worker.JOBS}
    assert names["guardian"]["cmds"] == [["guardian"]] and names["unstick"]["every"] >= 10800 and names["agent-review"]["at"] == "05:30"


def test_the_seo_prompt_carries_the_playbook_and_a_remembered_lesson(tmp_path, monkeypatch):
    import scriptgen
    import seo
    folder = tmp_path / "v"
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"topic": "Mami Wata", "title": "Old", "description": "Old.", "lines": [{"text": "She rises."}], "tags": []}))
    monkeypatch.setattr(seo, "core_phrase", lambda m: "mami wata")
    monkeypatch.setattr(seo, "suggest", lambda q: [])
    monkeypatch.setattr(seo, "competitors", lambda core: [])
    prompts = []
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: prompts.append(p) or {"titles": ["Mami Wata: The Real Story"], "description_intro": "Mami Wata rises.", "tags": []})
    with agenteval.sandbox():
        lessons.record("seo", "mami wata", "name first then twist titles", True, NOW)
        seo.make(folder)
    assert "Playbook of the seo agent" in prompts[0] and "name first then twist titles" in prompts[0]


def test_every_command_and_autopilot_action_maps_to_an_agent_with_a_playbook():
    import agents
    assert agents.for_command("recheck") == "recheck" and agents.for_command("doc") == "creator" and agents.for_command("nonsense") is None
    assert agents.for_action("make_clip") == "clipper" and agents.for_action("upload") == "publisher" and agents.for_action("cost_stop") == "autopilot"
    assert all(agents.for_action(a) in agents.AGENTS for a in agents.ACTIONS)
    assert agents.problems() == []


def test_a_model_call_under_an_agent_carries_its_role_and_limits_and_one_outside_does_not(monkeypatch, tmp_path):
    import json as _json

    import llm
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "SETTINGS_FILE", tmp_path / "settings.json")
    llm.save_config({**llm.DEFAULTS, "enabled": True, "models": {"script": "v/w", "review": "v/c", "cheap": "v/s"}})
    llm.SETTINGS_FILE.write_text(_json.dumps({"openrouter_key": "sk-test"}))
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append(payload) or {"choices": [{"message": {"content": '{"ok": 1}'}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}})
    import playbook
    llm.chat("plain prompt", "cheap", now=NOW)
    with playbook.acting_as("publisher"):
        llm.chat("plain prompt", "cheap", now=NOW)
    text = lambda p: p["messages"][-1]["content"] if "messages" in p else str(p)
    assert text(sent[0]).startswith("plain prompt") and "Playbook of the publisher agent" in text(sent[1]) and "Never upload twice" not in text(sent[0]) and text(sent[1]).endswith("plain prompt")


def test_doctor_scan_reads_results_from_the_worker_log_and_a_new_install_is_not_a_fault():
    import doctor
    import worker
    ts = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"{ts(5)} recheck recheck -> exit 0", f"{ts(4)} recheck recheck -> exit 3", f"{ts(3)} recheck recheck timed out after 900s", f"{ts(1)} health health -> exit 0"]
    assert doctor.log_results("recheck", lines) == [True, False, False]
    rows = {r["agent"]: r["status"] for r in doctor.scan(NOW, {"recheck": ts(1), "health": ts(1)}, lines, worker.JOBS)}
    assert rows["recheck"] == "failing" and rows["health"] == "ok" and rows["guardian"] == "not_yet"
    assert doctor.scan(NOW, {}, [], worker.JOBS) and {r["status"] for r in doctor.scan(NOW, {}, [], worker.JOBS)} == {"not_yet"}


def test_doctor_cannot_restart_the_main_loop_or_run_a_job_while_a_render_runs(monkeypatch):
    import doctor
    import risk
    import worker
    ran = []
    f = doctor.fixes_for("autopilot", "autopilot", worker.JOBS, runner=lambda j: ran.append(j) or 0)
    assert f["rerun_job"][1]()[0] is False and ran == []
    g = doctor.fixes_for("recheck", "recheck", worker.JOBS, runner=lambda j: ran.append(j["name"]) or 0)
    monkeypatch.setattr(risk, "running_jobs", lambda: ["run.py doc"])
    assert g["rerun_job"][1]() == (False, "a render is running: not now") and ran == []
    monkeypatch.setattr(risk, "running_jobs", lambda: [])
    assert g["rerun_job"][1]()[0] is True and ran == ["recheck"]


def test_setup_requests_keep_exact_commands_for_the_owner_and_the_risk_row_shows_the_doctor(tmp_path):
    import risk
    with agenteval.sandbox() as root:
        t = agentbus.post("setup_request", "doctor", "owner", "dashboard", reason="x", now=NOW, commands=["docker compose restart dashboard", "python run.py agents"])
        assert t["commands"] == ["docker compose restart dashboard", "python run.py agents"]
        ev = root / "ev.json"
        ev.write_text(json.dumps({"at": "2026-10-26T06:00:00Z", "passed": 14, "failed": 0, "cases": []}))
        doc = root / "doc.json"
        doc.write_text(json.dumps({"agents": [{"agent": "recheck", "status": "stale"}], "needs": ["dashboard"]}))
        row = risk.agents_row(NOW, ev, root / "none.json", doc)
        assert row["level"] == "watch" and "recheck unhealthy" in row["evidence"] and "missing setup: dashboard" in row["evidence"]
        doc.write_text(json.dumps({"agents": [{"agent": "recheck", "status": "ok"}], "needs": []}))
        assert risk.agents_row(NOW, ev, root / "none.json", doc)["level"] == "ok"


def test_triage_counts_problems_and_not_routine_news():
    ev = lambda kind, title, detail="d": {"at": "2026-10-25T10:00:00Z", "kind": kind, "title": title, "detail": detail}
    events = [ev("found", "New competitor: Ancient Explain", "63,400 subscribers"), ev("found", "Added to your reference channels: X", "15 videos in the last year"),
              ev("found", "Re-check: a scheduled video has a problem (A)"), ev("found", "YouTube changed its page: Spam", "Creators should disclose"),
              ev("error", "Needs your eyes: Delphi", "reviewer says fail"), ev("applied", "Guardian repaired the metadata of A"), ev("info", "Started")]
    import tempfile
    from pathlib import Path
    with agenteval.sandbox(), tempfile.TemporaryDirectory() as d:
        rep = tracetriage.triage(7, NOW, events, report=Path(d) / "t.json", post=False)
    assert {f["example"][:12] for f in rep["families"]} == {"Re-check: a ", "YouTube chan", "Needs your e"}


def test_the_scope_case_starts_from_a_clean_scope_even_when_the_command_set_an_agent():
    import playbook
    playbook.set_agent("evaluator")
    try:
        ok, why = agenteval.case_playbook_scope_injects_role_and_limits_only_when_acting()
    finally:
        playbook.set_agent(None)
    assert ok, why


def _blocked(tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    return f / "sub"  # a path whose parent is a file: every mkdir and write under it fails


def test_the_guardian_goes_on_to_the_next_video_when_one_fails(monkeypatch):
    import guardian
    with agenteval.sandbox() as root:
        a = agenteval._video(root, "a-first", video_id="V1", publish_at=agenteval.FUTURE)
        b = agenteval._video(root, "b-second", video_id="V2", publish_at=agenteval.FUTURE)

        class YT(agenteval.FakeYT):
            def videos(self):
                v = super().videos()
                orig = v.update
                yt = self

                def update(**k):
                    if k["body"]["id"] == "V1":
                        raise RuntimeError("YouTube refused")
                    return orig(**k)
                v.update = update
                return v
        res = agenteval._guard(root, YT())
        assert agenteval._meta(b)["title"].lower().startswith("mami wata") and [x["slug"] for x in res["actions"]] == ["b-second"]
        assert any("could not finish checking a-first" in e["title"] for e in agentlog.recent(10))


def test_unwritable_places_never_crash_an_agent(tmp_path, monkeypatch):
    import doctor
    import guardian
    import records
    bad = _blocked(tmp_path)
    assert doctor.propose("recheck", "p", "e", NOW, chat=lambda p, r: {}, may_spend=True, directory=bad) is None
    fam = {"example": "A real problem", "detail": "d", "count": 5}
    assert doctor.draft_skill(fam, NOW, chat=lambda p, r: {"name": "studio-ok-name", "description": "Use when X.", "steps": ["Do Y"]}, directory=bad) is None
    assert lessons.record("fixer", "some problem", "fix", True, NOW, file=bad / "l.jsonl") is None
    assert lessons.prune(bad / "l.jsonl") == 0
    with agenteval.sandbox():
        res = doctor.run(NOW, chat=lambda p, r: {}, get=lambda u: 200, state={}, lines=[], may_spend=False, busy=lambda: [], report=bad / "d.json", triage_file=tmp_path / "x.json", proposals=bad)
        assert res["saved"] is False
        owner = escalate.solve("fixer", "unknown problem", "e", {"a": ("a", lambda: (False, "no"))}, may_spend=False, bus_file=bad / "t.json", now=NOW)
        assert owner["owner"] is True and not owner["solved"]
        rep = tracetriage.triage(7, NOW, [], report=bad / "t.json", post=False)
        assert rep["saved"] is False
        assert agenteval.run(write=True, result=bad / "e.json")["saved"] is False
        f = agenteval._video(tmp_path, "held", video_id="V", publish_at=agenteval.FUTURE, hold=True)

        def boom(folder, fn):
            raise OSError("disk full")
        monkeypatch.setattr(records, "update", boom)
        assert guardian.reissue(f, agenteval._meta(f), NOW) is False
        stuck = {"verdict": "fail", "checks": [{"name": "facts", "ok": False, "severity": "block"}]}
        agenteval._video(tmp_path, "d9", review=stuck, fix_attempts=2)
        assert unstick.run(NOW, out=tmp_path / "out", lock_file=tmp_path / "lock") == {"skipped": "could not save the video record"}


def test_the_inbox_never_raises_when_it_cannot_save(tmp_path):
    import doctor
    import guardian
    bad = _blocked(tmp_path)
    with agenteval.sandbox() as root:
        agentbus.FILE = bad / "tasks.json"
        t = agentbus.post("setup_request", "doctor", "owner", "x", reason="r", commands=["python run.py agents"], now=NOW)
        assert t["state"] == "unsaved" and t["saved"] is False and t["commands"] == ["python run.py agents"]
        assert agentbus.finish("t00001", "done", now=NOW) is None and agentbus.close_for("x", "done", now=NOW) == 0
        res = doctor.run(NOW, chat=lambda p, r: {}, get=lambda u: 500, state={}, lines=[], may_spend=False, busy=lambda: [], report=root / "d.json", triage_file=root / "n.json", proposals=root / "p")
        assert res["needs"] and "dashboard" in res["needs"]  # the setup items are found and reported even though the inbox could not take them
        rep = tracetriage.triage(7, NOW, [{"at": "2026-10-25T10:00:00Z", "kind": "error", "title": "A recurring error", "detail": "d"}] * 3, report=root / "t.json")
        assert rep["families"][0]["count"] == 3


def test_a_stuck_draft_fix_on_an_unreadable_record_says_so_instead_of_raising(tmp_path):
    folder = tmp_path / "gone"
    folder.mkdir()
    fixes = unstick.fixes_for(folder, chat=lambda p, r: {}, review=lambda f: {"verdict": "pass"})
    assert fixes["new_title"][1]() == (False, "could not read the video record (FileNotFoundError)")
    (folder / "meta.json").write_text("{broken")
    assert fixes["one_more_repair"][1]() == (False, "could not read the video record (JSONDecodeError)")


def test_the_shared_feed_never_raises_when_it_cannot_write(tmp_path, monkeypatch):
    bad = _blocked(tmp_path)
    monkeypatch.setattr(agentlog, "FILE", bad / "events.jsonl")
    e = agentlog.event("found", "Something happened", "detail", now=NOW)
    assert e["saved"] is False and e["title"] == "Something happened"
    agentlog.mark_read()


def test_ordinary_repairs_and_guardian_actions_become_lessons_without_any_escalation(monkeypatch):
    import autopilot
    import fixer
    with agenteval.sandbox() as root:
        stuck = {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block"}, {"name": "ok_check", "ok": True, "severity": "block"}]}
        agenteval._video(root, "v1", review=stuck)
        monkeypatch.setattr(autopilot.config, "OUT", root / "out")
        monkeypatch.setattr(fixer, "fix", lambda slug, now=None, **k: {"fixed": ["new title: Mami Wata: The Honest Story", "rewrote the description to match"], "verdict": "pass"})
        autopilot.do_fix("v1", {"auto_approve": False}, NOW)
        got = lessons.recall("fixer", "check title_matches failed")
        assert {g["tried"] for g in got} == {"new title", "rewrote the description to match"} and all(g["wins"] == 1 for g in got)
        monkeypatch.setattr(fixer, "fix", lambda slug, now=None, **k: {"fixed": [], "verdict": "fail"})
        autopilot.do_fix("v1", {"auto_approve": False}, NOW)
        assert any(g["tried"] == "repair pass without a change" and g["losses"] == 1 for g in lessons.recall("fixer", "check title_matches failed"))
        f = agenteval._video(root, "sched", video_id="V2", publish_at=agenteval.FUTURE)
        agenteval._guard(root, agenteval.FakeYT())
        mine = lessons.recall("guardian", "seo_title_front on a video not public yet")
        assert mine and mine[0]["tried"] == "deterministic metadata repair" and mine[0]["wins"] >= 1


def test_lessons_that_cannot_be_saved_never_stop_the_guardian_or_the_repair_counter(tmp_path, monkeypatch):
    import autopilot
    import fixer
    with agenteval.sandbox() as root:
        lessons.FILE = _blocked(tmp_path) / "lessons.jsonl"
        f = agenteval._video(root, "sched", video_id="V2", publish_at=agenteval.FUTURE)
        res = agenteval._guard(root, agenteval.FakeYT())
        assert res["actions"] and agenteval._meta(f)["title"].lower().startswith("mami wata")
        stuck = {"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block"}]}
        agenteval._video(root, "v1", review=stuck)
        monkeypatch.setattr(autopilot.config, "OUT", root / "out")
        monkeypatch.setattr(fixer, "fix", lambda slug, now=None, **k: {"fixed": ["new title: x"], "verdict": "pass"})
        assert autopilot.do_fix("v1", {"auto_approve": False}, NOW)["verdict"] == "pass"


def test_an_unreadable_feed_is_an_empty_feed(tmp_path, monkeypatch):
    d = tmp_path / "events.jsonl"
    d.mkdir()  # reading a directory raises an OSError
    monkeypatch.setattr(agentlog, "FILE", d)
    assert agentlog._all() == [] and agentlog.recent(5) == [] and agentlog.unread() == 0


def test_a_video_deleted_in_studio_is_reported_once_and_does_not_break_the_guardian():
    with agenteval.sandbox() as root:
        f = agenteval._video(root, "gone", video_id="V404", publish_at=agenteval.FUTURE)
        before = agenteval._meta(f)

        class Empty(agenteval.FakeYT):
            def videos(self):
                v = super().videos()

                def lst(**k):
                    self.calls.append(("list", k))
                    return type("R", (), {"execute": lambda s: {"items": []}})()
                v.list = lst
                return v
        yt = Empty()
        res = agenteval._guard(root, yt)
        assert not yt.writes() and agenteval._meta(f)["title"] == before["title"] and res["actions"] == []
        tasks = [t for t in agentbus.tasks() if t["kind"] == "video_missing"]
        assert len(tasks) == 1 and "V404" in tasks[0]["reason"]
        assert not any("could not finish checking" in e["title"] for e in agentlog.recent(10))


def test_lines_at_picks_the_line_that_starts_at_the_flagged_second_even_when_the_second_is_rounded(tmp_path):
    import fixer
    (tmp_path / "words.json").write_text(json.dumps([{"i": 0, "s": 0.0}, {"i": 1, "s": 192.5}, {"i": 2, "s": 203.1000001}, {"i": 2, "s": 203.9}, {"i": 3, "s": 211.7}]))
    meta = {"lines": [{"text": "zero"}, {"text": "one"}, {"text": "two"}, {"text": "three"}]}
    assert fixer.lines_at(meta, tmp_path, [203.1]) == ["two"]   # was "one": the rounded second sat a hair before the line's own start
    assert fixer.lines_at(meta, tmp_path, [211.6]) == ["three"]  # within the slack of the next start; a second well before the start stays with the earlier line
    assert fixer.lines_at(meta, tmp_path, [200.0]) == ["one"]


def test_the_reviewer_reads_the_source_paragraphs_that_back_the_narration_not_just_the_first_characters():
    import reviewer
    maya = "\n\n".join(f"The Maya lowland city number {i} shifted its trade routes during the ninth century drought and its rulers changed." for i in range(160))
    teo = ("Teotihuacan lies about 40 kilometres northeast of Mexico City.\n\nAt its height around 450 CE the city held perhaps 100,000 people, one of the largest in the world.\n\n"
           + "\n\n".join(f"A filler paragraph about pottery workshops of Teotihuacan barrio number {i}." for i in range(160)))
    source = maya + "\n\n" + teo
    narration = "Teotihuacan lies about 40 kilometres northeast of Mexico City. At its height around 450 CE it held perhaps 100,000 people."
    assert len(source) > 20000 and "100,000 people" not in source[:12000]                      # what the old cut showed the reviewer: no Teotihuacan at all
    got = reviewer.relevant_source(source, narration, 12000)
    assert len(got) <= 12000 and "100,000 people" in got and "40 kilometres northeast of Mexico City" in got
    assert got.index("40 kilometres") < got.index("100,000 people")                                   # original order is kept
    short = "A short article.\n\nWith two paragraphs."
    assert reviewer.relevant_source(short, "anything", 12000) == short                                # a short source is untouched
    assert reviewer.relevant_source(source, "Teotihuacan pottery", 300).count("\n\n") <= 3 and len(reviewer.relevant_source(source, "x", 50)) <= 50


def test_a_claim_with_no_supporting_paragraph_is_still_not_in_the_excerpt():
    import reviewer
    source = "\n\n".join(f"Paragraph {i} about copper mining in a valley with several named workshops and traders." for i in range(300))
    assert "Atlantis" not in reviewer.relevant_source(source, "The city of Atlantis sank in a single night with 9,000 people.", 6000)


def test_lessons_for_one_problem_are_not_returned_for_another_that_only_shares_generic_words():
    with agenteval.sandbox():
        lessons.record("fixer", "check title_matches failed", "new title", True, NOW)
        lessons.record("fixer", "check visual_review failed", "redrew the pictures at the named lines", True, NOW)
        assert [l["tried"] for l in lessons.recall("fixer", "check visual_review failed")] == ["redrew the pictures at the named lines"]
        assert [l["tried"] for l in lessons.recall("fixer", "check title_matches failed on another video")] == ["new title"]
        assert lessons.recall("fixer", "check failed") == []                                  # nothing specific: nothing matches


def test_an_unwritable_lock_file_or_a_corrupt_state_time_never_crashes_the_guardian_unstick_or_doctor(tmp_path):
    import doctor
    import guardian
    import worker
    bad = _blocked(tmp_path) / "lock"
    assert guardian.run(NOW, out=tmp_path / "out", lock_file=bad) == {"skipped": "cannot open the lock file"}
    assert unstick.run(NOW, out=tmp_path / "out", lock_file=bad) == {"skipped": "cannot open the lock file"}
    rows = {r["agent"]: r["status"] for r in doctor.scan(NOW, {"recheck": "not a time", "guardian": 12345}, [], worker.JOBS)}
    assert rows["recheck"] == "stale" and rows["guardian"] == "stale"


def test_a_command_that_crashes_ends_with_a_plain_message_a_feed_entry_and_a_failing_exit_code(tmp_path, monkeypatch, capsys):
    import run
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")

    def boom():
        raise OSError("disk full")
    assert run.guarded_main(boom, ["guardian"]) == 1
    assert "run.py guardian failed: OSError: disk full" in capsys.readouterr().out
    assert any("A command failed: run.py guardian" in e["title"] for e in agentlog.recent(5))
    assert run.guarded_main(lambda: None, ["agents"]) == 0
    import pytest
    with pytest.raises(SystemExit):                                                          # a command's own refusal is not swallowed
        run.guarded_main(lambda: (_ for _ in ()).throw(SystemExit("not approved")), ["upload"])
    monkeypatch.setattr(agentlog, "FILE", _blocked(tmp_path) / "e.jsonl")
    assert run.guarded_main(boom, ["doctor"]) == 1                                           # even with an unwritable feed


def test_a_videos_folder_that_cannot_be_listed_is_a_skipped_run_not_a_crash(tmp_path, monkeypatch):
    import pathlib

    import guardian

    def denied(self, pattern):
        raise PermissionError("denied")
    monkeypatch.setattr(pathlib.Path, "glob", denied)
    assert guardian.run(NOW, out=tmp_path / "out", lock_file=tmp_path / "lock")["skipped"] == "cannot read the videos folder"
    assert unstick.candidates(tmp_path / "out") == []


def test_the_free_model_cache_and_the_login_state_record_never_break_a_model_call_or_the_health_check_on_a_full_disk(tmp_path, monkeypatch):
    import datetime as dt

    import freemodels
    import ytlogin
    bad = _blocked(tmp_path)
    monkeypatch.setattr(freemodels, "FILE", bad / "free.json")
    freemodels._save({"x": 1})                                                                  # no exception
    monkeypatch.setattr(ytlogin, "STATE", bad / "login.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    res = ytlogin.check(dt.datetime(2026, 10, 26, 12, 0, tzinfo=dt.timezone.utc), refresh=lambda: (_ for _ in ()).throw(RuntimeError("invalid_grant")))
    assert res["ok"] is False and res["error"] == "expired"                                    # the check still reports the expired login
    assert any("login expired" in e["title"] for e in agentlog.recent(5))
    ytlogin.stamp(dt.datetime(2026, 10, 26, 12, 0, tzinfo=dt.timezone.utc))                     # recording the consent date does not raise either


def test_the_trend_inbox_case_passes_and_fails_when_the_link_rule_is_broken(monkeypatch):
    import re

    import trendinbox

    ok, detail = agenteval.case_research_trend_inbox_is_data_only_expires_and_refuses_foreign_links()
    assert ok, detail
    monkeypatch.setattr(trendinbox, "WATCH", re.compile(r".*"))  # mutation: any link accepted
    ok, detail = agenteval.case_research_trend_inbox_is_data_only_expires_and_refuses_foreign_links()
    assert not ok and "refused=False" in detail


def test_the_short_structure_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import re

    import reviewer
    import scriptgen

    name = "case_short_structure_rules_only_warn_ask_for_a_payoff_never_for_loops_and_keep_the_creators_safety_rules_in_its_prompt"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    real = scriptgen.short_prompt
    monkeypatch.setattr(scriptgen, "short_prompt", lambda *a, **k: real(*a, **k).replace("payoff", "ending"))  # mutation: the writer is not asked for a payoff
    ok, detail = case()
    assert not ok and "asks=False" in detail
    monkeypatch.setattr(scriptgen, "short_prompt", real)
    monkeypatch.setattr(reviewer, "LOOP", re.compile(r".*"))  # mutation: any first line counts as a hook
    ok, detail = case()
    assert not ok and "catches=False" in detail

    monkeypatch.undo()
    import playbook

    real_brief = playbook.brief
    monkeypatch.setattr(playbook, "brief", lambda agent, **k: real_brief(agent, max_chars=700))  # mutation: the prompt cuts off the creator's Never rules
    ok, detail = case()
    assert not ok and "safe=False" in detail


def test_the_subscribe_wording_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import reviewer
    import scriptgen

    name = "case_a_shorts_closing_invitation_says_subscribe_never_follow_and_story_lines_are_left_alone"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    real = scriptgen.short_prompt
    monkeypatch.setattr(scriptgen, "short_prompt", lambda *a, **k: real(*a, **k).replace("invitation to subscribe", "invitation to follow"))  # mutation: the writer is asked to follow again
    ok, detail = case()
    assert not ok and "asks=False" in detail
    monkeypatch.setattr(scriptgen, "short_prompt", real)
    monkeypatch.setattr(scriptgen, "subscribe_invitation", lambda lines: (lines, 0))  # mutation: the rule does nothing
    ok, detail = case()
    assert not ok and "fixes=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(scriptgen, "follow_invitation", lambda text: False)  # mutation: the reviewer no longer sees a 'follow' invitation
    ok, detail = case()
    assert not ok and "warns=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(scriptgen, "INVITE_CUE", __import__("re").compile(r".*"))  # mutation: any closing line with the word counts, so a story line is rewritten
    ok, detail = case()
    assert not ok and "fixes=False" in detail


def test_the_voice_tail_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import studiochecks
    import tts

    name = "case_a_styled_voice_cuts_the_services_silent_tail_and_a_long_gap_between_lines_is_flagged"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setitem(tts.VOICE_STYLES["energetic"], "tail", 5.0)  # mutation: the tail is not really cut
    ok, detail = case()
    assert not ok and "cut=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(tts, "line_length", lambda duration, words, pause, tail: (min(duration, 1.0) if tail is not None else duration) + pause + 5)  # mutation: a line gains time
    ok, detail = case()
    assert not ok
    monkeypatch.undo()
    monkeypatch.setattr(studiochecks, "DEAD_AIR_MAX", 9.0)  # mutation: nothing is ever flagged
    ok, detail = case()
    assert not ok and "flags=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(studiochecks, "FREEZE_MAX", 99.0)  # mutation: a frozen picture is never flagged
    ok, detail = case()
    assert not ok and "freezes=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(tts, "PRONUNCIATION", {})  # mutation: the voice is given the plain spelling again
    ok, detail = case()
    assert not ok and "says=False" in detail


def test_the_hook_question_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import re

    import reviewer
    import scriptgen

    name = "case_a_shorts_hook_is_an_open_question_and_a_yes_or_no_hook_that_holds_the_answer_is_warned"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    real = scriptgen.short_prompt
    monkeypatch.setattr(scriptgen, "short_prompt", lambda *a, **k: real(*a, **k).replace("never as a yes/no question", "any kind of question"))  # mutation: the writer may open with a yes/no again
    ok, detail = case()
    assert not ok and "asks=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(reviewer, "YES_NO", re.compile(r"^\b$"))  # mutation: a yes/no hook is never seen
    ok, detail = case()
    assert not ok and "warns=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(reviewer, "YES_NO", re.compile(r".*"))  # mutation: every hook counts as yes/no, so an open question is warned about too
    ok, detail = case()
    assert not ok and "warns=False" in detail


def test_the_camera_motion_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import re

    import animate
    import motiongraphics
    import reviewer

    name = "case_camera_motion_moves_only_drawn_pictures_and_graphics_show_only_what_the_script_says"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(animate, "_drawn", lambda path: True)  # mutation: an archive picture would be animated too
    ok, detail = case()
    assert not ok and "motion=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(motiongraphics, "YEAR", re.compile(r"(\d{4}|\d,\d{3})"))  # mutation: any four digits, or 1,000 style numbers, become a year
    monkeypatch.setattr(motiongraphics, "ERA", re.compile(r"(\d{4})(x)"))
    ok, detail = case()
    assert not ok
    monkeypatch.undo()
    monkeypatch.setattr(motiongraphics, "HOOK_CLEAR", 0.0)  # mutation: graphics may cover the hook
    ok, detail = case()
    assert not ok and "quiet=False" in detail
    monkeypatch.undo()
    real = reviewer.generator_checks
    monkeypatch.setattr(reviewer, "generator_checks", lambda meta, probe, rules=None: [c for c in real(meta, probe, rules) if c["name"] != "parallax_clips"])  # mutation: lost clips are not reported
    ok, detail = case()
    assert not ok and "flagged=False" in detail


def test_the_depth_model_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import hashlib

    import depth

    name = "case_the_depth_model_is_only_kept_when_its_hash_is_the_checked_one_and_a_picture_without_it_gets_approximate_depth"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(depth, "MODEL_SHA256", hashlib.sha256(b"not the model").hexdigest())  # mutation: any file with a hash is accepted
    ok, detail = case()
    assert not ok and "refused=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(depth, "_download", lambda url, dest: dest.write_bytes(b"x"))  # mutation: any host may be used
    ok, detail = case()
    assert not ok and "host=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(depth, "make_and_store", lambda path: depth.approximate_depth())  # mutation: a made-up map is called a model map
    monkeypatch.setattr(depth, "load_depth", lambda path: None)
    ok, detail = case()
    assert not ok and "approx=False" in detail


def test_the_documentary_shape_case_passes_and_fails_when_its_rules_are_broken(monkeypatch):
    import reviewer
    import scriptgen

    name = "case_a_documentary_is_written_in_the_owners_shape_and_length_and_warned_about_when_it_is_outside_it"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(scriptgen, "DOC_STRUCTURE", scriptgen.DOC_STRUCTURE.replace("The LAST chapter gives value", "The last chapter says goodbye"))  # mutation: no closing chapter of value
    ok, detail = case()
    assert not ok and "shape=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(scriptgen, "MAX_DOC_LINES", 50)  # mutation: the old cap, 7.6 minutes
    ok, detail = case()
    assert not ok and "room=False" in detail
    monkeypatch.undo()
    real = reviewer.generator_checks
    monkeypatch.setattr(reviewer, "generator_checks", lambda meta, probe, rules=None: [c for c in real(meta, probe, rules) if c["name"] != "doc_length"])  # mutation: a wrong length is not reported
    ok, detail = case()
    assert not ok and "warns=False" in detail


def test_the_whole_narration_case_passes_and_fails_with_the_old_7000_character_cut(monkeypatch):
    import reviewer

    case = getattr(agenteval, "case_the_ai_review_reads_the_whole_narration_of_a_long_documentary_and_not_only_its_start")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(reviewer, "REVIEW_TEXT_CHARS", 7000)  # mutation: the old cut that dropped the closing chapter
    ok, detail = case()
    assert not ok and "whole=False" in detail


def test_the_quotation_case_passes_and_fails_when_the_finder_never_matches_or_always_matches(monkeypatch):
    import reviewer

    case = getattr(agenteval, "case_a_quotation_is_sourced_by_its_own_words_and_an_invented_one_stays_open_with_no_passage")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(reviewer, "claim_span", lambda source, claim: None)  # mutation: the old behaviour, a sourced quotation is never found
    ok, detail = case()
    assert not ok and "found=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(reviewer, "claim_span", lambda source, claim: (0, 10))  # mutation: anything is "found", so an invented quotation would be verified
    ok, detail = case()
    assert not ok and "open=False" in detail


def test_the_animation_prompt_case_passes_and_fails_when_the_ban_on_invented_events_is_removed(monkeypatch):
    import animate

    case = getattr(agenteval, "case_an_animated_clip_is_asked_to_show_only_what_its_picture_already_shows")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(animate, "motion_prompt", lambda line, visual="": "Gentle animation of this scene. Slow camera push-in, warm light flickering. No text.")  # mutation: the old wording
    ok, detail = case()
    assert not ok and "banned=False" in detail


def test_the_clip_and_people_case_passes_and_fails_when_a_clip_may_loop_or_a_face_may_bend(monkeypatch):
    import parallax
    import render

    case = getattr(agenteval, "case_a_clip_plays_once_and_a_picture_with_people_never_bends_or_pushes_in_hard")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(render, "clip_fit", lambda clip_s, scene_s, max_slow=1.25: (1.0, 0.0))  # mutation: a short clip is not fitted, so it would loop
    ok, detail = case()
    assert not ok and "once=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(parallax, "depth_safe", lambda note: True)  # mutation: every picture may bend with depth
    ok, detail = case()
    assert not ok and "people_flat=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(parallax, "gentle", lambda plan: plan)  # mutation: faces may be pushed to 1.45x
    ok, detail = case()
    assert not ok and "gentle=False" in detail


def test_the_subscribe_case_passes_and_fails_when_the_timing_or_the_safety_is_broken(monkeypatch):
    import subscribe

    case = getattr(agenteval, "case_the_subscribe_pop_up_lands_on_the_spoken_word_or_at_high_points_and_never_breaks_a_video")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(subscribe, "LEAD", 0.0)  # mutation: the pop-up starts on the word, so the click comes after it
    ok, detail = case()
    assert not ok and "spoken=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(subscribe, "moments", lambda kind, durations, words=None: [0.0])  # mutation: it pops up at the very start
    ok, detail = case()
    assert not ok and "high=False" in detail
    monkeypatch.undo()

    def blind(cmd, **k):  # mutation: the length check is blind and a broken output replaces the video
        open(cmd[-1], "wb").write(b"broken")

    monkeypatch.setattr(subscribe.subprocess, "run", blind)
    monkeypatch.setattr(subscribe, "_seconds", lambda p: 60.0)
    ok, detail = case()
    assert not ok and "safe=False" in detail


def test_the_narration_case_passes_and_fails_when_the_finish_is_skipped_or_the_voice_changes(monkeypatch):
    import audiofinish
    import config

    case = getattr(agenteval, "case_the_narration_is_finished_to_the_target_loudness_and_the_channel_voice_is_the_owners_choice")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(audiofinish, "finish", lambda *a, **k: False)  # mutation: the finish does nothing
    ok, detail = case()
    assert not ok and "loud=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(config, "VOICE", "en-US-GuyNeural")  # mutation: the voice is changed back
    ok, detail = case()
    assert not ok and "voice=False" in detail


def test_the_reschedule_case_passes_and_fails_when_it_goes_public_ignores_the_future_repeats_or_autopilot_does_it(monkeypatch):
    import reschedule

    case = getattr(agenteval, "case_a_cleared_schedule_is_put_back_in_the_future_once_only_when_the_owner_asks_and_a_public_video_is_never_touched")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(__import__("autopilot"), "free_slot", lambda slug, fmt, cfg, now: now - __import__("datetime").timedelta(hours=1))  # mutation: a time in the past, which YouTube publishes at once
    ok, detail = case()
    assert not ok and "future=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(reschedule, "_read", lambda yt, vid: {"status": {"privacyStatus": "private", "uploadStatus": "processed"}})  # mutation: a public video is read as private
    ok, detail = case()
    assert not ok and "public_safe=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(reschedule, "lost", lambda meta: True)  # mutation: a repaired video is repaired again, every time
    ok, detail = case()
    assert not ok and "once=False" in detail
    monkeypatch.undo()
    monkeypatch.setitem(__import__("autopilot").EXECUTORS, "reschedule", lambda slug, cfg, now: None)  # mutation: Autopilot can repair it by itself again
    ok, detail = case()
    assert not ok and "owner_only=False" in detail


def test_the_channel_mark_case_passes_and_fails_when_the_timing_corner_switch_or_tenant_guard_is_broken(monkeypatch):
    import brandmark
    import subscribe
    import tenantmode

    case = getattr(agenteval, "case_the_channel_mark_shows_after_the_cold_open_in_its_own_corner_and_only_on_the_owners_studio")
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(brandmark, "APPEAR", 0.0)  # mutation: the mark covers the cold open
    ok, detail = case()
    assert not ok and "timing=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(brandmark, "spec", lambda size, vertical, seconds, mark=brandmark.MARK: {"file": "x", "width": 10, "x": size[0] - 20, "y": 5, "start": 4.0, "seconds": seconds})  # mutation: the mark sits top right, on the pop-up
    ok, detail = case()
    assert not ok and "corners=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: False)
    real = subscribe.add_to

    def ignore_tenant(*a, **k):  # mutation: the tenant guard is gone and the switch is ignored
        monkeypatch.setattr(tenantmode, "is_tenant", lambda: False)
        return real(a[0], {**a[1], "brand_mark": True}, *a[2:], **k)

    monkeypatch.setattr(subscribe, "add_to", ignore_tenant)
    ok, detail = case()
    assert not ok and "switch=False" in detail
