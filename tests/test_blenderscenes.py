"""Blender as a production component (blenderscenes.py, ccrender.render_clip, 20 Nov 2026): only true-to-the-line scenes, never on the hook or a people scene, a globe only
from the source article's own coordinates, and a failure never stops a video."""
import json
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import blenderscenes
import ccrender

REAL_BLENDER = Path(os.environ.get("BLENDER") or Path.home() / "tools" / "blender" / "blender")


def doc(lines, chapters=None, sources=("Wikipedia: Hampi (CC BY-SA 4.0), retold in our own words",), anchors=()):
    return {"lines": [{"text": t, "visual": v} for t, v in lines], "chapters": chapters or [{"title": "a", "start_line": 0}], "sources": list(sources), "anchors": list(anchors)}


def test_a_template_is_chosen_only_by_whole_words_of_the_line():
    assert blenderscenes.match({"text": "The caravan crossed the desert for weeks.", "visual": ""}) == "dunes"
    assert blenderscenes.match({"text": "A stone circle stood on the hill.", "visual": ""}) == "stones"
    assert blenderscenes.match({"text": "They walked past the colonnade of the agora.", "visual": ""}) == "temple"
    assert blenderscenes.match({"text": "The fleet sailed into the open sea.", "visual": ""}) == "sea"
    assert blenderscenes.match({"text": "He served a dessert at the seaside temple of Bulguksa.", "visual": "Bulguksa temple"}) is None  # no Greek columns for a Korean temple, no 'sea' in 'seaside'


def test_the_source_title_is_read_from_the_wikipedia_credit():
    assert blenderscenes.source_title({"sources": ["Wikipedia: Nok culture (CC BY-SA 4.0), retold in our own words", "https://en.wikipedia.org/wiki/Nok_culture"]}) == "Nok culture"
    assert blenderscenes.source_title({"sources": ["https://example.org"]}) == ""


def test_the_globe_goes_on_the_first_line_that_names_the_place_never_on_the_hook():
    d = doc([("Hampi was once the richest city on Earth?", "Hampi ruins"), ("What happened to it?", "Hampi"), ("Travellers reached the city.", "travellers"),
             ("In Hampi, markets sold horses.", "Hampi bazaar"), ("Then came 1565.", "battle")] + [("More.", "x")] * 10,
            chapters=[{"title": "a", "start_line": 0}, {"title": "b", "start_line": 2}])
    got = blenderscenes.plan(d, "doc", (15.335, 76.462))
    globes = [p for p in got if p["kind"] == "globe"]
    assert len(globes) == 1 and globes[0]["line"] == 3 and globes[0]["params"] == {"lat": 15.335, "lon": 76.462, "label": "Hampi"}
    assert all(p["line"] >= blenderscenes.HOOK_LINES["doc"] for p in got)
    assert not [p for p in blenderscenes.plan(d, "doc", None) if p["kind"] == "globe"]  # no coordinates from the article: no globe, never a guess


def test_stills_skip_people_scenes_neighbours_and_take_one_per_chapter():
    d = doc([("Hook?", "x"), ("Stakes.", "y"),
             ("The caravan crossed the desert.", "desert caravan"),        # 2: dunes
             ("The dunes rose higher.", "dunes"),                         # 3: next to 2, skipped
             ("A king rode across the desert.", "king portrait desert"),  # 4: its picture is a person, skipped
             ("Chapter two opened on the open sea.", "open sea"),         # 5: a new chapter
             ("They sailed the sea again.", "ship at sea")],              # 6: same chapter as 5
            chapters=[{"title": "a", "start_line": 0}, {"title": "b", "start_line": 5}])
    got = blenderscenes.plan(d, "doc", None)
    assert [(p["line"], p["scene"]) for p in got] == [(2, "dunes"), (5, "sea")]


class FakeRenderer:
    def __init__(self, tmp, fail=()):
        self.tmp, self.fail, self.calls = tmp, set(fail), []

    def version(self):
        return "Blender 5.2.3 LTS"

    def render(self, spec):
        self.calls.append(("still", spec))
        if spec["scene"] in self.fail:
            raise RuntimeError("Blender failed: out of memory")
        f = self.tmp / f"{spec['scene']}.png"
        f.write_bytes(b"png")
        return f

    def render_clip(self, spec, seconds, size):
        self.calls.append(("clip", seconds))
        f = self.tmp / "globe.mp4"
        f.write_bytes(b"mp4")
        return f


