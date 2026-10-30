"""The Gloamtale mark, small in a corner of every video of the owner's channel (30 Oct 2026, owner's request: "with logo and brand"). It is laid over the finished video in the same ffmpeg pass
as the subscribe pop-up, fades in after the 4 s cold open and out with the video, sits bottom left on a documentary and top left on a vertical Short, has its own switch `brand_mark`
(independent of `subscribe_pop`), and a user studio on this server never shows it."""
import shutil
import subprocess

import pytest

import brandmark
import config
import subscribe


def png(path):
    from PIL import Image

    Image.new("RGBA", (150, 150), (233, 189, 106, 255)).save(path)
    return path


def test_a_documentary_carries_the_mark_bottom_left_at_six_percent_of_its_width(tmp_path):
    m = brandmark.spec((1920, 1080), False, 500.0, mark=png(tmp_path / "m.png"))
    assert (m["width"], m["x"], m["y"]) == (115, 48, 917) and m["start"] == 4.0 and m["seconds"] == 500.0


def test_a_vertical_short_carries_it_top_left_below_the_status_bar_and_clear_of_the_pop_up(tmp_path):
    m = brandmark.spec((1080, 1920), True, 50.0, mark=png(tmp_path / "m.png"))
    assert (m["width"], m["x"], m["y"]) == (130, 43, 134)
    pop_w, pop_x, pop_y = subscribe._place((1080, 1920), True)
    mark_bottom = m["y"] + m["width"]  # the mark picture is square
    assert mark_bottom <= pop_y or m["x"] + m["width"] <= pop_x  # the two rectangles never meet: the pop-up starts below the mark


def test_no_mark_when_the_file_is_missing_or_the_video_is_too_short_to_fade_it_in_and_out(tmp_path):
    assert brandmark.spec((1920, 1080), False, 500.0, mark=tmp_path / "nothing.png") is None
    good = png(tmp_path / "m.png")
    assert brandmark.spec((1920, 1080), False, 6.0, mark=good) is None
    assert brandmark.spec((1920, 1080), False, 7.0, mark=good) is not None


def test_the_filter_chain_fades_the_mark_in_after_the_cold_open_and_out_before_the_end(tmp_path):
    m = brandmark.spec((1920, 1080), False, 100.0, mark=png(tmp_path / "m.png"))
    inputs, graph, out = brandmark.chain(m, 3, "[0:v]")
    text = ";".join(graph)
    assert inputs[:2] == ["-loop", "1"] and inputs[-2:] == ["-i", m["file"]]
    assert text.startswith("[3:v]scale=115:-1") and "colorchannelmixer=aa=0.75" in text
    assert "fade=t=in:st=4.0:d=1.0:alpha=1" in text and "fade=t=out:st=98.500:d=1.5:alpha=1" in text
    assert "[0:v][mk]overlay=x=48:y=917:eof_action=pass[vm]" in text and out == "[vm]"


def test_the_mark_goes_in_first_so_the_pop_up_is_drawn_over_it(tmp_path):
    (tmp_path / "pop-000.png").write_bytes(b"")
    m = brandmark.spec((1920, 1080), False, 100.0, mark=png(tmp_path / "m.png"))
    text = " ".join(subscribe.command(tmp_path / "v.mp4", tmp_path / "o.mp4", [40.0], (1920, 1080), False, assets=tmp_path, mark=m))
    assert text.index("[0:v][mk]overlay") < text.index("[p0]overlay")  # the mark's overlay comes before the pop-up's
    assert "[2:v]scale=422:-1" in text and "setpts=PTS+40.000/TB" in text  # input 1 is the mark, so the pop-up is input 2


