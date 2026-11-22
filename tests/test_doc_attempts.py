"""A documentary whose every script attempt failed stops: a refused script never goes on to voice and pictures (22 Nov 2026 audit)."""
import pytest

import run
import scriptgen
import wikipedia


def test_a_thin_script_refused_in_the_first_attempt_is_never_produced_when_the_later_attempts_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(wikipedia, "facts_multi", lambda *a, **k: [{"title": "Topic", "text": "Some source text. " * 50, "url": "https://en.wikipedia.org/wiki/Topic"}])
    monkeypatch.setattr(wikipedia, "is_media_work", lambda text: False)
    monkeypatch.setattr(run, "_second_sources", lambda topic, arts: (False, None))
    calls = []

    def doc_script(topic, grounded=None):
        calls.append(topic)
        if len(calls) == 1:
            return {"title": "T", "lines": [{"text": "The sources say little about this."}], "chapters": []}
        raise ValueError("the writer did not answer")

    monkeypatch.setattr(scriptgen, "doc_script", doc_script)
    monkeypatch.setattr(scriptgen, "thin_script", lambda lines: len(calls) == 1)
    produced = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: produced.append(data))
    with pytest.raises(SystemExit, match="could not generate"):
        run._cmd_doc("Topic")
    assert len(calls) == 4 and produced == []


def test_low_memory_stops_new_heavy_work_only(monkeypatch):
    import autopilot
    import checkpoint

    low = "MemTotal: 24000000 kB\nMemAvailable: 1500000 kB\n"
    assert "1.5 GB" in checkpoint.memory_short(meminfo=low)
    assert checkpoint.memory_short(meminfo="MemAvailable: 8000000 kB\n") is None
    assert checkpoint.memory_short(meminfo="garbage") is None              # unreadable is never a reason to stop


def test_a_draft_waiting_for_its_fact_check_is_the_next_documentary_until_its_checks_are_used(monkeypatch, tmp_path):
    import json
    import duplicates
    import topicqueue
    import topicrank

    f = tmp_path / "pending_draft.json"
    monkeypatch.setattr(scriptgen, "DRAFT_FILE", f)
    monkeypatch.setattr(topicqueue, "pop_pinned", lambda fmt: None)
    monkeypatch.setattr(topicrank, "pop_best", lambda fmt, want_kind=None: "Queue topic")
    monkeypatch.setattr(duplicates, "topic_conflict", lambda topic, fmt: False)
    f.write_text(json.dumps({"topic": "Maximilian I of Mexico", "lines": [{"text": "x"}], "uses": 1}))
    assert run._best_topic("doc") == "Maximilian I of Mexico"
    assert run._best_topic("short") == "Queue topic"                                    # a Short never takes a documentary draft
    f.write_text(json.dumps({"topic": "Maximilian I of Mexico", "lines": [{"text": "x"}], "uses": scriptgen.MAX_DRAFT_USES}))
    assert run._best_topic("doc") == "Queue topic"                                      # its checks are used up: a new topic is written
    f.write_text(json.dumps({"topic": "Maximilian I of Mexico", "lines": [{"text": "x"}], "uses": 0}))
    monkeypatch.setattr(duplicates, "topic_conflict", lambda topic, fmt: True)
    assert run._best_topic("doc") == "Queue topic"                                      # the same story is already made: never twice


def test_a_script_far_under_the_owners_length_is_never_voiced(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(wikipedia, "facts_multi", lambda *a, **k: [{"title": "Topic", "text": "Some source text. " * 50, "url": "https://en.wikipedia.org/wiki/Topic"}])
    monkeypatch.setattr(wikipedia, "is_media_work", lambda text: False)
    monkeypatch.setattr(run, "_second_sources", lambda topic, arts: (False, None))
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 3000)
    monkeypatch.setattr(scriptgen, "thin_script", lambda lines: False)
    monkeypatch.setattr(run, "_script_gate", lambda data, src, topic: data)
    short = {"title": "T", "lines": [{"text": "word " * 30} for _ in range(50)], "chapters": []}  # 1,500 words
    monkeypatch.setattr(scriptgen, "doc_script", lambda topic, grounded=None: short)
    produced = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: produced.append(data))
    with pytest.raises(SystemExit):
        run._cmd_doc("Topic")
    assert produced == []
    long = {"title": "T", "lines": [{"text": "word " * 30} for _ in range(95)], "chapters": []}  # 2,850 words: within 90 % of 3,000
    monkeypatch.setattr(scriptgen, "doc_script", lambda topic, grounded=None: long)
    monkeypatch.setattr(run, "anchor_terms", lambda *a, **k: [])
    run._cmd_doc("Topic")
    assert len(produced) == 1
