"""The Channels dashboard view: it lists the profiles, shows the money and approval settings, and survives a broken profile file."""
import json

import channelconfig
import channelprofile
import channelsview


def test_the_shipped_profiles_have_no_budget_and_ask_a_person_to_approve():
    rows = {r["id"]: r for r in channelsview.build()["channels"]}
    assert {"tech", "crisis"} <= set(rows)
    for name in ("tech", "crisis"):
        assert rows[name]["daily_budget_usd"] == 0 and rows[name]["human_approval"] is True and "error" not in rows[name]


def test_a_broken_profile_is_listed_as_invalid_not_raised(tmp_path, monkeypatch):
    good = json.loads((channelconfig.DIR / "tech.json").read_text())
    (tmp_path / "ok.json").write_text(json.dumps({**good, "id": "ok"}))
    (tmp_path / "bad.json").write_text("{not json")
    (tmp_path / "short.json").write_text(json.dumps({"id": "short"}))
    monkeypatch.setattr(channelconfig, "DIR", tmp_path)
    rows = {r["id"]: r for r in channelsview.build()["channels"]}
    assert "error" not in rows["ok"] and "not valid JSON" in rows["bad"]["error"] and "missing" in rows["short"]["error"]


def test_no_profile_folder_is_an_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(channelconfig, "DIR", tmp_path / "nowhere")
    assert channelsview.build()["channels"] == []


def test_the_studio_setting_comes_from_its_own_profile_file(tmp_path, monkeypatch):
    monkeypatch.setattr(channelprofile, "FILE", tmp_path / "profile.json")
    assert channelsview.build()["studio_human_approval"] is False
    (tmp_path / "profile.json").write_text(json.dumps({"human_approval": True}))
    assert channelsview.build()["studio_human_approval"] is True
