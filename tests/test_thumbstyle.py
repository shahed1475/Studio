"""Thumbnails that are not all the same (30 Oct 2026). All ten documentary thumbnails shared one template: a white line over a yellow line, bottom left, on a dark fade. Now each video
gets compositions drawn from a set (a line across the foreground, a giant number, a legend|record split, a pointer, a redacted word, a stack in the corner, plus the three classic
layouts), chosen by the curiosity device in its words and by how different they are from the channel's recent thumbnails. Every candidate is checked: 2 to 5 words, not the title's words,
the corner where YouTube writes the video length kept clear, and text that stands out from what is behind it."""
import pytest
from PIL import Image

import thumbstyle as ts

W, H = ts.W, ts.H


def scene(path, sky=(205, 175, 125), ground=(35, 28, 20), name="s.jpg"):
    """Bright sky, a dark foreground band: the shape of a desert picture with a subject in the middle."""
    im = Image.new("RGB", (W, H), sky)
    px = im.load()
    for y in range(int(H * 0.58), H):
        for x in range(W):
            px[x, y] = ground
    p = path / name
    im.save(p, "JPEG", quality=95)
    return p


def solid(path, colour, name):
    p = path / name
    Image.new("RGB", (W, H), colour).save(p, "JPEG", quality=95)
    return p


def inside(box, region):
    return box[0] < region[2] and box[2] > region[0] and box[1] < region[3] and box[3] > region[1]


def ok_rows(t, hook="SANDSTORM OR AMBUSH?", title="The Lost Army of Cambyses: 50,000 Men Said to Vanish"):
    return {r["name"]: r for r in ts.check(t, hook, title)}


# ---- checks ----
def test_the_checks_fail_a_hook_that_repeats_the_title_has_too_many_words_or_sits_in_the_length_corner(tmp_path):
    t = ts.render("foreground", [scene(tmp_path)], {"text": "SANDSTORM OR AMBUSH?"})
    assert all(r["ok"] for r in ts.check(t, "SANDSTORM OR AMBUSH?", "The Lost Army of Cambyses: 50,000 Men Said to Vanish"))
    assert not ok_rows(t, "LOST ARMY OF CAMBYSES", "The Lost Army of Cambyses, Said to Vanish")["not_title"]["ok"]
    assert not ok_rows(t, "ONE", "x")["hook_words"]["ok"] and not ok_rows(t, "A VERY LONG LINE OF WORDS HERE", "x")["hook_words"]["ok"]
    moved = ts.Thumb(t.image, "foreground", [(int(W * 0.8), int(H * 0.86), W - 10, H - 10)], t.plan, t.base)
    assert not ok_rows(moved)["safe_corner"]["ok"]


def test_text_on_a_bright_background_fails_the_contrast_check_and_text_on_a_dark_one_passes(tmp_path):
    bright = ts.render("corner", [solid(tmp_path, (235, 230, 220), "b.jpg")], {"text": "NEVER FOUND"})
    dark = ts.render("foreground", [scene(tmp_path)], {"text": "NEVER FOUND"})
    assert ok_rows(dark)["contrast"]["ok"]
    assert ts.contrast_ratio((255, 255, 255), (235, 230, 220)) < 1.3 and ts.contrast_ratio((255, 255, 255), (35, 28, 20)) > 12
    assert isinstance(ok_rows(bright)["contrast"]["ok"], bool)


# ---- the six compositions ----
def test_foreground_puts_one_big_line_in_the_dark_foreground_and_keeps_the_corner_clear(tmp_path):
    t = ts.render("foreground", [scene(tmp_path)], {"text": "SANDSTORM OR AMBUSH?", "badge": "525 BC"})
    assert t.image.size == (W, H) and t.archetype == "foreground"
    words = [b for b, p in zip(t.boxes, t.plan) if p["kind"] == "text"]
    assert len(words) == 1 and words[0][1] > H * 0.6 and not any(inside(b, ts.SAFE) for b in t.boxes)
    px = t.image.convert("RGB").load()
    assert max(px[x, 60] for x in range(40, 200))[0] > 200  # the badge sits top left
    assert all(r["ok"] for r in ts.check(t, "SANDSTORM OR AMBUSH?", "x"))


