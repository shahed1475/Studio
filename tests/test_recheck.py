import datetime as dt
import json

import pytest

import config
import recheck

NOW = dt.datetime(2026, 10, 25, 6, tzinfo=dt.timezone.utc)


class FakeYT:
    def __init__(self):
        self.updates = []
        self.status = {"privacyStatus": "private", "publishAt": "2026-10-25T14:00:00Z", "selfDeclaredMadeForKids": False}

    def videos(self):
        return self

    def list(self, part, id):
        item = {"snippet": {"title": "old", "description": "d", "categoryId": "27", "tags": ["x"]}, "status": dict(self.status)}
        return type("R", (), {"execute": lambda s: {"items": [item]}})()

    def update(self, part, body):
        self.updates.append((part, body))
        return type("R", (), {"execute": lambda s: {}})()


def result(verdict, *bad):
    checks = [{"name": n, "ok": False, "severity": "block", "detail": f"{n} failed"} for n in bad] + [{"name": "ok1", "ok": True, "severity": "block", "detail": ""}]
    return {"verdict": verdict, "checks": checks}


@pytest.fixture
def vid(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(recheck.agentlog, "FILE", tmp_path / "events.jsonl")
    d = config.OUT / "v1"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"title": "Old title", "description": "intro", "video_id": "abc", "publish_at": "2026-10-25T14:00:00Z", "tags": ["history stories for sleep", "legends and folklore"],
                                             "topic": "t", "chapters": [], "format": "doc", "credits": []}))
    return d


def meta_of(d):
    return json.loads((d / "meta.json").read_text())


def test_a_passing_video_is_only_marked_checked(vid):
    yt = FakeYT()
    out = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("pass"), may_edit=True)
    assert out["actions"] == [] and not yt.updates and meta_of(vid)["recheck"]["verdict"] == "pass"


def test_a_misleading_title_is_repaired_and_pushed_to_youtube(vid, monkeypatch):
    import fixer
    monkeypatch.setattr(fixer, "realign_description", lambda meta, covers, chat=None: False)
    monkeypatch.setattr(fixer, "pick_title", lambda *a, **k: "A New Honest Title")
    import reviewer
    monkeypatch.setattr(reviewer, "title_ok", lambda meta, title: (True, ""))
    yt = FakeYT()
    out = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=True)
    assert "new title: A New Honest Title" in out["actions"]
    assert yt.updates and yt.updates[0][1]["snippet"]["title"] == "A New Honest Title"
    assert meta_of(vid)["title"] == "A New Honest Title"


def test_without_permission_a_metadata_problem_is_only_reported(vid):
    yt = FakeYT()
    out = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=False)
    assert not yt.updates and "no permission" in out["actions"][0]


def test_a_content_problem_warns_first_and_pulls_a_scheduled_video_on_the_second_failure(vid):
    yt = FakeYT()
    first = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "invented_facts"), may_edit=True)
    assert not yt.updates and "1 of 2" in first["actions"][0] and not meta_of(vid).get("hold")
    second = recheck.check_one(NOW + dt.timedelta(hours=7), vid, meta_of(vid), yt, lambda f: result("fail", "invented_facts"), may_edit=True)
    part, body = yt.updates[0]
    assert part == "status" and body["status"]["privacyStatus"] == "private" and "publishAt" not in body["status"]
    assert meta_of(vid)["hold"] is True and "taken back" in second["actions"][0]


def test_a_public_video_with_a_content_problem_is_never_touched(vid):
    yt = FakeYT()
    later = NOW + dt.timedelta(days=1)
    for _ in range(3):
        recheck.check_one(later, vid, meta_of(vid), yt, lambda f: result("fail", "invented_facts"), may_edit=True)
    assert not yt.updates and not meta_of(vid).get("hold")


def test_a_model_failure_is_not_a_finding(vid):
    yt = FakeYT()
    out = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: {"verdict": "unreviewed", "checks": []}, may_edit=True)
    assert not yt.updates and meta_of(vid)["recheck"]["verdict"] == "unreviewed" and "could not run" in out["actions"][0]


