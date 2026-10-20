import datetime as dt
import json
import os

import config
import pytest
import risk

NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)


def vid(root, name, **meta):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta))
    return d


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    (tmp_path / "output").mkdir()
    return tmp_path


def test_facts_act_on_a_contradicted_claim_watch_on_open_or_ungrounded_ok_when_clean(world):
    d = vid(world / "output", "a", approved=True, grounded=True)
    (d / "claims.json").write_text(json.dumps([{"verification_status": "VERIFIED"}]))
    assert risk.facts(risk.videos())["level"] == "ok"
    (d / "claims.json").write_text(json.dumps([{"verification_status": "UNVERIFIED"}]))
    assert risk.facts(risk.videos())["level"] == "watch"
    (d / "claims.json").write_text(json.dumps([{"verification_status": "CONFLICTING"}]))
    assert risk.facts(risk.videos())["level"] == "act" and "a (1)" in risk.facts(risk.videos())["evidence"]
    vid(world / "output", "b", approved=True, grounded=False)
    (d / "claims.json").write_text("[]")
    assert risk.facts(risk.videos())["level"] == "watch" and "no source article: b" in risk.facts(risk.videos())["evidence"]


def test_rights_flag_unlicensed_credits_on_videos_about_to_go_out(world):
    vid(world / "output", "ok", approved=True, credits=["x.jpg (Wikimedia Commons, Public domain)"])
    assert risk.rights(risk.videos())["level"] == "ok"
    vid(world / "output", "bad", approved=True, credits=["y.jpg (Flickr, All rights reserved)"])
    assert risk.rights(risk.videos())["level"] == "act" and "bad" in risk.rights(risk.videos())["evidence"]


def test_pattern_risk_rises_with_identical_structure_near_identical_openings_and_pace(world):
    for i in range(6):
        vid(world / "output", f"d{i}", format="doc", made_at=f"2026-10-1{i}T00:00:00Z", chapters=[{}] * 8, lines=[{"text": "What really happened to the people of the lost village?"}] * 48)
    r = risk.pattern(risk.videos(), NOW)
    assert r["level"] == "act" and "100%" in r["evidence"] and "pairs of near-identical openings" in r["evidence"]
    for i in range(6):
        vid(world / "output", f"v{i}", format="doc", made_at=f"2026-10-2{i}T00:00:00Z", chapters=[{}] * (5 + i), lines=[{"text": ["Why did the bells ring under the sea", "A queen vanished from her own palace", "Nobody expected the map to be wrong", "The last ship never reached the harbor", "Stone circles hum on certain nights", "A sealed letter outlived its writer"][i]}] * (30 + 7 * i))
    assert risk.pattern([x for x in risk.videos() if x[0].name.startswith("v")], NOW)["level"] == "ok"


def test_money_levels_and_runway():
    assert risk.money(10.0, 0.5)["level"] == "ok"
    assert risk.money(3.0, 0.5)["level"] == "watch"  # under the watch line
    assert risk.money(1.0, 0.5)["level"] == "act" and risk.money(5.0, 2.5)["level"] == "act"  # two days left
    assert risk.money(None, 0.5)["level"] == "watch"


