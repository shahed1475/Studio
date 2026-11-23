"""A documentary opens on its central question and keeps re-asking (23 Nov 2026). The Maximilian film (23 Nov) opened "Born in Vienna at Schonbrunn
Palace on July 6, 1832..." and its 89 lines held no question at all: the outline was told to open on the central question, but the chapter writer,
who writes the lines, was never told. Now chapter 1 is told, every chapter is asked for questions and turns, and a script that still opens without a
question gets one opening question line, asked of the writer before the fact-check (so the new line is checked like every other)."""
import pytest

import scriptgen


def _lines(*texts):
    return [{"text": t, "visual": "v"} for t in texts]


def test_a_script_without_an_opening_question_gets_one_question_line_before_its_first_line():
    lines = _lines("Born in Vienna on July 6, 1832, the archduke grew up at court.", "His mother supervised his schooling.", "Later he sailed.")
    chapters = [{"title": "A", "start_line": 0}, {"title": "B", "start_line": 2}]
    asked = []

    def chat(prompt):
        asked.append(prompt)
        return {"text": "How did an Austrian archduke end up before a Mexican firing squad? By the end you will know.", "visual": "Queretaro"}

    out, ch = scriptgen.hook_fix(lines, chapters, "Maximilian I of Mexico", "The Emperor", "rules", "calm", chat=chat)
    assert out[0]["text"].startswith("How did") and out[1:] == lines
    assert ch == [{"title": "A", "start_line": 0}, {"title": "B", "start_line": 3}]  # the later chapters still start on their own first line
    assert len(asked) == 1 and "never yes/no" in asked[0].lower() and lines[0]["text"] in asked[0]


def test_a_script_that_already_opens_with_a_question_is_left_alone_and_no_model_is_asked():
    lines = _lines("Why would ten people leave a ship that could still sail?", "This film follows the record.")
    out, ch = scriptgen.hook_fix(lines, [{"title": "A", "start_line": 0}], "t", "T", "r", "s", chat=lambda p: pytest.fail("asked"))
    assert out == lines and ch == [{"title": "A", "start_line": 0}]


@pytest.mark.parametrize("reply", [{"text": "The archduke was born in 1832."}, {"text": ""}, {"text": "Why? " + "word " * 60}, RuntimeError("busy")])
def test_an_answer_that_is_not_a_short_question_or_a_failed_call_changes_nothing(reply):
    lines = _lines("Born in Vienna in 1832.", "He grew up at court.")

    def chat(prompt):
        if isinstance(reply, Exception):
            raise reply
        return reply

    out, ch = scriptgen.hook_fix(lines, [{"title": "A", "start_line": 0}], "t", "T", "r", "s", chat=chat)
    assert out == lines and ch == [{"title": "A", "start_line": 0}]


def test_the_chapter_writer_is_told_to_open_on_the_central_question_and_to_keep_asking(monkeypatch):
    prompts = []
    calls = {"n": 0}

    def fake(prompt):
        prompts.append(str(prompt))
        calls["n"] += 1
        if calls["n"] == 1:
            return {"title": "T", "chapters": [{"title": f"C{i}", "summary": "s"} for i in range(6)]}
        raise RuntimeError("stop after the first chapter")

    monkeypatch.setattr(scriptgen, "_script_chat", fake)
    monkeypatch.setattr(scriptgen, "_load_draft", lambda *a: None)
    with pytest.raises(RuntimeError):
        scriptgen.doc_script("The Mary Celeste", grounded="Some article text.")
    first = prompts[1].lower()
    assert "line 1 of the film is the hook" in first and "never yes/no" in first and "birth date" in first  # 'never open on a birth date'
    assert "question" in first and ("'but'" in first or "but," in first)  # every chapter keeps re-asking: questions or turns
