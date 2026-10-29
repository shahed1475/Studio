"""2.5D camera motion for a drawn picture (29 Oct 2026): a depth map moves near parts more than far parts while the camera drifts, so a still picture gains depth.
No new dependency: Pillow warps each frame on a mesh, ffmpeg encodes. Only the studio's own drawn pictures (cache/art) move; archive pictures never do."""
import subprocess

import pytest
from PIL import Image

import config
import depth
import parallax


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    (tmp_path / "cache" / "art").mkdir(parents=True)
    (tmp_path / "cache" / "anim").mkdir()


def gradient(tmp_path, name="g.jpg", size=(320, 180), where="art"):
    im = Image.new("RGB", size)
    px = im.load()
    for x in range(size[0]):
        for y in range(size[1]):
            px[x, y] = (int(255 * x / (size[0] - 1)), 90, 90)
    d = tmp_path / "cache" / where
    d.mkdir(exist_ok=True)
    p = d / name
    im.save(p, "JPEG", quality=95)
    return p


def split_depth(size=(64, 36)):
    """Left half near (white), right half at the middle depth, which the camera keeps still."""
    m = Image.new("L", size, 128)
    m.paste(255, (0, 0, size[0] // 2, size[1]))
    return m


def test_the_camera_starts_and_ends_where_the_shot_says_and_the_sway_goes_one_way_or_the_other():
    plan = dict(z0=1.0, z1=1.22, fx0=0.5, fy0=0.5, fx1=0.5, fy1=0.42)
    a, b = parallax.camera(plan, 0.0), parallax.camera(plan, 1.0)
    assert a["z"] == pytest.approx(parallax.MIN_ZOOM) and b["z"] == pytest.approx(1.22)  # never a window as big as the whole picture: the warp needs a margin
    assert (b["fy"], b["fx"]) == (pytest.approx(0.42), pytest.approx(0.5))
    assert (a["u"], b["u"]) == (pytest.approx(-1.0), pytest.approx(1.0))
    assert parallax.camera(plan, 0.0, sway=-1)["u"] == pytest.approx(1.0)


def test_the_mesh_covers_the_whole_frame_and_never_reaches_outside_the_picture():
    src, out = (1376, 768), (1920, 1080)
    for t in (0.0, 0.5, 1.0):
        cam = parallax.camera(dict(z0=1.0, z1=1.5, fx0=0.0, fy0=0.0, fx1=1.0, fy1=1.0), t)
        mesh = parallax.mesh(src, out, split_depth(), cam)
        assert len(mesh) >= (out[0] // parallax.CELL) * (out[1] // parallax.CELL)
        xs = [x for _, quad in mesh for x in quad[0::2]]
        ys = [y for _, quad in mesh for y in quad[1::2]]
        assert min(xs) >= 0 and max(xs) <= src[0] and min(ys) >= 0 and max(ys) <= src[1]
        boxes = [b for b, _ in mesh]
        assert min(b[0] for b in boxes) == 0 and min(b[1] for b in boxes) == 0 and max(b[2] for b in boxes) == out[0] and max(b[3] for b in boxes) == out[1]


def test_near_parts_move_more_than_far_parts_when_the_camera_sways(tmp_path):
    p = gradient(tmp_path)
    src = Image.open(p).convert("RGB")
    plan = dict(z0=1.2, z1=1.2, fx0=0.5, fy0=0.5, fx1=0.5, fy1=0.5)
    left, right = {}, {}
    for u in (-1, 1):
        cam = dict(parallax.camera(plan, 0.5), u=u)
        fr = parallax.frame(src, split_depth(), (320, 180), cam)
        left[u] = sum(fr.getpixel((x, 90))[0] for x in range(20, 140)) / 120  # the near half
        right[u] = sum(fr.getpixel((x, 90))[0] for x in range(180, 300)) / 120  # the far half
    assert abs(left[1] - left[-1]) > 3 * max(abs(right[1] - right[-1]), 0.5)


def test_a_real_clip_is_encoded_with_the_right_size_length_and_motion(tmp_path):
    p = gradient(tmp_path)
    out = tmp_path / "cache" / "anim" / "t.mp4"
    parallax.render_clip(p, depth.approximate_depth((64, 36)), 1.0, out, (160, 90), dict(z0=1.1, z1=1.3, fx0=0.3, fy0=0.5, fx1=0.7, fy1=0.5))
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames", "-of", "csv=p=0", str(out)]).decode().strip()
    w, h, n = probe.split(",")
    assert (int(w), int(h)) == (160, 90) and abs(int(n) - config.FPS) <= 2


def test_apply_moves_only_drawn_pictures_reuses_a_clip_it_made_and_reports_how_deep(tmp_path):
    drawn = gradient(tmp_path, "d.jpg", (320, 180), "art")
    archive = gradient(tmp_path, "a.jpg", (320, 180), "archive")
    clips, durs = [drawn, archive, None, drawn], [0.6, 0.6, 0.6, 0.6]
    out, stats = parallax.apply(clips, durs, (160, 90), workers=1)
    assert out[1] == archive and out[2] is None  # archive pictures and missing scenes are not touched
    assert str(out[0]).endswith(".mp4") and out[0].parent.name == "anim" and out[3] != out[0]  # a repeated picture gets another camera move, so it is another clip
    assert stats["made"] == 2 and stats["approximate"] == 2 and stats["cached"] == 0 and stats["skipped"] == 2
    stamp = out[0].stat().st_mtime_ns
    again, stats2 = parallax.apply(clips, durs, (160, 90), workers=1)
    assert again == out and stats2["made"] == 0 and stats2["cached"] == 2 and out[0].stat().st_mtime_ns == stamp


def test_a_stored_depth_map_is_used_and_counted(tmp_path):
    drawn = gradient(tmp_path, "d.jpg")
    (config.CACHE / "depth").mkdir()
    split_depth((192, 108)).save(config.CACHE / "depth" / f"{depth.depth_key(drawn)}.png")
    _, stats = parallax.apply([drawn], [0.5], (160, 90), workers=1)
    assert stats["model"] == 1 and stats["approximate"] == 0
