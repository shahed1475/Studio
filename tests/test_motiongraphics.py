"""2D animated graphics for a documentary (29 Oct 2026), written as extra events of the burned-in ASS subtitles: a chapter title card (a bar that wipes in, the chapter's
own title, a fade) and a date badge when a line names a year. Everything shown is text already in the script or the chapter list; nothing is added or worked out."""
import re

import motiongraphics as mg

SIZE = (1920, 1080)


def doc(lines, chapters):
    return {"lines": [{"text": t} for t in lines], "chapters": chapters}


def start_of(event):
    m = re.match(r"Dialogue: \d+,(\d+):(\d\d):(\d\d)\.(\d\d),", event)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 100


def end_of(event):
    m = re.match(r"Dialogue: \d+,[^,]+,(\d+):(\d\d):(\d\d)\.(\d\d),", event)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 100


def test_year_labels_come_only_from_a_real_year_in_the_line():
    assert mg.year_label("The army vanished in 525 BC, somewhere in the desert.") == "525 BC"
    assert mg.year_label("Cyrus made him co-ruler in 530 BCE, then marched away.") == "530 BCE"
    assert mg.year_label("In January 1933, British officer Orde Wingate went looking.") == "1933"
    assert mg.year_label("He argued in 2015 that it was an ambush.") == "2015"
    assert mg.year_label("Bone fragments dated to 1500 BC, a thousand years too early.") == "1500 BC"
    assert mg.year_label("Fifty thousand men, or 50,000 in some tellings, marched out.") is None
    assert mg.year_label("The brothers made five shockumentaries in the 1970s.") is None
    assert mg.year_label("They found roughly 500 tumuli and no artifacts.") is None
    assert mg.year_label("A thousand years passed with nothing found.") is None


def test_a_chapter_card_appears_when_its_chapter_starts_and_the_first_chapter_has_none():
    lines = ["Hook line."] + ["Line."] * 9
    d = doc(lines, [{"start_line": 0, "title": "The Legend"}, {"start_line": 4, "title": "Searching the Desert"}])
    ev = mg.graphics_events(d, [2.0] * 10, SIZE)
    cards = [e for e in ev if "Searching the Desert" in e]
    assert len(cards) == 1 and "The Legend" not in "".join(ev) and "CHAPTER 2" in cards[0]
    assert abs(start_of(cards[0]) - (4 * 2.0 + mg.CARD_DELAY)) < 0.02 and 3 <= end_of(cards[0]) - start_of(cards[0]) <= 4.5
    assert any("\\clip" in e and "\\p1" in e for e in ev)  # the bar that wipes in


def test_a_date_badge_shows_the_year_the_line_names_but_never_over_the_hook_or_a_card():
    lines = ["Somewhere in 525 BC an army vanished."] + ["Plain line."] * 5 + ["In 1983 a journalist led an expedition.", "Plain.", "By 2015 a scholar argued otherwise.", "Plain."]
    d = doc(lines, [{"start_line": 0, "title": "A"}, {"start_line": 6, "title": "B"}])
    ev = mg.graphics_events(d, [3.0] * 10, SIZE)
    badges = [e for e in ev if "1983" in e or "2015" in e or "525 BC" in e]
    assert not any("525 BC" in e for e in ev)  # the hook is left alone
    assert not any("1983" in e for e in ev)  # a chapter card is showing on that line
    assert len(badges) == 1 and "2015" in badges[0]
    assert start_of(badges[0]) >= mg.HOOK_CLEAR


def test_badges_keep_a_gap_and_texts_cannot_break_the_subtitle_format():
    lines = ["Plain."] * 3 + ["In 1933 one.", "In 1983 two.", "In 2000 three."]
    d = doc(lines, [{"start_line": 0, "title": "Odd {\\b1}title\\N"}])
    ev = [e for e in mg.graphics_events(d, [3.0] * 6, SIZE) if "Badge" in e]
    starts = sorted(start_of(e) for e in ev)
    assert all(b - a >= mg.BADGE_GAP for a, b in zip(starts, starts[1:]))
    cards = mg.graphics_events(doc(lines, [{"start_line": 0, "title": "x"}, {"start_line": 2, "title": "Odd {\\b1}title\\N"}]), [3.0] * 6, SIZE)
    assert "Odd b1title" in "".join(cards) and "{\\b1}title" not in "".join(cards)


def test_adding_to_a_subtitle_file_keeps_what_was_there_and_adds_styles_and_events(tmp_path):
    f = tmp_path / "c.ass"
    f.write_text("[Script Info]\nPlayResX: 1920\n\n[V4+ Styles]\nFormat: Name\nStyle: Sub,DejaVu Sans\n\n[Events]\nFormat: Layer,Start,End,Style,Text\nDialogue: 0,0:00:01.00,0:00:02.00,Sub,Hello\n")
    ev = mg.graphics_events(doc(["Hook."] + ["In 2015 it was argued."] * 4, [{"start_line": 0, "title": "A"}]), [3.0] * 5, SIZE)
    mg.add_to_ass(f, ev, SIZE)
    text = f.read_text()
    assert "Dialogue: 0,0:00:01.00,0:00:02.00,Sub,Hello" in text and "Style: Card," in text and "Style: Badge," in text
    assert text.index("Style: Card,") < text.index("[Events]") and text.count("[Events]") == 1
    assert "2015" in text
    mg.add_to_ass(f, ev, SIZE)  # a second call does not add the styles twice
    assert f.read_text().count("Style: Card,") == 1