def test_candidates_skip_held_recent_and_far_off_videos(vid):
    assert [c[1].name for c in recheck.candidates(NOW)] == ["v1"]
    m = meta_of(vid)
    (vid / "meta.json").write_text(json.dumps({**m, "recheck": {"at": (NOW - dt.timedelta(hours=1)).strftime(recheck.TS)}}))
    assert recheck.candidates(NOW) == []
    (vid / "meta.json").write_text(json.dumps({**m, "hold": True}))
    assert recheck.candidates(NOW) == []
    (vid / "meta.json").write_text(json.dumps({**m, "publish_at": "2026-12-25T14:00:00Z"}))
    assert recheck.candidates(NOW) == []


def test_if_youtube_refuses_to_take_a_video_back_the_owner_is_told(vid, monkeypatch):
    yt = FakeYT()
    monkeypatch.setattr(recheck, "take_back", lambda yt, vid: (_ for _ in ()).throw(RuntimeError("403")))
    recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "invented_facts"), may_edit=True)
    out = recheck.check_one(NOW + dt.timedelta(hours=7), vid, meta_of(vid), yt, lambda f: result("fail", "invented_facts"), may_edit=True)
    assert "could not take it back" in out["actions"][0] and not meta_of(vid).get("hold")


def test_no_recheck_when_the_days_cap_is_nearly_used(vid, monkeypatch, tmp_path):
    import autopilot
    import llm
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "ap.lock")
    monkeypatch.setattr(llm, "spent_today", lambda now: 2.9)
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 3.0})
    assert recheck.run(NOW, yt=object(), review=lambda f: 1 / 0, may_edit=True) == {"skipped": "the day's spending cap is nearly used"}


def test_a_video_uploaded_straight_to_public_is_found_by_its_upload_time(vid):
    m = meta_of(vid)
    m.pop("publish_at")
    m["uploaded_at"] = (NOW - dt.timedelta(hours=26)).strftime(recheck.TS)
    (vid / "meta.json").write_text(json.dumps(m))
    assert [c[1].name for c in recheck.candidates(NOW)] == ["v1"]
    m["uploaded_at"] = (NOW - dt.timedelta(hours=60)).strftime(recheck.TS)
    (vid / "meta.json").write_text(json.dumps(m))
    assert recheck.candidates(NOW) == []


UPLOADED = {"video_id": "abc", "approved": True, "publish_at": "2026-10-25T14:00:00Z", "review": {"verdict": "pass"}, "prelaunch": {"ok": True}}


def test_editing_an_uploaded_video_keeps_its_approval_and_slot():
    import reviewer
    m = dict(UPLOADED)
    reviewer.invalidate(m)
    assert m["approved"] is True and m["publish_at"] == "2026-10-25T14:00:00Z" and "review" not in m


def test_editing_a_draft_still_drops_approval_and_slot():
    import reviewer
    m = {"approved": True, "publish_at": "2026-10-25T14:00:00Z", "review": {"verdict": "pass"}}
    reviewer.invalidate(m)
    assert m["approved"] is False and "publish_at" not in m


def test_the_planner_sees_an_uploaded_video_in_its_slot_even_without_a_saved_time(tmp_path, monkeypatch):
    import autopilot
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    d = config.OUT / "u1"
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"format": "doc", "video_id": "abc", "title": "t", "upload_check": {"ok": True, "publishAt": "2026-10-25T14:00:00Z"}}))
    v = autopilot.build_state(NOW, autopilot.load_config())["videos"][0]
    assert v["publish_at"] == "2026-10-25T14:00:00Z"


def test_heal_restores_the_schedule_and_approval_an_upload_record_proves(vid):
    m = meta_of(vid)
    m.pop("publish_at")
    m["approved"] = False
    m["upload_check"] = {"ok": True, "publishAt": "2026-10-25T14:00:00Z"}
    (vid / "meta.json").write_text(json.dumps(m))
    assert recheck.heal() == ["v1"]
    fixed = meta_of(vid)
    assert fixed["publish_at"] == "2026-10-25T14:00:00Z" and fixed["approved"] is True and fixed["healed"]
    assert recheck.heal() == []


