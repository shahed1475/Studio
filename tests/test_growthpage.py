import growthpage

SNAPS = [{"date": "2026-10-19", "subscribers": 0, "views": 0, "videos": 4}, {"date": "2026-10-24", "subscribers": 3, "views": 410, "videos": 8},
         {"date": "2026-10-28", "subscribers": 8, "views": 1056, "videos": 12}, {"date": "bad", "subscribers": None, "views": "x"}]
METRICS = {"updated": "T", "problems": ["Reporting API off"], "videos": {
    "a": {"title": "Mami Wata", "published": "2026-10-27T22:00:00Z", "kind": "doc", "daily_views_total": 7, "views_90d": None, "avg_pct_viewed": None, "retention_at_30s": None, "ctr": None,
          "sources": {"ctr": "no reach report yet"}, "unavailable": {"avg_pct_viewed": "needs 48 hours"}},
    "b": {"title": "Thunderbird", "published": "2026-10-20T10:00:00Z", "kind": "short", "daily_views_total": 54, "views_90d": 54, "avg_pct_viewed": 61.5, "retention_at_30s": 70.2, "ctr": None},
    "d": {"title": "The Voynich Manuscript", "published": "2026-10-25T10:00:00Z", "kind": "short", "daily_views_total": 328, "avg_pct_viewed": 49.5, "retention_at_30s": 50.0, "ctr": 0.01633, "impressions": 245},
    "c": {"title": None, "daily_views_total": None}}}


def test_the_series_is_clean_ordered_numbers_and_the_change_is_measured_against_a_real_earlier_day():
    s = growthpage.series(SNAPS)
    assert [p["date"] for p in s] == ["2026-10-19", "2026-10-24", "2026-10-28"]  # the broken row is dropped, nothing is invented
    d = growthpage.change(s, days=7)
    assert d == {"days": 9, "subscribers": 8, "views": 1056, "videos": 8}  # the oldest snapshot is 9 days back: that is what is said, not "7 days"
    d4 = growthpage.change(s, days=4)
    assert d4["days"] == 4 and d4["subscribers"] == 5 and d4["views"] == 646  # 28 Oct against 24 Oct
    assert growthpage.change([], 7) is None and growthpage.change(s[:1], 7) is None


def test_video_rows_keep_missing_numbers_missing_and_say_why():
    rows = growthpage.video_rows(METRICS, [{"title": "Mami Wata", "window": "48h", "primary": "insufficient_data", "evidence": "too few views"}])
    assert [r["title"] for r in rows] == ["The Voynich Manuscript", "Thunderbird", "Mami Wata", "(untitled)"]  # most views first, an untitled video is still listed
    mami = rows[2]
    assert mami["views"] == 7 and mami["avg_pct_viewed"] is None and mami["why"]["ctr"] == "no reach report yet" and mami["why"]["avg_pct_viewed"] == "needs 48 hours"
    assert mami["diagnosis"]["primary"] == "insufficient_data"
    assert rows[1]["avg_pct_viewed"] == 61.5 and rows[1]["retention_30s"] == 70.2 and rows[1]["why"]["ctr"] == "not available yet"
    assert rows[3]["views"] is None


def test_click_rate_is_stored_as_a_fraction_and_shown_as_a_percentage():
    """The collector stores 0.01633 for a 1.6 percent click rate (growthdata divides by 100). Shown as stored, it read as 0.0 percent."""
    voynich = growthpage.video_rows(METRICS)[0]
    assert voynich["title"] == "The Voynich Manuscript" and voynich["ctr"] == 1.63 and voynich["impressions"] == 245 and voynich["avg_pct_viewed"] == 49.5


def test_build_survives_every_source_missing_or_in_a_new_shape():
    out = growthpage.build({"report": {"week": "W44", "queued": []}, "strategies": None, "config": {"mode": "off"}}, None, None, None)
    assert out["series"] == [] and out["videos"] == [] and out["change"] is None and out["strategies"] == []
    full = growthpage.build({"report": None, "strategies": [{"id": "1", "status": "proposed"}], "own": {"subscribers": 8}}, SNAPS, {"report": "text", "hold": None}, METRICS)
    assert full["latest"]["subscribers"] == 8 and len(full["videos"]) == 4 and full["metrics_updated"] == "T" and full["metrics_problems"] == ["Reporting API off"]
    assert full["growth"]["report"] == "text"
