import datetime as dt
import json

import growthdata

NOW = dt.datetime(2026, 10, 28, 12, 0, tzinfo=dt.timezone.utc)
ISO = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
CURVE = [[round(i / 100, 2), round(1.3 - i * 0.008, 4)] for i in range(1, 101)]
REACH = "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n20261027,C,V1,600,0.02\n20261026,C,V1,400,0.045\n20261027,C,OTHER,50,0.5\n"


class Req:
    def __init__(self, v):
        self.v = v

    def execute(self):
        if isinstance(self.v, Exception):
            raise self.v
        return self.v


class Analytics:
    def __init__(self, totals=None, curve=CURVE, traffic=None, bad_curve=()):
        self.totals, self.curve, self.traffic, self.bad, self.calls = totals, curve, traffic or [["SHORTS", 40], ["YT_SEARCH", 5]], set(bad_curve), []

    def reports(self):
        return self

    def query(self, **kw):
        self.calls.append(kw)
        d = kw["dimensions"]
        if d == "video":
            return Req(self.totals if isinstance(self.totals, Exception) else {"rows": self.totals})
        if d == "day,video":
            return Req({"rows": [["2026-10-26", "V1", 5], ["2026-10-27", "V1", 7], ["2026-10-27", "V2", 9]]})
        if d == "day,insightTrafficSourceType":
            return Req({"rows": [["2026-10-26", "SHORTS", 30], ["2026-10-26", "YT_SEARCH", 10], ["2026-10-27", "SHORTS", 20]]})
        if d == "elapsedVideoTimeRatio":
            return Req(RuntimeError("quota") if kw["filters"].split("==")[1] in self.bad else {"rows": self.curve})
        return Req({"rows": self.traffic})


class Reports:
    def __init__(self, reports):
        self.reports_ = reports

    def list(self, **kw):
        return Req({"reports": self.reports_})


class Reporting:
    def __init__(self, reports=None, error=None):
        self.created, self.error, self._reports = [], error, reports if reports is not None else [{"id": "r1", "downloadUrl": "https://x/r1"}]

    def jobs(self):
        return self

    def list(self):
        return Req(self.error or {"jobs": []})

    def create(self, body):
        self.created.append(body)
        return Req({"id": "job1", **body})

    def reports(self):
        return Reports(self._reports)


class Session:
    def get(self, url, timeout=0):
        r = type("R", (), {"text": REACH, "raise_for_status": lambda self: None})()
        return r


def videos(now=NOW):
    return [{"id": "V1", "title": "Young doc", "views": 100, "seconds": 600, "published": ISO(now - dt.timedelta(days=2))},
            {"id": "V2", "title": "Old short", "views": 900, "seconds": 40, "published": ISO(now - dt.timedelta(days=20))}]


TOTALS = [["V1", 100, 41.234, 55, 3], ["V2", 900, 70.0, 300, 1]]


def run(tmp_path, an=None, rp=None, now=NOW):
    return growthdata.collect(now, (None, an or Analytics(TOTALS), rp if rp is not None else Reporting(), Session()), tmp_path / "videos.json", lambda: videos(now))


def test_retention_is_read_at_thirty_seconds_into_the_video_and_never_invented():
    assert growthdata.retention_at(CURVE, 30, 600) == round((1.3 - 5 * 0.008) * 100, 1)  # 5% into a 10-minute video
    assert growthdata.retention_at(CURVE, 30, 20) == round(CURVE[-1][1] * 100, 1)  # a 20-second video: clamped to its end
    assert growthdata.retention_at([], 30, 600) is None and growthdata.retention_at(CURVE, 30, 0) is None


def test_the_reach_report_is_summed_per_video_day_and_percent_columns_are_converted():
    r = growthdata.parse_reach_csv(REACH)
    assert r["V1"]["2026-10-27"] == {"impressions": 600, "ctr": 0.02} and r["V1"]["2026-10-26"]["impressions"] == 400 and "OTHER" in r
    pct = growthdata.parse_reach_csv("date,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n20261027,V1,100,4.5\n20261027,V1,100,5.5\n")
    assert pct["V1"]["2026-10-27"] == {"impressions": 200, "ctr": 0.05}
    assert growthdata.parse_reach_csv("a,b\n1,2\n") == {} and growthdata.parse_reach_csv("") == {}


def test_a_video_is_due_every_six_hours_while_young_and_daily_when_older():
    young, old = ISO(NOW - dt.timedelta(days=2)), ISO(NOW - dt.timedelta(days=20))
    e = {"collected": ISO(NOW - dt.timedelta(hours=5))}
    assert growthdata.due(None, young, NOW) and not growthdata.due(e, young, NOW) and not growthdata.due(e, old, NOW)
    e = {"collected": ISO(NOW - dt.timedelta(hours=7))}
    assert growthdata.due(e, young, NOW) and not growthdata.due(e, old, NOW)
    assert growthdata.due({"collected": ISO(NOW - dt.timedelta(hours=25))}, old, NOW)


