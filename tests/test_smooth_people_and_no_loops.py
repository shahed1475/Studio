"""30 Oct 2026, the owner rejected the Cambyses film: faces, noses and hands looked big and shaky, and clips ran the same footage twice.
Cause 1: the depth warp (parallax.py) bends a picture by depth, which stretches a nose or a hand; the plain camera (ffmpeg zoompan) steps in whole pixels. Now a picture that shows people
gets a smooth sub-pixel zoom with no depth bend, and only a picture whose note says it has no people keeps the depth effect.
Cause 2: render.py looped (-stream_loop -1) any clip shorter than its scene; seven of eight 8-second animated clips sat under scenes of 8.2 to 10.2 seconds."""
import pytest
from PIL import Image

import parallax
import render


@pytest.mark.parametrize("note,safe", [
    ("empty Egyptian dunes at dawn, a faint line of footprints, no people", True),
    ("hidden oasis valley at dusk with palm trees and old stone ruins, no people", True),
    ("ancient Egyptian fortress wall at Dakhla Oasis at dusk, no faces", True),
    ("an ancient scroll lying on desert sand, still life", True),
    ("1983 ultralight aircraft over tangled dunes near Bahariya Oasis, aerial view", True),
    ("Persian soldiers storming the walls of Pelusium, 525 BC, wide battle view", False),
    ("Siwa Oasis", False),  # an old short note: the picture drawn from it had a woman's face, so unknown means people
    ("", False),
])
def test_only_a_picture_that_says_it_has_no_people_keeps_the_depth_effect(note, safe):
    assert parallax.depth_safe(note) is safe


def test_flat_scenes_are_the_ones_that_may_show_people():
    lines = [{"visual": "empty dunes, no people"}, {"visual": "a soldier at a well"}, {"visual": "temple at Siwa in morning light, no people"}]
    assert parallax.flat_scenes(lines) == {1}


def test_a_flat_scene_gets_no_sideways_depth_shift_and_the_others_keep_their_sway(tmp_path, monkeypatch):
    import animate
    import config
    import depth

    jobs = []
    monkeypatch.setattr(config, "CACHE", tmp_path)
    monkeypatch.setattr(animate, "_drawn", lambda p: True)
    monkeypatch.setattr(depth, "depth_for", lambda p: (Image.new("L", (8, 8), 128), "model"))
    monkeypatch.setattr(parallax, "_job", lambda job: jobs.append(job))
    pics = []
    for i in range(3):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (64, 36), (i * 40, 0, 0)).save(p)
        pics.append(p)
    parallax.apply(pics, [5.0, 5.0, 5.0], (64, 36), workers=1, flat={1})
    sways = {Path_name: job[5] for job in jobs for Path_name in [job[0].split("/")[-1]]}
    assert sways["p1.jpg"] == 0 and sways["p0.jpg"] == 1 and sways["p2.jpg"] == 1


def test_a_flat_scene_is_a_smooth_zoom_with_every_frame_a_little_different_and_no_depth_bend(tmp_path):
    """The picture's near and far parts must move together: the same pixel row of a flat frame is the whole picture scaled, so a bright near object and a dark far object keep their distance ratio."""
    import math
    src = Image.new("RGB", (400, 225), (30, 30, 30))
    for x in range(100, 140):
        for y in range(60, 160):
            src.putpixel((x, y), (250, 250, 250))
    dmap = Image.new("L", (400, 225), 0)
    for x in range(100, 140):
        for y in range(60, 160):
            dmap.putpixel((x, y), 255)  # the bright bar is the nearest thing
    plan = {"z0": 1.1, "z1": 1.1, "fx0": 0.5, "fx1": 0.5, "fy0": 0.5, "fy1": 0.5}
    a = parallax.frame(src, dmap, (200, 112), parallax.camera(plan, 0.0, sway=0))
    b = parallax.frame(src, dmap, (200, 112), parallax.camera(plan, 1.0, sway=0))
    assert list(a.getdata()) == list(b.getdata())  # no sway, no zoom change: nothing moves, and nothing bends with depth


def test_a_clip_fills_its_scene_once_slowed_a_little_and_held_on_its_last_frame_never_looped():
    assert render.clip_fit(8.0, 7.8) == (1.0, 0.0)         # long enough: played at its own speed and cut
    f, hold = render.clip_fit(8.0, 10.2)
    assert f == pytest.approx(1.25) and hold == pytest.approx(0.2)  # 8 s slowed to 10 s, 0.2 s held
    f, hold = render.clip_fit(8.0, 9.0)
    assert f == pytest.approx(1.125) and hold == pytest.approx(0.0)  # slowed just enough, nothing held
    f, hold = render.clip_fit(8.0, 12.0)
    assert f == pytest.approx(1.25) and hold == pytest.approx(2.0)
    assert render.clip_fit(0.0, 5.0) == (1.0, 0.0)  # an unreadable length changes nothing


def test_generated_animation_is_never_looped_but_other_clips_keep_the_old_behaviour(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd=None: seen.append(list(a)))
    monkeypatch.setattr(render, "_clip_seconds", lambda p: 8.0)
    anim = tmp_path / "anim"
    anim.mkdir()
    gen, stock = anim / "x.mp4", tmp_path / "stock.mp4"
    gen.write_bytes(b"x"); stock.write_bytes(b"x")
    work = tmp_path / "w"
    work.mkdir()
    try:
        render._render_ungated([gen, stock], [10.2, 10.2], work / "n.wav", None, work, work / "o.mp4")
    except Exception:
        pass  # the later mux steps need real files; only the scene commands matter here
    first = next(a for a in seen if str(gen) in a)
    second = next(a for a in seen if str(stock) in a)
    vf = first[first.index("-vf") + 1]
    assert "-stream_loop" not in first and "setpts=1.2500*PTS" in vf and "tpad=stop_mode=clone" in vf and "framerate=fps=" in vf
    assert "-stream_loop" in second  # stock footage keeps looping as before


def test_a_people_scene_gets_a_gentle_push_no_more_than_8_percent_from_a_near_full_frame():
    """Scene 22 pushed in 1.1x to 1.45x and some scenes sat at a fixed 1.3x crop: faces looked big (owner, 30 Oct 2026)."""
    for k in range(len(render.SHOTS)):
        g = parallax.gentle(render.shot_plan(k))
        assert parallax.MIN_ZOOM <= g["z0"] <= 1.10 and g["z0"] <= g["z1"] <= g["z0"] + 0.08 + 1e-9
        assert all(g[key] == render.shot_plan(k)[key] for key in ("fx0", "fx1", "fy0", "fy1"))  # where the camera looks is unchanged


def test_flat_scenes_use_the_gentle_plan_and_depth_scenes_keep_theirs(tmp_path, monkeypatch):
    import animate
    import config
    import depth

    jobs = []
    monkeypatch.setattr(config, "CACHE", tmp_path)
    monkeypatch.setattr(animate, "_drawn", lambda p: True)
    monkeypatch.setattr(depth, "depth_for", lambda p: (Image.new("L", (8, 8), 128), "model"))
    monkeypatch.setattr(parallax, "_job", lambda job: jobs.append(job))
    pics = []
    for i in range(2):
        p = tmp_path / f"q{i}.jpg"
        Image.new("RGB", (64, 36), (i * 40, 9, 9)).save(p)
        pics.append(p)
    parallax.apply(pics, [5.0, 5.0], (64, 36), workers=1, flat={1})
    plans = {job[0].split("/")[-1]: job[4] for job in jobs}
    assert plans["q1.jpg"] == parallax.gentle(render.shot_plan(1)) and plans["q0.jpg"] == render.shot_plan(0)
