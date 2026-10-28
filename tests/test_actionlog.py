import json

import pytest

import actionlog
import agentbus
import recheck
import titletest
from test_recheck import FakeYT as RecheckYT, NOW as RNOW, meta_of, result, vid  # noqa: F401  (the recheck fixtures)


class Req:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


class Live:
    """A YouTube that remembers what was written, so a rollback can be seen."""
    def __init__(self, **sn):
        self.sn = {"title": "Old title", "description": "old description", "categoryId": "27", "tags": ["a"], **sn}
        self.updates = []

    def videos(self):
        return self

    def list(self, part, id):
        return Req({"items": [{"snippet": dict(self.sn), "status": {"privacyStatus": "private", "publishAt": "2026-11-01T10:00:00Z"}}] if id != "GONE" else []})

    def update(self, part, body):
        self.updates.append((part, body))
        if part == "snippet":
            self.sn.update(body["snippet"])
        return Req({})


@pytest.fixture(autouse=True)
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(actionlog, "ACTIONS", tmp_path / "actions.json")
    monkeypatch.setattr(actionlog, "EDITS", tmp_path / "edits.json")
    monkeypatch.setattr(agentbus, "FILE", tmp_path / "tasks.json")


def meta(**kw):
    return {"video_id": "V1", "title": "New title", "description": "new description", "tags": ["b"], "format": "doc", "credits": [], **kw}


def test_every_push_is_logged_with_what_it_replaced_and_what_it_wrote():
    yt = Live()
    recheck.push_metadata(yt, meta(), "recheck", "title did not match")
    a = actionlog.actions()[0]
    assert a["video_id"] == "V1" and a["source"] == "recheck" and a["before"]["title"] == "Old title" and a["after"]["title"] == "New title" and a["why"] == "title did not match"
    assert yt.updates[0][1]["snippet"]["categoryId"] == "27"  # the rest of the snippet is sent back unchanged


def test_the_title_test_and_taking_a_video_back_are_logged_too():
    yt = Live()
    titletest.set_title(yt, {"id": "V1", "snippet": {"title": "Old title", "description": "d", "categoryId": "27", "tags": []}}, "A better title")
    recheck.take_back(yt, "V1")
    kinds = [(a["source"], a["kind"]) for a in actionlog.actions()]
    assert ("title test", "metadata") in kinds and ("recheck", "status") in kinds
    status = next(a for a in actionlog.actions() if a["kind"] == "status")
    assert status["before"]["publishAt"] == "2026-11-01T10:00:00Z" and status["after"]["privacyStatus"] == "private"


def test_a_rollback_puts_the_before_back_logs_itself_and_works_once():
    yt = Live()
    recheck.push_metadata(yt, meta(), "recheck", "x")
    aid = actionlog.actions()[0]["id"]
    assert yt.sn["title"] == "New title"
    assert "rolled back" in actionlog.rollback(aid, yt) and yt.sn["title"] == "Old title" and yt.sn["description"] == "old description" and yt.sn["tags"] == ["a"]
    assert any(a["source"] == "owner" and a["why"] == f"rollback of {aid}" for a in actionlog.actions())
    assert "already rolled back" in actionlog.rollback(aid, yt) and actionlog.rollback("a99999", yt) == "no action a99999"


def test_a_status_change_is_undone_in_studio_not_by_rollback_and_a_missing_video_is_reported():
    yt = Live()
    recheck.take_back(yt, "V1")
    assert "YouTube Studio" in actionlog.rollback(actionlog.actions()[0]["id"], yt) and len(yt.updates) == 1
    aid = actionlog.record("GONE", {"title": "a"}, {"title": "b"}, "x")
    assert "not rolled back" in actionlog.rollback(aid, yt)


def test_a_proposal_for_a_public_video_writes_nothing_and_gives_the_owner_the_commands():
    yt = Live()
    pid = actionlog.propose("V1", "slug-1", {"title": "Old title"}, {"title": "New title"}, "recheck", "the title overpromises")
    task = agentbus.tasks()[0]
    assert pid == "p00001" and not yt.updates and task["kind"] == "approve_edit" and task["state"] == "owner" and task["commands"] == [f"python run.py edits approve {pid}", f"python run.py edits reject {pid}"]
    assert actionlog.propose("V1", "slug-1", {"title": "Old title"}, {"title": "New title"}, "recheck", "again") == pid and len(agentbus.tasks()) == 1
    assert actionlog.propose("V1", "slug-1", {"title": "Same"}, {"title": "Same"}, "recheck", "nothing changes") is None


def test_only_the_owners_approval_writes_it_and_only_if_the_video_still_reads_as_proposed():
    yt = Live()
    pid = actionlog.propose("V1", "s", {"title": "Old title"}, {"title": "New title"}, "recheck", "w")
    yt.sn["title"] = "Someone edited this in Studio"
    assert "changed on YouTube after it was proposed" in actionlog.resolve(pid, True, yt) and not yt.updates and actionlog.pending()
    yt.sn["title"] = "Old title"
    assert "approved and applied" in actionlog.resolve(pid, True, yt) and yt.sn["title"] == "New title" and not actionlog.pending()
    a = actionlog.actions()[0]
    assert a["before"]["title"] == "Old title" and "approved by the owner" in a["why"]
    assert "no pending proposal" in actionlog.resolve(pid, True, yt)


def test_a_rejected_proposal_is_closed_and_nothing_is_written():
    yt = Live()
    pid = actionlog.propose("V1", "s", {"title": "Old title"}, {"title": "New title"}, "recheck", "w")
    assert actionlog.resolve(pid, False) == f"{pid} rejected" and not yt.updates and not actionlog.pending() and actionlog.actions() == []


def test_a_full_disk_never_hides_a_change_that_already_happened(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert actionlog.record("V1", {}, {}, "x", file=blocker / "sub" / "actions.json") == ""


def test_recheck_proposes_instead_of_changing_a_public_video_and_still_repairs_one_that_is_not_public_yet(vid, monkeypatch):
    import fixer
    import reviewer

    monkeypatch.setattr(fixer, "realign_description", lambda *a, **k: False)
    monkeypatch.setattr(fixer, "pick_title", lambda *a, **k: "A New Honest Title")
    monkeypatch.setattr(reviewer, "title_ok", lambda m, t: (True, ""))
    m = meta_of(vid)
    m["publish_at"] = "2026-10-25T04:00:00Z"  # two hours before the check: the video is public
    (vid / "meta.json").write_text(json.dumps(m))
    yt = RecheckYT()
    out = recheck.check_one(RNOW, vid, meta_of(vid), yt, lambda f: result("fail", "title_matches"), may_edit=True)
    assert yt.updates == [] and meta_of(vid)["title"] == "Old title" and "public video: metadata change proposed, owner decides" in out["actions"]
    p = actionlog.pending()[0]
    assert p["after"]["title"] == "A New Honest Title" and p["before"]["title"] == "old" and agentbus.tasks()[0]["kind"] == "approve_edit"
    assert actionlog.actions() == []  # a proposal is not a change
    m["publish_at"] = "2026-10-25T14:00:00Z"  # scheduled, not public: repaired and logged as before
    m.pop("recheck", None)
    (vid / "meta.json").write_text(json.dumps(m))
    yt2 = RecheckYT()
    recheck.check_one(RNOW, vid, meta_of(vid), yt2, lambda f: result("fail", "title_matches"), may_edit=True)
    assert len(yt2.updates) == 1 and actionlog.actions()[0]["source"] == "recheck"
