import datetime as dt
import json

import config
import pytest
import reviewer
import studiochecks as sc

NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)
SOURCE = "Delphi was called Pytho. French archaeologists excavated from 1893."


def by(rows, name):
    return next(r for r in rows if r["name"] == name)


def short(**over):
    lines = [{"text": "What happened at Delphi?"}] + [{"text": f"Narration line {i} tells more of the old story for the listener."} for i in range(1, 12)]
    return {"format": "short", "grounded": True, "lines": lines, "title": "A title", "description": "d" * 100, **over}


def test_script_rules_catch_loops_long_hooks_and_unevidenced_claims():
    ok = sc.check_script(short(), SOURCE)
    assert all(r["ok"] for r in ok if r["severity"] == "block")
    bad = short(lines=[{"text": "This is a very long opening line that rambles on for well over fourteen words before it ever gets to the point."}] +
                [{"text": "Same line again and again."}] * 8 + [{"text": "A fire swept the site in 1938."}], conflicting_claims=[{"claim": "1938", "fact": "1937"}])
    rows = sc.check_script(bad, SOURCE)
    assert not by(rows, "short_hook")["ok"] and not by(rows, "no_repeated_lines")["ok"] and not by(rows, "no_conflicting_claims")["ok"]
    unverified = sc.check_script(short(lines=short()["lines"] + [{"text": "A fire swept the site in 1938."}]), SOURCE)
    assert not by(unverified, "no_unverified_claims")["ok"] and "1938" in by(unverified, "no_unverified_claims")["detail"]


def test_sources_need_evidence_for_every_verified_claim(tmp_path):
    meta = short(sources=["Wikipedia: Delphi (CC BY-SA 4.0), retold", "Checked against: http://insecure.example"], lines=[{"text": "French diggers arrived in 1893."}])
    rows = sc.check_sources(meta, tmp_path, SOURCE)
    assert by(rows, "verified_has_evidence")["ok"] and not by(rows, "https_sources")["ok"] and not by(rows, "ledger_file")["ok"]
    assert "1 VERIFIED" in by(rows, "ledger_summary")["detail"]


def test_licenses_allow_public_domain_cc0_and_labelled_ai_art_and_refuse_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    good = {"credits": ["Map.jpg (Wikimedia Commons, Public domain)", "Temple.jpg (Wikimedia Commons, CC0)", "Illustration: AI-generated storybook art"],
            "footage": {"drawn": 2}, "grounded": True, "sources": ["Wikipedia: X (CC BY-SA 4.0), retold"]}
    assert all(r["ok"] for r in sc.check_licenses(good))
    bad = {"credits": ["Photo.jpg (Flickr, All rights reserved)", "Pic.jpg (some blog)"], "footage": {"drawn": 3}}
    rows = sc.check_licenses(bad)
    assert not by(rows, "licenses_allowed")["ok"] and not by(rows, "ai_art_labelled")["ok"]
    assert not by(sc.check_licenses({**good, "sources": [], "description": "x"}), "wikipedia_attribution")["ok"]


def test_music_needs_a_license_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "music").mkdir()
    (tmp_path / "music" / "a.mp3").write_bytes(b"x")
    assert not by(sc.check_licenses({"credits": ["a (Public domain)"]}), "music_license")["ok"]
    (tmp_path / "music" / "LICENSE.txt").write_text("CC0")
    assert by(sc.check_licenses({"credits": ["a (Public domain)"]}), "music_license")["ok"]


SRT = "1\n00:00:00,000 --> 00:00:02,000\nWhat happened at Delphi\n\n2\n00:00:02,100 --> 00:00:04,000\nLong ago a priestess\n"


def test_captions_must_be_in_order_inside_the_video_and_match_the_script(tmp_path):
    (tmp_path / "captions.srt").write_text(SRT)
    meta = {"lines": [{"text": "What happened at Delphi?"}, {"text": "Long ago a priestess."}]}
    rows = sc.caption_checks(tmp_path, meta, 4.5)
    assert all(r["ok"] for r in rows) and by(rows, "captions_match_script")["detail"].startswith("100%")
    assert not by(sc.caption_checks(tmp_path, meta, 2.5), "captions_inside_video")["ok"]
    assert not by(sc.caption_checks(tmp_path, {"lines": [{"text": "Completely different words are spoken here instead."}]}, 4.5), "captions_match_script")["ok"]
    (tmp_path / "captions.srt").write_text("1\n00:00:03,000 --> 00:00:04,000\nA\n\n2\n00:00:01,000 --> 00:00:02,000\nB\n")
    assert not by(sc.caption_checks(tmp_path, meta, 5), "captions_in_order")["ok"]


def test_publish_readiness_lists_exactly_what_is_missing():
    ready = {"approved": True, "approved_by": "you", "review": {"verdict": "pass"}, "publish_at": "2026-10-22T16:30:00Z"}
    assert all(r["ok"] for r in sc.check_publish_ready(ready, NOW, 0))
    rows = sc.check_publish_ready({"hold": True, "video_id": "abc", "review": {"verdict": "fail"}, "publish_at": "2026-10-20T12:01:00Z", "upload_started": "x"}, NOW, 2)
    failing = {r["name"] for r in rows if not r["ok"]}
    assert failing == {"approved", "not_on_hold", "review_passed", "not_uploaded_yet", "daily_limit", "scheduled_in_future"}  # a video id exists, so no attempt is "interrupted"
    interrupted = sc.check_publish_ready({"approved": True, "review": {"verdict": "pass"}, "publish_at": "2026-10-22T16:30:00Z", "upload_started": "2026-10-20T10:00:00Z"}, NOW, 0)
    assert not by(interrupted, "no_interrupted_upload")["ok"]


def test_the_gate_fails_on_any_blocking_row_and_reports_a_check_that_cannot_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = tmp_path / "v"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps(short()))
    monkeypatch.setattr(reviewer, "review", lambda folder, use_llm=True, persist=True: {"verdict": "pass", "checks": [{"name": "duration", "ok": True, "severity": "block", "detail": "ok"}]})
    monkeypatch.setattr(reviewer, "source_text", lambda meta: SOURCE)
    result = sc.quality_gate("v", quick=True)  # video.mp4 does not exist: that check cannot run and must say so
    assert result["verdict"] == "FAIL" and any(r["name"] == "video: could not run" and not r["ok"] for r in result["rows"])
    assert sc.main(["gate", "missing-slug"]) == 2 and sc.main(["nonsense"]) == 2
