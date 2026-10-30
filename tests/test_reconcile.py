"""30 Oct 2026: the studio said three videos were on YouTube; asked by id, YouTube had none of them (deleted in Studio or removed: unknown), and the owner saw the studio's claim stay wrong.
The hourly health check now reconciles: a record with a video id that YouTube cannot find on two checks in a row loses the id, is HELD (it is never uploaded again silently: it may have been
deleted on purpose) and the owner gets one plain event. Newly uploaded videos (YouTube lags) and an empty answer for many ids (an outage) are never read as 'gone'."""
import datetime as dt
import json

import agentlog
import config
import reconcile
import records

NOW = dt.datetime(2026, 10, 30, 18, 0, tzinfo=dt.timezone.utc)


class YT:
    def __init__(self, present=(), boom=False):
        self.present, self.boom = set(present), boom

    def videos(self):
        return self

    def list(self, part, id):
        self.ids = id.split(",")
        return self

    def execute(self):
        if self.boom:
            raise OSError("network")
        return {"items": [{"id": i} for i in self.ids if i in self.present]}


def make(tmp_path, monkeypatch, name, vid, hours_old=48, **k):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    when = (NOW - dt.timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    records.save(d, {"title": name.upper(), "video_id": vid, "uploaded_at": when, **k})
    return d


def meta(d):
    return json.loads((d / "meta.json").read_text())


def test_a_video_youtube_cannot_find_twice_is_cleared_held_and_the_owner_told(tmp_path, monkeypatch):
    d = make(tmp_path, monkeypatch, "film", "GONE1")
    ok = make(tmp_path, monkeypatch, "other", "OK1")
    yt = YT(present={"OK1"})
    reconcile.run(NOW, yt)
    assert meta(d)["video_id"] == "GONE1" and meta(d)["missing_seen"] == 1 and not meta(d).get("hold")  # one miss is a count, not a verdict
    reconcile.run(NOW + dt.timedelta(hours=1), yt)
    m = meta(d)
    assert m["video_id"] is None and m["hold"] is True and m["gone_from_youtube"]["video_id"] == "GONE1" and "not uploaded again" in m["hold_reason"]
    assert meta(ok)["video_id"] == "OK1"
    assert any("not on YouTube" in e["title"] and "FILM" in e["title"] for e in agentlog.recent(5))


def test_a_video_that_reappears_resets_its_count(tmp_path, monkeypatch):
    d = make(tmp_path, monkeypatch, "film", "V1")
    make(tmp_path, monkeypatch, "pad", "P1")
    reconcile.run(NOW, YT(present={"P1"}))
    assert meta(d)["missing_seen"] == 1
    reconcile.run(NOW, YT(present={"P1", "V1"}))
    assert not meta(d).get("missing_seen") and meta(d)["video_id"] == "V1"


def test_a_fresh_upload_a_network_error_and_an_empty_answer_for_many_ids_change_nothing(tmp_path, monkeypatch):
    fresh = make(tmp_path, monkeypatch, "fresh", "NEW1", hours_old=1)
    make(tmp_path, monkeypatch, "a", "A1")
    make(tmp_path, monkeypatch, "b", "B1")
    make(tmp_path, monkeypatch, "c", "C1")
    for _ in range(3):
        reconcile.run(NOW, YT(present=set()))   # YouTube answers nothing for four ids: an outage, not four deletions
    assert meta(fresh)["video_id"] == "NEW1" and all(meta(tmp_path / n)["video_id"] for n in "abc") and not meta(tmp_path / "a").get("missing_seen")
    assert reconcile.run(NOW, YT(boom=True)).get("error")
    assert meta(tmp_path / "a")["video_id"] == "A1"


def test_the_hourly_health_check_runs_the_reconciliation_and_survives_its_failure(monkeypatch):
    import inspect

    import safety

    assert "reconcile" in inspect.getsource(safety.check)
    monkeypatch.setattr(reconcile, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert safety.check(NOW, YT(present=set())) == {"checked": 0, "problems": [], "paused": False}


def test_a_video_uploaded_an_hour_ago_that_youtube_does_not_list_yet_is_left_alone_even_on_many_checks(tmp_path, monkeypatch):
    fresh = make(tmp_path, monkeypatch, "fresh", "NEW1", hours_old=1)
    make(tmp_path, monkeypatch, "old", "OLD1")
    for h in range(4):
        reconcile.run(NOW + dt.timedelta(minutes=h), YT(present={"OLD1"}))
    assert meta(fresh)["video_id"] == "NEW1" and not meta(fresh).get("missing_seen") and not meta(fresh).get("hold")


# ---- review of 30 Oct 2026 ----
def test_a_video_that_was_meant_to_be_public_and_is_gone_pauses_autopilot_like_the_health_check_always_did(tmp_path, monkeypatch):
    import autopilot
    import safety

    d = make(tmp_path, monkeypatch, "film", "GONE1", publish_at=(NOW - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    make(tmp_path, monkeypatch, "other", "OK1")
    saved = {}
    monkeypatch.setattr(autopilot, "load_config", lambda: {"enabled": True})
    monkeypatch.setattr(autopilot, "save_config", lambda c: saved.update(c))
    yt = YT(present={"OK1"})
    reconcile.run(NOW, yt)
    assert meta(d)["video_id"] == "GONE1"  # one miss is not enough
    safety.check(NOW + dt.timedelta(hours=1), yt)
    assert meta(d)["video_id"] is None and saved.get("enabled") is False
    assert any("not on YouTube any more" in str(e) for e in agentlog.recent(8))


def test_a_private_or_future_video_that_is_gone_does_not_pause_autopilot(tmp_path, monkeypatch):
    import autopilot
    import safety

    make(tmp_path, monkeypatch, "film", "GONE1", publish_at=(NOW + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    make(tmp_path, monkeypatch, "other", "OK1")
    saved = {}
    monkeypatch.setattr(autopilot, "load_config", lambda: {"enabled": True})
    monkeypatch.setattr(autopilot, "save_config", lambda c: saved.update(c))
    for h in (0, 1):
        safety.check(NOW + dt.timedelta(hours=h), YT(present={"OK1"}))
    assert not saved


def test_the_outage_guard_works_per_batch_and_upload_started_is_kept_so_a_later_upload_still_looks_for_an_earlier_copy(tmp_path, monkeypatch):
    d = make(tmp_path, monkeypatch, "film", "GONE1", upload_started="2026-10-29T10:00:00Z")
    make(tmp_path, monkeypatch, "other", "OK1")
    yt = YT(present={"OK1"})
    reconcile.run(NOW, yt)
    reconcile.run(NOW, yt)
    assert meta(d)["video_id"] is None and meta(d)["upload_started"] == "2026-10-29T10:00:00Z"
