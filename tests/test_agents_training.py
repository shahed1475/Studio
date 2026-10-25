import datetime as dt
import json

import agentbus
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
