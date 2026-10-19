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
