import json

import pytest
import reviewer
import scriptgen


def L(*texts):
    return [{"text": t, "visual": "v"} for t in texts]


def test_headings_and_label_sentences_are_taken_out_of_the_narration():
    lines = L("The sanctuary stood on the slope of Mount Parnassus above the valley.",
              "Chapter 5: The Temples of Apollo",
              "Mythical temples once stood on the site, starting with one built of olive branches.",
              "Chapter 6 examines the artifacts in the museum, such as the Charioteer of Delphi.",
              "Part 2: The first temple was built in the seventh century BC by Greek builders.",
              "The Pythia was the priestess of Apollo at the oracle.")
    chapters = [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 1}, {"title": "c", "start_line": 3}, {"title": "d", "start_line": 5}]
    out, ch, n = scriptgen.strip_labels(lines, chapters)
    assert [l["text"] for l in out] == [
        "The sanctuary stood on the slope of Mount Parnassus above the valley.",
        "Mythical temples once stood on the site, starting with one built of olive branches.",
        "The first temple was built in the seventh century BC by Greek builders.",
        "The Pythia was the priestess of Apollo at the oracle."]
    assert n == 3
    assert [c["start_line"] for c in ch] == [0, 1, 2, 3]  # every chapter still starts on a line that exists, in order


def test_normal_lines_that_only_mention_a_part_or_chapter_stay():
    lines = L("Part of the temple still stands above the village of Kastri today.",
              "The chapter of the monks in the town kept the records for many years.")
    out, ch, n = scriptgen.strip_labels(lines, [{"title": "a", "start_line": 0}])
    assert out == lines and n == 0 and ch == [{"title": "a", "start_line": 0}]


def test_a_chapter_whose_lines_all_go_is_left_out_not_pointed_at_a_wrong_line():
    lines = L("An opening line about the oracle that is long enough to stay.", "Chapter 2: Heading only", "Chapter 2 continues the story of the temple.",
              "A later line about the museum that is long enough to stay.")
    chapters = [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 1}, {"title": "c", "start_line": 3}]
    out, ch, n = scriptgen.strip_labels(lines, chapters)
    assert len(out) == 2 and [c["title"] for c in ch] == ["a", "c"] and [c["start_line"] for c in ch] == [0, 1]


def test_the_reviewer_blocks_a_script_with_a_label_line():
    meta = {"lines": L("The oracle spoke.", "Chapter 5: The Temples of Apollo", "More story here.")}
    bad = reviewer.label_check(meta)
    assert bad["name"] == "script_labels" and bad["ok"] is False and bad["severity"] == "block" and "Chapter 5" in bad["detail"]
    good = reviewer.label_check({"lines": L("The oracle spoke.")})
    assert good["ok"] is True
