"""A new review is demonstrably new, tied to the script it read, and never erases the one before (24 Nov 2026: the owner saw the Seven Sleepers report of
21 Nov again and again; its four findings are rule checks, so an unchanged script gives them again, and the panel showed no date, id or history)."""
import json

import dashboard
import reviewer


def _video(tmp_path, lines):
    folder = tmp_path / "out" / "doc-test"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"title": "A Test Film", "format": "doc", "lines": [{"text": t} for t in lines]}))
    return folder


def _fake(monkeypatch, findings, llm_ok=True):
    monkeypatch.setattr(reviewer, "probe_video", lambda p: {})
    monkeypatch.setattr(reviewer, "source_text", lambda meta: "")
    monkeypatch.setattr(reviewer, "rule_checks", lambda *a, **k: [{"name": n, "ok": False, "severity": "warn", "detail": n} for n in findings]
                        + [{"name": "duration", "ok": True, "severity": "block", "detail": "ok"}])
    monkeypatch.setattr(reviewer, "llm_review", lambda meta, source: [{"name": "llm_review", "ok": llm_ok, "severity": "block",
                                                                     "detail": "ok" if llm_ok else "review unavailable: ModelUnavailable"}])


def test_review_b_is_new_tied_to_its_script_and_review_a_stays_in_history(monkeypatch, tmp_path):
    folder = _video(tmp_path, ["Line one.", "Line two."])
    _fake(monkeypatch, ["hook_question"])
    a = reviewer.review(folder)
    (folder / "meta.json").write_text(json.dumps({**json.loads((folder / "meta.json").read_text()),
                                                   "lines": [{"text": "Why did it happen?"}, {"text": "Line two."}]}))  # script version B
    _fake(monkeypatch, [])
    b = reviewer.review(folder)
    meta = json.loads((folder / "meta.json").read_text())
    assert a["id"] != b["id"] and len(b["id"]) == 12  # a fresh execution id each time
    assert a["script_sha"] != b["script_sha"] == reviewer.script_fingerprint(meta)  # B is tied to the current script
    assert meta["review"]["id"] == b["id"]  # B is the stored, current review
    assert [h["id"] for h in meta["review_history"]] == [a["id"]]  # A is still there
    trail = dashboard.review_trail(meta)  # what the panel receives
    assert trail["script_sha_now"] == b["script_sha"] and trail["review_history"][0]["findings"] == ["hook_question"]


def test_an_unchanged_script_gives_the_same_findings_but_a_new_review_id(monkeypatch, tmp_path):
    folder = _video(tmp_path, ["Line one."])
    _fake(monkeypatch, ["hook_question", "doc_length"])
    a, b = reviewer.review(folder), reviewer.review(folder)
    assert a["id"] != b["id"] and a["script_sha"] == b["script_sha"]  # honest: same script, same rule findings, but a new run
    assert [c["name"] for c in a["checks"] if not c["ok"]] == [c["name"] for c in b["checks"] if not c["ok"]]


def test_a_failed_ai_review_keeps_the_last_review_and_records_the_attempt(monkeypatch, tmp_path):
    folder = _video(tmp_path, ["Line one."])
    _fake(monkeypatch, [])
    good = reviewer.review(folder)
    _fake(monkeypatch, [], llm_ok=False)
    bad = reviewer.review(folder)
    meta = json.loads((folder / "meta.json").read_text())
    assert bad["verdict"] == "unreviewed" and "review" not in meta  # Autopilot still sees it as not reviewed and tries again
    assert meta["review_history"][-1]["id"] == good["id"]  # the last good review was not erased
    assert meta["review_attempt"]["id"] == bad["id"] and "ModelUnavailable" in meta["review_attempt"]["why"]
    _fake(monkeypatch, [])
    reviewer.review(folder)
    assert "review_attempt" not in json.loads((folder / "meta.json").read_text())  # a finished review clears the failed try


def test_history_is_capped_and_an_edit_keeps_the_dropped_review(monkeypatch, tmp_path):
    folder = _video(tmp_path, ["Line one."])
    _fake(monkeypatch, [])
    for _ in range(reviewer.HISTORY_KEEP + 3):
        reviewer.review(folder)
    meta = json.loads((folder / "meta.json").read_text())
    assert len(meta["review_history"]) == reviewer.HISTORY_KEEP
    last = meta["review"]["id"]
    reviewer.invalidate(meta)
    assert "review" not in meta and meta["review_history"][-1]["id"] == last


def test_history_keeps_only_the_failing_checks_and_a_count_of_the_rest(monkeypatch, tmp_path):
    folder = _video(tmp_path, ["Line one."])
    _fake(monkeypatch, ["hook_question"])
    reviewer.review(folder)
    reviewer.review(folder)
    h = json.loads((folder / "meta.json").read_text())["review_history"][-1]
    assert [c["name"] for c in h["checks"]] == ["hook_question"] and h["passed"] == 2  # duration and llm_review passed; only the failure is kept
    assert {"id", "at", "verdict", "script_sha"} <= set(h)
