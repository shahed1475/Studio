import datetime as dt
import re

import pytest

import agentbus
import agentlog
import drift
import rulesfile

END = dt.date(2026, 10, 27)
NOW = dt.datetime(2026, 10, 28, 8, 0, tzinfo=dt.timezone.utc)
STEADY = [9, 10, 11, 10, 9, 11, 10]


def days(n):
    return [str(END - dt.timedelta(days=i)) for i in range(n - 1, -1, -1)]


def series(n=35, shift_from=None, level=40, base=STEADY):
    """n days ending 2026-10-27: a steady pattern, jumping to `level` for the last `shift_from` days."""
    return {d: (level if shift_from and i >= n - shift_from else base[i % len(base)]) for i, d in enumerate(days(n))}


def daily(n_shifting=3, n_steady=2, **kw):
    v = {f"S{i}": series(shift_from=7, **kw) for i in range(n_shifting)}
    v.update({f"T{i}": series() for i in range(n_steady)})
    return {"videos": v, "traffic": {}}


def test_a_sustained_jump_needs_every_recent_day_beyond_the_noise_in_the_same_direction():
    v = list(series(shift_from=7).values())
    s = drift.sustained_shift(v, 28, 7, 2)
    assert s["direction"] == "up" and s["recent_mean"] == 40 and s["change_pct"] > 250
    v[-1] = 10  # one ordinary day inside the window: not sustained
    assert drift.sustained_shift(v, 28, 7, 2) is None
    assert drift.sustained_shift(list(series(shift_from=7, level=0).values()), 28, 7, 2)["direction"] == "down"


def test_a_quiet_series_and_too_little_history_never_trigger():
    quiet = [0, 1, 0, 0, 1, 0, 0] * 5
    assert drift.sustained_shift(quiet[:28] + [5] * 7, 28, 7, 2) is None  # a mean under 2 views a day says nothing
    assert drift.sustained_shift([10] * 20, 28, 7, 2) is None


def test_one_video_moving_is_that_video_but_three_moving_together_is_a_finding():
    one = drift.detect(daily(n_shifting=1, n_steady=4))
    assert one["status"] == "ok" and one["events"] == []
    many = drift.detect(daily(n_shifting=3))
    e = many["events"][0]
    assert e["kind"] == "views" and e["direction"] == "up" and len(e["videos"]) == 3 and e["since"] == "2026-10-21" and "3 videos" in e["text"]


def test_the_traffic_mix_is_checked_by_each_sources_share_of_views():
    traffic = {d: {"SHORTS": 40 + (i % 3), "YT_SEARCH": 20 + (i % 2)} for i, d in enumerate(days(35))}
    for d in days(35)[-7:]:
        traffic[d] = {"SHORTS": 15, "YT_SEARCH": 45}  # search takes over from Shorts
    res = drift.detect({"videos": {}, "traffic": traffic})
    kinds = {(e["source"], e["direction"]) for e in res["events"]}
    assert ("SHORTS", "down") in kinds and ("YT_SEARCH", "up") in kinds


def test_not_enough_history_is_said_plainly_with_the_days_missing():
    res = drift.detect({"videos": {"V": series(n=20)}, "traffic": {}})
    assert res["status"] == "not enough history" and res["have_days"] == 20 and res["need_days"] == 35 and res["events"] == []


def test_the_four_numbers_come_from_the_rules_file():
    d = daily(n_shifting=2, n_steady=3)
    assert drift.detect(d)["events"] == []
    r = rulesfile.load()
    r["benchmarks"]["drift_min_videos"] = 2
    assert len(drift.detect(d, r)["events"]) == 1
    r["benchmarks"]["drift_sigma"] = 6
    r["benchmarks"]["drift_min_videos"] = 2
    d2 = {"videos": {f"S{i}": series(shift_from=7, level=20) for i in range(3)}, "traffic": {}}
    assert drift.detect(d2)["events"] != [] and drift.detect(d2, r)["events"] == []
    src = open("drift.py").read()
    assert "sigma = 2" not in src and not re.search(r"\b28\b", src.replace("2026", "")) and "MIN_VIDEOS" not in src  # the numbers live in rules.json


def test_a_finding_goes_to_the_owner_once_with_the_rule_changes_of_that_window_and_changes_nothing(tmp_path):
    import json

    path = tmp_path / "daily.json"
    path.write_text(json.dumps(daily(n_shifting=3)))
    hints = [{"at": "2026-10-20T06:10:00Z", "page": "Monetization policies", "severity": "high"}, {"at": "2025-01-01T00:00:00Z", "page": "Old page"}]
    before = rulesfile.load()
    res = drift.run(NOW, path, policy_changes=hints)
    t = agentbus.tasks()[0]
    assert len(res["events"]) == 1 and t["kind"] == "algorithm_drift" and t["state"] == "owner" and "Monetization policies (high)" in t["evidence"] and "Old page" not in t["evidence"]
    assert "Nothing was changed" in agentlog.recent(1)[0]["detail"]
    drift.run(NOW, path, policy_changes=hints)
    assert len(agentbus.tasks()) == 1 and rulesfile.load() == before  # one task however often it runs; no rule or strategy was touched


def test_with_no_file_yet_the_detector_reports_no_history_and_does_not_crash(tmp_path):
    assert drift.run(NOW, tmp_path / "missing.json")["status"] == "not enough history"


def test_days_before_the_channel_had_any_views_are_not_history():
    zeros = {str(END - dt.timedelta(days=i)): 0 for i in range(88, 7, -1)}
    week = {str(END - dt.timedelta(days=i)): 10 for i in range(6, -1, -1)}
    res = drift.detect({"videos": {"V": {**zeros, **week}}, "traffic": {}})
    assert res["status"] == "not enough history" and res["have_days"] == 7 and res["events"] == []
    assert drift.detect({"videos": {}, "traffic": {}})["have_days"] == 0
