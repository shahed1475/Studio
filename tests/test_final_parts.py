"""A long film's final pass in parts (21 Nov 2026, load-shedding): the parts give the same picture, captions and sound as the single pass, a cut between
parts keeps the finished ones, and a damaged part is made again. Real ffmpeg on tiny disposable videos; nothing here touches output/, data/ or the live studio."""
import re
import shutil
import subprocess

import pytest

import checkpoint
import render

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg missing")
SIZE = (160, 90)
# A white box drawn by libass itself (a vector shape needs no font), on screen from 5.2 s to 5.9 s: inside the third part when parts are 2.5 s long.
ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 160
PlayResY: 90

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:05.20,0:00:05.90,Default,,0,0,0,,{\\an7\\pos(20,20)\\p1}m 0 0 l 60 0 60 40 0 40{\\p0}
"""


def _job(tmp_path, n=8):
    work = tmp_path / "work"
    work.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={n}", "-ar", "44100", str(work / "narration.wav")], check=True)
    pics = []
    for i in range(n):
        p = tmp_path / f"p{i}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={['red', 'green', 'blue', 'yellow'][i % 4]}:s=320x180", "-frames:v", "1", str(p)], check=True)
        pics.append(p)
    (work / "captions.ass").write_text(ASS)
    return work, pics, [1.0] * n


def _frame(video, t):
    """One frame at t seconds as grey pixel values."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    assert len(raw) == SIZE[0] * SIZE[1]
    return raw


