"""The AI review read only the first 7,000 characters of the narration. The 8 to 10 minute documentaries (1,300 words, about 7,700 characters; the line cap allows about 9,000) lost their
closing chapter, the one that gives the viewer value, and the reviewer then reported a script "cut off mid-sentence" (Cambyses documentary, 30 Oct 2026)."""
import reviewer
import scriptgen


def nine_minute_script():
    lines = [{"text": f"Line {i} " + "word " * 24 + "ends here."} for i in range(57)]
    lines.append({"text": "THE VERY LAST WORDS OF THE FILM."})
    return {"title": "T", "description": "d", "lines": lines}


def test_the_ai_review_and_the_title_check_read_the_whole_script_of_a_nine_minute_documentary(monkeypatch):
    seen = []
    monkeypatch.setattr(scriptgen, "_review_chat", lambda prompt, *a, **k: seen.append(str(prompt)) or {"invented_facts_risk": 1, "policy_risk": 1, "misleading_title": False})
    meta = nine_minute_script()
    assert 7000 < sum(len(l["text"]) + 1 for l in meta["lines"]) < reviewer.REVIEW_TEXT_CHARS  # longer than the old cap, inside the new one
    reviewer.llm_review(meta)
    reviewer.title_ok(meta, "Another title")
    assert len(seen) == 2 and all("THE VERY LAST WORDS OF THE FILM." in p for p in seen)


def test_a_script_far_beyond_any_documentary_is_still_cut_so_one_review_cannot_cost_without_limit(monkeypatch):
    seen = []
    monkeypatch.setattr(scriptgen, "_review_chat", lambda prompt, *a, **k: seen.append(str(prompt)) or {"invented_facts_risk": 1, "policy_risk": 1, "misleading_title": False})
    meta = {"title": "T", "description": "d", "lines": [{"text": "x" * 500}] * 100 + [{"text": "FINAL MARKER"}]}
    reviewer.llm_review(meta)
    assert "FINAL MARKER" not in seen[0] and len(seen[0]) < reviewer.REVIEW_TEXT_CHARS + 6000
