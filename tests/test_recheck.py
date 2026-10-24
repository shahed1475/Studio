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
    (d / "meta.json").write_text(json.dumps({"title": "Old title", "description": "intro", "video_id": "abc", "publish_at": "2026-10-25T14:00:00Z", "tags": ["x"],
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
