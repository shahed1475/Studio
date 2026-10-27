import datetime as dt
import json

import pytest

import agentbus
import diagnose
import growthdata
import rulesfile

NOW = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc)
ISO = lambda days: (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
FLAT = [[round(i / 100, 2), 1.0] for i in range(1, 101)]
DROP = [[x, 1.0 if x < 0.40 else max(0.5, 1.0 - (x - 0.39) * 5)] for x, _ in FLAT]  # a 25-point fall between 40% and 45% of the video


def entry(days=10, **kw):
    e = {"title": "A video", "published": ISO(days), "seconds": 600, "kind": "doc", "views_90d": 100, "avg_pct_viewed": 40.0, "retention_at_30s": 60.0,
         "retention_curve": FLAT, "ctr": None, "impressions": None}
    e.update(kw)
    return e


@pytest.fixture
def world(tmp_path):
    def make(videos, metas=()):
        (tmp_path / "metrics.json").write_text(json.dumps({"videos": videos}))
        for name, m in metas:
            (tmp_path / "out" / name).mkdir(parents=True, exist_ok=True)
            (tmp_path / "out" / name / "meta.json").write_text(json.dumps(m))
        return dict(now=NOW, metrics=tmp_path / "metrics.json", path=tmp_path / "diag.json", out=tmp_path / "out", tasks=tmp_path / "tasks.json")
    return make


def primary(args, vid):
    diagnose.run(**args)
    return {w: d["primary"] for w, d in diagnose.load(args["path"])[vid].items()}


def test_a_low_click_rate_on_enough_impressions_is_a_packaging_problem(world):
    assert primary(world({"A": entry(ctr=0.02, impressions=1000)}), "A") == {"48h": "packaging", "7d": "packaging"}


def test_too_few_impressions_do_not_make_a_packaging_diagnosis(world):
    assert primary(world({"A": entry(ctr=0.01, impressions=50)}), "A") == {"48h": "none", "7d": "none"}


def test_early_drop_off_with_a_good_click_rate_is_a_broken_promise_and_without_one_it_says_so(world):
    a = world({"A": entry(ctr=0.06, impressions=2000, retention_at_30s=30.0)})
    assert primary(a, "A")["48h"] == "hook"
    f = diagnose.findings("B", entry(retention_at_30s=30.0), {"B": entry()})
    assert f[0][0] == "hook" and "not proven" in f[0][1]


def test_a_steep_drop_at_one_moment_names_the_time(world):
    f = diagnose.findings("C", entry(retention_curve=DROP), {})
    assert f[0][0] == "pacing" and "4:" in f[0][1] and "points" in f[0][1]
    assert diagnose.findings("C", entry(retention_curve=FLAT), {}) == []
    assert diagnose.findings("C", entry(retention_curve=DROP, kind="short"), {}) == []  # a Short's curve falls naturally: only documentaries are checked


def test_a_short_that_held_its_viewers_with_no_documentary_on_the_story_is_a_missed_long_video(world):
    args = world({"D": entry(kind="short", seconds=40, avg_pct_viewed=75.0)}, metas=[("voynich-short", {"video_id": "D", "format": "short", "topic": "Voynich Manuscript"})])
    assert primary(args, "D")["48h"] == "missed_long"
    args = world({"D": entry(kind="short", seconds=40, avg_pct_viewed=75.0)},
                 metas=[("voynich-short", {"video_id": "D", "format": "short", "topic": "Voynich Manuscript"}), ("voynich-doc", {"video_id": "X", "format": "doc", "topic": "Voynich Manuscript"})])
    assert diagnose.findings("D", entry(kind="short", seconds=40, avg_pct_viewed=75.0), {}, out=args["out"]) == []


def test_too_few_views_is_insufficient_data_and_nothing_is_guessed(world):
    args = world({"A": entry(views_90d=5, ctr=0.001, impressions=900, retention_at_30s=1.0)})
    assert primary(args, "A") == {"48h": "insufficient_data", "7d": "insufficient_data"}
    assert not agentbus.tasks(args["tasks"])


def test_each_window_runs_once_after_two_and_after_seven_days(world):
    young = world({"A": entry(days=1, ctr=0.02, impressions=1000)})
    assert diagnose.run(**young)["diagnosed"] == 0
    two = world({"A": entry(days=3, ctr=0.02, impressions=1000)})
    assert diagnose.run(**two)["diagnosed"] == 1 and diagnose.run(**two)["diagnosed"] == 0  # the 48 h window only, and only once
    seven = dict(two, now=NOW + dt.timedelta(days=5))
    assert diagnose.run(**seven)["diagnosed"] == 1 and set(diagnose.load(two["path"])["A"]) == {"48h", "7d"}


def test_a_real_problem_becomes_one_owner_task_and_nothing_else_is_written(world):
    args = world({"A": entry(ctr=0.02, impressions=1000)})
    out = diagnose.run(**args)
    rows = agentbus.tasks(args["tasks"])
    assert out["tasks_for_owner"] == 1 and len(rows) == 1 and rows[0]["kind"] == "growth_packaging" and rows[0]["state"] == "owner" and "three new titles" in rows[0]["reason"]


def test_thresholds_come_from_the_rules_file_not_from_the_module(world, monkeypatch, tmp_path):
    base = entry(ctr=0.035, impressions=1000)
    assert diagnose.findings("A", base, {}) == []  # 3.5% is above the 3% retest line
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"benchmarks": {"ctr_retest_below": 0.04}}))
    assert diagnose.findings("A", base, {}, rulesfile.load(p))[0][0] == "packaging"
    src = open("diagnose.py").read()
    assert "0.03" not in src and "0.04" not in src and "< 40" not in src and "15" not in src.replace("1500", "")


def test_the_report_lists_each_diagnosis(world):
    args = world({"A": entry(ctr=0.02, impressions=1000)})
    diagnose.run(**args)
    assert "packaging" in diagnose.report(args["path"]) and diagnose.report(args["path"] / "nope") == "no diagnoses yet"
