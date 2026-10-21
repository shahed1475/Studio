import datetime as dt
import json

import config
import editprofile
import pytest
import strategy


@pytest.fixture(autouse=True)
def tmp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy, "FILE", tmp_path / "strategies.json")
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "profile.json")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    (tmp_path / "topics.json").write_text(json.dumps(["Existing topic"]))


GOOD_EDIT = {"kind": "edit", "text": "Make narration a little louder", "why": "Rivals are louder", "evidence": ["LEMMiNO -16.6 LUFS"], "profile": {"target_lufs": -15}}
GOOD_TOPIC = {"kind": "topic", "text": "The vanishing village of Hoia Baciu", "why": "Mystery titles do well", "evidence": []}


def test_validate_rejects_unknown_kind_and_short_text():
    assert strategy.validate({"kind": "hack", "text": "long enough text"}) is None
    assert strategy.validate({"kind": "topic", "text": "short"}) is None
    assert strategy.validate({"kind": "topic", "text": "x" * 301}) is None
    assert strategy.validate("not a dict") is None


def test_validate_edit_needs_valid_profile():
    assert strategy.validate({**GOOD_EDIT, "profile": {"target_lufs": -3}}) is None
    assert strategy.validate({**GOOD_EDIT, "profile": {}}) is None
    ok = strategy.validate(GOOD_EDIT)
    assert ok["profile"] == {"target_lufs": -15.0} and ok["auto_ok"] is True and ok["status"] == "proposed"


def test_validate_advice_kinds_never_auto():
    s = strategy.validate({"kind": "schedule", "text": "Publish on Fridays at six", "why": "w", "evidence": ["e"]})
    assert s["auto_ok"] is False


def test_add_dedupes_by_id():
    first = strategy.add([GOOD_TOPIC, GOOD_TOPIC, {"kind": "bad"}])
    assert len(first) == 1
    assert strategy.add([GOOD_TOPIC]) == []
    assert len(strategy.load()) == 1


def test_apply_edit_updates_profile():
    sid = strategy.add([GOOD_EDIT])[0]["id"]
    done = strategy.apply(sid)
    assert done["status"] == "applied" and done["applied_at"]
    assert editprofile.load()["target_lufs"] == -15.0


def test_apply_topic_appends_once(tmp_path):
    sid = strategy.add([GOOD_TOPIC])[0]["id"]
    strategy.apply(sid)
    strategy.set_status(sid, "proposed")
    strategy.apply(sid)
    assert json.loads((tmp_path / "topics.json").read_text()) == ["Existing topic", GOOD_TOPIC["text"]]


def test_apply_advice_kind_raises():
    sid = strategy.add([{"kind": "title", "text": "Use a number in the title", "why": "w", "evidence": []}])[0]["id"]
    with pytest.raises(ValueError, match="advice only"):
        strategy.apply(sid)
    assert strategy.load()[0]["status"] == "proposed"


def test_set_status_unknown_id_and_value():
    with pytest.raises(ValueError):
        strategy.set_status("nope", "dismissed")
    sid = strategy.add([GOOD_TOPIC])[0]["id"]
    with pytest.raises(ValueError):
        strategy.set_status(sid, "banana")


def test_generate_drops_malformed():
    seen = {}

    def chat(prompt):
        seen["p"] = prompt
        return {"strategies": [GOOD_TOPIC, {"kind": "topic", "text": "x"}, {"kind": "edit", "text": "valid text here", "profile": {"target_lufs": 99}}, "junk"]}

    got = strategy.generate({"subs": 5, "best": []}, [{"channel": "C", "top": [{"title": "Big video", "views": 10}], "summary": {}}], chat)
    assert [g["text"] for g in got] == [GOOD_TOPIC["text"]]
    assert "Big video" in seen["p"] and "target_lufs" in seen["p"]


def test_generate_model_failure_returns_empty():
    def chat(prompt):
        raise RuntimeError("down")

    assert strategy.generate({}, [], chat) == []


def test_clickbait_title_advice_is_refused_and_the_same_advice_in_other_words_is_not_added_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy, "FILE", tmp_path / "s.json")
    assert strategy.validate({"kind": "title", "text": "Use a title format like 'The True Story of [Legend] - What Really Happened?'"}) is None
    assert strategy.validate({"kind": "thumbnail", "text": "Use curiosity-gap thumbnails with a shocking face"}) is None
    assert strategy.validate({"kind": "title", "text": "Name the subject and the question plainly in the title."})
    first = strategy.add([{"kind": "format", "text": "Publish one long documentary and one Short each week."}])
    again = strategy.add([{"kind": "format", "text": "Publish one long documentary and one short every week."}])
    assert len(first) == 1 and again == []


def test_no_more_than_three_open_proposals_per_kind_and_tidy_keeps_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy, "FILE", tmp_path / "s.json")
    texts = ["Add a map in the first minute of each documentary", "End each documentary with a quiet thought about the source",
             "Show the source article's title on screen for two seconds", "Name every image credit aloud once at the end"]
    added = strategy.add([{"kind": "format", "text": t} for t in texts])
    assert len(added) == 3
    rows = strategy.load()
    old = dict(rows[0], id="x", text="Add a map within the first minute of each documentary", created="2020-01-01T00:00:00Z")
    strategy._save(rows + [old])
    assert strategy.tidy()["duplicates"] == 1
    assert [r["status"] for r in strategy.load() if r["id"] == "x"] == ["dismissed"] and all(r["status"] == "proposed" for r in strategy.load() if r["id"] != "x")


def test_production_feedback_counts_the_owner_alerts_and_their_causes(tmp_path, monkeypatch):
    import agentlog
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "e.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    import config
    monkeypatch.setattr(config, "ROOT", tmp_path)
    now = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.timezone.utc)
    agentlog.event("error", "Needs your eyes: A", "I used every try and the reviewer still says fail: title_matches title may mislead", now=now)
    agentlog.event("applied", "Fixed: A", "new title", now=now)
    got = strategy.production_feedback(now)
    assert got["videos_that_needed_the_owner"] == 1 and got["repairs_applied"] == 1 and got["most_common_failures"] == ["title_matches"]
