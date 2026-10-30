"""A film opens with its question on screen (30 Oct 2026, owner: curiosity from the first second). Shorts already do; the film's first lines were a calm statement over a still picture.
The first question sentence of the first two narration lines, 14 words or fewer, shows large for the first three seconds; nothing is invented and a statement shows nothing."""
import motiongraphics as mg

DUR = [9.0] * 30


def data(*lines):
    return {"lines": [{"text": t} for t in lines], "chapters": [{"title": "Hook", "start_line": 0}, {"title": "Story", "start_line": 5}]}


def test_the_first_question_in_the_first_two_lines_becomes_the_hook_text_in_capitals():
    assert mg.hook_text(data("Where did an army of fifty thousand Persian soldiers go?", "The legend says a sandstorm.")) == "WHERE DID AN ARMY OF FIFTY THOUSAND PERSIAN SOLDIERS GO?"
    assert mg.hook_text(data("In 525 BC an army set out. Did any of them come home?", "x")) == "DID ANY OF THEM COME HOME?"
    assert mg.hook_text(data("A calm opening.", "So who gave the order?")) == "SO WHO GAVE THE ORDER?"


def test_a_statement_a_late_question_or_a_long_question_shows_nothing():
    assert mg.hook_text(data("Somewhere in the desert an army vanished.", "The legend says a sandstorm.", "Could anything still lie there?")) is None  # the third line is too late
    long_q = "Why did the king of kings send fifty thousand men across the western desert to silence one small oracle?"
    assert mg.hook_text(data(long_q, "x")) is None  # a question cut short would not be the question
    assert mg.hook_text({"lines": []}) is None


def test_the_event_is_large_centred_near_the_top_and_gone_after_three_and_a_half_seconds():
    ev = [e for e in mg.graphics_events(data("Where did the army go?", "x"), DUR) if ",Hook," in e]
    assert len(ev) == 1
    assert ev[0].startswith("Dialogue: 2,0:00:00.25,0:00:03.45,Hook,") and "\\an8" in ev[0] and "WHERE DID THE ARMY GO?" in ev[0] and "\\fad(" in ev[0]
    assert any(s.startswith("Style: Hook,") for s in mg.styles((1920, 1080)))


def test_long_hooks_break_into_lines_and_the_text_cannot_open_an_override_block():
    ev = [e for e in mg.graphics_events(data("What really happened to the lost army {of} Cambyses in the desert?", "x"), DUR) if ",Hook," in e][0]
    assert "\\N" in ev and "{of}" not in ev and "of}" not in ev


def test_a_film_without_a_question_gets_no_hook_event_and_its_cards_are_unchanged():
    plain = mg.graphics_events(data("Somewhere an army vanished.", "x"), DUR)
    assert not [e for e in plain if ",Hook," in e] and [e for e in plain if ",Card," in e]


def test_a_second_pass_over_the_subtitle_file_does_not_stack_hooks(tmp_path):
    f = tmp_path / "c.ass"
    f.write_text("[Script Info]\n\n[V4+ Styles]\nStyle: Default,x\n\n[Events]\nDialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,hi\n")
    ev = mg.graphics_events(data("Where did the army go?", "x"), DUR)
    mg.add_to_ass(f, ev)
    mg.add_to_ass(f, ev)
    assert f.read_text().count(",Hook,") == 1 and f.read_text().count("Style: Hook,") == 1


def test_the_hook_has_its_own_entry_and_switch_so_every_film_gets_it_without_the_other_graphics():
    only = mg.hook_events(data("Where did the army go?", "x"))
    assert len(only) == 1 and ",Hook," in only[0]
    assert mg.hook_events({**data("Where did the army go?", "x"), "hook_text": False}) == []
    assert mg.hook_events(data("A statement.", "x")) == []


def test_the_documentary_producer_asks_for_the_hook_even_when_the_video_does_not_ask_for_graphics():
    import inspect

    import run

    src = inspect.getsource(run._produce_doc)
    assert "hook_events" in src and "graphics_events" in src
