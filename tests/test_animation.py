import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

import aiart
import config
import llm
import modelcfg

NOW = __import__("datetime").datetime(2026, 10, 27, 12, 0, tzinfo=__import__("datetime").timezone.utc)


def png_b64(size=(1376, 768)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 60, 70)).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def art(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(aiart.config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": True, "daily_budget_usd": 5.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    monkeypatch.setattr(llm, "_account", lambda *a, **k: None)
    monkeypatch.setattr(aiart, "_off_until", {})
    monkeypatch.setattr(llm, "_post", lambda body, key: sent.append((body["model"], body["messages"][0]["content"])) or {"choices": [{"message": {"images": [{"image_url": {"url": png_b64()}}]}}]})
    return sent


def test_the_3d_style_draws_in_a_3d_animated_film_look_with_its_own_model_and_its_own_cache(art):
    plain = aiart.generate("A woman combs her hair on a rock.", "rock", "Mami Wata", now=NOW)
    threed = aiart.generate("A woman combs her hair on a rock.", "rock", "Mami Wata", now=NOW, style="3d")
    assert plain and threed and plain[0] != threed[0]  # same scene, a different picture file: the styles never share a cache entry
    (m1, p1), (m2, p2) = art
    assert "3D animated" in p2 and "3D animated" not in p1 and "No text" in p2 or "no text" in p2.lower()
    assert m2 == modelcfg.get("scene_art_3d") == "google/gemini-3.1-flash-image" and m1 == modelcfg.get("scene_art")


# ---- animate.py: some drawn scenes become short moving clips (image to video) ----
import animate


@pytest.fixture
def scenes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    art_dir = tmp_path / "cache" / "art"
    art_dir.mkdir(parents=True)
    clips = []
    for i in range(6):
        p = (art_dir if i not in (1, 4) else tmp_path) / f"s{i}.jpg"  # scenes 1 and 4 are real archive pictures: never animated
        Image.new("RGB", (1280, 720), (10 * i, 40, 60)).save(p)
        clips.append(p)
    lines = [{"text": f"Line {i} of the story.", "visual": f"thing {i}"} for i in range(6)]
    return clips, lines


def test_the_scenes_to_animate_are_drawn_ones_spread_across_the_video(scenes):
    clips, lines = scenes
    assert animate.pick_scenes(clips, 2) == [0, 5]  # the drawn scenes are 0, 2, 3, 5; two spread ones: first and last
    assert animate.pick_scenes(clips, 3) == [0, 3, 5] or animate.pick_scenes(clips, 3) == [0, 2, 5]
    assert animate.pick_scenes(clips, 99) == [0, 2, 3, 5] and animate.pick_scenes(clips, 0) == [] and animate.pick_scenes(clips, 1) == [0]


def test_the_motion_prompt_describes_gentle_movement_of_the_scene_without_text_or_links():
    p = animate.motion_prompt("She lifts the golden comb. See evil.com now!", "golden comb")
    assert "She lifts the golden comb" in p and "No text" in p and "evil.com" not in p and len(p) < 700 and "slow camera" in p.lower()


def test_chosen_scenes_become_clips_the_rest_stay_pictures_and_a_repeat_costs_nothing(scenes):
    clips, lines = scenes
    made, calls = [], []

    def gen(prompt, first_frame):
        calls.append((prompt, first_frame))
        out = Path(config.CACHE) / f"gen{len(calls)}.mp4"
        out.write_bytes(b"mp4-" + str(len(calls)).encode())
        return out, 0.24

    new, stats = animate.animate_scenes(clips, lines, 2, 3.0, gen)
    assert [c.suffix for c in new] == [".mp4", ".jpg", ".jpg", ".jpg", ".jpg", ".mp4"] and new[1] == clips[1]
    assert len(calls) == 2 and calls[0][1].startswith("data:image/jpeg;base64,") and "Line 0 of the story" in calls[0][0]
    assert stats == {"animated": 2, "cached": 0, "failed": 0, "spent": 0.48, "scenes": [0, 5]}
    again, stats2 = animate.animate_scenes(clips, lines, 2, 3.0, lambda p, f: pytest.fail("a repeat must not buy a clip"))
    assert [c.suffix for c in again] == [".mp4", ".jpg", ".jpg", ".jpg", ".jpg", ".mp4"] and stats2["cached"] == 2 and stats2["spent"] == 0


def test_a_failed_clip_leaves_the_picture_and_two_failures_in_a_row_stop_buying(scenes):
    clips, lines = scenes
    calls = []

    def gen(prompt, first_frame):
        calls.append(1)
        raise RuntimeError("provider said no")

    new, stats = animate.animate_scenes(clips, lines, 4, 3.0, gen)
    assert new == clips and stats["failed"] == 2 and stats["animated"] == 0 and len(calls) == 2


def test_the_budget_for_one_video_stops_further_clips(scenes):
    clips, lines = scenes
    count = []
    gen = lambda prompt, first_frame: (count.append(1), (Path(config.CACHE) / f"g{len(count)}.mp4").write_bytes(b"x"), (Path(config.CACHE) / f"g{len(count)}.mp4", 0.9))[2]
    new, stats = animate.animate_scenes(clips, lines, 4, 1.0, gen)
    assert stats["animated"] == 1 and stats["spent"] == 0.9 and len(count) == 1  # the next clip would take it past $1.00


def test_nothing_is_animated_when_zero_clips_are_asked_for(scenes):
    clips, lines = scenes
    new, stats = animate.animate_scenes(clips, lines, 0, 3.0, lambda p, f: pytest.fail("no"))
    assert new == clips and stats["animated"] == 0


# ---- run.py: the remake command and the animation step of a documentary ----
import run


def test_the_animation_step_adds_the_ai_credit_and_is_skipped_when_not_asked_for(monkeypatch, scenes):
    clips, lines = scenes
    data = {"lines": lines, "animate": 2, "animate_budget": 1.5}
    seen = {}
    monkeypatch.setattr(animate, "clip_generator", lambda vertical=False: "GEN")
    monkeypatch.setattr(animate, "animate_scenes", lambda c, l, n, budget, gen, **k: (seen.update(n=n, budget=budget, gen=gen, **k) or ([Path("a.mp4")] + c[1:], {"animated": 1, "cached": 0, "failed": 0, "spent": 0.24, "scenes": [0]})))
    new, credits, stats = run._animate(data, clips, ["real.jpg (Wikimedia Commons, CC0)"])
    assert seen == {"n": 2, "budget": 1.5, "gen": "GEN", "size": (1280, 720)} and new[0] == Path("a.mp4") and credits[-1] == animate.credit(modelcfg.get("video_generation")) and stats["animated"] == 1
    monkeypatch.setattr(animate, "animate_scenes", lambda *a: pytest.fail("not asked for"))
    same, credits2, stats2 = run._animate({"lines": lines}, clips, ["x"])
    assert same == clips and credits2 == ["x"] and stats2 is None


def test_remake_makes_a_new_held_video_from_the_saved_script_and_never_touches_the_uploaded_one(monkeypatch, tmp_path):
    out = tmp_path / "output"
    (out / "doc-old").mkdir(parents=True)
    saved = {"format": "doc", "title": "Mami Wata", "topic": "Mami Wata", "lines": [{"text": "x"}], "chapters": [], "video_id": "OLD", "approved": True, "uploaded_at": "t", "publish_at": "p"}
    (out / "doc-old" / "meta.json").write_text(json.dumps(saved))
    monkeypatch.setattr(config, "OUT", out)
    made = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: made.append((data, folder)))
    run.cmd_remake("doc-old", ["--style", "3d", "--animate", "8"])
    data, folder = made[0]
    assert folder is None  # a new folder: never the old one
    assert data["art_style"] == "3d" and data["animate"] == 8 and data["hold"] is True and data["remake_of"] == "doc-old" and data["replaces_video"] == "OLD"
    assert "video_id" not in data and not data.get("approved") and "publish_at" not in data
    assert json.loads((out / "doc-old" / "meta.json").read_text()) == saved
    with pytest.raises(SystemExit, match="style"):
        run.cmd_remake("doc-old", ["--style", "neon"])
    saved["format"] = "short"
    (out / "doc-old" / "meta.json").write_text(json.dumps(saved))
    with pytest.raises(SystemExit, match="documentar"):
        run.cmd_remake("doc-old", [])


def test_animated_clips_are_not_darkened_like_stock_footage(tmp_path, monkeypatch):
    """The renderer darkens stock clips (eq brightness -0.08); the generated golden-hour animation keeps its light."""
    import render

    seen = []
    monkeypatch.setattr(render, "_ff", lambda *args, cwd: seen.append(list(args)))
    (tmp_path / "anim").mkdir()
    (tmp_path / "stock.mp4").write_bytes(b"x")
    (tmp_path / "anim" / "gen.mp4").write_bytes(b"x")
    for clip in (tmp_path / "stock.mp4", tmp_path / "anim" / "gen.mp4"):
        seen.clear()
        render._render_ungated([clip], [3.0], tmp_path / "n.wav", None, tmp_path, tmp_path / "out.mp4")
        vf = next(a[a.index("-vf") + 1] for a in seen if "-stream_loop" in a)
        assert ("eq=brightness" in vf) == (clip.parent.name != "anim")


def test_a_3d_remake_always_draws_the_opening_scenes_so_the_hook_is_never_a_museum_photo():
    """27 Oct, Mami Wata v2: the first 75 seconds were real museum photos; the hook should be the animated, drawn scene."""
    lines = [{"text": f"Line {i}."} for i in range(8)]
    assert run._forced_art({"lines": lines}) == set()
    assert run._forced_art({"lines": lines, "art_style": "3d"}) == {"Line 0.", "Line 1.", "Line 2.", "Line 3."}
    assert run._forced_art({"lines": lines, "art_style": "3d", "redraw_lines": ["Line 6."]}) == {"Line 0.", "Line 1.", "Line 2.", "Line 3.", "Line 6."}


# ---- vertical (Shorts) ----
def test_a_vertical_first_frame_is_720_by_1280_and_the_clip_settings_ask_for_9_16(tmp_path):
    img = tmp_path / "v.jpg"
    Image.new("RGB", (900, 900), (1, 2, 3)).save(img)
    url = animate.frame_url(img, (720, 1280))
    assert Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size == (720, 1280)
    base = {"model": "x", "aspect_ratio": "16:9", "resolution": "720p", "cost_scope": "footage-test"}
    assert animate.clip_config(base, True)["aspect_ratio"] == "9:16" and animate.clip_config(base, False)["aspect_ratio"] == "16:9"
    assert animate.clip_config(base, True)["cost_scope"] == "animation" and animate.clip_config(base, True)["model"] == modelcfg.get("video_generation")


def test_a_shorts_animation_step_uses_the_vertical_size_and_generator(monkeypatch, scenes):
    clips, lines = scenes
    seen = {}
    monkeypatch.setattr(animate, "clip_generator", lambda vertical=False: seen.update(vertical=vertical) or "GEN")
    monkeypatch.setattr(animate, "animate_scenes", lambda c, l, n, budget, gen, **k: seen.update(k) or (c, {"animated": 0, "cached": 0, "failed": 0, "spent": 0.0, "scenes": []}))
    run._animate({"lines": lines, "animate": 1}, clips, [], vertical=True)
    assert seen == {"vertical": True, "size": (720, 1280)}


# ---- a Short cut from one named documentary, in 3D with animation ----
import clipper
import test_clipper


def test_a_3d_short_is_cut_from_a_named_documentary_and_the_chapter_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    test_clipper.make_doc(tmp_path, "doc-a")
    made = []
    produce = lambda data, topic, **kw: made.append((data, kw)) or tmp_path / "short-1"
    got = clipper.make_from("doc-a", {"art_style": "3d", "animate": 2, "hold": True}, produce=produce, chat=lambda p: {"hook": "Why did it fall?", "title": "The fall"})
    data, kw = made[0]
    assert got == tmp_path / "short-1" and data["source_doc"] == "doc-a" and data["art_style"] == "3d" and data["animate"] == 2 and data["hold"] is True and kw["requeue"] is False
    assert json.loads((tmp_path / "doc-a" / "meta.json").read_text())["clips"] == [data["clip_start_line"]]
    assert clipper.make_from("no-such-doc", {}, produce=produce) is None


def test_the_motion_prompt_forbids_anything_the_scene_does_not_already_show():
    """Real clip, 30 Oct 2026: 'warm light flickering' on a desert soldier gave fire and explosions after 3 seconds, events no source states. A documentary must not show them."""
    p = animate.motion_prompt("An army marched into the desert.", "dunes").lower()
    assert "no fire" in p and "no explosions" in p and "no new people or objects" in p and "does not already show" in p
    assert "flickering" not in p  # the word that invited flames
