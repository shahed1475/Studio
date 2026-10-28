import datetime as dt
import json

import actionlog
import diagnose
import growthdata
import growthview
import learner
import policyclass
import rulesfile

NOW = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.timezone.utc)


def test_with_nothing_collected_yet_the_view_is_complete_and_calm():
    v = growthview.view(NOW)
    assert v["hold"] is None and v["metrics"]["videos"] == 0 and v["diagnoses"] == [] and v["report"] == "" and v["edits_pending"] == 0 and v["actions"] == []
    assert v["rules"]["pending"] == 0 and v["rules"]["version"] == "1.0.0" and v["drift"]["status"] == "not enough history"


def test_the_view_gathers_every_part_and_puts_real_problems_first():
    growthdata.FILE.write_text(json.dumps({"updated": "2026-11-02T06:00:00Z", "videos": {"A": {"ctr": 0.03}, "B": {}}, "problems": ["reach reports unavailable: 403"]}))
    diagnose.FILE.write_text(json.dumps({"A": {"48h": {"title": "Fine video", "primary": "none", "findings": []}},
                                         "B": {"48h": {"title": "Weak hook", "primary": "hook", "findings": [{"problem": "hook", "evidence": "retention at 30 s is 30%"}]},
                                               "7d": {"title": "Weak hook", "primary": "hook", "findings": [{"problem": "hook", "evidence": "still 30%"}]}}}))
    policyclass.start_hold("Monetization policies", "strong change", NOW)
    rulesfile.propose({"benchmarks": {"ctr_target": 0.05}}, "w", "s", NOW)
    actionlog.propose("V1", "slug", {"title": "a"}, {"title": "b"}, "recheck", "w", NOW)
    actionlog.record("V2", {"title": "x"}, {"title": "y"}, "recheck", "repair", NOW)
    v = growthview.view(NOW)
    assert v["hold"]["pages"] == ["Monetization policies"] and v["rules"]["pending"] == 1 and v["edits_pending"] == 1 and v["actions"][0]["video_id"] == "V2"
    assert v["metrics"] == {"updated": "2026-11-02T06:00:00Z", "videos": 2, "with_ctr": 1, "problems": ["reach reports unavailable: 403"]}
    assert [r["primary"] for r in v["diagnoses"]] == ["hook", "none"] and v["diagnoses"][0]["window"] == "7d" and v["diagnoses"][0]["evidence"] == "still 30%"


def test_this_weeks_report_is_included_and_an_old_one_is_not():
    learner.REPORTS.mkdir(parents=True)
    (learner.REPORTS / "latest.md").write_text("# Weekly growth report, 2026-W45\n\n- a line\n")
    (learner.REPORTS / "latest.json").write_text(json.dumps({"week": "2026-W45"}))
    assert growthview.view(NOW)["report"].startswith("# Weekly growth report, 2026-W45")
    assert growthview.view(NOW + dt.timedelta(days=10))["report"] == ""


def test_a_part_that_cannot_be_read_never_breaks_the_view(monkeypatch):
    monkeypatch.setattr(policyclass, "hold_active", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(growthdata, "load", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(rulesfile, "load", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    v = growthview.view(NOW)
    assert v["hold"] is None and v["metrics"]["videos"] == 0 and v["rules"]["problems"] == ["rules could not be read"]


def test_the_view_only_reads(tmp_path):
    import os

    before = {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()}
    growthview.view(NOW)
    assert {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()} == before
    assert not any(w in open("growthview.py").read() for w in ("write_atomic", ".write_text(", ".videos()", "propose(", "resolve("))


def test_the_dashboard_serves_the_growth_view_and_the_page_shows_it():
    py, html = open("dashboard.py").read(), open("dashboard.html").read()
    assert '"growth": __import__("growthview").view()' in py and "<h2>Growth</h2>" in html and "A.growth" in html
    assert "python run.py policy release" in html and "Nothing here writes to YouTube" in html
    assert html.count("${esc(") > 0 and "A.growth||{}" in html  # every value from the view goes through esc()
