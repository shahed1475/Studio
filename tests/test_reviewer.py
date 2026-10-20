import copy

import pytest

import reviewer
import scriptgen

LINES = [{"text": f"This is unique narration line number {i} about the town and its long history.", "visual": "old town"} for i in range(60)]
GOOD_META = {
    "format": "doc", "topic": "The Pied Piper", "title": "The Pied Piper of Hamelin: What Really Happened?",
    "description": "A tale of music and mystery from medieval Germany, retold in our own words with care for what is known.\n\nChapters:\n0:00 The Song\n0:40 The Town\n1:20 The Written Story\n2:00 The Theories",
    "tags": ["pied piper", "hamelin", "legend", "folklore", "history", "medieval"],
    "lines": LINES, "credits": ["a.jpg (Wikimedia Commons, CC0)"],
}
GOOD_PROBE = {"duration": 319.0, "width": 1920, "height": 1080, "has_audio": True, "mean_db": -22.0, "black_ratio": 0.01}


def run(meta=None, probe=None, titles=(), thumb=150_000):
    return reviewer.rule_checks(meta or copy.deepcopy(GOOD_META), probe or dict(GOOD_PROBE), list(titles), thumb)


def failed(checks, severity="block"):
    return {c["name"] for c in checks if not c["ok"] and c["severity"] == severity}


def test_good_video_has_no_blocking_failures():
    assert failed(run()) == set()


def test_blocks_short_duration():
    assert "duration" in failed(run(probe={**GOOD_PROBE, "duration": 60.0}))


def test_blocks_wrong_resolution():
    assert "resolution" in failed(run(probe={**GOOD_PROBE, "width": 1080, "height": 1920}))


def test_blocks_silent_audio():
    assert "audio" in failed(run(probe={**GOOD_PROBE, "mean_db": -60.0}))
    assert "audio" in failed(run(probe={**GOOD_PROBE, "has_audio": False, "mean_db": None}))


def test_blocks_mostly_black():
    assert "black_frames" in failed(run(probe={**GOOD_PROBE, "black_ratio": 0.4}))


def test_blocks_duplicate_title():
    assert "duplicate_title" in failed(run(titles=["The Pied Piper of Hamelin: What Really Happened"]))


def test_blocks_missing_and_oversize_thumbnail():
    assert "thumbnail" in failed(run(thumb=None))
    assert "thumbnail" in failed(run(thumb=2_100_000))


def test_blocks_looping_script():
    meta = copy.deepcopy(GOOD_META)
    meta["lines"] = LINES[:30] + [LINES[0]] * 10 + LINES[30:]
    assert "script_loop" in failed(run(meta=meta))


def test_warns_on_placeholder_chapter():
    meta = copy.deepcopy(GOOD_META)
    meta["description"] = meta["description"].replace("The Written Story", "Part 3")
    assert "chapters" in failed(run(meta=meta), "warn")


def test_blocks_bad_first_chapter():
    meta = copy.deepcopy(GOOD_META)
    meta["description"] = meta["description"].replace("0:00 The Song", "0:05 The Song")
    assert "chapters" in failed(run(meta=meta))


def test_warns_few_tags():
    meta = copy.deepcopy(GOOD_META)
    meta["tags"] = ["a", "b"]
    assert "tags" in failed(run(meta=meta), "warn")


def test_verdict_rules():
    ok = [{"name": "x", "ok": True, "severity": "block", "detail": ""}]
    bad = [{"name": "x", "ok": False, "severity": "block", "detail": ""}]
    warn = [{"name": "x", "ok": False, "severity": "warn", "detail": ""}]
    assert reviewer.verdict_from(ok, None) == "pass"
    assert reviewer.verdict_from(warn, None) == "pass"
    assert reviewer.verdict_from(bad, None) == "fail"
    assert reviewer.verdict_from(ok, "news") == "needs_human"
    assert reviewer.verdict_from(bad, "news") == "fail"


def test_llm_unavailable_is_blocking(monkeypatch):
    def boom(prompt, *a, **k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(scriptgen, "_chat", boom)
    checks = reviewer.llm_review(GOOD_META)
    assert [c["name"] for c in checks] == ["llm_review"] and not checks[0]["ok"] and checks[0]["severity"] == "block"


def test_llm_flags_high_risk(monkeypatch):
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"invented_facts_risk": 8, "policy_risk": 1, "misleading_title": False, "issues": ["made-up date"]})
    checks = reviewer.llm_review(GOOD_META)
    assert any(c["name"] == "invented_facts" and not c["ok"] and c["severity"] == "block" for c in checks)


def lines(*texts):
    return [{"text": t, "visual": "x"} for t in texts]


def with_extra(meta_lines):
    meta = copy.deepcopy(GOOD_META)
    meta["lines"] = LINES + lines(*meta_lines)
    return meta


def test_flags_unhedged_specific_claims_for_human():
    meta = with_extra(["In the 16th century, a merchant named Martin von Dornburg recorded the tale in a book that shaped it."])
    assert "claims" in failed(run(meta=meta), "human")


