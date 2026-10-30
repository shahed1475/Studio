"""Sound cues of the studio's own making (30 Oct 2026, owner: hook and curiosity from the first second with voice, sound effects and a question). Made with ffmpeg so no licence question
exists: a riser into the first word, a hit on the reveal, a soft whoosh at each chapter change, a swell on the payoff. Mixed quietly under the narration, the loudness target does not move,
and the video's length and picture are untouched. No study shows sound effects raise retention (research of 30 Oct): this is a design choice with its own switch, `sfx` in the record."""
import json
import re
import shutil
import subprocess

import pytest

import sfx

NEEDS = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


def doc_durations(n=58, each=9.0):
    return [each] * n


CHAPTERS = [{"title": "Hook", "start_line": 0}, {"title": "Promise", "start_line": 6}, {"title": "Story", "start_line": 12}, {"title": "More", "start_line": 30}, {"title": "Value", "start_line": 50}]


def test_a_film_gets_a_riser_at_zero_a_hit_on_the_second_line_a_whoosh_per_chapter_and_a_swell_on_the_last_chapter():
    got = sfx.cues("doc", doc_durations(), CHAPTERS)
    names = [n for _, n in got]
    assert got[0] == (0.0, "riser") and got[1] == (9.0, "hit")
    assert names.count("whoosh") == 3 and names[-1] == "swell" and got[-1][0] == 450.0
    assert all(b[0] - a[0] >= 3.0 for a, b in zip(got, got[1:]))


def test_a_short_gets_only_a_short_riser_and_a_hit_and_a_tiny_video_gets_nothing_that_would_overrun_it():
    got = sfx.cues("short", [4.0, 4.0, 4.0, 6.0], [])
    assert got == [(0.0, "riser"), (4.0, "hit")]
    assert sfx.cues("doc", [0.8], []) == [] or all(t + sfx.LENGTHS[n] <= 0.8 + 1e-9 or n == "riser" for t, n in sfx.cues("doc", [0.8], []))


def test_cues_that_would_crowd_each_other_are_dropped_and_the_count_is_capped():
    chapters = [{"start_line": i} for i in range(40)]
    got = sfx.cues("doc", [2.0] * 80, chapters)
    assert all(b[0] - a[0] >= 3.0 for a, b in zip(got, got[1:])) and len(got) <= 14  # literal numbers: the module's own constants would make this a tautology


def test_the_effects_are_quiet_by_design():
    assert all(g <= -12 for g in sfx.GAIN_DB.values()) and sfx.GAIN_DB["riser"] <= -18 and sfx.GAIN_DB["swell"] <= -22


def test_a_user_studio_and_a_switched_off_video_get_no_sound_cues(tmp_path, monkeypatch):
    import tenantmode

    calls = []
    monkeypatch.setattr(sfx, "apply", lambda *a, **k: calls.append(1) or True)
    assert sfx.add_to(tmp_path / "v.mp4", {"sfx": False}, "doc", doc_durations(), CHAPTERS) is False
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: True)
    assert sfx.add_to(tmp_path / "v.mp4", {}, "doc", doc_durations(), CHAPTERS) is False and not calls
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: False)
    data = {}
    assert sfx.add_to(tmp_path / "v.mp4", data, "doc", doc_durations(), CHAPTERS) is True and calls and data["sfx_shown"]["cues"] >= 4


def test_a_failed_mix_leaves_the_finished_video_exactly_as_it_was(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"original")
    monkeypatch.setattr(sfx.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "ffmpeg")))
    monkeypatch.setattr(sfx, "_effect", lambda name, cache: tmp_path / f"{name}.wav")
    assert sfx.apply(video, [(0.0, "riser")], cache=tmp_path) is False
    assert video.read_bytes() == b"original" and not list(tmp_path.glob("*.tmp*"))


def lufs(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])


def rms_db(path, t0, t1):
    out = subprocess.run(["ffmpeg", "-nostats", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(path), "-af", "astats=metadata=0", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"RMS level dB:\s+(-?[\d.inf]+)", out)[-1])


@NEEDS
def test_a_real_film_keeps_its_length_picture_and_loudness_and_the_cues_are_heard(tmp_path):
    video = tmp_path / "video.mp4"
    # 30 s of picture and a steady 'voice' (modulated tone) with a quiet gap at the start so a cue is audible
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x202040:s=320x180:r=25:d=30", "-f", "lavfi", "-i",
                    "aevalsrc='0.12*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*3*t))*gt(t,2.5)':d=30:s=44100", "-shortest", "-c:v", "libopenh264", "-b:a", "192k", "-c:a", "aac", str(video)], check=True)
    before_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout)
    quiet_before, loud_before = rms_db(video, 0.2, 1.6), lufs(video)
    data = {}
    assert sfx.add_to(video, data, "doc", [3.0] * 10, [{"start_line": 0}, {"start_line": 4}], cache=tmp_path / "sfx") is True
    after_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout)
    assert abs(after_len - before_len) < 0.5
    assert subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip() == "h264"
    assert rms_db(video, 0.2, 1.6) > quiet_before + 10  # the riser is there where there was silence
    assert abs(lufs(video) - loud_before) < 0.6          # the loudness target does not move


def test_a_mix_that_comes_out_a_different_length_replaces_nothing(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"original")
    monkeypatch.setattr(sfx, "_effect", lambda name, cache: tmp_path / f"{name}.wav")
    monkeypatch.setattr(sfx.subprocess, "run", lambda cmd, **k: open(cmd[-1], "wb").write(b"mixed"))
    lengths = iter([60.0, 41.0])  # the new file is much shorter: something went wrong
    monkeypatch.setattr(sfx, "_seconds", lambda p: next(lengths))
    assert sfx.apply(video, [(0.0, "riser")], cache=tmp_path) is False and video.read_bytes() == b"original" and not list(tmp_path.glob("*.tmp*"))
    monkeypatch.setattr(sfx, "_seconds", lambda p: 60.0)
    assert sfx.apply(video, [(0.0, "riser")], cache=tmp_path) is True and video.read_bytes() == b"mixed"


def test_both_producers_lay_the_cues_after_the_pop_up_with_their_own_kind():
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "run.py").read_text()
    kinds = re.findall(r'sfx\.add_to\(folder / "video.mp4", data, "(\w+)"', src)
    assert sorted(kinds) == ["doc", "short"]
    for kind in ("short", "doc"):
        at = src.index(f'subscribe.add_to(folder / "video.mp4", data, "{kind}"')
        assert src.index(f'sfx.add_to(folder / "video.mp4", data, "{kind}"') > at  # the pop-up pass re-encodes the picture first; the sound pass copies it
