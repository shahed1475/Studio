import shutil
import subprocess

import pytest
import render
import tts

W = [{"s": 0.0, "e": 0.5, "w": "Why", "i": 0}, {"s": 0.5, "e": 1.0, "w": "did", "i": 0}, {"s": 1.0, "e": 1.5, "w": "they", "i": 0},
     {"s": 1.9, "e": 2.3, "w": "A", "i": 1}, {"s": 2.3, "e": 2.8, "w": "strange", "i": 1}, {"s": 2.8, "e": 3.2, "w": "tune", "i": 1},
     {"s": 3.2, "e": 3.6, "w": "came", "i": 1}]


def test_shot_plan_varies_and_stays_inside_the_picture():
    plans = [render.shot_plan(k) for k in range(6)]
    assert len({tuple(sorted(p.items())) for p in plans[:5]}) == 5  # five different shots before any repeat
    assert plans[5] == plans[0]
    for p in plans:
        assert p["z0"] >= 1.0 and p["z1"] >= 1.0
        assert all(0.0 <= p[k] <= 1.0 for k in ("fx0", "fy0", "fx1", "fy1"))


def test_plain_captions_unchanged_when_motion_is_zero():
    ass = tts._ass([(w["s"], w["e"], w["w"]) for w in W], motion=0)
    assert "Alignment" in ass and ",Cap,WHY DID THEY" in ass and "Hook" not in ass


def test_rich_captions_lower_third_active_word_and_hook_card():
    words = [(w["s"], w["e"], w["w"], w["i"]) for w in W]
    ass = tts._ass(words, motion=2)
    assert "Style: Cap," in ass and "Style: Hook," in ass
    hook = [l for l in ass.splitlines() if ",Hook," in l]
    assert len(hook) == 1 and "\\fad(" in hook[0] and "WHY DID THEY" in hook[0].replace("\\N", " ")
    assert hook[0].split(",")[1] == "0:00:00.00" and hook[0].split(",")[2] == "0:00:01.65"  # the first line, until the next line starts
    caps = [l for l in ass.splitlines() if ",Cap," in l]
    assert len(caps) == 4  # one event per word of the lines after the hook
    assert caps[1].count("\\c&H") >= 1 and "STRANGE" in caps[1]
    assert caps[0].split(",")[1] == "0:00:01.90"


def test_rich_captions_without_line_numbers_still_work():
    ass = tts._ass([(0.0, 0.4, "one"), (0.4, 0.8, "two")], motion=2)
    assert ",Cap," in ass


def _have_ffmpeg():
    return shutil.which("ffmpeg") and shutil.which("ffprobe")


@pytest.mark.skipif(not _have_ffmpeg(), reason="needs ffmpeg")
def test_render_with_shots_crossfade_and_grain_really_runs(tmp_path):
    from PIL import Image

    imgs = []
    for k, color in enumerate(((200, 30, 30), (30, 200, 30), (30, 30, 200))):
        p = tmp_path / f"i{k}.png"
        Image.new("RGB", (640, 480), color).save(p)
        imgs.append(p)
    work = tmp_path / "w"
    work.mkdir()
    narration = work / "n.wav"  # like the real pipeline: the voice file sits in the work folder
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "3.0", str(narration)], check=True)
    out = tmp_path / "out.mp4"
    render.render([imgs[0], imgs[1], imgs[0]], [1.0, 1.0, 1.0], narration, None, work, out, size=(270, 480), crossfade=0.3, grain=True, loudness=-16.0)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)]).decode())
    assert 2.8 <= dur <= 3.2  # crossfades must not shorten the video: it stays in sync with the voice


def test_crossfade_command_lengths_and_offsets(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd: calls.append(list(a)))
    work = tmp_path / "w"
    work.mkdir()
    render.render([None, None, None], [3.0, 3.0, 3.0], work / "n.mp3", None, work, tmp_path / "o.mp4", crossfade=0.3)
    seg_lengths = [c[c.index("-t") + 1] for c in calls if "-t" in c and "color" in " ".join(map(str, c))]
    assert seg_lengths == ["3.300", "3.300", "3.000"]
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]
    assert graph.count("xfade") == 2 and "offset=3.000" in graph and "offset=6.000" in graph
