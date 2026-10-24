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
