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

    def __init__(self, status, content=None):
        self.status, self.updates, self.content = dict(status), [], content

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
        item = {"id": "vid1", "status": dict(self.status)}
        if self.content is not None and "contentDetails" in self._op[1]:
            item["contentDetails"] = self.content
        return {"items": [item]}


def folder(tmp_path, monkeypatch, **meta):
    monkeypatch.setattr(reschedule.time, "sleep", lambda s: None)  # the read-back retries wait a few seconds in real life
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
    assert logged["kind"] == "status" and logged["video_id"] == "vid1" and logged["source"] == "owner command"
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


def test_a_read_back_that_lags_behind_the_write_is_retried_before_it_is_judged(tmp_path, monkeypatch):
    """30 Oct 2026, real YouTube: the update took, but the read right after it still showed no schedule. Judging on the first read left the change unrecorded."""
    d = folder(tmp_path, monkeypatch)

    class Lags(FakeYT):
        stale_reads = 2

        def execute(self):
            if self._op[0] == "list" and self.updates and self.stale_reads:
                self.stale_reads -= 1
                return {"items": [{"id": "vid1", "status": {"privacyStatus": "private", "uploadStatus": "processed"}}]}  # the old status
            return super().execute()

    yt = Lags({"privacyStatus": "private", "uploadStatus": "processed"})
    assert reschedule.apply("la-llorona", CFG, NOW, yt=yt) is None
    meta = json.loads((d / "meta.json").read_text())
    assert meta["rescheduled"]["verified"] is True and meta["publish_at"] == yt.updates[0]["status"]["publishAt"]
    assert len(actionlog.actions(5)) == 1


def test_a_write_that_cannot_be_confirmed_is_still_logged_as_unverified_but_not_recorded_as_done(tmp_path, monkeypatch):
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
    logged = actionlog.actions(5)
    assert len(logged) == 1 and "unverified" in logged[0]["why"] and logged[0]["after"]["publishAt"] == yt.updates[0]["status"]["publishAt"]  # a change may have happened: it is on record


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


def test_autopilot_never_reschedules_by_itself():
    """A cleared schedule is most often a person's edit in YouTube Studio (safety.py says so): putting the video back on course to go public is the owner's decision, so Autopilot only
    reports it (the safety pause) and the repair is a command the owner runs."""
    v = {"slug": "la-llorona", "video_id": "vid1", "hold": False, "fails": 0, "lost": True, "approved": True, "verdict": "pass", "publish_at": None}
    st = {"queue_len": 5, "connected": True, "busy": False, "uploads_today": 0, "news_pending": 0, "videos": [v]}
    assert "reschedule" not in [a["do"] for a in autopilot.plan_actions(st, CFG, NOW)]
    assert "reschedule" not in autopilot.EXECUTORS


def test_it_refuses_in_a_user_studio(tmp_path, monkeypatch):
    folder(tmp_path, monkeypatch)
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "processed"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out and "user studio" in out["skipped"] and yt.updates == []


def test_it_refuses_while_an_invented_facts_warning_is_open_unless_the_owner_approved_the_video(tmp_path, monkeypatch):
    import fixer

    folder(tmp_path, monkeypatch)
    monkeypatch.setattr(fixer, "watch_problems", lambda checks: ["a date the source does not give"])
    yt = FakeYT({"privacyStatus": "private", "uploadStatus": "processed"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=yt)
    assert out and "facts" in out["skipped"] and yt.updates == []
    folder(tmp_path, monkeypatch, approved_by="you")  # the owner read the video and approved it as it is
    assert reschedule.apply("la-llorona", CFG, NOW, yt=yt) is None and len(yt.updates) == 1


def test_it_refuses_a_video_youtube_rejected_or_blocked_in_countries(tmp_path, monkeypatch):
    folder(tmp_path, monkeypatch)
    rejected = FakeYT({"privacyStatus": "private", "uploadStatus": "rejected", "rejectionReason": "copyright"})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=rejected)
    assert out and "rejected" in out["skipped"] and rejected.updates == []
    blocked = FakeYT({"privacyStatus": "private", "uploadStatus": "processed"}, content={"regionRestriction": {"blocked": ["DE", "FR"]}})
    out = reschedule.apply("la-llorona", CFG, NOW, yt=blocked)
    assert out and "blocked" in out["skipped"] and blocked.updates == []


def test_without_write_permission_no_connection_is_made(tmp_path, monkeypatch):
    import titletest
    import upload

    folder(tmp_path, monkeypatch)
    monkeypatch.setattr(titletest, "can_write", lambda token=None: False)
    monkeypatch.setattr(upload, "_service", lambda: (_ for _ in ()).throw(AssertionError("must not connect")))
    out = reschedule.apply("la-llorona", CFG, NOW)
    assert out and "permission" in out["skipped"]


def test_the_owner_runs_it_with_a_command_that_holds_the_autopilot_lock():
    import inspect

    import run

    src = inspect.getsource(run.main)
    assert 'a[0] == "reschedule"' in src and "exclusive()" in src.split('a[0] == "reschedule"')[1][:600]
