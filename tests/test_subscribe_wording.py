"""A Short invites people to SUBSCRIBE, never to "follow" (29 Oct 2026): YouTube has subscribers, not followers. The writer prompt asked for "an invitation to follow",
so nine Shorts ended with "Follow for the next story." The prompt is fixed, the last line is corrected by a rule before any voice or caption is made, the reviewer warns."""
import pytest

import reviewer
import run
import scriptgen


def lines(*texts):
    return [{"text": t, "visual": "v"} for t in texts]


# The real closing lines of the nine Shorts that went out or were drafted with "follow" (read from the server on 29 Oct 2026), and what they become.
REAL = {
    "Follow for the next story, and listen for the rain.": "Subscribe for the next story, and listen for the rain.",
    "Follow along, and I'll tell you the next story.": "Subscribe, and I'll tell you the next story.",
    "If this kept you wondering, follow along for the next story.": "If this kept you wondering, subscribe for the next story.",
    "If this kind of story calls to you, follow for the next one.": "If this kind of story calls to you, subscribe for the next one.",
    "Next time thunder rolls, remember the old stories. Follow for the next story.": "Next time thunder rolls, remember the old stories. Subscribe for the next story.",
    "Follow along, and I will tell you the next story soon.": "Subscribe, and I will tell you the next story soon.",
    "Follow for the next story, and let the old tales keep you company.": "Subscribe for the next story, and let the old tales keep you company.",
    "Follow along for the next story, and keep wondering what those pages say.": "Subscribe for the next story, and keep wondering what those pages say.",
    "So was it a fox, or just the dark? Follow for the next story.": "So was it a fox, or just the dark? Subscribe for the next story.",
    "Hit follow for more of history's unsolved mysteries.": "Hit subscribe for more of history's unsolved mysteries.",
}


@pytest.mark.parametrize("before,after", list(REAL.items()))
def test_every_real_closing_that_said_follow_now_says_subscribe(before, after):
    got, n = scriptgen.subscribe_invitation(lines("A hook.", "A middle.", before))
    assert got[-1]["text"] == after and n == 1 and got[-1]["visual"] == "v"


def test_other_ways_to_ask_are_handled_too():
    fix = lambda t: scriptgen.subscribe_invitation(lines("x", t))[0][-1]["text"]
    assert fix("Follow us for the next story.") == "Subscribe for the next story."
    assert fix("Follow this channel for more old tales.") == "Subscribe to this channel for more old tales."
    assert fix("Please follow our channel for more stories.") == "Please subscribe to our channel for more stories."
    assert fix("FOLLOW for more!") == "SUBSCRIBE for more!"


def test_a_story_line_that_uses_the_word_follow_is_never_touched():
    story = ["The children follow the piper out of town.", "Pick up the comb and take it home; Mammy Water will follow, but keep it secret in this story.",
             "Hunters tried to follow the tracks for more than a mile.", "Why did the children follow?"]
    for t in story:
        assert scriptgen.subscribe_invitation(lines("x", t)) == (lines("x", t), 0)


def test_only_the_last_line_is_changed_and_a_second_pass_changes_nothing():
    ls = lines("Follow for the next story.", "The children follow the piper.", "Follow for the next story.")
    got, n = scriptgen.subscribe_invitation(ls)
    assert [l["text"] for l in got] == ["Follow for the next story.", "The children follow the piper.", "Subscribe for the next story."] and n == 1
    assert scriptgen.subscribe_invitation(got) == (got, 0)
    assert ls[-1]["text"] == "Follow for the next story."  # the input is not changed in place


def test_the_clipped_shorts_closings_and_empty_scripts_are_left_alone():
    for closing in ["The full story of Hong Gildong is on our channel.", "Watch the complete Mami Wata documentary on our channel.", "Stay a while: our channel is full of stories like Delphi."]:
        assert scriptgen.subscribe_invitation(lines("x", closing))[1] == 0
    assert scriptgen.subscribe_invitation([]) == ([], 0)


def test_the_writer_is_asked_to_say_subscribe_and_never_follow():
    low = scriptgen.short_prompt("A topic").lower()
    assert "invitation to subscribe" in low and "never 'follow'" in low
    assert "invitation to follow" not in low


def test_a_new_script_comes_out_with_subscribe(monkeypatch):
    body = [{"text": f"Line {i} of the old story is told with eight plain words here.", "visual": "v"} for i in range(10)]
    body.append({"text": "Follow for the next story.", "visual": "v"})
    monkeypatch.setattr(scriptgen, "_script_chat", lambda prompt: {"title": "T", "description": "d", "tags": [], "anchors": [], "lines": body})
    out = scriptgen.script("A topic")
    assert out["lines"][-1]["text"] == "Subscribe for the next story."


def test_every_render_path_voices_the_corrected_line(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(run.config, "OUT", tmp_path)
    monkeypatch.setattr(run.config, "PEXELS_KEY", "")

    def narrate(ls, work, *a, **k):
        seen["voiced"] = list(ls)
        raise RuntimeError("reached voice")

    monkeypatch.setattr(run.tts, "narrate", narrate)
    data = {"title": "T", "topic": "t", "anchors": [], "lines": [{"text": "x", "visual": "y"}] * 3 + [{"text": "Follow for the next story.", "visual": "y"}]}
    with pytest.raises(RuntimeError, match="reached voice"):
        run._produce_short(data, "t", requeue=False)
    assert seen["voiced"][-1] == "Subscribe for the next story." and data["lines"][-1]["text"] == "Subscribe for the next story."


def test_the_reviewer_warns_about_a_follow_invitation_and_is_quiet_for_subscribe():
    def check(last):
        meta = {"format": "short", "description": "A hook first.", "lines": [{"text": t} for t in ("No one has ever found the army that vanished.", "Only the desert knows, and it has never said.", last)]}
        return {c["name"]: c for c in reviewer.generator_checks(meta, {"duration": 50})}["invite_wording"]
    bad, good = check("Follow for the next story."), check("Subscribe for the next story.")
    assert not bad["ok"] and bad["severity"] == "warn" and "subscribe" in bad["detail"].lower()
    assert good["ok"] and check("The full story is on our channel.")["ok"]


def test_a_documentary_gets_no_invitation_check():
    meta = {"format": "doc", "description": "d", "lines": [{"text": "Follow for the next story."}] * 3}
    assert "invite_wording" not in {c["name"] for c in reviewer.generator_checks(meta, {"duration": 400})}


def test_a_follow_invitation_still_gets_the_invitation_delivery_and_the_payoff_check():
    import tts
    ls = ["Did a sandstorm swallow them?", "Herodotus wrote that it did.", "Follow for the next story."]
    assert tts.line_prosody("energetic", ls[-1], 2, 3) == tts.line_prosody("energetic", "Subscribe for the next story.", 2, 3)
    meta = {"format": "short", "description": "d", "lines": [{"text": t} for t in ls]}
    assert {c["name"]: c for c in reviewer.generator_checks(meta, {"duration": 50})}["short_payoff"]["ok"]
