"""30 Oct 2026, owner: faster voice, louder but not too loud, AndrewMultilingual. Measured that day: the studio asked ffmpeg's one-pass loudnorm for -14 LUFS and got about -15; a gentle 3:1
compressor then a two-pass loudnorm reaches the target exactly at a -1.5 dB true peak, with a steadier level (loudness range 2.4 to 1.6 LU). The finish is applied to the narration
file only (the lines' lengths do not change), and a failed finish leaves the file as it was."""
import os
import re
import subprocess

import pytest

import audiofinish
import config
import tts


def speechlike(path, seconds=8, amp=0.03):
    """Pink noise with a slow, shallow tremolo: quiet, with the level swings of speech (a 90 percent tremolo has far taller peaks than any voice, which the true-peak limit then caps). Not a voice; enough to measure loudness handling."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anoisesrc=d={seconds}:c=pink:r=44100:a={amp}", "-af", "tremolo=f=3:d=0.5,lowpass=f=4000",
                    "-c:a", "libmp3lame", "-b:a", "128k", str(path)], check=True)


def measure(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)[-1])


def test_a_quiet_voice_is_brought_to_the_target_with_a_safe_true_peak(tmp_path):
    src = tmp_path / "narration.mp3"
    speechlike(src)
    before, _ = measure(src)
    assert before < -25  # really quiet to begin with
    assert audiofinish.finish(src, lufs=-14.5, tp=-1.5) is True
    after, peak = measure(src)
    assert abs(after - -14.5) <= 0.5 and peak <= -1.2, (after, peak)


def test_a_file_that_cannot_be_finished_is_left_exactly_as_it_was(tmp_path):
    bad = tmp_path / "narration.mp3"
    bad.write_bytes(b"not audio at all")
    assert audiofinish.finish(bad) is False and bad.read_bytes() == b"not audio at all"
    assert audiofinish.finish(tmp_path / "missing.mp3") is False
    assert not list(tmp_path.glob("*.tmp*"))


def test_narrate_finishes_the_narration_file_it_makes(tmp_path, monkeypatch):
    seen = []

    async def fake(text, mp3, prosody=None):
        return [(0.0, 0.5, "hi")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    monkeypatch.setattr(tts, "_duration", lambda p: 1.0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(tts.audiofinish, "finish", lambda path, *a, **k: seen.append((path.name, k.get("lufs", a[0] if a else None))) or True)
    tts.narrate(["One line.", "Another line."], tmp_path, pause=0.1)
    assert seen == [("narration.mp3", tts.FINISH_LUFS)] and tts.FINISH_LUFS == -14.5


@pytest.mark.skipif(os.getenv("YT_VOICE") is not None, reason="the owner's environment overrides the default")
def test_the_channel_voice_is_andrew_multilingual_a_little_faster_than_before():
    assert config.VOICE == "en-US-AndrewMultilingualNeural" and config.VOICE_RATE == "+10%" and config.VOICE_PITCH == "+0Hz"
    assert tts.VOICE_STYLES["energetic"]["voice"] == "en-US-AndrewMultilingualNeural"  # one voice for the whole channel
