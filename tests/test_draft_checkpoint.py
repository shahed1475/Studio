"""The documentary draft is saved before its fact-check and resumed instead of rewritten (scriptgen DRAFT_FILE, 20 Nov 2026); a script's own writer writes its next
part first (llm sticky writers), so enough free models stay free to judge it."""
import datetime as dt
import json

import pytest

import llm
import scriptgen


def writer(asked):
    def chat(prompt):
        text = str(prompt)
        asked.append("outline" if "Plan a" in text else "chapter")
        if "Plan a" in text:
            return {"title": "T", "description": "d", "tags": [], "anchors": [], "chapters": [{"title": f"C{n}", "summary": "s"} for n in range(13)]}
        return {"lines": [{"text": " ".join([f"w{i}"] * 40) + ".", "visual": "v"} for i in range(4)]}
    return chat


def test_a_draft_whose_judges_were_busy_is_resumed_not_written_again_and_its_writers_stay_barred(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 100)
    asked = []
    monkeypatch.setattr(scriptgen, "_script_chat", writer(asked))
    llm._WRITERS.clear()
    monkeypatch.setattr(llm, "writers", lambda: ["vendor/w1:free"])
    monkeypatch.setattr(scriptgen, "checked", lambda *a, **k: (_ for _ in ()).throw(ValueError("the script could not be fact-checked (ModelUnavailable)")))
    with pytest.raises(ValueError):
        scriptgen.doc_script("Seven Sleepers", grounded="SRC")
    written = len(asked)
    saved = json.loads(scriptgen.DRAFT_FILE.read_text())
    assert written > 1 and saved["writers"] == ["vendor/w1:free"] and len(saved["lines"]) == 52
    seen_writers = []
    monkeypatch.setattr(scriptgen, "checked", lambda lines, chapters, sources, sleep=None: seen_writers.append(set(llm._WRITERS)) or (lines, chapters))
    out = scriptgen.doc_script("Seven Sleepers", grounded="SRC")
    assert len(asked) == written  # nothing written again
    assert "vendor/w1:free" in seen_writers[0]  # the draft's writer is still barred from judging it
    assert len(out["lines"]) == 52 and not scriptgen.DRAFT_FILE.exists()  # the checkpoint is spent once the draft passed


def test_a_draft_the_sources_do_not_support_is_dropped_and_other_sources_get_a_new_draft(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 100)
    asked = []
    monkeypatch.setattr(scriptgen, "_script_chat", writer(asked))
    monkeypatch.setattr(scriptgen, "checked", lambda *a, **k: (_ for _ in ()).throw(ValueError("the sources do not support 40 of 52 lines")))
    with pytest.raises(ValueError):
        scriptgen.doc_script("Seven Sleepers", grounded="SRC")
    assert not scriptgen.DRAFT_FILE.exists()
    monkeypatch.setattr(scriptgen, "checked", lambda *a, **k: (_ for _ in ()).throw(ValueError("the script could not be fact-checked (ModelUnavailable)")))
    with pytest.raises(ValueError):
        scriptgen.doc_script("Seven Sleepers", grounded="SRC")
    assert scriptgen._load_draft("Seven Sleepers", "OTHER SOURCES") is None  # a draft is only for the sources it was written from
    for _ in range(scriptgen.MAX_DRAFT_USES):
        assert scriptgen._load_draft("Seven Sleepers", "SRC") is not None
    assert scriptgen._load_draft("Seven Sleepers", "SRC") is None  # checked too often: a new draft is written


def test_the_scripts_own_writer_is_asked_first_and_alone(monkeypatch, tmp_path):
    import freemodels

    now = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(freemodels, "refresh", lambda now: [])
    monkeypatch.setattr(freemodels, "choose", lambda role, now, avoid=None, n=4: ["a/new:free", "b/old:free", "c/other:free"])
    monkeypatch.setattr(llm, "extra_models", lambda role: [])
    asked = []
    monkeypatch.setattr(llm, "_ask_free", lambda mid, prompt, role, cfg, key, now: asked.append(mid) or {"ok": 1})
    monkeypatch.setattr(llm, "_race", lambda models, *a, **k: pytest.fail("the writer must not be raced against a newcomer"))
    llm._WRITERS.clear()
    llm._WRITERS.add("b/old:free")
    assert llm._free_chat("p", "script", {"max_output_tokens": 6000}, "k", now) == {"ok": 1} and asked == ["b/old:free"]
    llm._WRITERS.clear()


def test_a_check_without_judges_keeps_the_drafts_uses_and_the_make_stops_at_once(monkeypatch, tmp_path):
    import run
    import wikipedia

    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 100)
    asked = []
    monkeypatch.setattr(scriptgen, "_script_chat", writer(asked))
    monkeypatch.setattr(scriptgen, "checked", lambda *a, **k: (_ for _ in ()).throw(ValueError("the script could not be fact-checked (ModelUnavailable)")))
    with pytest.raises(ValueError):
        scriptgen.doc_script("Seven Sleepers", grounded="SRC")
    with pytest.raises(ValueError):
        scriptgen.doc_script("Seven Sleepers", grounded="SRC")  # resumed, then no judge again
    assert json.loads(scriptgen.DRAFT_FILE.read_text())["uses"] == 0  # neither failed check counted against the draft
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(wikipedia, "facts_multi", lambda topic, n=2, chars_each=7000: [{"title": "A", "url": "https://en.wikipedia.org/wiki/A", "text": "x " * 500}])
    monkeypatch.setattr(wikipedia, "is_media_work", lambda text: False)
    monkeypatch.setattr(run, "_second_sources", lambda topic, arts: (False, None))
    tries = []
    monkeypatch.setattr(run.scriptgen, "doc_script", lambda topic, grounded=None: tries.append(1) or (_ for _ in ()).throw(ValueError("the script could not be fact-checked (ModelUnavailable)")))
    with pytest.raises(SystemExit, match="waits for a free judge"):
        run._cmd_doc("Seven Sleepers")
    assert len(tries) == 1  # not three more attempts that would each use the saved draft
