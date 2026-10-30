"""Real moving footage in a film (30 Oct 2026, owner: use real footage, make AI pictures only where needed). Wikimedia Commons video only, with the licences the studio's own check accepts (public
domain, CC0, CC BY and CC BY-SA with a credit line; never non-commercial or no-derivatives), kept only when the file's own title or categories name one of the film's anchors (the live probe
showed Commons search returns dolphins for "Delphi" and a video game for "Egypt desert"), never on a scene that may show people, never on the hook scene or a scene chosen for an animated clip.
Whatever is not found stays an AI picture; any failure leaves the scene as it was."""
import pytest

import footage_real as fr


def page(title, lic="Public domain", cats="", size=5_000_000, duration=40.0, media="VIDEO", url=None):
    return {"title": f"File:{title}", "imageinfo": [{"url": url or f"https://upload.wikimedia.org/{title}", "size": size, "mediatype": media, "duration": duration, "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{title}",
                                                      "extmetadata": {"LicenseShortName": {"value": lic}, "Categories": {"value": cats}, "ImageDescription": {"value": ""}}}]}


class Resp:
    def __init__(self, pages=None, content=b"x" * 100):
        self.pages, self.content, self.status_code = pages, content, 200

    def json(self):
        return {"query": {"pages": {str(i): p for i, p in enumerate(self.pages or [])}}}

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self.content


def test_only_licences_the_studios_own_check_accepts_pass():
    for ok in ("Public domain", "CC0", "CC BY-SA 4.0", "CC BY 3.0", "PD-old-70", "Public domain (US government)"):
        assert fr.licence_ok(ok), ok
    for bad in ("CC BY-NC 2.0", "CC BY-ND 4.0", "CC BY-NC-SA 3.0", "All rights reserved", "", "Fair use", "Non-commercial use only"):
        assert not fr.licence_ok(bad), bad


def test_candidates_keep_only_relevant_usable_free_video_of_a_sensible_size_and_length():
    pages = [page("Siwa_Oasis_palm_grove.webm", cats="Siwa Oasis|Egypt", lic="CC BY-SA 4.0"),
             page("Common_Dolphins_in_the_Bay.webm", cats="Dolphins", lic="CC BY-SA 3.0"),            # the word Delphi is not in it: irrelevant
             page("Siwa_festival.webm", cats="Siwa Oasis", lic="CC BY-NC 2.0"),                        # not free enough
             page("Siwa_huge.webm", cats="Siwa Oasis", size=900_000_000),                              # too big
             page("Siwa_blink.webm", cats="Siwa Oasis", duration=1.5),                                 # too short to cut a shot from
             page("Siwa_photo.jpg", cats="Siwa Oasis", media="BITMAP")]                                # not video
    got = fr.candidates("Siwa Oasis", ["Siwa Oasis", "Herodotus"], get=lambda *a, **k: Resp(pages))
    assert [c["title"] for c in got] == ["Siwa_Oasis_palm_grove.webm"] and got[0]["license"] == "CC BY-SA 4.0" and got[0]["page"].endswith("File:Siwa_Oasis_palm_grove.webm")


def test_a_network_failure_finds_nothing_and_raises_nothing():
    def boom(*a, **k):
        raise fr.requests.RequestException("down")
    assert fr.candidates("Siwa Oasis", ["Siwa"], get=boom) == []


def test_a_fetched_segment_is_a_short_silent_clip_with_a_credit_line_that_names_the_file_its_licence_and_address(tmp_path):
    cand = {"title": "Siwa_Oasis_palm_grove.webm", "url": "https://upload.wikimedia.org/x.webm", "license": "CC BY-SA 4.0", "page": "https://commons.wikimedia.org/wiki/File:Siwa_Oasis_palm_grove.webm", "duration": 40.0, "size": 5_000_000}
    cut = []
    dest = tmp_path / "real-1.mp4"
    got = fr.fetch_segment(cand, dest, get=lambda *a, **k: Resp(content=b"video"), run=lambda cmd, **k: cut.append(cmd) or open(cmd[-1], "wb").write(b"clip"))
    assert got == dest and dest.read_bytes() == b"clip"
    cmd = " ".join(map(str, cut[0]))
    assert "-an" in cut[0] and "-t" in cut[0] and "scale=" in cmd and "-ss" in cut[0]
    credit = dest.with_suffix(".txt").read_text()
    assert "Siwa_Oasis_palm_grove.webm" in credit and "CC BY-SA 4.0" in credit and "commons.wikimedia.org/wiki/File:Siwa" in credit and "Wikimedia Commons" in credit


