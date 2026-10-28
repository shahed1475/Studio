"""Writer bench: free rules only, free models only, nothing written outside data/writerbench."""
import json

import pytest

import freemodels
import llm
import scriptgen
import writerbench

SOURCE = "The army set out from Thebes in 525 BC with 50,000 men. A storm is said to have buried them near Siwa. Herodotus wrote the account. " * 4


def good_script(n=11):
    lo, hi = scriptgen.short_word_range()
    per = (lo + hi) // 2 // n + 1
    lines = [{"text": " ".join(["Legend says the army reached the dunes"][0].split()[:2] + [f"word{i}x{j}" for j in range(per - 2)]), "visual": "Siwa oasis"} for i in range(n)]
    lines[0]["text"] = "Legend says an army vanished near Siwa."
    return {"title": "The Lost Army", "lines": lines}


def test_a_good_script_scores_full_and_each_rule_catches_its_own_fault():
    ok = writerbench.score(good_script(), SOURCE)
    assert ok["hard_fail"] == [] and ok["score"] >= 0.9, ok
    cases = {
        "json": (None, "json"), "grounded_numbers": (lambda s: s["lines"][3].update(text="In 1823 they were found near Siwa again, people say."), "grounded_numbers"),
        "no_admission": (lambda s: s["lines"][2].update(text="I won't invent details because my sources say very little."), "no_admission"),
        "hook": (lambda s: s["lines"][0].update(text="Nobody has ever found them"), "hook"), "no_loop": (lambda s: s["lines"][5].update(text=s["lines"][4]["text"]), "no_loop"),
        "no_labels": (lambda s: s["lines"][1].update(text="Chapter 2: the march begins now"), "no_labels"), "visuals": (lambda s: s["lines"][2].update(visual=""), "visuals"),
        "line_count": (lambda s: s.update(lines=s["lines"][:5]), "line_count"),
    }
    for name, (mutate, expect) in cases.items():
        script = good_script()
        if mutate is None:
            res = writerbench.score(None, SOURCE)
        else:
            mutate(script)
            res = writerbench.score(script, SOURCE)
        assert not res["checks"][expect][0], (name, res["checks"][expect])
    assert "json" in writerbench.score({"title": "x", "lines": "nope"}, SOURCE)["hard_fail"]
    assert "grounded_numbers" in writerbench.score({**good_script(), "lines": [{"text": "In 1823 something happened here.", "visual": "x"}] * 11}, SOURCE)["hard_fail"]


def test_the_run_scores_every_model_on_every_case_and_ranks_the_usable_first(tmp_path, monkeypatch):
    monkeypatch.setattr(writerbench, "DIR", tmp_path)
    cs = [{"topic": "A", "source": SOURCE}, {"topic": "B", "source": SOURCE}]
    prompts = []

    def ask(model, prompt):
        prompts.append(prompt)
        return (good_script(), "") if model == "good/model:free" else (None, "no JSON in the answer")

    res = writerbench.run(["bad/model:free", "good/model:free"], cs, ask=ask, pause=0)
    assert len(res["rows"]) == 4 and [s["model"] for s in res["summary"]] == ["good/model:free", "bad/model:free"]
    assert next(r for r in res["rows"] if r["model"] == "good/model:free")["script"]["title"] == "The Lost Army"  # kept, so a fact-check can read it later
    assert res["summary"][0]["usable"] == 2 and res["summary"][1]["usable"] == 0 and res["summary"][1]["answered"] == 0
    assert all(p == scriptgen.short_prompt(c["topic"], c["source"]) for p, c in zip(prompts[:2], cs))  # the production prompt, not a copy
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert saved["cases"] == ["A", "B"] and not list(tmp_path.parent.glob("*.json"))


def test_only_free_models_are_called_and_the_productions_allowance_is_kept(monkeypatch):
    import datetime as dt
    now = dt.datetime(2026, 10, 29, 12, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(freemodels, "refresh", lambda n: [{"id": "vendor/free:free", "context": 32000, "score": 1}])
    monkeypatch.setattr(llm, "_post", lambda *a, **k: pytest.fail("a paid or unlisted model must never be called"))
    assert writerbench.ask_free("anthropic/claude-sonnet-5.5", "p", "k", now) == (None, "not a free model")
    monkeypatch.setattr(freemodels, "remaining", lambda *a: writerbench.KEEP_FREE_REQUESTS)
    assert writerbench.ask_free("vendor/free:free", "p", "k", now) == (None, "free allowance kept for production")
    monkeypatch.setattr(freemodels, "remaining", lambda *a: 500)
    monkeypatch.setattr(freemodels, "count_request", lambda *a: None)
    monkeypatch.setattr(llm, "_post", lambda payload, key: {"choices": [{"message": {"content": '{"title": "t", "lines": []}'}}]})
    got, why = writerbench.ask_free("vendor/free:free", "p", "k", now)
    assert got == {"title": "t", "lines": []} and why == ""


def test_the_bench_never_calls_a_claude_model_or_the_review_role():
    text = open(writerbench.__file__).read()
    for banned in ("scriptgen._review_chat", "llm.chat(", "anthropic/", "role=\"review\""):
        assert banned not in text.split('"""', 2)[2], banned


def test_the_judge_reads_only_the_models_usable_scripts_and_a_failing_checker_is_not_a_pass(tmp_path):
    import benchjudge
    rows = [{"model": "m", "topic": "A", "script": good_script(), "hard_fail": []}, {"model": "m", "topic": "B", "script": good_script(), "hard_fail": ["grounded_numbers"]},
            {"model": "other", "topic": "A", "script": good_script(), "hard_fail": []}, {"model": "m", "topic": "C", "script": None, "hard_fail": ["no answer"]}]
    f = tmp_path / "bench.json"
    f.write_text(json.dumps({"rows": rows}))
    rep = benchjudge.check(f, "m", {"A": SOURCE, "B": SOURCE}, ask=lambda lines, src: {2: "not in the source"})
    assert [s["topic"] for s in rep["scripts"]] == ["A"] and rep["lines_flagged"] == 1 and rep["scripts"][0]["unsupported"] == {"2": "not in the source"}
    broke = benchjudge.check(f, "m", {"A": SOURCE}, ask=lambda lines, src: 1 / 0)
    assert broke["judged"] == 0 and "error" in broke["scripts"][0] and broke["lines_ok_pct"] is None
    assert "label" in rep["note"]