def test_hedged_claims_are_fine():
    meta = with_extra(["Legend says that in 1284 a piper named Hans led the children out of the town gates."])
    assert "claims" not in failed(run(meta=meta), "human")


def test_human_failure_gives_needs_human_not_fail():
    human = [{"name": "claims", "ok": False, "severity": "human", "detail": ""}]
    assert reviewer.verdict_from(human, None) == "needs_human"
    assert reviewer.verdict_from(human + [{"name": "x", "ok": False, "severity": "block", "detail": ""}], None) == "fail"


def test_warns_without_subtitles_but_never_blocks():
    checks = run()
    assert "subtitles" in failed(checks, "warn") and "subtitles" not in failed(checks, "block")


def test_subtitles_ok_when_burned():
    meta = copy.deepcopy(GOOD_META)
    meta["subtitles"] = "burned"
    assert "subtitles" not in failed(run(meta=meta), "warn")


SHORT_PROBE = {"duration": 45.0, "width": 1080, "height": 1920, "has_audio": True, "mean_db": -22.0, "black_ratio": 0.0}


def short_meta(first_line):
    m = copy.deepcopy(GOOD_META)
    m["format"] = "short"
    m["lines"] = [{"text": first_line, "visual": "x"}] + LINES
    return m


def test_warns_when_short_hook_is_long():
    long_hook = " ".join(["word"] * 20)
    assert "hook" in failed(run(meta=short_meta(long_hook), probe=SHORT_PROBE, thumb=None), "warn")


def test_short_with_tight_hook_is_fine_and_doc_has_no_hook_check():
    ok = run(meta=short_meta("Ever notice the tiny hole in a plane window?"), probe=SHORT_PROBE, thumb=None)
    assert "hook" not in failed(ok, "warn") and "hook" not in failed(ok)
    assert not any(c["name"] == "hook" for c in run())


# ---- anti-template checks: YouTube judges the pattern across recent uploads ----
def _other(first, last, title):
    return {"title": title, "lines": [{"text": first}, {"text": "middle line of the story goes here"}, {"text": last}]}


def _mine(first, last, title="A Fresh Title About Something Else"):
    m = copy.deepcopy(GOOD_META)
    m["title"], m["lines"] = title, [{"text": first}, {"text": "another middle line of a different story"}, {"text": last}]
    return m


def test_same_opening_as_a_recent_video_needs_a_human():
    prev = _other("Long ago, in a quiet valley, something strange began to happen.", "And that is why they still whisper about it.", "T1")
    c = reviewer.rule_checks(_mine("Long ago, in a quiet valley, something strange began.", "A totally different way to end."), dict(GOOD_PROBE), [], 150_000, [prev])
    assert "variety_script" in failed(c, "human")


def test_same_ending_as_a_recent_video_needs_a_human():
    prev = _other("An entirely different beginning here.", "And that is why they still whisper about it tonight.", "T1")
    c = reviewer.rule_checks(_mine("Nothing like the other opening at all, really.", "And that is why they still whisper about it."), dict(GOOD_PROBE), [], 150_000, [prev])
    assert "variety_script" in failed(c, "human")


def test_different_scripts_pass_variety():
    prev = _other("Long ago, in a quiet valley, something strange began to happen.", "And that is why they still whisper about it.", "T1")
    c = reviewer.rule_checks(_mine("The ship never reached the harbour that night.", "Nobody ever found the captain."), dict(GOOD_PROBE), [], 150_000, [prev])
    assert "variety_script" not in failed(c, "human") and "variety_title" not in failed(c, "warn")


def test_repeated_title_opening_warns():
    prev = [_other("a b c d e f", "x y z w v u", f"The Legend of Place {i}") for i in range(3)]
    c = reviewer.rule_checks(_mine("The ship never reached the harbour that night.", "Nobody ever found the captain.", "The Legend of Another Place"), dict(GOOD_PROBE), [], 150_000, prev)
    assert "variety_title" in failed(c, "warn")


def test_more_than_fifteen_hashtags_blocks():
    m = copy.deepcopy(GOOD_META)
    m["description"] += "\n" + " ".join(f"#tag{i}" for i in range(14))
    assert "hashtags" in failed(run(meta=m))
    assert "hashtags" not in failed(run())


def test_shouting_title_warns():
    m = copy.deepcopy(GOOD_META)
    m["title"] = "YOU WON'T BELIEVE WHAT HAPPENED IN HAMELIN!!!"
    assert "title_style" in failed(run(meta=m), "warn")
    assert "title_style" not in failed(run(), "warn")


def test_an_unusable_ai_reply_means_unreviewed_not_failed(monkeypatch):
    monkeypatch.setattr(reviewer.scriptgen, "_review_chat", lambda p: {"policy_risk": 1})  # a free model that forgot a key
    checks = reviewer.llm_review({"title": "t", "lines": [{"text": "a line"}]})
    assert checks[0]["name"] == "llm_review" and not checks[0]["ok"]
    assert reviewer.verdict_from(checks + [{"name": "x", "ok": False, "severity": "block"}], None) == "unreviewed"
