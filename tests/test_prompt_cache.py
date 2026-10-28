"""The calls that repeat the same source article send it as one shared cache block (llm.cached), so the second and later calls read it at a tenth of the price."""
import llm
import reviewer
import scriptgen

SOURCES = "The army set out from Thebes in 525 BC. " * 90  # over the cache minimum
LINES = [{"text": "The army marched west.", "visual": "Thebes"}, {"text": "A storm swallowed it.", "visual": "Siwa"},
         {"text": "It set out in 525 BC.", "visual": "Thebes"}, {"text": "Nobody came back.", "visual": "Siwa"}]


def head(prompt: str) -> str:
    return prompt.partition(llm.CACHE_MARK)[0]


def test_fact_check_and_rewrite_share_one_source_block(monkeypatch):
    seen = []

    def fake(prompt):
        seen.append(prompt)
        return {"unsupported": [{"n": 1, "why": "not in SOURCES"}]} if "fact-checker" in prompt else {"lines": [{"n": 1, "text": "A storm is said to have swallowed it whole.", "visual": "Siwa"}]}

    monkeypatch.setattr(scriptgen, "_review_chat", fake)
    monkeypatch.setattr(scriptgen, "_script_chat", fake)
    scriptgen.verify_and_revise(LINES, [{"title": "x", "start_line": 0}], SOURCES, rounds=1)
    assert len(seen) >= 3  # check, rewrite, check again
    assert len({head(p) for p in seen}) == 1, "every call of the series starts with the same source block"
    assert head(seen[0]) == "SOURCES:\n" + SOURCES + "\n\n"
    assert all(llm.CACHE_MARK in p for p in seen)


def test_the_review_sends_the_article_as_the_cached_part_and_the_script_after_it(monkeypatch):
    seen = []
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p: seen.append(p) or {"invented_facts_risk": 1, "policy_risk": 0, "misleading_title": False})
    meta = {"title": "T", "description": "d", "lines": [{"text": "The army marched west."}], "topic": "army"}
    reviewer.llm_review(meta, SOURCES)
    before, _, after = seen[0].partition(llm.CACHE_MARK)
    assert "<article>" in before and "Narration:" in after and "Narration:" not in before


def test_chapter_writing_sends_the_rules_and_sources_before_the_mark(monkeypatch):
    seen = []

    def fake(prompt):
        seen.append(prompt)
        if "Plan a" in prompt:
            return {"title": "T", "description": "d", "tags": [], "anchors": [], "chapters": [{"title": f"C{i}", "summary": "s"} for i in range(6)]}
        return {"lines": [{"text": " ".join(["word"] * 20), "visual": "Siwa oasis"} for _ in range(8)]}

    monkeypatch.setattr(scriptgen, "_script_chat", fake)
    monkeypatch.setattr(scriptgen, "verify_and_revise", lambda lines, chapters, sources, **k: (lines, chapters))
    scriptgen.doc_script("Lost Army of Cambyses", grounded=SOURCES)
    chapters = [p for p in seen if "Write chapter" in p]
    assert len(chapters) >= 5
    assert len({head(p) for p in chapters}) == 1 and SOURCES in head(chapters[0])
    assert "Story so far" not in head(chapters[0]) and "Story so far" in chapters[1].partition(llm.CACHE_MARK)[2]
