import datetime as dt
import json
import re
from pathlib import Path

import pytest

import packaging
import reviewer
import risk
import rulesfile

NOW = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc)


def write(tmp_path, data) -> Path:
    p = tmp_path / "rules.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data))
    return p


def test_the_shipped_file_matches_the_defaults_so_nothing_drifts_silently():
    shipped = json.loads((rulesfile.config.ROOT / "config" / "rules.json").read_text())  # the file in the repo, not the isolated copy the fixtures use
    assert shipped == rulesfile.DEFAULTS
    assert rulesfile.load(rulesfile.config.ROOT / "config" / "rules.json")["_problems"] == []


def test_a_missing_or_broken_file_falls_back_to_defaults_and_says_so(tmp_path):
    for src in (tmp_path / "nope.json", write(tmp_path, "{not json"), write(tmp_path, "[1, 2]")):
        r = rulesfile.load(src)
        assert r["benchmarks"] == rulesfile.DEFAULTS["benchmarks"] and r["_problems"]


def test_valid_values_override_and_invalid_ones_are_ignored_one_by_one(tmp_path):
    p = write(tmp_path, {"benchmarks": {"ctr_target": 0.05, "title_chars": [45, 60], "pace_wpm": [200, 100], "mystery": 1, "hook_max_seconds": "ten"},
                         "limits": {"doc_duration_s": [480, 840]}})
    r = rulesfile.load(p)
    assert r["benchmarks"]["ctr_target"] == 0.05 and r["benchmarks"]["title_chars"] == [45, 60] and r["limits"]["doc_duration_s"] == [480, 840]
    assert r["benchmarks"]["pace_wpm"] == [105, 175] and r["benchmarks"]["hook_max_seconds"] == 15 and "mystery" not in r["benchmarks"]
    assert len(r["_problems"]) == 3


def test_the_hard_rules_cannot_be_changed_by_the_file_or_a_patch(tmp_path):
    p = write(tmp_path, {"hard_rules": ["Mislead the viewer."]})
    assert rulesfile.load(p)["hard_rules"] == list(rulesfile.HARD_RULES)
    for patch in ({"hard_rules": []}, {"benchmarks": {"hard_rules": 1}}, {"policy_constraints": []}, {}, "x"):
        assert not rulesfile.validate_patch(patch)[0]
    assert len(rulesfile.HARD_RULES) == 4 and any("disclose" in h.lower() for h in rulesfile.HARD_RULES)


def test_a_proposal_changes_nothing_until_the_owner_approves_it(tmp_path):
    p = write(tmp_path, rulesfile.DEFAULTS)
    pid = rulesfile.propose({"benchmarks": {"ctr_target": 0.05}}, "CTR above 4% in 3 of 4 weeks", "weekly report", NOW, p)
    assert pid and rulesfile.load(p)["benchmarks"]["ctr_target"] == 0.04 and len(rulesfile.load(p)["pending_changes"]) == 1
    assert rulesfile.propose({"benchmarks": {"ctr_target": 0.05}}, "again", "x", NOW, p) == pid  # the same patch is not queued twice
    assert rulesfile.propose({"benchmarks": {"ctr_target": 7}}, "out of range", "x", NOW, p) is None
    out = rulesfile.resolve(pid, True, NOW + dt.timedelta(days=3), p)
    r = rulesfile.load(p)
    assert "approved" in out and r["benchmarks"]["ctr_target"] == 0.05 and r["rules_version"] == "1.0.1" and r["last_verified"] == "2026-10-31"
    assert r["pending_changes"] == [] and r["history"][-1]["decision"] == "approved"


def test_a_rejected_change_is_recorded_and_not_applied(tmp_path):
    p = write(tmp_path, rulesfile.DEFAULTS)
    pid = rulesfile.propose({"banned_patterns_add": ["titles that start with Why"]}, "w", "s", NOW, p)
    assert "rejected" in rulesfile.resolve(pid, False, NOW, p)
    r = rulesfile.load(p)
    assert "titles that start with Why" not in r["banned_patterns"] and r["rules_version"] == "1.0.0" and r["history"][-1]["decision"] == "rejected"
    assert rulesfile.resolve("p-none", True, NOW, p).startswith("no pending change")


def test_rules_older_than_thirty_days_are_reported_stale():
    r = rulesfile.load()
    assert rulesfile.stale_days(r, NOW) is None
    assert rulesfile.stale_days(r, NOW + dt.timedelta(days=31)) == 31


def test_the_risks_card_shows_the_rules_file_state(tmp_path, monkeypatch):
    assert risk.growth_rules(NOW)["level"] == "ok"
    monkeypatch.setattr(rulesfile, "FILE", tmp_path / "missing.json")
    row = risk.growth_rules(NOW)
    assert row["level"] == "watch" and "missing" in row["evidence"] and "run.py rules" in row["owner_decision"]
    p = write(tmp_path, rulesfile.DEFAULTS)
    monkeypatch.setattr(rulesfile, "FILE", p)
    rulesfile.propose({"benchmarks": {"ctr_target": 0.05}}, "w", "s", NOW, p)
    assert "1 proposed change" in risk.growth_rules(NOW)["evidence"]
    assert "stale" not in risk.growth_rules(NOW)["evidence"].lower() and "Not verified" in risk.growth_rules(NOW + dt.timedelta(days=40))["evidence"]


