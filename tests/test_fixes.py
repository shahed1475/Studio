"""Regression tests for the final-review findings."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import autopilot
import config
import dashboard
import newswatch
import reviewer
import run
import scriptgen
import seo
import upload

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def test_redo_clears_stale_review_and_schedule():
    data = {"title": "t", "approved": True, "approved_by": "you", "review": {"verdict": "pass"}, "publish_at": "2026-10-23T22:00:00Z",
            "autopilot_fails": 2, "hold": True, "lines": []}
    out = run.reset_for_rerender(data)
    assert not {"approved", "approved_by", "review", "publish_at", "autopilot_fails"} & out.keys()
    assert out["hold"] is True and out["title"] == "t"


def test_unique_folder_never_reuses(tmp_path):
    (tmp_path / "doc-x").mkdir()
    (tmp_path / "doc-x-2").mkdir()
    assert run.unique_folder(tmp_path / "doc-x") == tmp_path / "doc-x-3"
    assert run.unique_folder(tmp_path / "doc-y") == tmp_path / "doc-y"


def test_failed_rereview_removes_reviewer_approval_but_not_yours():
    m = {"approved": True, "approved_by": "reviewer-agent", "autopilot_fails": 2}
    reviewer.apply_verdict(m, {"verdict": "fail"})
    assert m["approved"] is False and "approved_by" not in m
    mine = {"approved": True, "approved_by": "you"}
    reviewer.apply_verdict(mine, {"verdict": "fail"})
    assert mine["approved"] is True
    ok = {"approved": False}
    reviewer.apply_verdict(ok, {"verdict": "pass"})
    assert ok["review"] == {"verdict": "pass"} and ok["autopilot_fails"] == 0


def test_editing_invalidates_review_and_agent_approval():
    m = {"review": {"verdict": "pass"}, "approved": True, "approved_by": "reviewer-agent", "publish_at": "2026-10-23T22:00:00Z"}
    reviewer.invalidate(m)
    assert "review" not in m and m["approved"] is False and "publish_at" not in m
    mine = {"review": {"verdict": "needs_human"}, "approved": True, "approved_by": "you", "publish_at": "x"}
    reviewer.invalidate(mine)
    assert "review" not in mine and mine["approved"] is True


def test_news_entry_fails_after_two_attempts_and_does_not_block(tmp_path, monkeypatch):
    monkeypatch.setattr(newswatch, "NEWS_QUEUE", tmp_path / "q.json")
    (tmp_path / "q.json").write_text(json.dumps([{"topic": "A", "status": "queued", "facts": "f", "sources": []}]))
    def boom(*a, **k):
        raise ValueError("thin script")
    monkeypatch.setattr(scriptgen, "doc_script", boom)
    for _ in range(2):
        with pytest.raises(ValueError):
            newswatch.make_next_news_video()
    entry = json.loads((tmp_path / "q.json").read_text())[0]
    assert entry["status"] == "failed" and entry["attempts"] == 2
    assert newswatch.make_next_news_video() is None


@pytest.mark.parametrize("exc,counted", [(ConnectionError("x"), False), (TimeoutError(), False), (OSError("dns"), False),
                                         (SystemExit("daily upload limit reached"), False), (ValueError("bad"), True), (KeyError("k"), True)])
def test_only_video_specific_failures_count(exc, counted):
    assert autopilot.counts_as_failure(exc) is counted


def test_auth_errors_not_counted():
    class RefreshError(Exception):
        pass
    assert autopilot.counts_as_failure(RefreshError("expired")) is False


def test_dashboard_busy_reads_live_pid(tmp_path):
    f = tmp_path / "job.pid"
    assert autopilot.dashboard_busy(f) is False
    f.write_text(str(os.getpid()))
    assert autopilot.dashboard_busy(f) is True
    f.write_text("999999999")
    assert autopilot.dashboard_busy(f) is False


def test_busy_plans_nothing():
    st = {"queue_len": 5, "connected": True, "busy": True, "uploads_today": 0, "news_pending": 0,
          "videos": [{"slug": "v", "source": None, "approved": True, "approved_by": "you", "verdict": "pass", "hold": False,
                      "video_id": None, "publish_at": (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "fails": 0}]}
    assert autopilot.plan_actions(st, {**autopilot.DEFAULTS, "enabled": True}, NOW) == []


def test_seo_keeps_sources_block():
    old = "Intro.\n\nSources:\nhttps://blog.youtube/a\n\nChapters:\n0:00 One"
    new = seo.rebuild_description(old, "New intro.")
    assert new.startswith("New intro.") and "Sources:\nhttps://blog.youtube/a" in new and "0:00 One" in new


def test_safe_slug_rejects_traversal():
    assert dashboard.safe_slug("doc-the-mystery-1") == "doc-the-mystery-1"
    for bad in ("", "..", ".", "a/b", "../x", ".hidden", "A B"):
        with pytest.raises(ValueError):
            dashboard.safe_slug(bad)


def test_release_hold_clears_old_slot_and_fails():
    m = {"hold": True, "publish_at": "2026-10-23T22:00:00Z", "autopilot_fails": 3}
    dashboard.set_hold(m, False)
    assert m["hold"] is False and "publish_at" not in m and m["autopilot_fails"] == 0


def test_upload_rejects_past_publish_time(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "v"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"approved": True, "title": "t", "description": "d", "tags": []}))
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(SystemExit, match="future"):
        upload.upload(d, "private", past)


def test_failed_video_stays_in_needs_you_even_when_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "f"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"title": "f", "approved": True, "approved_by": "you", "review": {"verdict": "fail", "checks": []}}))
    assert [v["slug"] for v in dashboard.autopilot_view()["needs_you"]] == ["f"]


def test_seo_drops_tv_show_and_off_topic_suggestions():
    for bad in ("unsolved mysteries theme", "unsolved mysteries season 1", "oracle of delphi secret history of hollywood", "history audiobook"):
        assert seo.OFF_TOPIC.search(bad), bad
    for good in ("oracle of delphi story", "history stories for sleep", "minotaur labyrinth myth"):
        assert not seo.OFF_TOPIC.search(good), good
