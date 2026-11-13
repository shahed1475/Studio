"""13 Nov 2026: with free models only, three Short scripts in a row came back 84 to 87 words against a 100 word floor and the retry repeated the same prompt. A retry now says what was wrong."""
import scriptgen
import run


def lines(n, words):
    return [{"text": " ".join(["word"] * words), "visual": "a b"} for _ in range(n)]


def test_script_adds_the_retry_note_to_the_prompt(monkeypatch):
    seen = []
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p: seen.append(p) or {"title": "t", "lines": lines(11, 12)})
    scriptgen.script("topic", note="Your last attempt was rejected: 87 words (need 100).")
    assert "Your last attempt was rejected: 87 words (need 100)." in seen[0]
    seen.clear()
    scriptgen.script("topic")
    assert "rejected" not in seen[0]


def test_a_failed_short_script_is_asked_again_with_the_reason_and_a_word_target(monkeypatch):
    import wikipedia

    notes = []
    monkeypatch.setattr(wikipedia, "facts_for", lambda topic, chars=0: None)
    monkeypatch.setattr(run, "_best_topic", lambda kind: "t")

    def fake_script(topic, grounded=None, note=""):
        notes.append(note)
        return {"title": "t", "lines": lines(11, 8), "anchors": []}

    def gate(data, source, topic):
        if len(notes) < 2:
            raise ValueError("script review holds this script: script_length: 87 words (need 100)")
        return data

    monkeypatch.setattr(scriptgen, "script", fake_script)
    monkeypatch.setattr(run, "_script_gate", gate)
    monkeypatch.setattr(run, "_produce_short", lambda data, topic, **k: "made")
    assert run._cmd_make("topic") == "made"
    lo, hi = scriptgen.short_word_range()
    assert notes[0] == "" and "87 words (need 100)" in notes[1] and str(hi) in notes[1] and "count" in notes[1].lower()
