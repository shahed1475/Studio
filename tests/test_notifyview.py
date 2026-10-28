import datetime as dt

import notifyview

NOW = dt.datetime(2026, 10, 29, 12, 0, tzinfo=dt.timezone.utc)
EVENTS = [{"at": "2026-10-29T11:00:00Z", "kind": "error", "title": "A render failed", "detail": "ffmpeg exited 1", "read": False},
          {"at": "2026-10-29T10:00:00Z", "kind": "applied", "title": "Repaired a title", "detail": "", "read": False},
          {"at": "2026-10-29T09:00:00Z", "kind": "strategy", "title": "A new strategy", "detail": "", "read": True},
          {"at": "2026-10-29T08:00:00Z", "kind": "info", "title": "Checked", "detail": "", "read": True}]
RISKS = [{"name": "Running out of money", "level": "act", "owner_decision": "Top up OpenRouter", "evidence": "$1 left"}, {"name": "Agents", "level": "watch", "evidence": "2 tasks"},
         {"name": "Backups", "level": "ok", "evidence": "fine"}]


def build(**k):
    return notifyview.build(NOW, events=EVENTS, **k)


def test_events_are_sorted_into_the_three_sources_with_a_level_each():
    items = {i["title"]: i for i in build()["items"]}
    assert (items["A render failed"]["source"], items["A render failed"]["level"]) == ("Warnings", "bad")
    assert (items["Repaired a title"]["source"], items["Repaired a title"]["level"]) == ("Activity", "ok")
    assert (items["A new strategy"]["source"], items["A new strategy"]["tab"]) == ("Growth", "growth")
    assert items["A render failed"]["unread"] and not items["Checked"]["unread"]


def test_the_badge_counts_what_needs_a_person_not_every_risk_at_watch():
    n = build(risks=RISKS, needs_you=2, growth={"rules": {"pending": 1}, "edits_pending": 0, "hold": None, "diagnoses": [1, 2], "drift": {"events": []}})
    c = n["counts"]
    assert c["unread"] == 2 and c["waiting"] == 3  # the act risk, the videos to decide on, the rule change; not the watch risk, not the diagnoses
    assert c["badge"] == 5 and c["warnings"] >= 4
    titles = [i["title"] for i in n["items"]]
    assert "Agents" in titles and "Backups" not in titles  # watch is listed, ok is not
    assert n["items"][0]["pinned"] and n["items"][0]["level"] == "bad"  # the most serious standing item first
    assert not any(i["pinned"] for i in n["items"][len([i for i in n["items"] if i["pinned"]]):])  # then the events


def test_a_policy_hold_and_failed_jobs_are_urgent_and_nothing_is_required_to_build():
    n = build(growth={"hold": {"reason": "x"}}, failed_jobs=[{"id": "1-doc", "cmd": "doc Lost Army"}])
    levels = {i["title"]: i["level"] for i in n["items"] if i["pinned"]}
    assert levels["A policy hold is active"] == "bad" and levels["A job failed: doc Lost Army"] == "bad"
    empty = notifyview.build(NOW, events=[])
    assert empty["items"] == [] and empty["counts"]["badge"] == 0
    assert notifyview.build(NOW, risks=[{"name": None}], growth={"drift": None}, events=[])["items"] == []  # odd data from a source does not break the page


def test_text_is_cut_to_a_size_the_screen_can_hold():
    long = [{"at": "T", "kind": "info", "title": "t" * 500, "detail": "d" * 900, "read": True}]
    i = notifyview.build(NOW, events=long)["items"][0]
    assert len(i["title"]) == 160 and len(i["detail"]) == 240
