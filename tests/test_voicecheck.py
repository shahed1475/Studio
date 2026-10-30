"""The studio listens to its own narration (30 Oct 2026: nobody had ever listened to the new voice). An audio model writes down what it hears WITHOUT being shown the script, and our
code compares that with the script: a line that was cut, skipped or repeated shows as a run of missing or extra words. Single odd words (names, numbers) are leads, never proof."""
import json

import pytest

import voicecheck

SCRIPT = ("Somewhere in the Western Desert of Egypt, in 525 BC, an army of fifty thousand Persian soldiers simply vanished. "
          "The legend says Cambyses II sent them to subjugate the Oracle of Amun at the Siwa Oasis, and they were never seen again.")


def test_a_faithful_transcript_matches_and_punctuation_case_and_hyphens_do_not_matter():
    heard = ("somewhere in the western desert of egypt in 525 BC an army of fifty-thousand persian soldiers simply vanished. The legend says Cambyses II sent them to "
             "subjugate the oracle of Amun at the Siwa oasis and they were never seen again")
    r = voicecheck.compare(SCRIPT, heard)
    assert r["match"] >= 0.97 and r["gaps"] == [] and r["words"] > 30


def test_a_skipped_sentence_shows_as_a_run_of_missing_words_with_what_was_missing():
    heard = "Somewhere in the Western Desert of Egypt, in 525 BC, an army of fifty thousand Persian soldiers simply vanished."
    r = voicecheck.compare(SCRIPT, heard)
    gap = next(g for g in r["gaps"] if g["kind"] == "missing")
    assert gap["words"] >= 20 and "legend says" in gap["script"] and r["match"] < 0.7
    assert not voicecheck.ok(r)


def test_extra_words_that_were_not_in_the_script_are_found_too():
    heard = SCRIPT.replace("simply vanished.", "simply vanished. And then something else was said that is not in the script at all.")
    r = voicecheck.compare(SCRIPT, heard)
    assert any(g["kind"] == "extra" and g["words"] >= 8 for g in r["gaps"]) and not voicecheck.ok(r)


def test_a_name_heard_differently_is_a_lead_not_a_failure():
    script = SCRIPT + " Half a century later, journalist Gary Chafetz led a six-month expedition across the sand with camels and an ultra-light aircraft."
    heard = script.replace("Chafetz", "Shafets").replace("six-month", "six month")
    r = voicecheck.compare(script, heard)
    assert r["gaps"] == [] and ("chafetz", "shafets") in [tuple(x) for x in r["heard_as"]] and voicecheck.ok(r) and r["match"] > 0.97


def test_a_number_the_voice_reads_out_is_not_flagged_as_a_difference():
    r = voicecheck.compare("In 525 BC the army set out with 50,000 men.", "In five twenty five BC the army set out with fifty thousand men.")
    assert voicecheck.ok(r) and not r["heard_as"]  # digits against words are not leads: the voice speaks them, the script writes them


def test_the_verdict_needs_both_a_good_match_and_no_long_run_missing():
    assert voicecheck.ok({"match": 0.96, "gaps": []})
    assert not voicecheck.ok({"match": 0.85, "gaps": []})
    assert not voicecheck.ok({"match": 0.96, "gaps": [{"kind": "missing", "words": 6}]})
    assert voicecheck.ok({"match": 0.96, "gaps": [{"kind": "missing", "words": 4}]})  # a few words dropped is a lead for the owner, not a failed voice


def test_the_audio_is_cut_at_line_starts_into_parts_of_about_two_and_a_half_minutes():
    starts = [i * 9.0 for i in range(58)]  # a 58-line film of 9 s lines
    parts = voicecheck.parts(starts, 522.0)
    assert parts[0][2] == 0.0 and parts[-1][3] == 522.0
    assert all(abs(b[2] - a[3]) < 1e-9 for a, b in zip(parts, parts[1:]))          # no gap and no overlap
    assert [l for p in parts for l in range(p[0], p[1] + 1)] == list(range(58))       # every line is in exactly one part
    assert all(p[3] - p[2] <= 190 for p in parts) and 3 <= len(parts) <= 5
    assert voicecheck.parts([0.0, 4.0], 9.0) == [(0, 1, 0.0, 9.0)]                  # a Short is one part


# ---- the listening itself, with a fake audio model: nothing is sent anywhere and nothing is bought ----
import config
import llm
import modelcfg
import videoinspect

LINES = ["Somewhere in the Western Desert of Egypt, an army of fifty thousand Persian soldiers simply vanished.",
         "The legend says Cambyses sent them to subjugate the Oracle of Amun at the Siwa Oasis.",
         "Many Egyptologists regard the story as apocryphal, yet people have searched for the soldiers for years.",
         "So the question hangs over the dunes: could anything of those men still lie out there?"]


ACCOUNTED = []


@pytest.fixture
def world(tmp_path, monkeypatch):
    ACCOUNTED.clear()
    out = tmp_path / "output"
    folder = out / "doc-x"
    folder.mkdir(parents=True)
    (folder / "video.mp4").write_bytes(b"video")
    (folder / "meta.json").write_text(json.dumps({"title": "T", "lines": [{"text": t} for t in LINES]}))
    rows = [{"s": 0.2 + 10 * i, "e": 0.5 + 10 * i, "w": "x", "i": i} for i in range(4)]
    (folder / "words.json").write_text(json.dumps(rows))
    monkeypatch.setattr(config, "OUT", out)
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 5.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    monkeypatch.setattr(llm, "key_for", lambda model: "k")
    monkeypatch.setattr(llm, "_account", lambda *a, **k: ACCOUNTED.append(a))
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("audio_listen"): ["text", "audio"]})
    monkeypatch.setattr(videoinspect, "_video_seconds", lambda path: 40.0)
    return folder


