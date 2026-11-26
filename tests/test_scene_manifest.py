"""Scene manifest (25 Nov 2026): the Seven Sleepers v2 film filled its first 46 scenes from the subject's reserve pool in search order and the record kept only
counts, so the mapping could not be traced. These tests use the real footage.scene_images with the Commons search faked (no network)."""
import hashlib
import json

import pytest

import aiart
import footage
import reviewer
import scenemanifest


@pytest.fixture
def library(monkeypatch, tmp_path):
    """A fake Commons: queries -> files. Topic and anchors fill the reserve; a line's own visual note finds only what is listed for it."""
    files = {}

    def f(name):
        if name not in files:
            p = tmp_path / f"{name}.jpg"
            p.write_bytes(name.encode())
            files[name] = (p, f"{name} (Wikimedia Commons, Public domain)")
        return files[name]

    db = {"Seven Sleepers": [f("legend_icon"), f("legend_fresco")], "Ephesus": [f("ephesus_coin"), f("diana_herm")], "Najran in Arabia": [f("najran_fort")]}

    def fake(query, anchors=None, limit=1, skip=(), judge=None):
        return [h for h in db.get(query, []) if h[0] not in skip][:limit]

    monkeypatch.setattr(footage, "images_for", fake)
    return f, db


def _lines(*texts):
    return [{"text": t, "visual": v} for t, v in texts]


def test_lines_whose_own_search_fails_get_the_reserve_in_search_order_and_the_trace_says_so(library):
    """The root cause, reproduced: four lines about different things get the subject's reserve in the order it was searched, whatever they say."""
    f, _ = library
    lines = _lines(("Jacob of Serugh, a Syriac bishop", "Syriac bishop writing"), ("the source is lost", "lost Greek scroll"),
                   ("the Orthodox Church honours them", "Orthodox icon"), ("the Qur'an's chapter", "Quran manuscript"), ("Najran's view", "Najran in Arabia"))
    trace = []
    clips, credits, stats = footage.scene_images(lines, "Seven Sleepers", ["Ephesus"], trace=trace)
    assert [c.stem for c in clips] == ["legend_icon", "legend_fresco", "ephesus_coin", "diana_herm", "najran_fort"]
    assert [t["how"] for t in trace] == ["reserve", "reserve", "reserve", "reserve", "line_search"]
    assert stats["unique"] == 5  # the old record: "5 different on-topic images", nothing about which line got which


def test_a_failed_drawing_that_falls_back_to_an_earlier_picture_is_named_reuse(library):
    lines = _lines(("a", "nothing"), ("b", "nothing"), ("c", "nothing"), ("d", "nothing"), ("e", "nothing"))
    trace = []
    clips, _, _ = footage.scene_images(lines, "Seven Sleepers", ["Ephesus"], art=lambda l: None, art_limit=5, trace=trace)
    assert [t["how"] for t in trace] == ["reserve"] * 4 + ["reuse"]  # the drawing failed: the fifth scene repeats the first picture, and the trace says so
    assert clips[4] == clips[0]


def test_drawn_forced_and_line_search_scenes_are_told_apart(library, tmp_path):
    drawn = tmp_path / "drawn.jpg"
    drawn.write_bytes(b"d")
    lines = _lines(("forced line", "anything"), ("Najran's view", "Najran in Arabia"), ("x", "nothing"), ("y", "nothing"), ("z", "nothing"), ("w", "nothing"))
    trace = []
    footage.scene_images(lines, "Seven Sleepers", ["Ephesus"], art=lambda l: (drawn, "AI"), art_limit=9, force_art={"forced line"}, art_first=True, trace=trace)
    assert [t["how"] for t in trace] == ["forced_drawn", "line_search", "art_first", "art_first", "art_first", "art_first"]


def test_the_trace_changes_no_choice(library):
    lines = _lines(("a", "nothing"), ("Najran's view", "Najran in Arabia"), ("c", "nothing"))
    assert footage.scene_images(lines, "Seven Sleepers", ["Ephesus"]) == footage.scene_images(lines, "Seven Sleepers", ["Ephesus"], trace=[])


def test_ids_come_from_the_narration_not_the_position_and_survive_reordering():
    a, b, c = {"text": "first"}, {"text": "second"}, {"text": "third"}
    ids = dict(zip(["first", "second", "third"], scenemanifest.scene_ids([a, b, c])))
    assert dict(zip(["third", "first", "second"], scenemanifest.scene_ids([c, a, b]))) == ids
    assert scenemanifest.scene_ids([a, a])[1].endswith("#2")  # the same sentence twice still gets two ids


def test_reordering_with_pictures_that_follow_their_lines_is_a_move_not_a_change(tmp_path):
    fa, fb, fc = (tmp_path / n for n in ("a.jpg", "b.jpg", "c.jpg"))
    for p in (fa, fb, fc):
        p.write_bytes(p.name.encode())
    old = scenemanifest.build(_lines(("A", "a"), ("B", "b"), ("C", "c")), [("selected", [fa, fb, fc])], [{"how": "drawn"}] * 3)
    new = scenemanifest.build(_lines(("C", "c"), ("A", "a"), ("B", "b")), [("selected", [fc, fa, fb])], [{"how": "drawn"}] * 3)
    d = scenemanifest.diff(old, new)
    assert d["changed"] == [] and sorted(d["moved"]) == [0, 1, 2]