def test_a_globe_is_as_long_as_its_line_allows_and_a_failed_scene_is_recorded_not_fatal(tmp_path):
    r = FakeRenderer(tmp_path, fail={"stones"})
    planned = [{"line": 3, "kind": "globe", "scene": "globe", "params": {"lat": 1.0, "lon": 2.0, "label": "X"}},
               {"line": 6, "kind": "still", "scene": "stones", "params": {}}, {"line": 9, "kind": "still", "scene": "dunes", "params": {}}]
    got, stats = blenderscenes.render(planned, [5.0] * 3 + [15.0] + [5.0] * 6, renderer=r)
    assert ("clip", pytest.approx(15.0 / 1.25 + 0.3)) in r.calls  # never shorter than the renderer's 1.25 slow-down can stretch to the line
    assert sorted(got) == [3, 9] and got[3][1] == blenderscenes.CREDIT_GLOBE and got[9][1] == blenderscenes.CREDIT_STILL
    assert stats["failed"] == [{"line": 6, "scene": "stones", "reason": "RuntimeError: Blender failed: out of memory"}] and stats["version"].startswith("Blender")
    clips, credits = blenderscenes.place(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"], ["Wikipedia credit"], got)
    assert clips[3] == got[3][0] and clips[9] == got[9][0] and clips[6] == "g"  # the failed line keeps its usual picture
    assert credits == ["Wikipedia credit", blenderscenes.CREDIT_GLOBE, blenderscenes.CREDIT_STILL]


def test_the_producer_records_blender_and_a_crash_never_stops_the_video(monkeypatch):
    import run

    d = doc([("Hook?", "x"), ("Stakes.", "y"), ("The caravan crossed the desert.", "desert")])
    monkeypatch.setattr(blenderscenes, "render", lambda planned, durations, size: ({2: (Path("dunes.png"), blenderscenes.CREDIT_STILL)},
                                                                                    {"version": "Blender 5.2.3", "engine": "x", "scenes": [{"line": 2}], "failed": []}))
    got = run._blender_scenes(d, [3.0, 3.0, 3.0], "doc", (1920, 1080))
    assert list(got) == [2] and d["blender"]["planned"] == 1 and d["blender"]["version"] == "Blender 5.2.3"
    monkeypatch.setattr(blenderscenes, "render", lambda *a, **k: (_ for _ in ()).throw(MemoryError()))
    d2 = doc([("Hook?", "x"), ("Stakes.", "y"), ("The caravan crossed the desert.", "desert")])
    assert run._blender_scenes(d2, [3.0] * 3, "doc", (1920, 1080)) == {} and d2["blender"]["failed"] is True
    d3 = {**doc([("Hook?", "x"), ("Stakes.", "y"), ("The caravan crossed the desert.", "desert")]), "blender": False}
    assert run._blender_scenes(d3, [3.0] * 3, "doc", (1920, 1080)) == {} and d3["blender"] is False  # switched off in the record


def frames(d: Path, n: int, size=(64, 36)):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        Image.new("RGB", size, (10 * i % 255, 40, 90)).save(d / f"f_{i:04d}.png")


def test_a_clip_whose_frames_are_all_on_disk_is_encoded_without_running_blender_again(tmp_path, monkeypatch):
    monkeypatch.setattr(ccrender.config, "CACHE", str(tmp_path))
    blender = tmp_path / "blender"
    blender.write_text("")
    monkeypatch.setattr(ccrender, "BLENDER", blender)
    spec, secs, size = {"scene": "globe", "params": {"lat": 1, "lon": 2}}, 2.0, (64, 36)
    job = ccrender.clip_job(spec, secs, size)
    frames(ccrender.cache_dir() / f"frames-{ccrender.spec_key(job)}", job["frames"], (32, 18))
    real = subprocess.run
    monkeypatch.setattr(ccrender.subprocess, "run", lambda args, **k: (_ for _ in ()).throw(AssertionError("Blender must not run")) if str(args[0]) == str(blender) else real(args, **k))
    out = ccrender.render_clip(spec, secs, size)
    assert out.exists() and ccrender.clip_seconds(out) >= secs * 0.95
    assert not (ccrender.cache_dir() / f"frames-{ccrender.spec_key(job)}").exists()  # its own frame folder is removed once the clip is checked


def test_a_placeholder_frame_from_a_stopped_render_is_drawn_again(tmp_path, monkeypatch):
    monkeypatch.setattr(ccrender.config, "CACHE", str(tmp_path))
    blender = tmp_path / "blender"
    blender.write_text("")
    monkeypatch.setattr(ccrender, "BLENDER", blender)
    job = ccrender.clip_job({"scene": "globe", "params": {}}, 2.0, (64, 36))
    fdir = ccrender.cache_dir() / f"frames-{ccrender.spec_key(job)}"
    frames(fdir, job["frames"], (32, 18))
    (fdir / "f_0007.png").write_bytes(b"")  # Blender's placeholder for the frame it was drawing when it was stopped
    asked = []
    real = subprocess.run

    def fake(args, **k):
        if str(args[0]) == str(blender):
            asked.append(args)
            assert not (fdir / "f_0007.png").exists()  # the empty placeholder was removed, so Blender draws that frame again
            Image.new("RGB", (32, 18)).save(fdir / "f_0007.png")
            return subprocess.CompletedProcess(args, 0, "ANIM_DONE globe 25\n", "")
        return real(args, **k)

    monkeypatch.setattr(ccrender.subprocess, "run", fake)
    assert ccrender.render_clip({"scene": "globe", "params": {}}, 2.0, (64, 36)).exists() and len(asked) == 1


def test_a_clip_shorter_than_asked_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ccrender.config, "CACHE", str(tmp_path))
    blender = tmp_path / "blender"
    blender.write_text("")
    monkeypatch.setattr(ccrender, "BLENDER", blender)
    monkeypatch.setattr(ccrender, "clip_seconds", lambda p: 0.5)
    job = ccrender.clip_job({"scene": "globe", "params": {}}, 2.0, (64, 36))
    frames(ccrender.cache_dir() / f"frames-{ccrender.spec_key(job)}", job["frames"], (32, 18))
    with pytest.raises(RuntimeError, match="was asked"):
        ccrender.render_clip({"scene": "globe", "params": {}}, 2.0, (64, 36))