def test_collect_stores_every_number_with_its_source_and_the_click_rate_from_the_reach_report(tmp_path):
    rp = Reporting()
    out = run(tmp_path, rp=rp)
    d = json.loads((tmp_path / "videos.json").read_text())
    v1, v2 = d["videos"]["V1"], d["videos"]["V2"]
    assert out["collected"] == 2 and out["with_ctr"] == 1
    assert (v1["views_90d"], v1["avg_pct_viewed"], v1["minutes_90d"], v1["subs_gained_90d"], v1["kind"], v2["kind"]) == (100, 41.2, 55, 3, "doc", "short")
    assert v1["retention_at_30s"] == growthdata.retention_at(CURVE, 30, 600) and v1["traffic"] == {"SHORTS": 40, "YT_SEARCH": 5} and v1["subs_per_1k_views"] == 30.0
    assert v1["impressions"] == 1000 and v1["ctr"] == 0.03 and "Reporting API channel_reach_basic_a1" in v1["sources"]["ctr"] and v2["ctr"] is None
    assert "Analytics API 2026-10-28" == v1["sources"]["analytics"] and "views_per_unique" in v1["unavailable"] and "unique" not in json.dumps({k: v for k, v in v1.items() if k != "unavailable"})
    assert [b["reportTypeId"] for b in rp.created] == ["channel_reach_basic_a1"]  # the only write: a read-only report job on Google's side


def test_with_the_reporting_api_off_the_click_rate_stays_empty_with_the_reason_and_the_rest_is_collected(tmp_path):
    out = run(tmp_path, rp=Reporting(error=PermissionError("403 YouTube Reporting API has not been used in project 1 before")))
    v1 = json.loads((tmp_path / "videos.json").read_text())["videos"]["V1"]
    assert v1["ctr"] is None and v1["impressions"] is None and "unavailable" in v1["sources"]["ctr"] and "403" in v1["sources"]["ctr"]
    assert v1["views_90d"] == 100 and out["with_ctr"] == 0 and any("reach reports unavailable" in p for p in out["problems"])


def test_one_failing_query_never_stops_the_other_videos_and_a_missing_number_is_not_filled_in(tmp_path):
    out = run(tmp_path, an=Analytics(TOTALS, bad_curve=["V1"]))
    d = json.loads((tmp_path / "videos.json").read_text())["videos"]
    assert d["V1"]["retention_at_30s"] is None and "retention" not in d["V1"]["sources"] and d["V2"]["retention_at_30s"] is not None
    assert any("V1 retention" in p for p in out["problems"])
    run(tmp_path / "x", an=Analytics(RuntimeError("quota")))  # even the totals failing writes a file, with nothing invented
    e = json.loads((tmp_path / "x" / "videos.json").read_text())["videos"]["V1"]
    assert e["views_90d"] is None and e["avg_pct_viewed"] is None and "analytics" not in e["sources"]


def test_young_videos_are_collected_again_after_six_hours_and_old_ones_after_a_day(tmp_path):
    assert run(tmp_path)["collected"] == 2
    assert run(tmp_path, now=NOW + dt.timedelta(hours=5))["collected"] == 0
    assert run(tmp_path, now=NOW + dt.timedelta(hours=7))["collected"] == 1  # V1 only
    assert run(tmp_path, now=NOW + dt.timedelta(hours=26))["collected"] == 2


def test_the_reach_reports_already_read_are_not_downloaded_twice(tmp_path):
    calls = []
    sess = type("S", (), {"get": lambda self, url, timeout=0: calls.append(url) or Session().get(url)})()
    growthdata.collect(NOW, (None, Analytics(TOTALS), Reporting(), sess), tmp_path / "videos.json", lambda: videos())
    growthdata.collect(NOW + dt.timedelta(hours=7), (None, Analytics(TOTALS), Reporting(), sess), tmp_path / "videos.json", lambda: videos(NOW))
    assert calls == ["https://x/r1"]
    assert json.loads((tmp_path / "videos.json").read_text())["videos"]["V1"]["ctr"] == 0.03  # and the earlier days are kept


def test_daily_views_per_video_and_source_are_kept_for_the_drift_detector_at_most_once_a_day(tmp_path):
    an = Analytics(TOTALS)
    run(tmp_path, an=an)
    d = json.loads((tmp_path / "daily.json").read_text())
    assert d["videos"]["V1"] == {"2026-10-26": 5, "2026-10-27": 7} and d["traffic"]["2026-10-26"] == {"SHORTS": 30, "YT_SEARCH": 10}
    n = sum(1 for c in an.calls if c["dimensions"] in ("day,video", "day,insightTrafficSourceType"))
    assert n == 2
    run(tmp_path, an=an, now=NOW + dt.timedelta(hours=7))
    assert sum(1 for c in an.calls if c["dimensions"] == "day,video") == 1  # not asked again within 20 hours
    run(tmp_path, an=an, now=NOW + dt.timedelta(hours=26))
    assert sum(1 for c in an.calls if c["dimensions"] == "day,video") == 2


def test_a_failing_daily_query_is_reported_and_does_not_stop_the_rest(tmp_path):
    class Bad(Analytics):
        def query(self, **kw):
            if kw["dimensions"] == "day,video":
                return Req(RuntimeError("quota"))
            return super().query(**kw)

    out = run(tmp_path, an=Bad(TOTALS))
    assert out["collected"] == 2 and any("daily series unavailable" in p for p in out["problems"])
