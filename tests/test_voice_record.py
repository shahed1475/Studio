import inspect

import config
import run
import tts


def test_the_default_voice_is_recorded_with_its_rate_pitch_and_the_loudness_finish():
    v = tts.voice_used(None)
    assert v == {"voice": config.VOICE, "rate": config.VOICE_RATE, "pitch": config.VOICE_PITCH, "style": None, "finish_lufs": tts.FINISH_LUFS}


def test_a_styled_voice_is_recorded_as_its_own_voice_and_style():
    v = tts.voice_used("energetic")
    assert v["voice"] == tts.VOICE_STYLES["energetic"]["voice"] and v["style"] == "energetic" and v["rate"] == tts.VOICE_STYLES["energetic"]["rate"]


def test_both_producers_write_the_voice_into_the_videos_record():
    for fn in (run._produce_short, run._produce_doc):
        assert "voice_used" in inspect.getsource(fn), fn.__name__
