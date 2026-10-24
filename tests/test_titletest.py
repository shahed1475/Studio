import datetime as dt
import json

import pytest

import config
import titletest

NOW = dt.datetime(2026, 10, 25, 12, tzinfo=dt.timezone.utc)


class FakeYT:
    def __init__(self, views, privacy="public"):
        self.views, self.privacy, self.updates = views, privacy, []

    def videos(self):
        return self

    def list(self, part, id):
        ids = id.split(",")
        items = [{"id": i, "snippet": {"title": "t", "description": "d", "categoryId": "27", "tags": ["x"]}, "statistics": {"viewCount": str(self.views[i])},
                  "status": {"privacyStatus": self.privacy}} for i in ids]
        return type("R", (), {"execute": lambda s: {"items": items}})()

    def update(self, part, body):
        self.updates.append(body)
        return type("R", (), {"execute": lambda s: {}})()


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(titletest, "CONFIG", tmp_path / "tt.json")
    monkeypatch.setattr(titletest.agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(titletest, "can_write", lambda token=None: True)
    return tmp_path


def make(slug, vid, days_old=6, fmt="short", title=None, **extra):
    d = config.OUT / slug
    d.mkdir(parents=True)
    pub = (NOW - dt.timedelta(days=days_old)).strftime(titletest.TS)
    (d / "meta.json").write_text(json.dumps({"title": title or f"Title {slug}", "video_id": vid, "publish_at": pub, "format": fmt, **extra}))
    return d / "meta.json"


def peers(n=3):
    return {f"p{i}": 600 for i in range(n)}


def build(weak_views=60):
    for i in range(3):
        make(f"peer{i}", f"p{i}")
    return make("weak", "w"), {**peers(), "w": weak_views}


def test_judge_needs_three_peers_and_marks_only_clearly_weak():
    assert titletest.judge(1, [100, 100]) == "learning"
    assert titletest.judge(30, [100, 100, 100]) == "weak"
    assert titletest.judge(60, [100, 100, 100]) == "ok"


def test_weak_video_gets_a_suggestion_but_nothing_changes_in_suggest_mode(out):
    path, views = build()
    yt = FakeYT(views)
    r = titletest.run(NOW, yt, pick=lambda m, o: "A better title for it")
    meta = json.loads(path.read_text())
    assert r["weak"] == ["weak"] and not yt.updates
    assert meta["title"] == "Title weak" and meta["title_test"]["proposed"] == "A better title for it" and not meta["title_test"]["applied"]


def test_a_weak_video_that_people_leave_early_is_not_retitled(out):
    path, views = build()
    yt = FakeYT(views)
    r = titletest.run(NOW, yt, pick=lambda m, o: "A better title for it", quality={"w": 12.0})
    meta = json.loads(path.read_text())
    assert r["content"] == ["weak"] and not r["weak"] and not yt.updates and meta["title"] == "Title weak"
    assert meta["title_test"]["verdict"] == "content"


def test_a_weak_video_people_watch_through_is_retitled_as_before(out):
    path, views = build()
    r = titletest.run(NOW, FakeYT(views), pick=lambda m, o: "A better title for it", quality={"w": 70.0})
    assert r["weak"] == ["weak"] and not r["content"]


def test_apply_mode_changes_only_the_title_and_keeps_the_rest(out):
    (out / "tt.json").write_text('{"mode": "apply"}')
    path, views = build()
    yt = FakeYT(views)
    titletest.run(NOW, yt, pick=lambda m, o: "A better title for it")
    assert yt.updates[0]["snippet"] == {"title": "A better title for it", "description": "d", "categoryId": "27", "tags": ["x"]}
    assert json.loads(path.read_text())["title"] == "A better title for it"


def test_apply_mode_without_permission_only_suggests(out, monkeypatch):
    (out / "tt.json").write_text('{"mode": "apply"}')
    monkeypatch.setattr(titletest, "can_write", lambda token=None: False)
    path, views = build()
    yt = FakeYT(views)
    titletest.run(NOW, yt, pick=lambda m, o: "Another one here")
    assert not yt.updates and json.loads(path.read_text())["title_test"]["applied"] is False


def test_young_private_and_peerless_videos_are_left_alone(out):
    make("new", "n", days_old=1)
    yt = FakeYT({"n": 0})
    assert titletest.run(NOW, yt)["checked"] == 0
    path = make("solo", "s")
    assert titletest.run(NOW, FakeYT({"s": 0, "n": 0}), pick=lambda m, o: "x" * 20)["learning"] == 1
    assert "title_test" not in json.loads(path.read_text())
    assert titletest.run(NOW, FakeYT({"s": 0, "n": 0}, privacy="private"))["checked"] == 0


def test_a_video_is_tested_only_once_and_one_change_a_day(out):
    (out / "tt.json").write_text('{"mode": "apply"}')
    for i in range(3):
        make(f"peer{i}", f"p{i}")
    make("weak1", "w1")
    make("weak2", "w2")
    yt = FakeYT({**peers(), "w1": 10, "w2": 10})
    r = titletest.run(NOW, yt, pick=lambda m, o: "New title " + m["video_id"])
    assert len(r["changed"]) == 1 and len(r["weak"]) == 1
    assert titletest.run(NOW, FakeYT({**peers(), "w1": 10, "w2": 10}), pick=lambda m, o: "again here")["changed"] == []


def test_a_worse_new_title_is_put_back_and_a_better_one_is_kept(out):
    (out / "tt.json").write_text('{"mode": "apply"}')
    for i in range(3):
        make(f"peer{i}", f"p{i}")
    changed = (NOW - dt.timedelta(days=6)).strftime(titletest.TS)
    tt = lambda orig: {"original": orig, "proposed": "New", "changed_at": changed, "views_at_change": 60, "rate_before": 10.0, "applied": True}
    bad = make("bad", "b", title="New", title_test=tt("Old bad"))
    good = make("good", "g", title="New", title_test=tt("Old good"))
    yt = FakeYT({**peers(), "b": 66, "g": 360})
    r = titletest.run(NOW, yt)
    assert r["reverted"] == ["bad"] and r["kept"] == ["good"]
    assert yt.updates[0]["snippet"]["title"] == "Old bad"
    assert json.loads(bad.read_text())["title"] == "Old bad" and json.loads(good.read_text())["title_test"]["verdict"] == "kept"


def test_write_permission_is_read_from_the_token(tmp_path):
    t = tmp_path / "token.json"
    t.write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/youtube.upload"]}))
    assert not titletest.can_write(t)
    t.write_text(json.dumps({"scopes": ["https://www.googleapis.com/auth/youtube"]}))
    assert titletest.can_write(t)
    assert not titletest.can_write(tmp_path / "none.json")