def test_inserting_a_line_silently_moves_reserve_pictures_and_the_diff_catches_it(library):
    """What the old pipeline did without a word: two unchanged lines get different pictures because a new line took the reserve's first one."""
    lines = _lines(("L1", "nothing"), ("L2", "nothing"))
    t1, t2 = [], []
    c1, _, _ = footage.scene_images(lines, "Seven Sleepers", ["Ephesus"], trace=t1)
    longer = _lines(("NEW", "nothing")) + lines
    c2, _, _ = footage.scene_images(longer, "Seven Sleepers", ["Ephesus"], trace=t2)
    d = scenemanifest.diff(scenemanifest.build(lines, [("selected", c1)], t1), scenemanifest.build(longer, [("selected", c2)], t2))
    assert d["changed"] == [1, 2] and d["new_lines"] == [0]


def test_a_revised_line_that_keeps_its_old_picture_is_stale_but_a_redrawn_one_is_not(tmp_path):
    fa, fb = tmp_path / "a.jpg", tmp_path / "b.jpg"
    fa.write_bytes(b"a")
    fb.write_bytes(b"b")
    old = scenemanifest.build(_lines(("A", "a"), ("B old", "b")), [("selected", [fa, fb])], [{"how": "reserve"}] * 2)
    kept = scenemanifest.build(_lines(("A", "a"), ("B new", "b")), [("selected", [fa, fb])], [{"how": "reserve"}] * 2)
    assert scenemanifest.diff(old, kept)["stale"] == [1]
    drawn = scenemanifest.build(_lines(("A", "a"), ("B new", "b")), [("selected", [fa, fb])], [{"how": "reserve"}, {"how": "drawn"}])
    assert scenemanifest.diff(old, drawn)["stale"] == []


def test_a_drawn_picture_is_keyed_by_its_line_so_reordering_cannot_move_it():
    def key(t):
        return hashlib.md5(aiart.prompt_for(t, "v", "Seven Sleepers", False).encode()).hexdigest()[:16]
    texts = ["one", "two", "three"]
    assert [key(t) for t in texts] == [key(t) for t in texts[::-1]][::-1]


def test_a_later_step_that_replaces_a_scene_is_recorded_with_what_it_replaced(tmp_path):
    a, b, globe = tmp_path / "a.jpg", tmp_path / "b.jpg", tmp_path / "globe.mp4"
    for p in (a, b, globe):
        p.write_bytes(p.name.encode())
    e = scenemanifest.build(_lines(("A", "a"), ("B", "b")), [("selected", [a, b]), ("blender", [a, globe])], [{"how": "reserve"}, {"how": "reserve"}])
    assert e[1]["how"] == "blender" and e[1]["replaced"].endswith("b.jpg") and e[0]["how"] == "reserve"


def test_write_is_atomic_keeps_the_previous_manifest_and_reports_the_changes(tmp_path):
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    lines = _lines(("A", "a"), ("B", "b"))
    s1 = scenemanifest.write(tmp_path, lines, [("selected", [a, b])], [{"how": "drawn"}] * 2)
    s2 = scenemanifest.write(tmp_path, lines, [("selected", [b, a])], [{"how": "reserve"}] * 2)
    assert (tmp_path / "scenes.prev.json").exists() and not (tmp_path / "scenes.tmp").exists()
    assert "changes_since_last_render" not in s1 and s2["changes_since_last_render"]["changed"] == [0, 1]
    assert s2["sha256"] == hashlib.sha256((tmp_path / "scenes.json").read_bytes()).hexdigest()
    assert json.loads((tmp_path / "scenes.json").read_text())["scenes"][0]["sha256"] == hashlib.sha256(b"b").hexdigest()


def test_the_reviewer_warns_on_a_reserve_run_and_stays_quiet_for_older_films():
    base = {"format": "doc", "footage": {"scenes": 6, "unique": 6, "missing": 0}, "grounded": True}
    rows = {r["name"]: r for r in reviewer.footage_checks(base)}
    assert "scene_sources" not in rows  # a film made before the manifest existed gets no new warning
    bad = dict(base, scene_manifest={"scenes": 6, "how": {"reserve": 5, "drawn": 1}, "reserve": [0, 1, 2, 3, 4], "reuse": [], "reserve_runs": [[0, 1, 2, 3, 4]], "same_file": {}})
    row = {r["name"]: r for r in reviewer.footage_checks(bad)}["scene_sources"]
    assert row["ok"] is False and row["severity"] == "warn" and "0-4" in row["detail"]
    good = dict(base, scene_manifest={"scenes": 6, "how": {"drawn": 6}, "reserve": [], "reuse": [], "reserve_runs": [], "same_file": {}})
    assert {r["name"]: r for r in reviewer.footage_checks(good)}["scene_sources"]["ok"] is True
    broken = dict(base, scene_manifest={"error": "OSError: disk"})
    assert {r["name"]: r for r in reviewer.footage_checks(broken)}["scene_sources"]["ok"] is False