def _counted(video) -> int:
    """Frames a full decode really produces (not the header's claim)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return int(out)


def _diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _part_list(args):
    """The part list an ffmpeg call encodes (partNN.txt), or None (the final join reads parts.txt)."""
    return next((x for x in args if re.fullmatch(r"part\d\d\.txt", str(x))), None)


def _parts_on(monkeypatch, size=2.5, from_=4.0):
    monkeypatch.setattr(render, "PART_SECONDS", size)
    monkeypatch.setattr(render, "PARTS_FROM", from_)


def test_scenes_are_grouped_into_parts_and_a_short_tail_joins_the_last_part():
    assert render.part_groups([1.0] * 8, 2.5) == [[0, 1, 2], [3, 4, 5], [6, 7]]
    assert render.part_groups([1.0] * 6 + [0.5], 2.5) == [[0, 1, 2], [3, 4, 5, 6]]  # a 0.5 s tail is under a third of a part: it joins the last one
    assert render.part_groups([1.0] * 7, 2.5) == [[0, 1, 2], [3, 4, 5], [6]]
    assert render.part_groups([10.0], 2.5) == [[0]]
    assert sum(render.part_groups([1.0] * 81, 12.0), []) == list(range(81))


def test_the_film_made_in_parts_matches_the_single_pass_picture_captions_and_length(tmp_path, monkeypatch):
    work_a, pics, durs = _job(tmp_path / "a")
    one = render._render_ungated(pics, durs, work_a / "narration.wav", work_a / "captions.ass", work_a, tmp_path / "a" / "video.mp4", size=SIZE, shots=True, loudness=-16)
    assert not list(work_a.glob("part??.mp4"))  # 8 s is under the original threshold: one pass, as before
    _parts_on(monkeypatch)
    work_b, pics_b, _ = _job(tmp_path / "b")
    parts = render._render_ungated(pics_b, durs, work_b / "narration.wav", work_b / "captions.ass", work_b, tmp_path / "b" / "video.mp4", size=SIZE, shots=True, loudness=-16)
    assert sorted(p.name for p in work_b.glob("part??.mp4")) == ["part00.mp4", "part01.mp4", "part02.mp4"]
    assert checkpoint.check_media(parts, seconds=8.0, need=("video", "audio"), tol=0.2, full=True) is None
    assert abs(checkpoint.media_seconds(parts) - checkpoint.media_seconds(one)) < 0.1
    scenes = sum(render.frames_of(s) for s in sorted(work_b.glob("seg??.mp4")))
    assert _counted(parts) == scenes == _counted(one)  # every scene frame is in the film once: none lost or doubled at a join
    for part in sorted(work_b.glob("part??.mp4")):
        assert abs(checkpoint.media_seconds(part) - render.frames_of(part) / render.config.FPS) < 0.001  # a part states its true length
    boxed_one, boxed_parts, plain_parts = _frame(one, 5.5), _frame(parts, 5.5), _frame(parts, 4.5)
    assert _diff(boxed_parts, boxed_one) < 3  # the same frame, caption box included, within encoder noise
    corner = [boxed_parts[y * SIZE[0] + x] for y in range(24, 56) for x in range(24, 76)]
    assert min(corner) > 200  # the white box is on screen in the part at the film's own 5.5 s, not shifted to the part's 0.5 s
    assert _diff(_frame(parts, 3.1), _frame(parts, 2.9)) > 5 and plain_parts != boxed_parts  # across the first part boundary (3.0 s) the next scene shows
    for t in (0.5, 2.9, 3.1, 7.5):
        assert _diff(_frame(parts, t), _frame(one, t)) < 3


def test_a_cut_between_parts_keeps_the_finished_parts_and_makes_only_the_rest(tmp_path, monkeypatch):
    _parts_on(monkeypatch)
    work, pics, durs = _job(tmp_path)
    real = render._ff
    count = {"n": 0}

    def cut_on_second_part(*args, cwd):
        if "part01.txt" in args:
            raise KeyboardInterrupt("power cut")
        count["n"] += 1
        return real(*args, cwd=cwd)

    monkeypatch.setattr(render, "_ff", cut_on_second_part)
    with pytest.raises(KeyboardInterrupt):
        render._render_ungated(pics, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    assert not (tmp_path / "video.mp4").exists() and (work / "part00.mp4").exists() and not (work / "part01.mp4").exists()
    before = (work / "part00.mp4").stat().st_ino, (work / "part00.mp4").stat().st_mtime_ns
    made = []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd: (made.append(_part_list(a)), real(*a, cwd=cwd)))
    out = render._render_ungated(pics, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    assert [m for m in made if m] == ["part01.txt", "part02.txt"]  # part00 was not made again
    assert ((work / "part00.mp4").stat().st_ino, (work / "part00.mp4").stat().st_mtime_ns) == before
    assert checkpoint.check_media(out, seconds=8.0, need=("video", "audio"), tol=0.2, full=True) is None
    assert not list(work.glob("*.part.*"))


def test_a_damaged_part_or_a_changed_caption_file_is_made_again(tmp_path, monkeypatch):
    _parts_on(monkeypatch)
    work, pics, durs = _job(tmp_path)
    render._render_ungated(pics, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    (tmp_path / "video.mp4").unlink()
    data = (work / "part01.mp4").read_bytes()
    (work / "part01.mp4").write_bytes(data[: len(data) // 2])  # a part the cut left half on the disk
    real, made = render._ff, []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd: (made.append(_part_list(a)), real(*a, cwd=cwd)))
    render._render_ungated(pics, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    assert [m for m in made if m] == ["part01.txt"]
    made.clear()
    (work / "captions.ass").write_text(ASS.replace("0:00:05.20", "0:00:01.20"))  # new captions: every part carries them, so every part is new
    render._render_ungated(pics, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    assert [m for m in made if m] == ["part00.txt", "part01.txt", "part02.txt"]


def test_a_short_with_dissolves_keeps_its_single_pass(tmp_path, monkeypatch):
    _parts_on(monkeypatch)
    work, pics, durs = _job(tmp_path)
    out = render._render_ungated(pics, durs, work / "narration.wav", None, work, tmp_path / "video.mp4", size=SIZE, shots=True, crossfade=0.3)
    assert not list(work.glob("part??.mp4")) and checkpoint.check_media(out, need=("video", "audio"), full=True) is None


def test_a_part_whose_scenes_change_pixel_format_keeps_every_frame(tmp_path, monkeypatch):
    """21 Nov 2026: a Blender globe clip (tv range, bt709, sRGB transfer, yuv420p) among JPEG stills (full range, yuvj420p) made ffmpeg rebuild the
    filters mid-part; STARTPTS restarted at zero and the part lost every frame after the clip (Seven Sleepers: 60.1 s of 121.7 s). Scenes of
    different formats must all reach the film."""
    _parts_on(monkeypatch, size=10.0, from_=4.0)
    work, pics, durs = _job(tmp_path, n=6)
    anim = tmp_path / "anim"
    anim.mkdir()
    clip = anim / "globe.mp4"  # like a Blender clip: a moving clip in an "anim" folder, with the globe's colour tags
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=1", "-pix_fmt", "yuv420p", "-color_range", "tv",
                    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "iec61966-2-1", str(clip)], check=True)
    scenes = []
    for i, p in enumerate(pics):
        j = p.with_suffix(".jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-q:v", "3", str(j)], check=True)
        scenes.append(clip if i == 2 else j)
    out = render._render_ungated(scenes, durs, work / "narration.wav", work / "captions.ass", work, tmp_path / "video.mp4", size=SIZE, shots=True)
    total = sum(render.frames_of(s) for s in sorted(work.glob("seg??.mp4")))
    assert _counted(out) == total and checkpoint.check_media(out, seconds=6.0, need=("video", "audio"), tol=0.2, full=True) is None