def test_credit_is_read_live_and_cached(monkeypatch):
    risk._credit_cache.clear()
    calls = []
    get = lambda url, **k: calls.append(url) or type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"data": {"total_credits": 32, "total_usage": 21.5}}})()
    assert risk.credit_left("k", get, now=1000) == 10.5 and risk.credit_left("k", get, now=1500) == 10.5 and len(calls) == 1
    assert risk.credit_left("k", get, now=1000 + 1801) == 10.5 and len(calls) == 2
    risk._credit_cache.clear()
    assert risk.credit_left("k", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")), now=1) is None


def test_guard_switches_off_ai_art_then_paid_models_and_logs_it(world, monkeypatch):
    import agentlog
    import llm
    monkeypatch.setattr(llm, "CONFIG_FILE", world / "llm.json")
    monkeypatch.setattr(agentlog, "FILE", world / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    llm.save_config({**llm.load_config(), "enabled": True, "ai_art": True})
    assert risk.guard(10.0) == [] and llm.load_config()["ai_art"] is True
    assert len(risk.guard(1.0)) == 1 and llm.load_config()["ai_art"] is False and llm.load_config()["enabled"] is True
    assert len(risk.guard(0.2)) == 1 and llm.load_config()["enabled"] is False
    assert risk.guard(None) == [] and any("Credit is low" in e["title"] for e in agentlog.recent())


def test_running_renders_are_found_in_proc_and_make_the_process_risk_watch(tmp_path):
    for pid, cmd in ((101, b"python\0run.py\0doc\0The Topic\0"), (102, b"python\0worker.py\0"), (103, b"python\0run.py\0review\0x\0")):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(cmd)
    found = risk.running_jobs(tmp_path)
    assert found == ["run.py doc"]
    assert risk.process(found, 0)["level"] == "watch" and risk.process([], 0)["level"] == "ok" and risk.process([], 5)["level"] == "watch"


def test_restarts_are_counted_from_the_worker_log(tmp_path):
    log = tmp_path / "w.log"
    log.write_text("2026-10-20T10:00:00Z worker started\n2026-10-19T01:00:00Z worker started\n2026-10-20T11:00:00Z autopilot tick -> exit 0\n2026-10-20T11:30:00Z worker started\n")
    assert risk.worker_starts(NOW, log) == 2


def test_skills_fingerprint_detects_a_changed_file(world):
    root = world / ".claude" / "skills" / "watch"
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text("a")
    import hashlib
    (root / "VENDORED.sha256.json").write_text(json.dumps({"files": {"SKILL.md": hashlib.sha256(b"a").hexdigest()}}))
    assert risk.skills()["level"] == "ok"
    (root / "SKILL.md").write_text("tampered")
    assert risk.skills()["level"] == "act" and "SKILL.md" in risk.skills()["evidence"]


def test_access_flags_group_readable_secrets_and_a_missing_login(world):
    (world / "token.json").write_text("{}")
    os.chmod(world / "token.json", 0o644)
    assert risk.access()["level"] == "act" and "token.json" in risk.access()["evidence"]
    os.chmod(world / "token.json", 0o600)
    assert risk.access()["level"] == "watch"  # no dashboard login in this temp folder


def test_publishing_risk_names_unchecked_videos_going_public_soon_and_failed_readbacks(world):
    soon = (NOW + dt.timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    vid(world / "output", "soon", approved=True, publish_at=soon)
    assert risk.publishing(risk.videos(), NOW)["level"] == "watch" and "soon" in risk.publishing(risk.videos(), NOW)["evidence"]
    vid(world / "output", "soon", approved=True, publish_at=soon, visual_check={"ok": True})
    assert risk.publishing(risk.videos(), NOW)["level"] == "ok"
    vid(world / "output", "wrong", upload_check={"ok": False}, video_id="X")
    assert risk.publishing(risk.videos(), NOW)["level"] == "act"


def test_assess_returns_all_ten_and_summary_counts():
    rows = risk.assess(NOW, left=10.0, running=[])
    assert [r["id"] for r in rows] == ["facts", "rights", "platform", "money", "process", "skills", "access", "publishing", "supply", "rules"]
    assert set(risk.summary(rows)) == {"act", "watch", "ok"} and all(r["controls"] for r in rows)



def test_the_deploy_script_is_valid_shell_and_protects_running_renders():
    import subprocess
    from pathlib import Path
    sh = Path(__file__).parent.parent / "deploy" / "deploy.sh"
    assert subprocess.run(["bash", "-n", str(sh)], capture_output=True).returncode == 0
    text = sh.read_text()
    assert "A render is running" in text and "FORCE" in text and "run\\.py (doc|make|redo" in text
    assert text.count("docker compose restart worker") == 1 and "up -d --build" in text  # restarted only for worker.py, rebuilt only for image changes


def test_documentary_shape_varies_by_topic_stays_within_limits_and_is_stable():
    import scriptgen
    shapes = {scriptgen.shape_for(t) for t in ["The Pied Piper", "The Oracle of Delphi", "The Bell Witch", "Srivijaya", "The Minotaur", "Roanoke", "Voynich manuscript", "Flying Dutchman"]}
    assert len(shapes) >= 4 and all(6 <= c <= 9 and 5 <= n <= 7 for c, n in shapes)
    assert scriptgen.shape_for("The Pied Piper") == scriptgen.shape_for("the pied piper")  # a retry keeps the same shape
    assert all(c * n * 16 >= 400 for c, n in shapes)  # the shortest still clears the 400-word documentary minimum


def test_the_documentary_prompt_uses_the_topic_shape(monkeypatch):
    import scriptgen
    prompts = []
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p: prompts.append(p) or {"title": "T", "description": "d", "tags": [], "anchors": [], "chapters": [{"title": f"C{i}", "summary": "s"} for i in range(9)], "lines": []})
    try:
        scriptgen.doc_script("The Pied Piper")
    except Exception:
        pass
    c, n = scriptgen.shape_for("The Pied Piper")
    assert f"Give {c} chapters" in prompts[0] and any(f"Write {n} narration lines" in p for p in prompts[1:])


def test_next_documentary_row_follows_the_just_in_time_plan(monkeypatch):
    import autopilot
    def view(status, at="2026-10-22T19:00:00Z", **kw):
        return {"rows": [{"format": "short", "status": "scheduled", "at": at, "us": "x", "title": ""}, {"format": "doc", "status": status, "at": at, "us": "Thu 22 Oct, 15:00",
                "title": "A doc", "starts_us": "Wed 21 Oct, 03:00", **kw}]}
    for status, level in (("scheduled", "ok"), ("ready", "ok"), ("later", "ok"), ("repairing", "watch")):
        monkeypatch.setattr(autopilot, "plan_view", lambda now, s=status: view(s))
        assert risk.supply(NOW)["level"] == level, status
    far = dt.datetime(2026, 10, 22, 19, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(autopilot, "plan_view", lambda now: view("empty"))
    assert risk.supply(far - dt.timedelta(hours=40))["level"] == "watch"  # due but plenty of time: it is being made
    assert risk.supply(far - dt.timedelta(hours=20))["level"] == "act"  # under 30 hours away and still nothing: look now
    monkeypatch.setattr(autopilot, "plan_view", lambda now: {"rows": []})
    assert risk.supply(NOW)["level"] == "watch"


def test_the_rules_row_counts_the_catalog_and_watches_pages_that_changed_after_a_rule_was_verified(world, monkeypatch):
    import newswatch

    monkeypatch.setattr(newswatch, "DATA_DIR", world / "data" / "newswatch")
    row = risk.rules(risk.videos(), NOW)
    assert row["id"] == "rules" and row["level"] == "ok" and "VERIFIED" in row["evidence"] and "conflicting" in row["evidence"].lower() and row["controls"]
    (world / "data" / "newswatch").mkdir(parents=True)
    (world / "data" / "newswatch" / "policy_log.json").write_text(json.dumps([{"at": "2026-10-25T06:10:00Z", "page": "Spam, deceptive practices and scams", "url": "u", "added": ["x"], "removed": []},
                                                                           {"at": "2026-10-01T06:10:00Z", "page": "Monetization policies", "url": "u", "added": ["old"], "removed": []}]))
    vid(world / "output", "p", review={"verdict": "fail", "checks": [{"name": "thumbnail_matches", "ok": False, "severity": "block", "detail": "x"}]})
    row = risk.rules(risk.videos(), dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc))
    assert row["level"] == "watch" and "thumbnail_matches" in row["evidence"] and "Spam, deceptive practices and scams" in row["evidence"] and "Monetization policies" not in row["evidence"]
