"""Dead air between the lines of an energetic Short (29 Oct 2026). The voice service ends every line with silence after the last spoken word: 0.83 s for the energetic
voice (measured: last word ends at 4.66 s, the file runs to 5.52 s). The renderer added its own breath on top, so the Cambyses Short had 1.1 to 1.2 s of no voice, no caption
and an unchanging picture before every line, the longest (1.2 s) just before its last line at 48 s. The styled voice now keeps only a short tail after the last word."""
import json
import subprocess

import pytest

import studiochecks
import tts


def _tone_then_silence(path, tone=1.0, silence=1.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={tone}", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
                    "-filter_complex", f"[0:a]aresample=44100[a];[1:a]atrim=0:{silence}[s];[a][s]concat=n=2:v=0:a=1[o]", "-map", "[o]", str(path)], check=True)


def test_a_line_keeps_only_a_short_tail_after_its_last_word_and_never_gains_time():
    assert tts.line_length(5.52, [(0.1, 4.662, "rebellion.")], 0.25, 0.15) == pytest.approx(4.662 + 0.15 + 0.25)
    assert tts.line_length(4.70, [(0.1, 4.662, "rebellion.")], 0.25, 0.15) == pytest.approx(4.70 + 0.25)  # the file's own tail is already shorter: keep it, never pad
    assert tts.line_length(5.52, [(0.1, 4.662, "x")], 0.25, None) == pytest.approx(5.52 + 0.25)  # no tail setting: exactly as before
    assert tts.line_length(5.52, [], 0.25, 0.15) == pytest.approx(5.52 + 0.25)  # no word timings: nothing to measure the speech by, keep the whole file


def test_only_the_energetic_voice_has_a_tail_setting_and_the_default_voice_is_unchanged(tmp_path, monkeypatch):
    assert 0 < tts.VOICE_STYLES["energetic"]["tail"] <= 0.3

    async def fake(text, mp3, prosody=None):
        return [(0.0, 0.5, "hi")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    monkeypatch.setattr(tts, "_duration", lambda p: 1.0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    _, _, plain = tts.narrate(["one", "two"], tmp_path, pause=0.25)
    assert plain == [1.25, 1.25]  # default voice: the whole file plus the breath, as before
    _, _, lively = tts.narrate(["one", "two"], tmp_path, pause=0.25, style="energetic")
    tail = tts.VOICE_STYLES["energetic"]["tail"]
    assert lively == [pytest.approx(0.5 + tail + 0.25)] * 2


def test_the_real_narration_of_a_styled_short_is_shorter_by_the_silent_tails_and_words_stay_in_step(tmp_path, monkeypatch):
    tone = tmp_path / "tone.mp3"
    _tone_then_silence(tone)

    async def fake(text, mp3, prosody=None):
        mp3.write_bytes(tone.read_bytes())
        return [(0.05, 1.0, "hello")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    out, _, durations = tts.narrate(["one", "two", "three"], tmp_path / "w", pause=0.25, style="energetic")
    tail = tts.VOICE_STYLES["energetic"]["tail"]
    assert durations == [pytest.approx(1.0 + tail + 0.25)] * 3
    length = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)]).decode())
    assert length == pytest.approx(sum(durations), abs=0.1)  # the audio is as long as the scene times the renderer will use
    words = json.loads((tmp_path / "w" / "words.json").read_text())
    assert [round(w["s"], 2) for w in words] == [0.05, round(durations[0] + 0.05, 2), round(sum(durations[:2]) + 0.05, 2)]


def _words(*lines):
    """lines: (start, end) of each line's speech."""
    return [{"s": s, "e": e, "w": "w", "i": i} for i, (s, e) in enumerate(lines)]


def test_dead_air_between_lines_of_a_short_is_warned_about_and_a_tight_one_is_not(tmp_path):
    def rows(words, fmt="short", duration=20.0):
        (tmp_path / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nhello there\n")
        (tmp_path / "words.json").write_text(json.dumps(words))
        return {r["name"]: r for r in studiochecks.caption_checks(tmp_path, {"format": fmt, "lines": [{"text": "hello there"}]}, duration)}

    loose = rows(_words((0, 4), (5.2, 9), (10.2, 14)))  # 1.2 s of silence before each line: the Cambyses Short
    assert not loose["no_dead_air"]["ok"] and loose["no_dead_air"]["severity"] == "warn" and "1.2" in loose["no_dead_air"]["detail"]
    tight = rows(_words((0, 4), (4.5, 9), (9.5, 14)))
    assert tight["no_dead_air"]["ok"]
    assert "no_dead_air" not in rows(_words((0, 4), (5.2, 9)), fmt="doc")  # a documentary keeps its own, longer pauses


# ---- a picture that stands still (29 Oct 2026): the other cause of "lag" ----
def _clip(path, still_seconds, moving_seconds=2.0):
    """A test video: `still_seconds` of one unchanging picture, then a moving one."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x335577:s=160x90:r=30:d={still_seconds}", "-f", "lavfi", "-i", f"testsrc2=s=160x90:r=30:d={moving_seconds}",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[o]", "-map", "[o]", "-pix_fmt", "yuv420p", "-c:v", "libopenh264" if "libx264" not in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout else "libx264", str(path)], check=True)


def test_a_picture_frozen_for_long_is_found_and_a_moving_one_is_not(tmp_path):
    still, moving = tmp_path / "still.mp4", tmp_path / "moving.mp4"
    _clip(still, 3.0)
    _clip(moving, 0.0 + 0.1)
    found = studiochecks.frozen_stretches(still)
    assert found and found[0] >= 2.5
    assert studiochecks.frozen_stretches(moving) == []
    rows = {r["name"]: r for r in studiochecks.freeze_checks(still)}
    assert not rows["no_frozen_picture"]["ok"] and rows["no_frozen_picture"]["severity"] == "warn" and "3." in rows["no_frozen_picture"]["detail"]
    assert studiochecks.freeze_checks(moving)[0]["ok"]


# ---- how a name is said (30 Oct 2026): the voice read "Amun" as "ah-mo-nee-us"; Gemini listened to four spellings and heard "ah-moon" only for "Ahmoon" ----
def test_a_name_the_voice_gets_wrong_is_spelled_for_the_ear_only_and_the_word_count_stays():
    assert tts.spoken("the Oracle of Amun at the Siwa Oasis.") == "the Oracle of Ahmoon at the Siwa Oasis."
    assert tts.spoken("Amun's temple") == "Ahmoon's temple" and tts.spoken("Amunet") == "Amunet"  # whole words only
    text = "The legend says Cambyses sent them to subjugate the Oracle of Amun, and they were never seen again."
    assert len(tts.spoken(text).split()) == len(text.split())  # captions are matched to the script word by word, so the count must not change


def test_narrate_sends_the_spelled_form_to_the_voice_and_nothing_else_changes(tmp_path, monkeypatch):
    import subprocess
    sent = []

    async def fake(text, mp3, prosody=None):
        sent.append(text)
        return [(0.0, 0.5, "hi")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    monkeypatch.setattr(tts, "_duration", lambda p: 1.0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    tts.narrate(["Oracle of Amun here.", "No change here."], tmp_path, pause=0.1)
    assert sent == ["Oracle of Ahmoon here.", "No change here."]