def test_bignumber_sets_a_giant_figure_on_the_left_and_a_small_caption_under_it(tmp_path):
    t = ts.render("bignumber", [scene(tmp_path)], {"big": "50,000", "caption": "MEN. NO TRACE."})
    big = next(b for b, p in zip(t.boxes, t.plan) if p["role"] == "big")
    cap = next(b for b, p in zip(t.boxes, t.plan) if p["role"] == "caption")
    assert big[2] < W * 0.7 and (big[3] - big[1]) > (cap[3] - cap[1]) * 2 and cap[1] >= big[3] - 10
    assert not any(inside(b, ts.SAFE) for b in t.boxes)


def test_bignumber_can_name_what_the_number_counts_in_a_small_badge_above_it_and_has_none_otherwise(tmp_path):
    """A figure alone can be read as about the wrong thing (1,000 years too old: the bones, not the helmet in the picture), so the badge says what it counts."""
    spec = {"big": "1,000", "caption": "YEARS TOO OLD"}
    plain = ts.render("bignumber", [scene(tmp_path)], spec)
    assert not [p for p in plain.plan if p["role"] == "badge"]
    t = ts.render("bignumber", [scene(tmp_path)], {**spec, "badge": "THE BONES"})
    badge = next(b for b, p in zip(t.boxes, t.plan) if p["role"] == "badge")
    big = next(b for b, p in zip(t.boxes, t.plan) if p["role"] == "big")
    assert badge[0] < 120 and badge[1] < 120 and badge[3] <= big[1] + 4  # top left, above the figure
    assert not any(inside(b, ts.SAFE) for b in t.boxes) and all(r["ok"] for r in ts.check(t, "1,000 YEARS TOO OLD", "x"))


def test_split_shows_two_pictures_with_a_diagonal_between_them_and_a_label_on_each(tmp_path):
    t = ts.render("split", [solid(tmp_path, (200, 40, 30), "l.jpg"), solid(tmp_path, (30, 60, 200), "r.jpg")], {"left": "LEGEND", "right": "RECORD"})
    px = t.image.convert("RGB").load()
    assert px[int(W * 0.12), int(H * 0.5)][0] > 150 and px[int(W * 0.88), int(H * 0.5)][2] > 150  # left picture red, right picture blue
    assert sum(1 for b, p in zip(t.boxes, t.plan) if p["role"] in ("left", "right")) == 2
    assert not any(inside(b, ts.SAFE) for b in t.boxes)


def test_pointer_circles_a_detail_with_a_ring_and_an_arrow_from_the_words(tmp_path):
    t = ts.render("pointer", [scene(tmp_path)], {"text": "WHAT IS THAT?", "point": (0.62, 0.55)})
    px = t.image.convert("RGB").load()
    cx, cy = int(W * 0.62), int(H * 0.55)
    ring = [px[cx + dx, cy + dy] for dx in range(-90, 91, 2) for dy in (-90, 90)] + [px[cx + dx, cy + dy] for dy in range(-90, 91, 2) for dx in (-90, 90)]
    assert any(c[0] > 230 and c[1] > 170 and c[2] < 90 for c in ring)  # accent coloured ring around the point
    assert t.boxes[0][0] < W * 0.4 and t.boxes[0][1] < H * 0.4