def test_a_failing_review_does_not_unapprove_a_video_that_is_already_uploaded():
    import reviewer
    up, draft = dict(UPLOADED), {"approved": True}
    reviewer.apply_verdict(up, {"verdict": "fail", "checks": []})
    reviewer.apply_verdict(draft, {"verdict": "fail", "checks": []})
    assert up["approved"] is True and draft["approved"] is False


def test_a_remade_video_is_a_new_upload_and_remembers_the_old_one():
    import run
    out = run.reset_for_rerender({"title": "t", "video_id": "old", "uploaded_at": "x", "upload_check": {"ok": True}, "hold": True, "lines": []})
    assert "video_id" not in out and "upload_check" not in out and out["replaces_video"] == "old" and out["hold"] is True


def test_a_held_scheduled_video_is_made_private_on_youtube(vid):
    m = meta_of(vid)
    (vid / "meta.json").write_text(json.dumps({**m, "hold": True}))
    yt = FakeYT()  # shows the video scheduled
    assert recheck.enforce_holds(yt, NOW) == ["v1"]
    assert yt.updates and "publishAt" not in yt.updates[0][1]["status"]
    yt2 = FakeYT()
    yt2.status = {"privacyStatus": "private"}  # already private with no time: nothing to do
    assert recheck.enforce_holds(yt2, NOW) == [] and not yt2.updates


def human_result(*names):
    checks = [{"name": n, "ok": False, "severity": "human", "detail": f"{n} needs a person"} for n in names]
    return {"verdict": "needs_human", "checks": checks + [{"name": "ok1", "ok": True, "severity": "block", "detail": ""}]}


def test_a_check_that_needs_a_human_never_pulls_a_video(vid):
    yt = FakeYT()
    for k in range(3):
        recheck.check_one(NOW + dt.timedelta(hours=13 * k), vid, meta_of(vid), yt, lambda f: human_result("claims", "variety_script"), may_edit=True)
    assert not yt.updates and not meta_of(vid).get("hold") and meta_of(vid)["recheck"]["verdict"] == "pass"


def test_a_failed_model_review_is_not_a_finding_even_beside_other_failures(vid):
    yt = FakeYT()
    res = {"verdict": "needs_human", "checks": [{"name": "llm_review", "ok": False, "severity": "block", "detail": "model down"},
                                                 {"name": "invented_facts", "ok": False, "severity": "block", "detail": "x"}]}
    out = recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: res, may_edit=True)
    assert not yt.updates and "could not run" in out["actions"][0]


def test_a_video_the_owner_approved_is_left_alone(vid):
    m = meta_of(vid)
    (vid / "meta.json").write_text(json.dumps({**m, "approved_by": "you"}))
    assert recheck.candidates(NOW) == []


def test_a_title_is_repaired_once_and_only_to_one_the_reviewer_accepts(vid, monkeypatch):
    import fixer
    import reviewer
    monkeypatch.setattr(fixer, "realign_description", lambda *a, **k: False)
    monkeypatch.setattr(fixer, "pick_title", lambda *a, **k: "Second Title")
    monkeypatch.setattr(reviewer, "title_ok", lambda meta, title: (False, "promises too much"))
    yt = FakeYT()
    recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=True)
    assert not yt.updates and meta_of(vid)["title"] == "Old title"  # rejected title: nothing pushed
    monkeypatch.setattr(reviewer, "title_ok", lambda meta, title: (True, ""))
    recheck.check_one(NOW + dt.timedelta(hours=2), vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=True)  # still before the 14:00 publish time
    assert len(yt.updates) == 1 and meta_of(vid)["title"] == "Second Title"
    recheck.check_one(NOW + dt.timedelta(hours=3), vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=True)
    assert len(yt.updates) == 1  # a second repair is the owner's


