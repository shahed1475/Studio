"""A voice line that hangs is asked again (23 Nov 2026). The Mary Celeste film stopped for 20 minutes on line 71 of 89: Microsoft's voice stream stopped
sending and `async for ev in comm.stream()` waited for ever (no timeout, so the retries never ran). Each attempt now has a time limit."""
import asyncio

import pytest

import tts


def test_a_hanging_line_is_cut_off_and_asked_again(tmp_path, monkeypatch):
    calls = []

    async def once(text, mp3, *a):
        calls.append(1)
        if len(calls) == 1:
            await asyncio.sleep(3600)  # the stream that never ends
        return [(0.0, 0.5, "hello")]

    monkeypatch.setattr(tts, "_synth_once", once)
    monkeypatch.setattr(tts, "LINE_TIMEOUT", 0.2)
    monkeypatch.setattr(tts, "RETRY_WAITS", (0.01, 0.01, 0.01, 0))
    assert asyncio.run(tts._synth_line("hello", tmp_path / "l.mp3")) == [(0.0, 0.5, "hello")]
    assert len(calls) == 2


def test_a_line_that_always_hangs_fails_in_bounded_time_instead_of_stopping_the_film(tmp_path, monkeypatch):
    async def once(text, mp3, *a):
        await asyncio.sleep(3600)

    monkeypatch.setattr(tts, "_synth_once", once)
    monkeypatch.setattr(tts, "LINE_TIMEOUT", 0.1)
    monkeypatch.setattr(tts, "RETRY_WAITS", (0.01, 0.01, 0.01, 0))
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(tts._synth_line("hello", tmp_path / "l.mp3"))


def test_the_limit_leaves_room_for_a_long_line():
    assert 60 <= tts.LINE_TIMEOUT <= 300  # a 45-word line takes a few seconds; minutes mean the stream is gone
