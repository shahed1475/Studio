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
    assert "110 to 135 words" in p and "10 to 12 lines" in p and "140 to 180" not in p
