import json

import autopilot
import channelprofile


def test_default_is_no_human_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(channelprofile, "FILE", tmp_path / "profile.json")
    assert channelprofile.human_approval() is False
    assert autopilot.auto_approves({"auto_approve": True}) is True
    assert autopilot.auto_approves({"auto_approve": False}) is False


def test_human_approval_turns_auto_approve_off_without_touching_the_saved_config(tmp_path, monkeypatch):
    monkeypatch.setattr(channelprofile, "FILE", tmp_path / "profile.json")
    (tmp_path / "profile.json").write_text(json.dumps({"human_approval": True}))
    cfg = {"auto_approve": True}
    assert autopilot.auto_approves(cfg) is False
    assert cfg == {"auto_approve": True}  # the owner's own setting is not rewritten


def test_a_bad_profile_file_means_no_gate_change(tmp_path, monkeypatch):
    monkeypatch.setattr(channelprofile, "FILE", tmp_path / "profile.json")
    for text in ("not json", "[1]", '{"human_approval": "yes"}'):
        (tmp_path / "profile.json").write_text(text)
        assert channelprofile.human_approval() is False
