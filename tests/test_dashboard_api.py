import pytest

import dashboard

OK = {"enabled": True, "auto_approve": True, "uploads_per_day": 2, "review_window_hours": 12, "upload_lead_hours": 2,
      "min_queue": 3, "max_waiting": 2, "news_videos": True, "slots": [{"day": "fri", "time": "18:00"}]}


def test_valid_config_passes_through():
    assert dashboard.validate_autopilot_config(OK) == OK


@pytest.mark.parametrize("bad", [
    {"uploads_per_day": 0}, {"uploads_per_day": 6}, {"review_window_hours": 2}, {"review_window_hours": 500},
    {"enabled": "yes"}, {"surprise": 1}, {"slots": []}, {"slots": [{"day": "xyz", "time": "18:00"}]},
    {"slots": [{"day": "fri", "time": "25:00"}]}, {"slots": [{"day": "fri", "time": "18"}]},
])
def test_invalid_config_rejected(bad):
    with pytest.raises(ValueError):
        dashboard.validate_autopilot_config({**OK, **bad})


def test_partial_update_is_allowed():
    assert dashboard.validate_autopilot_config({"enabled": False}) == {"enabled": False}


def test_autopilot_view_lists_scheduled_and_needs_you(tmp_path, monkeypatch):
    import json, config
    monkeypatch.setattr(config, "OUT", tmp_path)
    def add(name, **m):
        d = tmp_path / name; d.mkdir(); (d / "meta.json").write_text(json.dumps({"title": name, **m})); (d / "video.mp4").write_bytes(b"x")
    add("ok", review={"verdict": "pass", "checks": []}, publish_at="2026-10-23T22:00:00Z", approved=True)
    add("flag", review={"verdict": "needs_human", "checks": [{"name": "claims", "ok": False, "severity": "human", "detail": "d"}]})
    add("bad", review={"verdict": "fail", "checks": []})
    add("held", review={"verdict": "pass", "checks": []}, publish_at="2026-10-30T22:00:00Z", hold=True)
    view = dashboard.autopilot_view()
    assert [v["slug"] for v in view["scheduled"]] == ["ok", "held"]
    assert sorted(v["slug"] for v in view["needs_you"]) == ["bad", "flag"]
    assert view["scheduled"][0]["bd"] == "Sat 24 Oct, 04:00" and view["scheduled"][0]["us"] == "Fri 23 Oct, 18:00"
