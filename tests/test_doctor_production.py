"""The doctor knows the production failure classes added on 20 Nov 2026 (doctor.production_status): Blender missing, no usable music, a film waiting at its checkpoint
for free pictures (with the exact resume command once the allowance is back), set-aside scripts. It reads files only and never starts a production."""
import datetime as dt
import json

import ccrender
import doctor
import freeart
import musicbed

NOW = dt.datetime(2026, 11, 21, 1, 0, tzinfo=dt.timezone.utc)


def test_missing_blender_and_music_are_named_with_safe_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(ccrender, "BLENDER", tmp_path / "none" / "blender")
    monkeypatch.setattr(musicbed, "DIR", tmp_path / "no-music")
    got = doctor.production_status(NOW, tmp_path / "pending_doc.json")
    needs = {p["need"]: p for p in got["problems"]}
    assert got["blender"] is False and got["music_tracks"] == 0 and set(needs) == {"blender", "music"}
    assert any("only when no render is running" in c for c in needs["blender"]["commands"])  # a restart is never suggested over a running render


def test_a_film_waiting_for_pictures_is_reported_with_its_resume_step_and_ready_only_after_the_reset(tmp_path, monkeypatch):
    blender = tmp_path / "blender"
    blender.write_text("")
    monkeypatch.setattr(ccrender, "BLENDER", blender)
    pend = tmp_path / "pending_doc.json"
    pend.write_text(json.dumps({"data": {"title": "Hampi"}, "folder": "doc-hampi", "tries": 0, "waiting_for_pictures": {"short": 30, "total": 92}}))
    (tmp_path / "pending_doc.set-aside-20261120-090000.json").write_text("{}")
    monkeypatch.setattr(freeart, "quota_left", lambda cfg=None, now=None: 200.0)
    got = doctor.production_status(NOW, pend)
    assert got["checkpoints"][0]["ready_to_continue"] is False and got["checkpoints"][0]["scenes_left"] == 30
    assert "run.py autopilot make doc" in got["checkpoints"][0]["resume"] and got["set_aside"] == ["pending_doc.set-aside-20261120-090000.json"]
    monkeypatch.setattr(freeart, "quota_left", lambda cfg=None, now=None: 9000.0)  # the allowance reset at 00:00 UTC
    assert doctor.production_status(NOW, pend)["checkpoints"][0]["ready_to_continue"] is True
