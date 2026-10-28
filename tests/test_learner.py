import datetime as dt
import json

import pytest

import agentbus
import config
import learner
import rulesfile
import topicqueue
import worker
import agents

NOW = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.timezone.utc)  # a Monday
ISO = lambda days: (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def e(title, views, days=10, kind="doc", avg=45.0, ret=55.0, ctr=None, imp=None):
    return {"title": title, "published": ISO(days), "kind": kind, "views_90d": views, "avg_pct_viewed": avg, "retention_at_30s": ret, "ctr": ctr, "impressions": imp}


def fleet():
    return {"D1": e("Why Did the Piper Take the Children?", 300), "D2": e("Who Really Wrote Hong Gildong?", 250), "D3": e("The Bell Witch of Tennessee: A Legend", 40), "D4": e("The Oracle of Delphi: Sanctuary and Myth", 30),
            "D5": e("Tiny", 5), "S1": e("The Voynich Manuscript Nobody Can Read", 500, kind="short", avg=75.0), "S2": e("Thunderbird Myth", 100, kind="short", avg=50.0)}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    (tmp_path / "metrics.json").write_text(json.dumps({"videos": fleet()}))
    (tmp_path / "out" / "voynich-short").mkdir(parents=True)
    (tmp_path / "out" / "voynich-short" / "meta.json").write_text(json.dumps({"video_id": "S1", "format": "short", "topic": "Voynich Manuscript"}))
    return tmp_path


def run(world, now=NOW, **kw):
    return learner.run(now, metrics=world / "metrics.json", out=world / "out", article_of=kw.pop("article_of", lambda t: ("The Voynich manuscript is a medieval book. " * 80)), **kw)


def test_videos_are_ranked_per_kind_by_views_per_day_and_thin_ones_are_left_out():
    r = learner.ranking(fleet(), NOW, 30)
    assert [x["id"] for x in r["doc"]] == ["D1", "D2", "D3", "D4"] and [x["id"] for x in r["short"]] == ["S1", "S2"] and r["doc"][0]["vpd"] == 30.0  # 300 views in 10 days; D5 has 5 views: left out


def test_title_patterns_need_two_videos_and_four_to_say_anything_and_are_compared_with_the_median():
    rows = learner.ranking(fleet(), NOW, 30)
    p = learner.title_patterns(rows["doc"] + rows["short"])
    assert p["median"] and any(w.startswith("question titles") for w in p["winning"]) and any(w.startswith("colon titles") for w in p["losing"])
    assert learner.title_patterns(rows["doc"][:3]) == {"median": None, "stats": {}, "winning": [], "losing": []}


def test_the_trend_compares_with_last_week_and_says_when_it_cannot():
    cur = {"docs": {"n": 4, "avg_pct": 40.0, "ret30": 50.0}, "shorts": {"n": 2, "avg_pct": 60.0, "ret30": 70.0}, "ctr": None}
    assert learner.trend_lines(None, cur) == ["First week with numbers: no trend to compare yet."]
    prev = {"docs": {"n": 3, "avg_pct": 35.0, "ret30": None}, "shorts": {"n": 2, "avg_pct": 55.0, "ret30": 65.0}, "ctr": 0.03}
    lines = " | ".join(learner.trend_lines(prev, cur))
    assert "average percent viewed 40.0% (last week 35.0%)" in lines and "retention at 30 s not comparable" in lines and "click rate: not available yet" in lines


def test_a_short_that_held_its_viewers_queues_one_documentary_subject_once(world):
    out = run(world)
    assert out["queued"] == ["Voynich Manuscript"] and topicqueue.items() == ["Voynich Manuscript"]
    assert json.loads(learner.QUEUED.read_text())["S1"]["note"] == "queued"
    assert run(world, now=NOW + dt.timedelta(days=7))["queued"] == [] and topicqueue.items() == ["Voynich Manuscript"]  # never queued twice


def test_nothing_is_queued_when_a_documentary_covers_the_story_or_the_article_is_missing(world):
    (world / "out" / "voynich-doc").mkdir()
    (world / "out" / "voynich-doc" / "meta.json").write_text(json.dumps({"video_id": "X", "format": "doc", "topic": "Voynich Manuscript"}))
    assert run(world)["queued"] == [] and topicqueue.items() == []
    (world / "out" / "voynich-doc" / "meta.json").unlink()
    (world / "learner_q.json").unlink(missing_ok=True)
    learner.QUEUED.unlink(missing_ok=True)
    assert run(world, article_of=lambda t: None)["queued"] == [] and "no source article" in json.loads(learner.QUEUED.read_text())["S1"]["note"]


def test_only_one_subject_is_queued_per_run(world):
    m = json.loads((world / "metrics.json").read_text())
    m["videos"]["S3"] = e("The Skinwalker Legend", 400, kind="short", avg=80.0)
    (world / "metrics.json").write_text(json.dumps(m))
    (world / "out" / "skin").mkdir()
    (world / "out" / "skin" / "meta.json").write_text(json.dumps({"video_id": "S3", "format": "short", "topic": "Skinwalker Ranch"}))
    assert len(run(world, article_of=lambda t: f"{t} is a long article about a place. " * 80)["queued"]) == 1


def test_a_click_rate_far_above_target_for_three_weeks_is_only_a_proposal():
    weekly = {"2026-W42": {"ctr": 0.06}, "2026-W43": {"ctr": 0.055}, "2026-W44": {"ctr": 0.07}}
    pid = learner.propose_ctr_target(weekly, rulesfile.load(), NOW)
    assert pid and rulesfile.load()["benchmarks"]["ctr_target"] == 0.04 and rulesfile.load()["pending_changes"][0]["patch"] == {"benchmarks": {"ctr_target": 0.05}}
    assert learner.propose_ctr_target({"2026-W43": {"ctr": 0.06}, "2026-W44": {"ctr": 0.07}}, rulesfile.load(), NOW) is None
    assert learner.propose_ctr_target({**weekly, "2026-W44": {"ctr": 0.045}}, rulesfile.load(), NOW) is None


def test_the_run_writes_the_report_the_notes_and_the_weekly_snapshot_and_changes_nothing_else(world):
    before = rulesfile.load()
    out = run(world)
    text = (world / "x").exists() or open(out["report"]).read()
    assert "Weekly growth report, 2026-W45" in text and "Why Did the Piper Take the Children?" in text and "First week with numbers" in text and "unique viewers are not available" in text
    assert "Voynich Manuscript" in rulesfile.load()["insights"]["winning_topics"][0] and rulesfile.load()["benchmarks"] == before["benchmarks"]
    assert list(json.loads(learner.WEEKLY.read_text())) == ["2026-W45"] and out["videos"] == 6
    nxt = run(world, now=NOW + dt.timedelta(days=7))
    assert "last week" in open(nxt["report"]).read() and sorted(json.loads(learner.WEEKLY.read_text())) == ["2026-W45", "2026-W46"]


def test_the_digest_gets_this_weeks_summary_and_only_this_weeks(world):
    run(world)
    assert learner.latest_summary(NOW).startswith("# Weekly growth report, 2026-W45")
    assert learner.latest_summary(NOW + dt.timedelta(days=9)) == ""


def test_with_no_numbers_yet_the_report_says_so_and_nothing_breaks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    out = learner.run(NOW, metrics=tmp_path / "none.json", out=tmp_path / "out", article_of=lambda t: None)
    assert out["videos"] == 0 and out["queued"] == [] and "not enough videos with views yet" in open(out["report"]).read()


def test_the_weekly_job_runs_the_learner_before_the_news_digest_and_the_agent_is_registered():
    job = next(j for j in worker.JOBS if j["name"] == "weekly")
    assert job["cmds"] == [["learn"], ["newswatch"]] and agents.AGENTS["learner"]["job"] == "weekly"