def test_a_download_over_the_size_limit_or_a_cut_that_fails_gives_nothing_and_leaves_no_file(tmp_path):
    cand = {"title": "x.webm", "url": "https://upload.wikimedia.org/x.webm", "license": "Public domain", "page": "p", "duration": 40.0, "size": fr.MAX_BYTES + 1}
    assert fr.fetch_segment(cand, tmp_path / "a.mp4", get=lambda *a, **k: Resp(), run=lambda *a, **k: pytest.fail("must not cut")) is None
    ok = {**cand, "size": 5_000_000}

    def fail(cmd, **k):
        raise fr.subprocess.CalledProcessError(1, "ffmpeg")
    assert fr.fetch_segment(ok, tmp_path / "b.mp4", get=lambda *a, **k: Resp(), run=fail) is None and not list(tmp_path.glob("*.mp4")) and not list(tmp_path.glob("*.txt"))


def film(n=20):
    return {"anchors": ["Siwa Oasis", "Cambyses II", "Herodotus"], "animate_scenes": [4, 10], "lines": [{"text": f"line {i}", "visual": "a dune" if i % 3 else "a soldier face portrait"} for i in range(n)]}


def test_clips_go_to_evenly_spaced_scenes_that_are_not_the_hook_a_person_scene_or_an_animated_one_and_each_is_credited():
    clips = [f"img{i}.jpg" for i in range(20)]
    made = iter(range(10))
    cand = lambda q, anchors, get=None: [{"title": f"v{q}.webm", "url": "u", "license": "Public domain", "page": "p", "duration": 30.0, "size": 1}]
    fetch = lambda c, dest, **k: f"real{next(made)}.mp4"
    out, credits, stats = fr.for_film(film(), clips, [], 3, flat={2, 5}, search=cand, fetch=fetch, credit_of=lambda p: f"Footage: {p}")
    changed = [i for i, c in enumerate(out) if str(c).startswith("real")]
    assert len(changed) == 3 and 0 not in changed and not {2, 5, 4, 10} & set(changed) and changed == sorted(changed)
    assert changed[-1] - changed[0] >= 6                                    # spread over the film, not three in a row
    assert len(credits) == 3 and stats["used"] == 3 and out[0] == "img0.jpg" and clips[changed[0]].startswith("img")  # the input list is not changed


def test_nothing_found_or_asked_changes_nothing_and_a_crash_is_swallowed():
    clips = [f"img{i}.jpg" for i in range(10)]
    assert fr.for_film(film(10), clips, ["c"], 0)[0] == clips
    none = lambda q, anchors, get=None: []
    out, credits, stats = fr.for_film(film(10), clips, ["c"], 3, search=none)
    assert out == clips and credits == ["c"] and stats["used"] == 0 and stats["queries"] >= 1
    boom = lambda q, anchors, get=None: (_ for _ in ()).throw(RuntimeError("x"))
    out, credits, stats = fr.for_film(film(10), clips, [], 3, search=boom)
    assert out == clips and stats["used"] == 0


def test_the_documentary_producer_asks_for_real_footage_before_it_animates_and_a_film_that_does_not_ask_gets_none():
    import inspect

    import run

    src = inspect.getsource(run._produce_doc)
    assert src.index("_real_footage(") < src.index("_animate(")
    data = {"lines": [{"text": "a", "visual": "a dune"}]}
    clips = ["a.jpg"]
    assert run._real_footage(data, clips, [])[0] == clips and "real_footage" not in data
