"""24 Nov 2026: the script fact-check keeps who judged each part (model, what answered, family, provider, time, each judge's own answer), and a part
that could not get two judges of different families is recorded as blocked and never passes the script on."""
import pytest

import llm
import scriptgen

PAIR = {"mode": "free", "models": ["extra:glm-4.7-flash", "extra:qwen-3.8-27b"], "served": ["@cf/zai-org/glm-4.7-flash", "@cf/qwen/qwen3.8-27b"],
        "families": [["zhipu"], ["qwen"]], "providers": ["owner-provider", "owner-provider"], "at": "2026-11-24T00:10:00+00:00"}


def test_each_fact_check_part_keeps_who_judged_it_and_each_answer(monkeypatch):
    lines = [{"text": f"line {i}"} for i in range(35)]
    calls = []

    def fake(prompt, avoid=None):
        calls.append(prompt)
        first = len(calls) == 1
        llm.LAST_REVIEW.clear()
        llm.LAST_REVIEW.update({**PAIR, "answers": [{"unsupported": [{"n": 2, "why": "not in SOURCES"}]} if first else {"unsupported": []}, {"unsupported": []}]})
        return {"unsupported": [{"n": 2, "why": "not in SOURCES"}]} if first else {"unsupported": []}

    monkeypatch.setattr(scriptgen, "_review_chat", fake)
    scriptgen.FACTCHECK.clear()
    assert scriptgen.unsupported(lines, "S") == {2: "not in SOURCES"}
    got = scriptgen.factchecks()
    assert [c["lines"] for c in got] == [[0, 29], [30, 34]] and len(calls) == 2
    assert got[0]["result"] == "checked" and got[0]["flagged"] == [2] and got[1]["flagged"] == []
    assert got[0]["families"] == [["zhipu"], ["qwen"]] and got[0]["providers"] == ["owner-provider", "owner-provider"] and got[0]["at"]
    assert got[0]["answers"][1] == {"unsupported": []}  # the judge that disagreed stays on record: a disagreement is never smoothed away


def test_a_blocked_part_is_recorded_and_the_script_is_not_passed(monkeypatch):
    def fake(prompt, avoid=None):
        llm.LAST_REVIEW.clear()
        llm.LAST_REVIEW.update({"mode": "blocked", "models": ["extra:nemotron-3-ultra-550b"], "why": "no judge of a family other than nvidia answered"})
        raise llm.ModelUnavailable("the review is blocked: no judge of a family other than nvidia answered")

    monkeypatch.setattr(scriptgen, "_review_chat", fake)
    scriptgen.FACTCHECK.clear()
    with pytest.raises(ValueError, match="could not be fact-checked"):
        scriptgen.unsupported([{"text": "a"}], "S")
    rec = scriptgen.factchecks()[-1]
    assert rec["result"] == "blocked" and rec["mode"] == "blocked" and "nvidia" in rec["why"] and "ModelUnavailable" in rec["error"]


def test_a_new_script_starts_a_new_fact_check_record():
    scriptgen.FACTCHECK.append({"lines": [0, 1], "result": "checked"})
    for _ in range(scriptgen.FACTCHECK_KEEP + 5):
        scriptgen._keep_check(0, [{}], "checked")
    assert len(scriptgen.factchecks()) == scriptgen.FACTCHECK_KEEP  # the record never grows without end
    scriptgen.FACTCHECK.clear()
    assert scriptgen.factchecks() == []


def test_one_judges_empty_list_never_passes_when_the_other_gave_no_verdict(monkeypatch):
    """24 Nov 2026 review: strictest() kept GLM's {"unsupported": []} when Qwen answered in another shape, so one family's word passed the part."""
    def fake(prompt, avoid=None):
        llm.LAST_REVIEW.clear()
        llm.LAST_REVIEW.update({**PAIR, "answers": [{"unsupported": []}, {"result": "ok"}]})
        return {"unsupported": [], "result": "ok"}

    monkeypatch.setattr(scriptgen, "_review_chat", fake)
    scriptgen.FACTCHECK.clear()
    with pytest.raises(ValueError, match="could not be fact-checked"):
        scriptgen.unsupported([{"text": "a"}], "S")
    assert scriptgen.factchecks()[-1]["result"] == "blocked"
