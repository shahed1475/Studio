import re

import subtitles


def words(text, line=0, start=0.0, per=0.4):
    out, t = [], start
    for w in text.split():
        out.append({"s": t, "e": t + per, "w": w, "i": line})
        t += per
    return out


def lines_of(cue):
    return cue["text"].split("\n")


def test_cues_break_at_line_boundaries():
    ws = words("The town was quiet.", 0) + words("Then the music began.", 1, start=2.0)
    cues = subtitles.build_cues(ws)
    assert [c["text"].replace("\n", " ") for c in cues] == ["The town was quiet.", "Then the music began."]


def test_long_line_split_into_two_line_cues():
    ws = words(" ".join(f"word{i:02d}" for i in range(30)), 0)
    cues = subtitles.build_cues(ws)
    assert len(cues) >= 2
    for c in cues:
        assert len(lines_of(c)) <= 2 and all(len(l) <= 42 for l in lines_of(c))


def test_cue_never_longer_than_six_seconds():
    ws = words("slow " * 40, 0, per=0.9)
    assert all(c["end"] - c["start"] <= 6.0 + 1e-6 for c in subtitles.build_cues(ws))


def test_cues_ordered_and_not_overlapping_and_positive():
    ws = words("one two three four five six seven eight nine ten eleven twelve", 0) + words("Next sentence here.", 1, start=5.0)
    cues = subtitles.build_cues(ws)
    for a, b in zip(cues, cues[1:]):
        assert a["end"] <= b["start"] + 1e-9
    assert all(c["end"] > c["start"] for c in cues)


def test_minimum_duration_one_second_when_room():
    cues = subtitles.build_cues(words("Hi.", 0, per=0.2) + words("Much later words arrive.", 1, start=10.0))
    assert cues[0]["end"] - cues[0]["start"] >= 1.0


def test_srt_format():
    assert subtitles.to_srt([{"start": 0.0, "end": 1.5, "text": "Hello there"}]) == "1\n00:00:00,000 --> 00:00:01,500\nHello there\n\n"


def test_ass_has_playres_and_dialogue():
    ass = subtitles.to_ass([{"start": 0.0, "end": 1.5, "text": "Hello\nthere"}], (1920, 1080))
    assert "PlayResX: 1920" in ass and "PlayResY: 1080" in ass
    assert re.search(r"Dialogue: 0,0:00:00\.00,0:00:01\.50,Sub,Hello\\Nthere", ass)


def test_timings_match():
    ws = words("a b c", 0)
    assert subtitles.timings_match(ws, 1.2 + 0.5) is True
    assert subtitles.timings_match(ws, 30.0) is False


def test_punctuation_is_restored_from_the_narration_line_when_word_counts_match():
    ws = words("In the heart of medieval Germany a town once thrived", 0)
    got = subtitles.with_punctuation(ws, ["In the heart of medieval Germany, a town once thrived."])
    assert [w["w"] for w in got][5:7] == ["Germany,", "a"] and got[-1]["w"] == "thrived."
    assert [w["w"] for w in ws][5] == "Germany"  # the input is not changed
    odd = subtitles.with_punctuation(ws, ["A line with a different number of words."])
    assert [w["w"] for w in odd] == [w["w"] for w in ws]


def test_cues_break_after_a_clause_instead_of_in_the_middle():
    line = "Historians disagree on what happened, but the tale of his song has echoed through time."
    ws = subtitles.with_punctuation(words(line.replace(",", "").replace(".", ""), 0, per=0.3), [line])
    cues = subtitles.build_cues(ws)
    assert cues[0]["text"].replace("\n", " ").endswith("happened,")


def _cap_times(ass):
    import re
    out = []
    for m in re.finditer(r"Dialogue: 0,(\d+):(\d+):(\d+)\.(\d+),(\d+):(\d+):(\d+)\.(\d+),Cap,", ass):
        g = [int(x) for x in m.groups()]
        out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 100, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 100))
    return out


def test_two_word_caption_groups_never_show_at_the_same_time():
    import tts
    # the voice's timings abut: the last word of a group ends exactly where the next group's first word starts, and the group's tail (+0.15 s) overlapped it
    words = [(21.0, 21.9, "ancient", 1), (21.9, 22.8, "manuscript", 1), (22.8, 23.6, "deciphered", 1), (23.6, 24.4, "completely", 1), (24.4, 25.0, "today", 1)]
    for motion in (1, 2):
        times = _cap_times(tts._ass(words, motion))
        assert times and all(b <= nxt[0] + 1e-9 for (a, b), nxt in zip(times, times[1:]))
    times = _cap_times(tts._ass(words, 0).replace("Dialogue: 0,", "Dialogue: 0,"))
    assert all(b <= nxt[0] + 1e-9 for (a, b), nxt in zip(times, times[1:]))
