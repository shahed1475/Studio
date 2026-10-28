import scriptgen


def test_a_short_is_written_to_about_a_minute(monkeypatch):
    """Competitor Shorts with 20,000+ views run about 51 seconds at the median (27 Oct 2026 research); ours ran 1:02 to 1:24 at 140 to 180 words."""
    asked = []

    def chat(prompt, *a, **k):
        asked.append(prompt)
        return {"title": "t", "description": "d", "tags": [], "anchors": [], "lines": [{"text": f"A line number {i} with exactly ten words in it ok.", "visual": "x"} for i in range(11)]}

    monkeypatch.setattr(scriptgen, "_script_chat", chat)
    scriptgen.script("The Thunderbird", grounded=None)
    p = asked[0]
    lo, hi = scriptgen.short_word_range()
    assert f"{lo} to {hi} words" in p and "10 to 12 lines" in p and "140 to 180" not in p and "110 to 135" not in p


def test_a_shorts_word_budget_fits_the_length_target_once_the_pauses_are_counted(monkeypatch):
    """28 Oct 2026: 14 of 15 Shorts ran 60 to 84 s against a 35 to 58 s target (110 to 135 words plus 0.6 s after each of 11 lines)."""
    import editprofile
    import rulesfile
    top = rulesfile.get("benchmarks", "shorts_max_seconds")
    for pause_ms in (100, 250, 600, 900):
        pause = editprofile.short_pause({"sentence_pause_ms": pause_ms})
        lo, hi = scriptgen.short_word_range(11, pause)
        assert hi / scriptgen.WORDS_PER_SECOND + 11 * pause <= top, (pause_ms, hi)
        assert lo < hi
    assert editprofile.short_pause({"sentence_pause_ms": 900}) == 0.25 and editprofile.short_pause({"sentence_pause_ms": 100}) == 0.1
    assert editprofile.validate({"target_lufs": -18.0}) == {} and editprofile.validate({"target_lufs": -16.0}) == {"target_lufs": -16.0}