def said(text):
    return {"choices": [{"message": {"content": json.dumps({"text": text})}, "finish_reason": "stop"}], "usage": {"cost": 0.0004}}


def test_the_model_gets_only_the_audio_never_the_script(world):
    sent = []
    got = voicecheck.listen(world, post=lambda b, k: sent.append(b) or said(" ".join(LINES)), extract=lambda v, a, b: b"mp3-bytes")
    body = sent[0]
    parts = body["messages"][0]["content"]
    audio = next(p for p in parts if p["type"] == "input_audio")
    assert audio["input_audio"]["format"] == "mp3" and body["model"] == modelcfg.get("audio_listen") and body["temperature"] == 0
    assert not any(l[:30] in json.dumps(body) for l in LINES)  # not one script line is in the request
    assert got["ok"] is True and got["parts"] == 1 and got["match"] > 0.99 and len(ACCOUNTED) == 1 and got["cost"] == pytest.approx(0.0004)


def test_a_faithful_voice_passes_and_the_result_is_kept_with_its_limits(world):
    got = voicecheck.listen(world, post=lambda b, k: said(" ".join(LINES)), extract=lambda v, a, b: b"x")
    saved = json.loads((world / "voice_check.json").read_text())
    assert saved["ok"] is True and "without being shown the script" in got["coverage"] and "only a person can" in got["coverage"] and "numbers are not compared" in got["coverage"].lower()


def test_a_skipped_line_is_reported_with_the_words_that_were_never_spoken(world):
    got = voicecheck.listen(world, post=lambda b, k: said(" ".join([LINES[0], LINES[2], LINES[3]])), extract=lambda v, a, b: b"x")
    assert got["ok"] is False
    gap = next(g for g in got["gaps"] if g["kind"] == "missing")
    assert "legend says" in gap["script"] and gap["words"] >= 6


def test_a_part_that_cannot_be_cut_or_transcribed_is_named_and_a_total_failure_is_an_error(world):
    got = voicecheck.listen(world, post=lambda b, k: pytest.fail("no audio, nothing to send"), extract=lambda v, a, b: None)
    assert "no part" in got["error"] and got["failed_parts"] == [1]
    got = voicecheck.listen(world, post=lambda b, k: {"choices": [{"message": {"content": "not json at all"}, "finish_reason": "stop"}]}, extract=lambda v, a, b: b"x")
    assert "error" in got


def test_nothing_is_sent_for_a_video_that_is_not_ours_or_without_an_audio_model_or_credit(world, tmp_path, monkeypatch):
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    (elsewhere / "video.mp4").write_bytes(b"x")
    nope = lambda b, k: pytest.fail("must not be sent")
    assert "own videos" in voicecheck.listen(elsewhere, post=nope, extract=lambda v, a, b: b"x")["error"]
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("audio_listen"): ["text", "image"]})
    assert "audio" in voicecheck.listen(world, post=nope, extract=lambda v, a, b: b"x")["error"]
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("audio_listen"): ["text", "audio"]})  # the model is fine now: only the cap stops it
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 1.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 1.0)
    assert "cap" in voicecheck.listen(world, post=nope, extract=lambda v, a, b: b"x")["error"]


def test_a_model_that_raises_is_reported_never_raised(world):
    def boom(b, k):
        raise RuntimeError("502 bad gateway")
    got = voicecheck.listen(world, post=boom, extract=lambda v, a, b: b"x")
    assert "502" in got["error"]


def test_a_real_ffmpeg_cut_makes_a_small_mono_mp3(tmp_path):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    src = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=6", "-c:a", "aac", str(src)], check=True)
    audio = voicecheck._extract(src, 1.0, 4.0)
    assert audio and audio[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") and len(audio) < 40_000


def test_accented_letters_are_compared_as_their_plain_letters():
    r = voicecheck.compare("The Hungarian adventurer László Almásy, and Hŏ Kyun, crossed the Sitra Oasis near Dakhla.", "The Hungarian adventurer Laszlo Almasy and Ho Kyun crossed the Sitra Oasis near Dakhla.")
    assert r["gaps"] == [] and r["match"] > 0.97


def test_little_words_that_differ_are_not_leads():
    r = voicecheck.compare("They found a tomb in the desert, with bones of the soldiers and a bracelet in the sand.", "They found the tomb in a desert, with bones of the soldiers and the bracelet in the sand.")
    assert r["heard_as"] == []


def test_quotation_marks_around_words_are_not_part_of_the_words():
    r = voicecheck.compare("Korea's 'John Doe' novel may have an author named Ho Kyun, said the old book.", "Korea's John Doe novel may have an author named Ho Kyun said the old book")
    assert r["heard_as"] == [] and r["match"] > 0.99
    assert voicecheck.words("the 'quoted' word and kaper's name") == ["the", "quoted", "word", "and", "kaper's", "name"]


def test_a_short_script_full_of_names_is_judged_on_gaps_and_a_slightly_lower_match():
    """30 Oct 2026, the Hong Gildong Short: 89.4 percent, no gap, only Korean names heard differently: a false alarm at the film's 90 percent bar."""
    assert voicecheck.ok({"match": 0.894, "gaps": [], "words": 134})
    assert not voicecheck.ok({"match": 0.80, "gaps": [], "words": 134})
    assert not voicecheck.ok({"match": 0.894, "gaps": [{"kind": "missing", "words": 7}], "words": 134})   # a real hole still fails
    assert not voicecheck.ok({"match": 0.894, "gaps": [], "words": 1300})                                 # a long film keeps the 90 percent bar
