import datetime as dt

import prelaunch
import studiochecks


def test_prelaunch_passes_when_every_blocking_row_passes_and_reports_problems_otherwise(monkeypatch, tmp_path):
    ok = lambda *a, **k: [studiochecks.row("x", True, "fine")]
    monkeypatch.setattr(studiochecks, "load", lambda slug: (tmp_path, {"title": "t"}))
    monkeypatch.setattr(prelaunch.reviewer, "source_text", lambda meta: "")
    for fn in ("check_script", "check_sources", "check_licenses", "check_video", "check_publish_ready"):
        monkeypatch.setattr(studiochecks, fn, ok)
    now = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
    assert prelaunch.check("s", now) == {"at": "2026-10-20T00:00:00Z", "ok": True, "problems": []}
    monkeypatch.setattr(studiochecks, "check_video", lambda *a, **k: [studiochecks.row("audio", False, "no audio stream"), studiochecks.row("fps", False, "low", "warn")])
    r = prelaunch.check("s", now)
    assert not r["ok"] and r["problems"] == ["video: audio: no audio stream"]  # a warning alone does not fail it
    monkeypatch.setattr(studiochecks, "check_licenses", lambda *a, **k: 1 / 0)
    assert any("licenses: could not run" in p for p in prelaunch.check("s", now)["problems"])  # a check that cannot run fails, it is never skipped
