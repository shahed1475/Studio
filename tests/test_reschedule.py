import json
from datetime import datetime, timedelta, timezone

import actionlog
import autopilot
import config
import reschedule

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
CFG = {**autopilot.DEFAULTS, "enabled": True, "review_window_hours": 2}
LOST = {"video_id": "vid1", "approved": True, "approved_by": "reviewer-agent", "format": "short", "title": "La Llorona",
        "publish_at": "2026-10-29T16:30:00Z", "health": {"ok": False, "problems": ["la-llorona: it is still private after its publish time. Most often someone changed it"]}}


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeYT:
    """Keeps one video's status the way YouTube would: update replaces what is sent, a read returns what is stored."""

    def __init__(self, status):
        self.status, self.updates = dict(status), []

    def videos(self):
        return self

    def list(self, part, id):
        self._op = ("list", part)
        return self

    def update(self, part, body):
        self._op = ("update", part)
        self._body = body
        return self

    def execute(self):
        if self._op[0] == "update":
            self.updates.append(self._body)
            self.status = dict(self._body["status"])
            return {}
        return {"items": [{"id": "vid1", "status": dict(self.status)}]}


def folder(tmp_path, monkeypatch, **meta):
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(actionlog, "ACTIONS", tmp_path / "actions.json")
    d = tmp_path / "la-llorona"
    d.mkdir(exist_ok=True)
    (d / "meta.json").write_text(json.dumps({**LOST, **meta}))
    return d


def test_a_video_with_a_cleared_schedule_is_recognised():
    assert reschedule.lost(LOST)


def test_only_an_approved_uploaded_video_that_health_found_private_is_lost():
    assert not reschedule.lost({**LOST, "video_id": None})
    assert not reschedule.lost({**LOST, "approved": False})
    assert not reschedule.lost({**LOST, "hold": True})
    assert not reschedule.lost({**LOST, "taken_back": True})  # the recheck agent took it back on purpose
    assert not reschedule.lost({**LOST, "health": {"ok": True, "problems": []}})
    assert not reschedule.lost({**LOST, "health": {"ok": False, "problems": ["it is blocked in 2 countries"]}})


def test_a_video_is_rescheduled_once_not_in_a_loop():
    assert not reschedule.lost({**LOST, "rescheduled": {"at": "2026-10-30T12:00:00Z"}})


def test_it_sets_a_future_time_keeps_the_video_private_and_reads_it_back(tmp_path, monkeypatch):
    d = folder(tmp_path, monkeypatch)
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "processed", "embeddable": True, "license": "youtube"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out is None
    sent = yt.updates[0]["status"]
    when = datetime.strptime(sent["publishAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert when >= NOW + timedelta(hours=2)  # never in the past: YouTube publishes a past time at once
    assert sent["privacyStatus"] == "private"
    assert sent["selfDeclaredMadeForKids"] is False and sent["containsSyntheticMedia"] is True  # an update replaces what is not sent
    assert sent["embeddable"] is True and sent["license"] == "youtube"
    meta = json.loads((d / "meta.json").read_text())
    assert meta["publish_at"] == sent["publishAt"]
    assert meta["rescheduled"]["to"] == sent["publishAt"] and meta["rescheduled"]["verified"] is True
    logged = actionlog.actions(5)[0]
    assert logged["kind"] == "status" and logged["video_id"] == "vid1" and logged["source"] == "autopilot"
    assert logged["before"]["publishAt"] is None and logged["after"]["publishAt"] == sent["publishAt"]


def test_a_video_that_is_already_public_is_never_touched(tmp_path, monkeypatch):
    d = folder(tmp_path, monkeypatch)
    yt = FakeYT({"privacyStatus": "public", "uploadStatus": "processed"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out == {"skipped": "already public"} and yt.updates == []
    assert "rescheduled" not in json.loads((d / "meta.json").read_text())


def test_a_video_that_still_has_a_future_schedule_is_left_alone(tmp_path, monkeypatch):
    d = folder(tmp_path, monkeypatch)
    later = iso(NOW + timedelta(days=1))
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "processed", "publishAt": later})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out == {"skipped": "still scheduled"} and yt.updates == []
    assert json.loads((d / "meta.json").read_text())["publish_at"] == later  # the record learns the real time


def test_a_video_that_did_not_finish_processing_waits(tmp_path, monkeypatch):
    folder(tmp_path, monkeypatch)
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "uploaded"})
    assert reschedule.apply("la-llorona", CFG, NOW, yt=yt) == {"skipped": "not processed yet"} and yt.updates == []


def test_a_mismatch_on_read_back_is_not_recorded_as_done(tmp_path, monkeypatch):
    d = folder(tmp_path, monkeypatch)

    class Ignores(FakeYT):
        def execute(self):
            if self._op[0] == "update":
                self.updates.append(self._body)
                return {}
            return super().execute()

    yt = Ignores({"privacyStatus": "private", "uploadStatus": "processed"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out and "read back" in out["skipped"]
    assert "rescheduled" not in json.loads((d / "meta.json").read_text())


def test_the_new_slot_is_one_the_planner_would_give_and_not_taken(tmp_path, monkeypatch):
    folder(tmp_path, monkeypatch)
    other = tmp_path / "other"
    other.mkdir()
    first = autopilot.free_slot("la-llorona", "short", CFG, NOW)
    (other / "meta.json").write_text(json.dumps({"format": "short", "publish_at": iso(first)}))
    second = autopilot.free_slot("la-llorona", "short", CFG, NOW)
    assert second > first and abs((second - first).total_seconds()) >= 6 * 3600


def test_a_duplicate_story_is_held_not_rescheduled(tmp_path, monkeypatch):
    d = folder(tmp_path, monkeypatch)
    monkeypatch.setattr(autopilot, "_twin", lambda slug: {"slug": "older", "title": "Older"})
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "processed"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out == {"skipped": "duplicate"} and yt.updates == []
    assert json.loads((d / "meta.json").read_text())["hold"] is True


def test_autopilot_plans_the_repair_for_a_lost_video():
    v = {"slug": "la-llorona", "video_id": "vid1", "hold": False, "fails": 0, "lost": True, "approved": True, "verdict": "pass", "publish_at": None}
    st = {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "news_pending": 0, "videos": [v]}
    acts = [(a["do"], a.get("slug")) for a in autopilot.plan_actions(st, CFG, NOW)]
    assert ("reschedule", "la-llorona") in acts
    assert "reschedule" in autopilot.EXECUTORS
    v["lost"] = False
    assert ("reschedule", "la-llorona") not in [(a["do"], a.get("slug")) for a in autopilot.plan_actions(st, CFG, NOW)]
