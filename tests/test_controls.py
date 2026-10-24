import datetime as dt
import json

import pytest

import agentlog
import config
import controls

NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)


def make(slug, **meta):
    d = config.OUT / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"title": slug.upper(), "format": "doc", **meta}))
    return d


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    config.OUT.mkdir()
    return tmp_path


class YT:
    def __init__(self):
        self.updates = []
        self.status = {"privacyStatus": "private", "publishAt": "2026-10-26T14:00:00Z", "selfDeclaredMadeForKids": False}

    def videos(self):
        return self

    def list(self, part, id):
        return type("R", (), {"execute": lambda s: {"items": [{"status": dict(self.status)}]}})()

    def update(self, part, body):
        self.updates.append(body)
        return type("R", (), {"execute": lambda s: {}})()


def test_slugs_are_checked_before_any_path_is_built():
    for bad in ("../etc", "A", "", "a/b", "a b", "x" * 200, None, 5):
        with pytest.raises(ValueError):
            controls.video(bad)
    with pytest.raises(ValueError):
        controls.video("does-not-exist")


def test_videos_lists_state_without_the_script_or_secrets():
    make("v1", approved=True, video_id="abc", publish_at="2026-10-26T14:00:00Z", lines=[{"text": "secret script line"}],
         review={"verdict": "pass", "checks": []}, upload_check={"ok": True})
    out = controls.videos(NOW)
    assert out[0]["slug"] == "v1" and out[0]["verdict"] == "pass" and out[0]["on_youtube"] is True
    assert "secret script line" not in json.dumps(out)


def test_video_detail_names_failing_checks_and_trims_long_text():
    make("v2", description="d" * 900, review={"verdict": "fail", "checks": [{"name": "title_matches", "ok": False, "severity": "block", "detail": "x" * 600}]})
    d = controls.video("v2")
    assert d["failing"][0]["name"] == "title_matches" and len(d["failing"][0]["detail"]) <= 300 and len(d["description_start"]) <= 300


def test_events_returns_the_newest_first_and_caps_the_count():
    for i in range(30):
        agentlog.event("info", f"e{i}", now=NOW + dt.timedelta(minutes=i))
    out = controls.events(5)
    assert [e["title"] for e in out] == ["e29", "e28", "e27", "e26", "e25"]
    assert len(controls.events(10_000)) == 30 and len(controls.events(-3)) == 1


def test_holding_a_scheduled_upload_makes_it_private_on_youtube_and_remembers_why():
    make("v3", video_id="abc", publish_at="2026-10-26T14:00:00Z", approved=True)
    yt = YT()
    r = controls.hold("v3", yt=yt, now=NOW)
    meta = json.loads((config.OUT / "v3" / "meta.json").read_text())
    assert r["held"] and "private" in r["youtube"] and meta["hold"] is True and meta["taken_back"]
    assert yt.updates and "publishAt" not in yt.updates[0]["status"]


def test_holding_a_draft_only_sets_the_flag():
    make("d1")
    yt = YT()
    r = controls.hold("d1", yt=yt, now=NOW)
    assert r["held"] and not yt.updates and "not on YouTube" in r["youtube"]


def test_releasing_a_draft_gets_a_fresh_slot_and_releasing_an_upload_says_what_to_do():
    make("d2", hold=True, publish_at="2026-10-26T14:00:00Z", autopilot_fails=2)
    make("u2", hold=True, video_id="abc", publish_at="2026-10-26T14:00:00Z", taken_back="2026-10-25T10:00:00Z")
    r1, r2 = controls.release("d2"), controls.release("u2")
    m1 = json.loads((config.OUT / "d2" / "meta.json").read_text())
    m2 = json.loads((config.OUT / "u2" / "meta.json").read_text())
    assert m1["hold"] is False and "publish_at" not in m1 and m1["autopilot_fails"] == 0
    assert m2["hold"] is False and "YouTube Studio" in r2["note"]  # a pulled-back upload is published by the owner, never by this tool


def test_the_dispatcher_runs_only_named_calls_and_rejects_everything_else():
    assert controls.dispatch("events", {"n": 1}) == []
    for bad in ("os.system", "__import__", "hold; rm", "", None):
        with pytest.raises(ValueError):
            controls.dispatch(bad, {})
    with pytest.raises(ValueError):
        controls.dispatch("events", {"n": 1, "evil": 1})  # unknown argument names are refused


def test_every_call_returns_plain_json():
    make("v4", approved=True)
    for call, args in (("videos", {}), ("events", {"n": 3}), ("video", {"slug": "v4"})):
        json.dumps(controls.dispatch(call, args))
