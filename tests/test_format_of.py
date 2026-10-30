"""12 of 27 records (older Shorts) have no `format` key. The governor and `unstick` called them documentaries while the reviewer, fixer and Autopilot's state called them Shorts:
the weekly documentary cap counted Shorts, and a stuck Short was allowed the documentary's repair budget ($2.20 instead of $0.40). One rule decides it now."""
import json

import governor
import records
import unstick


def test_an_explicit_format_always_wins():
    assert records.format_of({"format": "doc"}, "short-looking-name") == "doc"
    assert records.format_of({"format": "short", "chapters": [{"title": "x"}]}, "doc-looks-like-a-doc") == "short"


def test_a_record_without_a_format_is_a_documentary_only_when_it_looks_like_one():
    assert records.format_of({"lines": [{"text": "a"}] * 12}, "the-thunderbird-a-name-that-keeps-flying") == "short"
    assert records.format_of({}, "doc-the-oracle-of-delphi") == "doc"          # the documentary producer always names its folder doc-...
    assert records.format_of({"chapters": [{"title": "One"}]}, "") == "doc"      # a chapter list is a documentary's
    assert records.format_of({"chapters": []}, "x") == "short"                   # an empty list is not
    assert records.format_of({"format": "news"}, "x") == "short"                 # an unknown value is not a documentary


def test_the_governor_does_not_count_an_older_short_as_a_documentary():
    older_short = {"publish_at": "2026-10-29T23:00:00Z", "lines": [{"text": "a"}] * 11}   # no format key, no chapters
    a_doc = {"publish_at": "2026-10-27T22:00:00Z", "format": "doc"}
    assert [t.day for t in governor._times([older_short, a_doc], "doc")] == [27]
    assert [t.day for t in governor._times([older_short, a_doc], "short")] == [29]


def test_a_stuck_short_with_no_format_gets_the_short_repair_budget_not_the_documentarys(tmp_path, monkeypatch):
    import escalate
    import llm

    folder = tmp_path / "seven-sleepers-mystery"
    folder.mkdir()
    checks = [{"name": "invented_facts", "ok": False, "severity": "block", "detail": "soldiers"}]
    records.save(folder, {"title": "t", "lines": [{"text": "a"}] * 10, "review": {"verdict": "fail", "checks": checks}, "fix_attempts": 5})
    asked = {}
    monkeypatch.setattr(llm, "video_cost", lambda slug: 0.5)           # more than a Short may still spend ($0.70 limit, 0.3 reserve), less than a documentary may
    monkeypatch.setattr(llm, "spent_today", lambda *a, **k: 0.0)
    monkeypatch.setattr(escalate, "solve", lambda agent, problem, evidence, fixes, **k: asked.update(problem=problem, may_spend=k.get("may_spend")) or {"solved": False})
    unstick._run(__import__("datetime").datetime(2026, 10, 30, 12, tzinfo=__import__("datetime").timezone.utc), tmp_path, None, lambda f: {"verdict": "fail"}, None)
    assert "short repair failed" in asked["problem"] and asked["may_spend"] is False


def test_a_stuck_short_is_tried_after_the_documentaries(tmp_path):
    for name, extra in (("a-short", {}), ("doc-b", {"format": "doc"})):
        d = tmp_path / name
        d.mkdir()
        records.save(d, {"review": {"verdict": "fail", "checks": [{"name": "x", "ok": False, "severity": "block"}]}, "fix_attempts": 5, **extra})
    assert [f.name for f, _ in unstick.candidates(tmp_path)] == ["doc-b", "a-short"]
