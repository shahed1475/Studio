"""Click rate on the Growth page (growthpage.ctr_summary, title_effects): YouTube's reach reports, impressions-weighted, read only; test rows such
as "V2" never count, and a before/after reading needs enough impressions on both sides."""
import datetime as dt

import growthpage as gp

RULES = {"benchmarks": {"ctr_target": 0.04, "ctr_retest_below": 0.03, "min_impressions_for_ctr": 200}}
END = dt.date(2026, 11, 19)


def reach(days: int, imp: int, ctr: float, end=END) -> dict:
    return {(end - dt.timedelta(days=i)).isoformat(): {"impressions": imp, "ctr": ctr} for i in range(days)}


def metrics():
    return {"videos": {
        "aaaaaaaaaaa": {"title": "Mami Wata", "kind": "doc", "reach": reach(20, 30, 0.07)},          # 600 impressions, 7%
        "bbbbbbbbbbb": {"title": "Kitsune", "kind": "short", "reach": reach(20, 25, 0.015)},          # 500, 1.5%
        "ccccccccccc": {"title": "Too new", "kind": "short", "reach": reach(3, 10, 0.5)},             # 30: not judged
        "V2": {"title": "test row", "kind": "doc", "reach": reach(20, 1000, 0.9)},                     # not a YouTube id: never judged
        "ddddddddddd": {"title": "Old one", "kind": "doc", "reach": reach(20, 20, 0.03, END - dt.timedelta(days=30))},
    }}


def test_the_summary_is_weighted_by_impressions_and_split_by_format():
    s = gp.ctr_summary(metrics(), rules=RULES)
    assert s["through"] == "2026-11-19"
    imp = 600 + 500 + 30 + 20 * 1000  # the last 28 days, the test row included in the channel total as the reports would
    assert s["last_28"]["impressions"] == imp
    assert s["by_kind"]["doc"]["impressions"] == 600 + 20000 and s["by_kind"]["short"]["impressions"] == 530
    assert s["by_kind"]["short"]["ctr_pct"] == round((500 * 0.015 + 30 * 0.5) / 530 * 100, 2)
    assert s["prev_28"]["impressions"] > 0  # the old video's days fall in the 28 before


def test_only_real_videos_with_enough_impressions_are_judged_and_the_retest_line_is_marked():
    s = gp.ctr_summary(metrics(), rules=RULES)
    assert [r["video_id"] for r in s["best"]] == ["aaaaaaaaaaa", "ddddddddddd", "bbbbbbbbbbb"]
    assert s["videos_judged"] == 3 and s["below_retest"] == 1
    k = next(r for r in s["best"] if r["video_id"] == "bbbbbbbbbbb")
    assert k["ctr_pct"] == 1.5 and k["below_retest"] is True
    assert s["target_pct"] == 4.0 and s["retest_pct"] == 3.0 and s["min_impressions"] == 200


def test_weakest_lists_the_lowest_videos_not_already_shown_as_best():
    vids = {f"vid{i:08d}": {"title": f"V{i}", "kind": "doc", "reach": reach(10, 30, 0.01 * i)} for i in range(1, 8)}
    s = gp.ctr_summary({"videos": vids}, rules=RULES)
    assert [r["title"] for r in s["best"]] == ["V7", "V6", "V5"] and [r["title"] for r in s["weakest"]] == ["V1", "V2", "V3"]


def test_no_data_and_odd_data_give_an_empty_summary_not_an_error():
    for m in (None, {}, {"videos": None}, {"videos": {"x": "odd"}}):
        s = gp.ctr_summary(m, now=dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc), rules=RULES)
        assert s["last_28"] == {"impressions": 0, "ctr_pct": None} and s["videos_judged"] == 0 and s["best"] == []


def test_an_unreadable_rules_file_falls_back_to_the_shipped_numbers(monkeypatch):
    import rulesfile

    monkeypatch.setattr(rulesfile, "load", lambda: (_ for _ in ()).throw(ValueError("broken")))
    assert gp.ctr_summary(metrics())["retest_pct"] == 3.0


def change(vid, at, old="Old title", new="New title", **k):
    return {"id": "a1", "at": at, "video_id": vid, "kind": "metadata", "source": "titletest", "before": {"title": old}, "after": {"title": new}, **k}


def test_a_title_change_is_read_before_and_after_with_enough_impressions():
    day = dt.date(2026, 11, 1)
    r = {**reach(7, 40, 0.02, day - dt.timedelta(days=1)), day.isoformat(): {"impressions": 999, "ctr": 0.5}, **reach(7, 40, 0.05, day + dt.timedelta(days=7))}
    m = {"videos": {"aaaaaaaaaaa": {"title": "t", "reach": r}}}
    got = gp.title_effects(m, [change("aaaaaaaaaaa", "2026-11-01T10:00:00Z", rolled_back=True)], rules=RULES)
    assert got[0]["before"] == {"impressions": 280, "ctr_pct": 2.0} and got[0]["after"] == {"impressions": 280, "ctr_pct": 5.0}
    assert got[0]["verdict"] == "higher after" and got[0]["rolled_back"] is True  # the change day itself (999 impressions) is left out


def test_too_recent_too_few_impressions_and_about_the_same():
    day = dt.date(2026, 11, 15)
    m = {"videos": {"aaaaaaaaaaa": {"title": "t", "reach": reach(10, 40, 0.02, dt.date(2026, 11, 17))},
                    "bbbbbbbbbbb": {"title": "t", "reach": reach(30, 5, 0.02, dt.date(2026, 11, 30))},
                    "ccccccccccc": {"title": "t", "reach": reach(30, 40, 0.031, dt.date(2026, 11, 30))}}}
    acts = [change(v, "2026-11-15T09:00:00Z") for v in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc")]
    got = {r["video_id"]: r["verdict"] for r in gp.title_effects(m, acts, rules=RULES)}
    assert got["aaaaaaaaaaa"].startswith("too recent") and got["bbbbbbbbbbb"].startswith("not enough impressions") and got["ccccccccccc"] == "about the same"
    assert day.isoformat() == "2026-11-15"


def test_test_rows_and_changes_that_are_not_title_changes_are_ignored():
    m = {"videos": {"V2": {"reach": reach(30, 100, 0.1)}, "aaaaaaaaaaa": {"reach": reach(30, 100, 0.1)}}}
    acts = [change("V2", "2026-11-01T00:00:00Z"), change("aaaaaaaaaaa", "2026-11-01T00:00:00Z", old="Same", new="Same"),
            {"video_id": "aaaaaaaaaaa", "kind": "status", "before": {"privacy": "private"}, "after": {"privacy": "public"}}, "odd", None]
    assert gp.title_effects(m, acts, rules=RULES) == [] and gp.title_effects(m, None) == []


def test_the_growth_page_carries_both():
    out = gp.build({}, [], {}, metrics(), [])
    assert out["ctr"]["videos_judged"] == 3 and out["title_effects"] == []
    assert gp.build(None, None, None, None)["ctr"]["best"] == []