def test_a_crash_stamps_the_video_so_the_next_run_moves_on(vid, tmp_path, monkeypatch):
    import autopilot
    import llm
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "ap.lock")
    monkeypatch.setattr(llm, "spent_today", lambda now: 0.0)
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 3.0})
    d2 = config.OUT / "v2"
    d2.mkdir()
    (d2 / "meta.json").write_text(json.dumps({**meta_of(vid), "video_id": "def", "publish_at": "2026-10-25T16:00:00Z"}))
    seen = []

    def review(f):
        seen.append(f.name)
        if f.name == "v1":
            raise RuntimeError("probe failed")
        return result("pass")
    out = recheck.run(NOW, yt=FakeYT(), review=review, may_edit=True)
    assert seen == ["v1", "v2"] and out["checked"] == 1 and "v1: RuntimeError" in out["errors"][0]
    assert meta_of(vid)["recheck"]["at"]  # v1 is stamped: it is not the first pick again


def test_odd_timestamps_do_not_stop_the_job(vid):
    m = meta_of(vid)
    d2 = config.OUT / "bad"
    d2.mkdir()
    (d2 / "meta.json").write_text(json.dumps({**m, "video_id": "zzz", "publish_at": "tomorrow afternoon"}))
    assert [c[1].name for c in recheck.candidates(NOW)] == ["v1"]


def test_a_video_deleted_in_studio_does_not_stop_the_hold_check(vid):
    m = meta_of(vid)
    (vid / "meta.json").write_text(json.dumps({**m, "hold": True}))

    class Gone(FakeYT):
        def list(self, part, id):
            return type("R", (), {"execute": lambda s: {"items": []}})()
    assert recheck.enforce_holds(Gone(), NOW) == []


def test_a_pulled_back_video_is_not_given_its_old_slot_back(vid):
    import autopilot
    m = meta_of(vid)
    m.pop("publish_at")
    m.update(approved=False, taken_back="2026-10-24T14:00:00Z", upload_check={"ok": True, "publishAt": "2026-10-25T14:00:00Z"})
    (vid / "meta.json").write_text(json.dumps(m))
    assert recheck.heal() == []
    assert autopilot.build_state(NOW, autopilot.load_config())["videos"][0]["publish_at"] is None


def test_the_recheck_writes_only_its_own_fields(vid):
    snapshot = meta_of(vid)
    m = meta_of(vid)
    (vid / "meta.json").write_text(json.dumps({**m, "title_test": {"verdict": "fine"}}))  # the title test wrote meanwhile
    recheck.check_one(NOW, vid, snapshot, FakeYT(), lambda f: result("pass"), may_edit=True)
    assert meta_of(vid)["title_test"] == {"verdict": "fine"} and meta_of(vid)["recheck"]["verdict"] == "pass"


class TitleYT:
    def __init__(self, titles):
        self.titles = titles

    def videos(self):
        return self

    def list(self, part, id):
        items = [{"id": i, "snippet": {"title": self.titles[i]}} for i in id.split(",") if i in self.titles]
        return type("R", (), {"execute": lambda s: {"items": items}})()


def test_a_title_changed_on_youtube_becomes_the_saved_title(vid):
    assert recheck.sync_titles(TitleYT({"abc": "Changed In Studio"}), NOW) == ["v1"]
    assert meta_of(vid)["title"] == "Changed In Studio"
    assert recheck.sync_titles(TitleYT({"abc": "Changed In Studio"}), NOW) == []  # nothing left to sync
    assert recheck.sync_titles(TitleYT({}), NOW) == []  # a video deleted in Studio is left alone


def test_the_saved_title_is_never_pushed_back_over_a_newer_youtube_title(vid, monkeypatch):
    import fixer
    import reviewer
    monkeypatch.setattr(fixer, "realign_description", lambda *a, **k: False)
    monkeypatch.setattr(fixer, "pick_title", lambda *a, **k: None)  # no new title found
    monkeypatch.setattr(reviewer, "title_ok", lambda meta, title: (True, ""))
    recheck.sync_titles(TitleYT({"abc": "The Title On YouTube Now"}), NOW)
    yt = FakeYT()
    recheck.check_one(NOW, vid, meta_of(vid), yt, lambda f: result("fail", "description"), may_edit=True)
    pushed = [b["snippet"]["title"] for _, b in yt.updates if "snippet" in b]
    assert all(t == "The Title On YouTube Now" for t in pushed)
