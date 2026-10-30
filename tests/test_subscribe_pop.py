"""A branded subscribe reminder that pops up on screen (30 Oct 2026, owner's request). Shorts: it appears just before the narrator says 'subscribe', so the cursor click lands on the word.
Documentaries end on the story (no spoken ask, a studio rule), so they get one or two pop-ups at high points: about 40 and 82 percent in, on the start of a narration line, never in the
first 45 s or the last 25 s, at least 120 s apart (creator advice, not a measured rule: ask once the viewer is engaged, keep it short, few asks). The overlay is a post-pass that fails safe."""
import pytest

import subscribe


def doc_durations(n=58, each=9.59):
    return [each] * n


def starts_of(durations):
    out, t = [], 0.0
    for d in durations:
        out.append(round(t, 3))
        t += d
    return out


def test_a_short_pop_starts_just_before_the_spoken_word_so_the_click_lands_on_it():
    durations = [4.0, 4.0, 4.0, 6.0]  # 18 s, last line starts at 12.0
    words = [{"s": 12.2, "e": 12.6, "w": "Now", "i": 3}, {"s": 17.0, "e": 17.5, "w": "Subscribe", "i": 3}]
    assert subscribe.moments("short", durations, words) == [pytest.approx(14.4)]  # 17.0 - 1.2 = 15.8, moved earlier so the 3.6 s pop ends with the video


def test_a_short_without_the_word_pops_at_the_start_of_its_last_line_and_a_tiny_one_gets_none():
    assert subscribe.moments("short", [4.0, 4.0, 4.0, 6.0], []) == [pytest.approx(12.0)]
    assert subscribe.moments("short", [1.0, 1.0, 1.0], []) == []


def test_a_documentary_gets_two_pops_on_line_starts_away_from_its_beginning_and_end():
    d = doc_durations()
    total = sum(d)
    got = subscribe.moments("doc", d)
    assert len(got) == 2 and all(any(abs(t - s) < 0.06 for s in starts_of(d)) for t in got)  # each on a line start
    assert got[0] >= 45 and got[-1] <= total - subscribe.POP_SECONDS - 25 and got[1] - got[0] >= 120
    assert abs(got[0] - 0.40 * total) < 12 and abs(got[1] - 0.82 * total) < 12


def test_a_shorter_documentary_gets_one_pop_in_the_middle_and_anything_else_gets_none():
    d = doc_durations(10, 10.0)
    got = subscribe.moments("doc", d)
    assert len(got) == 1 and abs(got[0] - 50.0) <= 10.0
    assert subscribe.moments("doc", [5.0, 5.0]) == [] and subscribe.moments("news", doc_durations()) == []


def test_the_overlay_command_delays_each_pop_scales_it_and_keeps_the_audio_untouched(tmp_path):
    cmd = subscribe.command(tmp_path / "v.mp4", tmp_path / "o.mp4", [100.0, 400.0], (1920, 1080), vertical=False, assets=tmp_path)
    text = " ".join(cmd)
    assert cmd.count("-i") == 3 and "-framerate" in cmd and "pop-%03d.png" in text
    assert "setpts=PTS+100.000/TB" in text and "setpts=PTS+400.000/TB" in text and text.count("eof_action=pass") == 2
    assert "scale=422:-1" in text and "x=1450:y=43" in text  # top right on a 1920x1080 video
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy" and cmd[-1].endswith("o.mp4")


def test_the_overlay_on_a_vertical_short_sits_in_the_middle_near_the_top(tmp_path):
    cmd = subscribe.command(tmp_path / "v.mp4", tmp_path / "o.mp4", [14.4], (1080, 1920), vertical=True, assets=tmp_path)
    text = " ".join(cmd)
    assert "scale=756:-1" in text and "x=162:y=269" in text


def test_a_failed_overlay_leaves_the_finished_video_exactly_as_it_was(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"original")

    def boom(*a, **k):
        raise subscribe.subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(subscribe.subprocess, "run", boom)
    assert subscribe.apply(video, [10.0], (1920, 1080), False, assets=tmp_path) is False
    assert video.read_bytes() == b"original" and not list(tmp_path.glob("*.tmp*"))


def test_a_good_overlay_replaces_the_video_only_when_its_length_matches(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"original")

    def fake(cmd, **k):
        open(cmd[-1], "wb").write(b"with pop")

    monkeypatch.setattr(subscribe.subprocess, "run", fake)
    monkeypatch.setattr(subscribe, "_seconds", lambda p: 60.0)
    assert subscribe.apply(video, [10.0], (1920, 1080), False, assets=tmp_path) is True and video.read_bytes() == b"with pop"
    video.write_bytes(b"original")
    lengths = iter([60.0, 41.0])  # the new file is much shorter: something went wrong
    monkeypatch.setattr(subscribe, "_seconds", lambda p: next(lengths))
    assert subscribe.apply(video, [10.0], (1920, 1080), False, assets=tmp_path) is False and video.read_bytes() == b"original"


def test_the_switch_can_turn_it_off_or_give_exact_times(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subscribe, "apply", lambda video, times, size, vertical, assets=None: calls.append(times) or True)
    d = doc_durations()
    data = {}
    subscribe.add_to(tmp_path / "v.mp4", data, "doc", d, [], (1920, 1080))
    assert len(calls[-1]) == 2 and data["subscribe_shown"]["at"] == calls[-1]
    data = {"subscribe_pop": False}
    subscribe.add_to(tmp_path / "v.mp4", data, "doc", d, [], (1920, 1080))
    assert len(calls) == 1 and "subscribe_shown" not in data
    data = {"subscribe_pop": [75.5, 300]}
    subscribe.add_to(tmp_path / "v.mp4", data, "doc", d, [], (1920, 1080))
    assert calls[-1] == [75.5, 300.0] and data["subscribe_shown"]["at"] == [75.5, 300.0]


def test_both_producers_call_the_pop_up_step_with_their_own_kind():
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "run.py").read_text()
    kinds = re.findall(r'subscribe\.add_to\(folder / "video.mp4", data, "(\w+)"', src)
    assert sorted(kinds) == ["doc", "short"]