def test_a_video_with_no_pop_up_moment_still_gets_its_mark_and_one_with_neither_is_left_alone(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(subscribe, "apply", lambda video, times, size, vertical, assets=None, mark=False: seen.append((times, mark)) or True)
    data = {"subscribe_pop": False}
    assert subscribe.add_to(tmp_path / "v.mp4", data, "doc", [9.0] * 58, [], (1920, 1080)) is True
    assert seen == [([], True)] and "subscribe_shown" not in data and data["brand_mark_shown"]["corner"] == "bottom left"
    data = {"subscribe_pop": False, "brand_mark": False}
    assert subscribe.add_to(tmp_path / "v.mp4", data, "doc", [9.0] * 58, [], (1920, 1080)) is False
    assert len(seen) == 1 and "brand_mark_shown" not in data


def test_the_two_switches_are_independent(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(subscribe, "apply", lambda video, times, size, vertical, assets=None, mark=False: seen.append((times, mark)) or True)
    data = {"brand_mark": False}
    subscribe.add_to(tmp_path / "v.mp4", data, "doc", [9.0] * 58, [], (1920, 1080))
    assert len(seen[-1][0]) == 2 and seen[-1][1] is False and "brand_mark_shown" not in data and "subscribe_shown" in data
    data = {}
    subscribe.add_to(tmp_path / "v.mp4", data, "short", [4.0, 4.0, 4.0, 6.0], [], (1080, 1920))
    assert seen[-1][1] is True and data["brand_mark_shown"] == {"corner": "top left", "from": 4.0} and "subscribe_shown" in data


def test_a_failed_overlay_records_nothing_and_a_user_studio_never_shows_the_owners_mark(tmp_path, monkeypatch):
    import tenantmode

    monkeypatch.setattr(subscribe, "apply", lambda *a, **k: False)
    data = {}
    assert subscribe.add_to(tmp_path / "v.mp4", data, "doc", [9.0] * 58, [], (1920, 1080)) is False and not data
    calls = []
    monkeypatch.setattr(subscribe, "apply", lambda *a, **k: calls.append(1) or True)
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: True)
    assert subscribe.add_to(tmp_path / "v.mp4", {"subscribe_pop": False}, "doc", [9.0] * 58, [], (1920, 1080)) is False and not calls


def test_apply_with_no_pop_up_and_no_mark_does_not_run_ffmpeg(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"original")
    monkeypatch.setattr(subscribe.subprocess, "run", lambda *a, **k: pytest.fail("ffmpeg must not run"))
    monkeypatch.setattr(subscribe, "_seconds", lambda p: 60.0)
    assert subscribe.apply(video, [], (1920, 1080), False) is False and video.read_bytes() == b"original"


def test_both_producers_leave_the_mark_to_the_same_step_as_the_pop_up():
    """The mark rides on `subscribe.add_to`, which both producers already call with their own kind: there is no second re-encode and no producer can forget it."""
    import inspect

    src = inspect.getsource(subscribe.add_to)
    assert "brand_mark" in src and "mark=" in src


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
def test_a_real_video_shows_the_mark_only_after_the_cold_open_keeps_its_length_and_its_audio(tmp_path):
    from PIL import Image

    video = tmp_path / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x101040:s=640x360:r=30:d=12", "-f", "lavfi", "-i", "sine=f=440:d=12",
                    "-shortest", *__import__("render")._venc("23", "ultrafast"), "-c:a", "aac", str(video)], check=True)
    assert subscribe.apply(video, [], (640, 360), False, mark=True) is True
    assert abs(subscribe._seconds(video) - 12.0) < 0.5
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
    assert has_audio == "aac"

    def corner(t, name):
        out = tmp_path / name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(out)], check=True)
        return Image.open(out).convert("RGB").crop((16, 306, 54, 344))  # where a 640 px wide landscape video carries the mark

    def lift(im):
        return max(hi for _lo, hi in im.getextrema()) - 0x40

    assert lift(corner(1.0, "early.png")) < 12      # before the cold open ends the corner is the plain background
    assert lift(corner(8.0, "mid.png")) > 60        # the gold mark is there, at partial opacity
