from datetime import datetime, timezone

import scheduler

UTC = timezone.utc


def at(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_next_slot_earliest_default():
    now = at("2026-10-19T12:00:00Z")  # Monday
    assert scheduler.to_rfc3339(scheduler.next_slot(now, scheduler.SLOTS_DEFAULT, [])) == "2026-10-22T19:00:00Z"


def test_respects_min_lead():
    now = at("2026-10-22T18:00:00Z")  # 1 h before Thursday's slot, lead 24 h
    assert scheduler.to_rfc3339(scheduler.next_slot(now, scheduler.SLOTS_DEFAULT, [])) == "2026-10-23T22:00:00Z"


def test_skips_taken_slot():
    now = at("2026-10-19T12:00:00Z")
    taken = [at("2026-10-22T19:00:00Z")]
    assert scheduler.to_rfc3339(scheduler.next_slot(now, scheduler.SLOTS_DEFAULT, taken)) == "2026-10-23T22:00:00Z"


def test_dst_change():
    sun = [{"day": "sun", "time": "10:00"}]
    assert scheduler.to_rfc3339(scheduler.next_slot(at("2026-10-24T00:00:00Z"), sun, [], 0)) == "2026-10-25T14:00:00Z"
    assert scheduler.to_rfc3339(scheduler.next_slot(at("2026-10-30T00:00:00Z"), sun, [], 0)) == "2026-11-01T15:00:00Z"


def test_to_rfc3339_and_local():
    d = at("2026-10-23T22:00:00Z")
    assert scheduler.to_rfc3339(d) == "2026-10-23T22:00:00Z"
    assert scheduler.fmt_local(d, "Asia/Dhaka") == "Sat 24 Oct, 04:00"