def test_the_modules_read_their_numbers_from_the_rules_file_not_from_literals():
    assert packaging.TITLE_BEST == tuple(rulesfile.get("benchmarks", "title_chars")) and packaging.TITLE_HARD_MAX == 70
    assert reviewer.PACE_RANGE == tuple(rulesfile.get("benchmarks", "pace_wpm"))
    assert reviewer.LIMITS["doc"]["duration"] == tuple(rulesfile.get("limits", "doc_duration_s")) == (180, 900)
    assert reviewer.LIMITS["short"]["duration"] == (20, 180)
    for name, banned in (("reviewer.py", ["(180, 900)", "(105, 175)", "(20, 180)"]), ("packaging.py", ["(40, 62)", "n <= 70"])):
        src = Path(name).read_text()
        assert not any(b in src for b in banned), (name, [b for b in banned if b in src])


def test_the_supply_row_survives_a_slot_status_it_does_not_know(monkeypatch):
    import planner

    monkeypatch.setattr(planner, "rows", lambda *a, **k: [{"format": "doc", "at": "2026-10-29T22:00:00Z", "us": "Thu", "status": "paused", "title": "", "slug": None, "starts_us": "Wed"}])
    row = risk.supply(NOW)
    assert row["id"] == "supply" and "paused" in row["evidence"]


def test_nothing_the_system_does_writes_the_shipped_file_it_all_goes_to_the_state_file():
    shipped_before = rulesfile.FILE.read_bytes()
    pid = rulesfile.propose({"benchmarks": {"ctr_target": 0.05}}, "w", "s", NOW)
    pid2 = rulesfile.propose({"banned_patterns_add": ["titles that start with Why"]}, "w", "s", NOW)
    rulesfile.resolve(pid, True, NOW)
    rulesfile.resolve(pid2, False, NOW)
    rulesfile.mark_verified(NOW + dt.timedelta(days=2))
    rulesfile.set_insights({"winning_topics": ["Voynich Manuscript"]})
    assert rulesfile.FILE.read_bytes() == shipped_before and rulesfile.STATE.exists()  # a deploy can always fast-forward the shipped file
    assert set(json.loads(rulesfile.STATE.read_text())) == {"benchmarks", "rules_version", "last_verified", "pending_changes", "history", "insights"}  # only what changed


def test_the_state_file_overrides_the_shipped_file_and_what_it_does_not_name_still_follows_the_shipped_file(tmp_path):
    rulesfile.FILE.write_text(json.dumps({"benchmarks": {"ctr_target": 0.06, "hook_max_seconds": 12}}))
    rulesfile.STATE.write_text(json.dumps({"benchmarks": {"ctr_target": 0.05}}))
    r = rulesfile.load()
    assert r["benchmarks"]["ctr_target"] == 0.05 and r["benchmarks"]["hook_max_seconds"] == 12 and r["benchmarks"]["ctr_retest_below"] == 0.03 and r["_problems"] == []
    rulesfile.FILE.write_text(json.dumps({"benchmarks": {"ctr_target": 0.07, "hook_max_seconds": 14}}))  # the next deploy changes a shipped value
    r = rulesfile.load()
    assert r["benchmarks"]["ctr_target"] == 0.05 and r["benchmarks"]["hook_max_seconds"] == 14  # the owner's approved value stays; untouched values follow the code


def test_an_approved_list_addition_keeps_the_shipped_entries_and_a_broken_state_file_is_ignored_and_reported():
    rulesfile.FILE.write_text(json.dumps({**rulesfile.DEFAULTS, "banned_patterns": ["shipped pattern one", "shipped pattern two"]}))
    pid = rulesfile.propose({"banned_patterns_add": ["a new pattern"]}, "w", "s", NOW)
    rulesfile.resolve(pid, True, NOW)
    assert rulesfile.load()["banned_patterns"] == ["shipped pattern one", "shipped pattern two", "a new pattern"]
    rulesfile.STATE.write_text("{broken")
    r = rulesfile.load()
    assert r["banned_patterns"] == ["shipped pattern one", "shipped pattern two"] and any("rules_state.json unreadable" in p for p in r["_problems"])
    rulesfile.STATE.unlink()
    assert rulesfile.load()["_problems"] == []  # no state file yet is normal


def test_insights_are_short_known_lists_only():
    out = rulesfile.set_insights({"winning_topics": [f"topic {i} " + "x" * 300 for i in range(15)], "losing_patterns": ["encyclopedia titles"], "made_up": ["x"], "winning_title_patterns": "not a list"})
    assert len(out["winning_topics"]) == 10 and all(len(t) <= 160 for t in out["winning_topics"]) and out["losing_patterns"] == ["encyclopedia titles"] and "made_up" not in out
    assert out["winning_title_patterns"] == [] and rulesfile.load()["insights"]["losing_patterns"] == ["encyclopedia titles"]