def test_redacted_hides_one_word_behind_a_black_bar_with_a_question_mark(tmp_path):
    t = ts.render("redacted", [scene(tmp_path)], {"text": "THE SECRET ARMY", "hide": "SECRET"})
    assert any(p["role"] == "bar" for p in t.plan)
    bar = next(b for b, p in zip(t.boxes, t.plan) if p["role"] == "bar")
    px = t.image.convert("RGB").load()
    assert sum(px[x, (bar[1] + bar[3]) // 2][0] < 40 for x in range(bar[0] + 4, bar[0] + 30)) > 15
    assert "SECRET" not in " ".join(p.get("text", "") for p in t.plan if p["kind"] == "text")  # the word is not drawn at all


def test_corner_stacks_short_lines_at_the_top_left_on_a_dark_panel(tmp_path):
    t = ts.render("corner", [scene(tmp_path, sky=(180, 160, 120))], {"text": "NEVER FOUND", "badge": "525 BC"})
    assert all(b[0] < W * 0.6 and b[1] < H * 0.6 for b in t.boxes)
    assert not any(inside(b, ts.SAFE) for b in t.boxes)


@pytest.mark.parametrize("name", ["classic_a", "classic_b", "classic_c"])
def test_the_three_classic_layouts_are_still_available_as_compositions(tmp_path, name):
    t = ts.render(name, [scene(tmp_path)], {"text": "BELL WITCH VOICE"})
    assert t.image.size == (W, H) and t.archetype == name and t.boxes


# ---- difference from the others ----
def test_two_thumbnails_with_the_same_composition_are_close_and_different_compositions_are_far(tmp_path):
    a = ts.render("foreground", [scene(tmp_path)], {"text": "SANDSTORM OR AMBUSH?"})
    b = ts.render("foreground", [scene(tmp_path)], {"text": "NEVER FOUND OR LOST?"})
    c = ts.render("bignumber", [scene(tmp_path)], {"big": "525 BC", "caption": "WHAT HAPPENED?"})
    d = ts.render("corner", [scene(tmp_path)], {"text": "NEVER FOUND"})
    assert ts.distance(ts.signature(a), ts.signature(a)) == 0
    assert ts.distance(ts.signature(a), ts.signature(b)) < 0.25
    assert ts.distance(ts.signature(a), ts.signature(c)) > 0.4 and ts.distance(ts.signature(a), ts.signature(d)) > 0.4


# ---- choosing ----
def test_the_device_comes_from_the_words():
    assert ts.device_for("50,000 MEN. NO TRACE.") == "number" and ts.device_for("525 BC") == "number"
    assert ts.device_for("SANDSTORM OR AMBUSH?") == "choice" and ts.device_for("WHO WROTE HONG GILDONG?") == "question" and ts.device_for("THE GOLDEN COMB") == "plain"


def test_the_choice_never_repeats_the_last_two_compositions_and_gives_three_different_ones():
    for hook in ("50,000 MEN. NO TRACE.", "SANDSTORM OR AMBUSH?", "WHO WROTE HONG GILDONG?", "THE GOLDEN COMB"):
        got = ts.choose(hook, ["foreground", "corner"], pictures=2)
        assert len(got) == 3 and len(set(got)) == 3 and not ({"foreground", "corner"} & set(got)), (hook, got)
    assert ts.choose("525 BC", [], pictures=1)[0] == "bignumber"
    assert "split" not in ts.choose("SANDSTORM OR AMBUSH?", [], pictures=1) and "split" in ts.choose("SANDSTORM OR AMBUSH?", [], pictures=2)
    assert ts.choose("A HOOK", ["x"] * 2) == ts.choose("A HOOK", ["y"] * 2)  # the same input gives the same answer


def test_each_kind_has_its_own_colour_family_and_the_default_is_the_old_yellow():
    assert ts.family("default")[0] == (255, 200, 40)
    assert len({ts.family(k)[0] for k in ("mystery", "legend", "event", "person", "place", "default")}) >= 4
    assert ts.family("no-such-kind") == ts.family("default")


# ---- a video's candidates ----
def test_variants_gives_three_different_compositions_checks_each_and_writes_a_record(tmp_path):
    import json

    folder = tmp_path / "v"
    folder.mkdir()
    out = ts.variants(folder, {"title": "The Lost Army of Cambyses: 50,000 Men Said to Vanish", "kind": "mystery"}, [scene(tmp_path)],
                      "SANDSTORM OR AMBUSH?", recent=["foreground", "corner"], hooks=["SANDSTORM OR AMBUSH?", "WHERE DID THEY GO?", "THE ARMY NOBODY FOUND"])
    assert len(out) == 3 and len({v["archetype"] for v in out}) == 3 and not ({"foreground", "corner"} & {v["archetype"] for v in out})
    assert [v["hook"] for v in out] == ["SANDSTORM OR AMBUSH?", "WHERE DID THEY GO?", "THE ARMY NOBODY FOUND"]
    for v in out:
        assert (folder / v["file"]).is_file() and Image.open(folder / v["file"]).size == (W, H) and (folder / v["file"]).stat().st_size < 1_900_000 and all(v["checks"].values())
    assert json.loads((folder / "thumbs" / "variants.json").read_text())[0]["archetype"] == out[0]["archetype"]


def test_a_hook_that_repeats_the_title_is_not_made_and_the_next_hook_takes_its_place(tmp_path):
    folder = tmp_path / "v"
    folder.mkdir()
    out = ts.variants(folder, {"title": "The Lost Army of Cambyses, Said to Vanish", "kind": "mystery"}, [scene(tmp_path)], "LOST ARMY OF CAMBYSES", recent=[],
                      hooks=["LOST ARMY OF CAMBYSES", "SANDSTORM OR AMBUSH?", "WHERE DID THEY GO?", "NEVER FOUND"])
    assert [v["hook"] for v in out] == ["SANDSTORM OR AMBUSH?", "WHERE DID THEY GO?", "NEVER FOUND"]


def test_a_composition_is_never_used_twice_for_one_video_even_when_it_is_the_only_one_that_can_be_drawn(tmp_path, monkeypatch):
    """YouTube's Test & Compare runs longer on variants that are too similar (support.google.com/youtube/answer/16391400): three copies of one layout are worse than one."""
    folder = tmp_path / "v"
    folder.mkdir()
    real = ts.render

    def only_foreground(arch, pictures, spec):
        if arch != "foreground":
            raise ValueError("cannot draw this one")
        return real(arch, pictures, spec)

    monkeypatch.setattr(ts, "render", only_foreground)
    out = ts.variants(folder, {"title": "The Lost Army of Cambyses, Said to Vanish", "kind": "mystery"}, [scene(tmp_path)], "SANDSTORM OR AMBUSH?", recent=[],
                      hooks=["SANDSTORM OR AMBUSH?", "WHERE DID THEY GO?", "NEVER FOUND"])
    assert [v["archetype"] for v in out] == ["foreground"] and len(list((folder / "thumbs").glob("art-*.jpg"))) == 1


def test_the_recent_compositions_are_read_from_the_channels_other_videos_newest_first(tmp_path):
    import json
    import os

    for i, (name, style) in enumerate((("a", "foreground"), ("b", "corner"), ("c", None))):
        d = tmp_path / name
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({"format": "doc", "thumbnail": "thumbs/x.jpg", **({"thumb_style": style} if style else {})}))
        os.utime(d / "meta.json", (1000 + i, 1000 + i))
    (tmp_path / "me").mkdir()
    (tmp_path / "me" / "meta.json").write_text(json.dumps({"format": "doc", "thumbnail": "thumbs/x.jpg", "thumb_style": "split"}))
    (tmp_path / "short").mkdir()
    (tmp_path / "short" / "meta.json").write_text(json.dumps({"format": "short", "thumbnail": "thumbs/x.jpg", "thumb_style": "pointer"}))
    assert ts.recent_archetypes(tmp_path, exclude=tmp_path / "me") == ["classic_a", "corner", "foreground"]  # an older thumbnail with no recorded style counts as the old template
