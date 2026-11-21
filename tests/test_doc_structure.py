"""A documentary has the owner's shape and length (30 Oct 2026): first the hook, then curiosity, then the story, and it finishes with value; 8 to 10 minutes. The writer's 50-line cap
had made the Cambyses documentary 7.6 minutes."""
import pytest

import reviewer
import scriptgen


def test_the_outline_prompt_asks_for_hook_then_curiosity_then_story_then_a_closing_chapter_of_value_in_the_owners_length(monkeypatch):
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        raise RuntimeError("stop after the outline")

    monkeypatch.setattr(scriptgen, "_script_chat", fake)
    with pytest.raises(RuntimeError):
        scriptgen.doc_script("The Lost Army", grounded="Some article text.")
    low = prompts[0].lower()
    lo, hi = scriptgen.DOC_MINUTES
    assert f"{lo:g} to {hi:g} minute" in low and "8 to 10 minute" not in low  # the owner's rules.json length (20 to 26 since 20 Nov 2026), not the old 8 to 10
    marks = ["chapter 1 is the hook", "chapter 2 builds curiosity", "middle chapters are the story", "last chapter gives value"]
    assert all(m in low for m in marks) and [low.index(m) for m in marks] == sorted(low.index(m) for m in marks)  # the order the owner asked for
    assert "promise" in low and "weigh" in low  # the bridge promises what the film will answer; the last chapter teaches how to weigh such a claim
    assert "no thanks, no subscribe" in low  # unchanged: it still ends on the story


def test_the_length_comes_from_the_owners_setting_and_the_old_setting_still_gives_the_old_numbers():
    import rulesfile

    assert scriptgen.DOC_MINUTES == (rulesfile.get("benchmarks", "long_min_minutes"), rulesfile.get("benchmarks", "long_max_minutes"))
    assert scriptgen.doc_budget(8, 10) == {"min_lines": 42, "max_lines": 58, "words": 1150, "chapters": (6, 9), "per": (5, 7), "line_words_max": 30}
    long_film = scriptgen.doc_budget(20, 26)
    assert long_film["max_lines"] <= scriptgen.LINE_CAP == 100 and long_film["min_lines"] >= 80  # one picture a line: about a free day of drawings plus real photos
    assert 20 <= long_film["words"] / scriptgen.DOC_WORDS_PER_MINUTE <= 26


def test_the_line_cap_leaves_room_for_the_owners_length_and_every_shape_stays_inside_it():
    (c0, c1), (p0, p1) = scriptgen.DOC_CHAPTERS, scriptgen.DOC_PER
    for topic in ("The Pied Piper", "The Oracle of Delphi", "Lost Army of Cambyses", "Srivijaya", "The Minotaur", "Roanoke", "Atlantis", "The Bell Witch"):
        chapters, per = scriptgen.shape_for(topic)
        assert scriptgen.MIN_DOC_LINES <= chapters * per <= scriptgen.MAX_DOC_LINES and c0 <= chapters <= c1 and p0 <= per <= p1, topic
    assert scriptgen.MAX_DOC_LINES * scriptgen.LINE_WORDS_MAX >= scriptgen.DOC_WORDS_TARGET  # the longest lines can carry the word budget


def doc(seconds):
    return {"format": "doc", "description": "d", "lines": [{"text": "A cold open that raises the question?"}] * 3}, {"duration": seconds}


def test_a_documentary_outside_the_owners_length_gets_a_warning_and_one_inside_does_not():
    lo, hi = (round(m * 60) for m in scriptgen.DOC_MINUTES)  # 1,200 to 1,560 seconds since 20 Nov 2026
    for seconds, ok in ((lo - 60, False), (lo, True), ((lo + hi) // 2, True), (hi, True), (hi + 1, False), (540, False)):
        meta, probe = doc(seconds)
        row = {c["name"]: c for c in reviewer.generator_checks(meta, probe)}["doc_length"]
        assert row["ok"] is ok and row["severity"] == "warn", seconds  # a warning, never a block: the hard limit is limits.doc_duration_s
    meta, probe = doc(lo - 60)
    assert str(lo) in {c["name"]: c for c in reviewer.generator_checks(meta, probe)}["doc_length"]["detail"]


def test_a_twenty_six_minute_documentary_is_inside_the_reviewers_hard_limit():
    lo, hi = reviewer.LIMITS["doc"]["duration"]
    assert lo <= 20 * 60 and 26 * 60 <= hi  # 180 to 1,800 seconds: the long film is never blocked for its length


def test_a_short_gets_no_documentary_length_check():
    meta = {"format": "short", "description": "d", "lines": [{"text": "Why?"}] * 3}
    assert "doc_length" not in {c["name"] for c in reviewer.generator_checks(meta, {"duration": 45})}


def test_every_shape_has_enough_lines_and_a_word_budget_that_lands_inside_the_owners_length():
    for t in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "Antikythera mechanism", "The Pied Piper"):
        c, per = scriptgen.shape_for(t)
        lo, hi = scriptgen.line_words(c, per)
        mid_total = c * per * (lo + hi) / 2
        assert c * per >= scriptgen.MIN_DOC_LINES and 16 <= lo < hi <= scriptgen.LINE_WORDS_MAX
        minutes = mid_total / scriptgen.DOC_WORDS_PER_MINUTE
        assert scriptgen.DOC_MINUTES[0] <= minutes <= scriptgen.DOC_MINUTES[1], (t, mid_total, minutes)


def test_the_word_rate_is_the_one_measured_on_a_real_long_film_so_a_script_that_passes_the_minimum_really_lasts_20_minutes():
    """21 Nov 2026: 2,839 words passed the 20-minute minimum at the old 127.8 words a minute and made a 19.1-minute film (1,148.7 s measured)."""
    measured_rate = 2839 / (1148.7 / 60)
    assert abs(scriptgen.DOC_WORDS_PER_MINUTE - measured_rate) < 0.5
    if scriptgen.DOC_MINUTES[0] >= 20:
        assert scriptgen.min_doc_words() / measured_rate >= scriptgen.DOC_MINUTES[0] - 0.01
        assert 2839 < scriptgen.min_doc_words()  # the Seven Sleepers script would now be asked to grow before any voice or picture is made
