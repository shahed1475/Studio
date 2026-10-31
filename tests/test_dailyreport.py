import datetime as dt
import json
import os

import agentlog
import config
import dailyreport
import llm

NOW = dt.datetime(2026, 10, 25, 7, 0, tzinfo=dt.timezone.utc)


def make(root, slug, hours_ago=None, **meta):
    d = root / "output" / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"title": slug.upper(), "format": "doc", **meta}))
    if hours_ago is not None:
        (d / "video.mp4").write_bytes(b"x")
        t = (NOW - dt.timedelta(hours=hours_ago)).timestamp()
        os.utime(d / "video.mp4", (t, t))


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(dailyreport, "STATE", tmp_path / "daily_report.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    (tmp_path / "usage.json").write_text(json.dumps({"2026-10-24": {"usd": 2.5, "calls": 100}}))


def test_report_counts_what_was_made_uploaded_and_is_coming(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    make(tmp_path, "made-today", hours_ago=5, approved=True, publish_at="2026-10-26T14:00:00Z")
    make(tmp_path, "uploaded-today", hours_ago=30, uploaded_at="2026-10-24T20:00:00Z", video_id="v", publish_at="2026-10-25T14:00:00Z")
    make(tmp_path, "old", hours_ago=200, uploaded_at="2026-10-20T20:00:00Z", video_id="o", publish_at="2026-10-21T14:00:00Z")
    r = dailyreport.build(NOW, credit=8.5)
    assert r["made"] == ["MADE-TODAY"] and r["uploaded"] == ["UPLOADED-TODAY"] and r["spend"] == 2.5 and r["credit"] == 8.5
    assert [u["title"] for u in r["coming"]] == ["UPLOADED-TODAY", "MADE-TODAY"]
    assert "2.50" in r["text"] and "8.50" in r["text"]


def test_report_names_what_is_wrong_in_plain_words(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    make(tmp_path, "broken", hours_ago=3, review={"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block", "detail": "x"}]})
    agentlog.event("found", "Re-check: something", "detail", now=NOW - dt.timedelta(hours=2))
    r = dailyreport.build(NOW, credit=0.9)
    assert any("BROKEN" in p and "title_matches" in p for p in r["problems"])
    assert any("Re-check: something" in p for p in r["problems"])
    assert any("0.90" in p for p in r["problems"])  # credit below the point where Autopilot stops making videos


def test_one_report_a_day(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert dailyreport.run(NOW, credit=5.0)["written"] is True
    assert dailyreport.run(NOW + dt.timedelta(hours=3), credit=5.0)["written"] is False
    assert dailyreport.run(NOW + dt.timedelta(days=1), credit=5.0)["written"] is True
    assert sum(1 for e in agentlog._all() if e["title"].startswith("Daily report")) == 2


def _ago(hours):
    return NOW - dt.timedelta(hours=hours)


def test_an_event_about_a_problem_that_is_gone_is_not_listed(tmp_path, monkeypatch):
    """The 31 Oct report listed ten problems; seven were events from the day before that had been fixed (a thumbnail set on retry, a duplicate the owner
    released, a film re-uploaded under a new title). An event is history: it counts only while the video it names still shows the problem."""
    setup(tmp_path, monkeypatch)
    make(tmp_path, "thumb-ok", hours_ago=30, video_id="a", uploaded_at="2026-10-24T20:00:00Z", thumbnail_uploaded=True)
    make(tmp_path, "dup-released", hours_ago=30, hold=False)
    make(tmp_path, "film", hours_ago=30, video_id="f", uploaded_at="2026-10-24T20:00:00Z", approved=True)
    for t in ("Thumbnail was not set: THUMB-OK", "Held a duplicate: DUP-RELEASED", "Pulled back for repair: FILM", "Stopped spending on: FILM",
              "Narration check found missing words: FILM", "Pulled back for repair: AN OLD TITLE NOBODY HAS ANY MORE"):
        agentlog.event("error", t, "detail", now=_ago(3))
    agentlog.event("found", "Re-check: something", "detail", now=_ago(3))
    r = dailyreport.build(NOW, credit=8.5)
    assert r["problems"] == ["Re-check: something"]


def test_an_event_is_listed_while_the_video_still_shows_the_problem(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    make(tmp_path, "dup", hours_ago=3, hold=True)
    make(tmp_path, "draft", hours_ago=3, approved=False)
    make(tmp_path, "heard", hours_ago=3)
    for t in ("Held a duplicate: DUP", "Stopped spending on: DRAFT", "Narration check found missing words: HEARD"):
        agentlog.event("error", t, "detail", now=_ago(2))
    r = dailyreport.build(NOW, credit=8.5)
    assert r["problems"] == ["Held a duplicate: DUP", "Stopped spending on: DRAFT", "Narration check found missing words: HEARD"]


def test_a_thumbnail_that_was_refused_and_never_set_is_a_problem_of_the_video_itself(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    make(tmp_path, "bare", hours_ago=30, video_id="b", uploaded_at="2026-10-24T20:00:00Z", thumbnail_error="refused")
    make(tmp_path, "fine", hours_ago=30, video_id="c", uploaded_at="2026-10-24T20:00:00Z", thumbnail_error="refused", thumbnail_uploaded=True)
    r = dailyreport.build(NOW, credit=8.5)
    assert [p for p in r["problems"] if "thumbnail" in p.lower()] == ["BARE has no custom thumbnail (YouTube refused it): add it in YouTube Studio"]


def test_videos_held_private_on_purpose_wait_for_the_owner_and_are_not_problems(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    make(tmp_path, "pulled", hours_ago=30, video_id="p", hold=True, hold_reason="owner, 30 Oct 2026: every video needs changes", taken_back="2026-10-30T16:01:20Z")
    make(tmp_path, "plain", hours_ago=30, video_id="q", hold=True)
    r = dailyreport.build(NOW, credit=8.5)
    assert r["problems"] == [] and r["held"] == ["PLAIN", "PULLED"]
    assert "PULLED (owner, 30 Oct 2026: every video needs changes)" in r["text"] and "PLAIN (held)" in r["text"]
    assert "Problems: none." in r["text"]