@pytest.mark.skipif(not REAL_BLENDER.exists(), reason="Blender is not installed on this machine")
def test_the_real_blender_renders_a_still_with_its_depth_map_and_a_globe_clip_headless(tmp_path, monkeypatch):
    """The real thing, small: Cycles on the CPU, no GPU, no OpenGL (the depth pass once used EEVEE and aborted in the container)."""
    monkeypatch.setattr(ccrender, "BLENDER", REAL_BLENDER)
    monkeypatch.setattr(ccrender.config, "CACHE", str(tmp_path))
    import depth

    monkeypatch.setattr(depth, "depth_dir", lambda: tmp_path / "depth")
    still = ccrender.render({"scene": "sea", "width": 96, "height": 54, "samples": 2})
    assert Image.open(still).size == (96, 54) and any((tmp_path / "depth").glob("*.png"))
    clip = ccrender.render_clip({"scene": "globe", "params": {"lat": 15.3, "lon": 76.5, "label": "Hampi"}, "samples": 1}, 0.5, (64, 36))
    assert ccrender.clip_seconds(clip) >= 0.45


def test_the_behaviour_check_holds_and_fails_on_each_broken_rule(monkeypatch):
    """The agenteval case passes on the real code and fails when a rule is broken (an eval that cannot fail proves nothing)."""
    import agenteval

    ok, why = agenteval.case_blender_scenes_are_true_to_the_line_and_never_stop_a_video()
    assert ok, why
    for name, value in (("person_scene", lambda line: False),                 # mutation: a person's line gets an empty 3D place
                        ("HOOK_LINES", {"doc": 0, "short": 0}),               # mutation: Blender takes the hook
                        ("place", lambda clips, credits, got: ([None] * len(clips), credits))):  # mutation: a failed scene blanks its line
        with monkeypatch.context() as m:
            m.setattr(blenderscenes, name, value)
            assert not agenteval.case_blender_scenes_are_true_to_the_line_and_never_stop_a_video()[0], name


def test_the_globe_uses_the_first_source_article_that_has_coordinates(monkeypatch):
    """20 Nov 2026: "Seven Sleepers" (a legend) has no coordinates; its second source, the cave, does."""
    monkeypatch.setattr(blenderscenes, "coordinates", lambda t: {"Cave of the Seven Sleepers": (31.8987, 35.9738), "Ephesus": (37.9394, 27.3417)}.get(t))
    d = {"sources": ["Wikipedia: Seven Sleepers (CC BY-SA 4.0), retold in our own words", "Wikipedia: Cave of the Seven Sleepers (CC BY-SA 4.0), retold in our own words"],
         "lines": [{"text": t, "visual": "v"} for t in ("Who slept for centuries?", "Why?", "Near Ephesus a cave was sealed.", "x", "x", "x")], "anchors": ["Ephesus"],
         "chapters": [{"title": "a", "start_line": 0}]}
    assert blenderscenes.source_title(d) == "Cave of the Seven Sleepers"
    globe = [p for p in blenderscenes.plan(d, "doc", blenderscenes.coordinates(blenderscenes.source_title(d))) if p["kind"] == "globe"]
    # the cave article (near Amman) is a second source no line names: the Ephesus line gets Ephesus's own pin, never the cave's
    assert globe == [{"line": 2, "kind": "globe", "scene": "globe", "params": {"lat": 37.9394, "lon": 27.3417, "label": "Ephesus"}}]
    d2 = {**d, "_place_title": None, "anchors": []}
    d2.pop("_place_title")
    assert not [p for p in blenderscenes.plan(d2, "doc", blenderscenes.coordinates(blenderscenes.source_title(d2))) if p["kind"] == "globe"]  # no named place: no globe at all
