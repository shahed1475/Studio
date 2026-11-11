"""Real moving footage in a film (30 Oct 2026, owner: use real footage, make AI pictures only where needed). Wikimedia Commons video only, with the licences the studio's own check accepts (public
domain, CC0, CC BY and CC BY-SA with a credit line; never non-commercial or no-derivatives), kept only when the file's own title or categories name one of the film's anchors (the live probe
showed Commons search returns dolphins for "Delphi" and a video game for "Egypt desert"), never on a scene that may show people, never on the hook scene or a scene chosen for an animated clip.
Whatever is not found stays an AI picture; any failure leaves the scene as it was."""
import pytest

import footage_real as fr

PUBLIC = lambda host: ["208.80.153.240"]  # a public address, so no real DNS look-up happens in a test


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
    got = fr.fetch_segment(cand, dest, get=lambda *a, **k: Resp(content=b"video"), run=lambda cmd, **k: cut.append(cmd) or open(cmd[-1], "wb").write(b"clip"), resolve=PUBLIC)
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


class Limited(Resp):
    def __init__(self, status, retry="3"):
        super().__init__()
        self.status_code, self.headers = status, ({"Retry-After": retry} if retry else {})

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_a_rate_limited_download_waits_the_pause_it_was_told_and_tries_again(tmp_path):
    cand = {"title": "x.ogv", "url": "https://upload.wikimedia.org/x.ogv", "license": "CC BY 4.0", "page": "https://commons.wikimedia.org/wiki/File:x.ogv", "duration": 30.0, "size": 1000}
    seq, waits, cut = [Limited(429), Limited(429), Limited(200)], [], []
    got = fr.fetch_segment(cand, tmp_path / "a.mp4", get=lambda *a, **k: seq.pop(0), sleep=waits.append, run=lambda cmd, **k: cut.append(cmd) or open(cmd[-1], "wb").write(b"mp4"), resolve=PUBLIC)
    assert got is not None and not seq and waits == [3.0, 3.0] and cut


def test_a_download_that_stays_rate_limited_gives_up_without_leaving_files(tmp_path):
    cand = {"title": "y.ogv", "url": "https://upload.wikimedia.org/y.ogv", "license": "CC BY 4.0", "page": "p", "duration": 30.0, "size": 1000}
    got = fr.fetch_segment(cand, tmp_path / "b.mp4", get=lambda *a, **k: Limited(429, None), sleep=lambda s: None, run=lambda *a, **k: pytest.fail("must not cut"))
    assert got is None and not list(tmp_path.glob("*.mp4")) and not list(tmp_path.glob("*.dl"))


# ---- NASA and Pixabay footage (owner's licence decision, 10 Nov 2026) ----
class Hop:
    def __init__(self, status=200, location=None, content=b"v"):
        self.status_code, self.headers, self.content = status, {"Location": location} if location else {}, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise fr.requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        yield self.content


def test_nasa_videos_must_name_the_subject_and_never_show_a_logo_or_insignia(monkeypatch):
    import openmedia
    rows = [{"title": "Antikythera wreck dive survey", "url": "https://images-assets.nasa.gov/a~medium.mp4", "licence": openmedia.NASA_LICENCE, "page": "https://images.nasa.gov/details/a", "credit": "NASA (a)"},
            {"title": "NASA insignia over the Antikythera wreck", "url": "https://images-assets.nasa.gov/b.mp4", "licence": openmedia.NASA_LICENCE, "page": "p", "credit": "NASA (b)"},
            {"title": "Apollo 11 launch", "url": "https://images-assets.nasa.gov/c.mp4", "licence": openmedia.NASA_LICENCE, "page": "p", "credit": "NASA (c)"},
            {"title": "Antikythera without a file", "url": None, "licence": openmedia.NASA_LICENCE, "page": "p", "credit": "NASA (d)"}]
    monkeypatch.setattr(openmedia, "nasa", lambda q, kind, n, get: rows)
    got = fr.nasa_candidates("Antikythera", ["Antikythera Mechanism"])
    assert [c["title"] for c in got] == ["Antikythera wreck dive survey"]
    assert got[0]["source"] == "NASA Image and Video Library" and fr.licence_ok(got[0]["license"]) and got[0]["duration"] == 0.0


def test_pixabay_videos_need_a_key_matching_tags_and_a_sensible_length(monkeypatch):
    import pixabay
    rows = [{"id": 1, "url": "https://cdn.pixabay.com/v/1.mp4", "page": "https://pixabay.com/videos/id-1/", "seconds": 12, "size": 4_000_000, "tags": "greece, shipwreck, antikythera", "credit": "Video by Ann via Pixabay (https://pixabay.com/videos/id-1/)"},
            {"id": 2, "url": "https://cdn.pixabay.com/v/2.mp4", "page": "p2", "seconds": 12, "size": 4_000_000, "tags": "cat, sofa", "credit": "c2"},
            {"id": 3, "url": "https://cdn.pixabay.com/v/3.mp4", "page": "p3", "seconds": 2, "size": 4_000_000, "tags": "antikythera", "credit": "c3"},
            {"id": 4, "url": "https://cdn.pixabay.com/v/4.mp4", "page": "p4", "seconds": 12, "size": fr.MAX_BYTES + 1, "tags": "antikythera", "credit": "c4"}]
    monkeypatch.setattr(pixabay, "search_videos", lambda q, n, get: rows)
    monkeypatch.setattr(pixabay, "key", lambda: "")
    assert fr.pixabay_candidates("Antikythera", ["Antikythera"]) == []          # no key: nothing, not an error
    monkeypatch.setattr(pixabay, "key", lambda: "k")
    got = fr.pixabay_candidates("Antikythera", ["Antikythera"])
    assert [c["page"] for c in got] == ["https://pixabay.com/videos/id-1/"] and got[0]["license"] == "Pixabay Content License" and fr.licence_ok(got[0]["license"])


def test_all_candidates_keep_the_licence_preference_order_commons_then_nasa_then_pixabay(monkeypatch):
    monkeypatch.setattr(fr, "candidates", lambda q, a, get=None: [{"title": "c", "url": "u1"}])
    monkeypatch.setattr(fr, "nasa_candidates", lambda q, a, get=None: [{"title": "n", "url": "u2"}, {"title": "dup", "url": "u1"}])
    monkeypatch.setattr(fr, "pixabay_candidates", lambda q, a, get=None: [{"title": "p", "url": "u3"}])
    assert [c["title"] for c in fr.all_candidates("x", ["x"])] == ["c", "n", "p"]


def test_a_film_uses_all_sources_by_default():
    assert fr.for_film.__defaults__[1] is fr.all_candidates


def test_a_nasa_clip_with_no_length_up_front_is_measured_and_credited_with_its_source_and_licence(tmp_path):
    import openmedia
    cand = {"title": "Antikythera wreck dive survey", "url": "https://images-assets.nasa.gov/a.mp4", "license": openmedia.NASA_LICENCE, "page": "https://images.nasa.gov/details/a",
            "duration": 0.0, "size": 0, "source": "NASA Image and Video Library", "credit": "NASA (a)"}
    cut = []
    got = fr.fetch_segment(cand, tmp_path / "n.mp4", get=lambda *a, **k: Hop(), run=lambda cmd, **k: cut.append(cmd) or open(cmd[-1], "wb").write(b"mp4"),
                           resolve=PUBLIC, probe=lambda p, run=None: 40.0)
    assert got and cut
    credit = (tmp_path / "n.txt").read_text()
    assert "NASA (a)" in credit and "NASA Image and Video Library" in credit and "images.nasa.gov/details/a" in credit and fr.licence_ok(credit) and "copyright" not in credit.lower()


def test_a_clip_too_short_to_cut_is_refused(tmp_path):
    cand = {"title": "t", "url": "https://images-assets.nasa.gov/a.mp4", "license": "NASA media (credit NASA; no NASA logos)", "page": "p", "duration": 0.0, "size": 0, "source": "NASA Image and Video Library"}
    assert fr.fetch_segment(cand, tmp_path / "s.mp4", get=lambda *a, **k: Hop(), run=lambda cmd, **k: pytest.fail("must not cut"), resolve=PUBLIC, probe=lambda p, run=None: 1.0) is None


def test_downloads_never_reach_a_private_address_even_through_a_redirect(tmp_path):
    cand = {"title": "t", "url": "https://cdn.pixabay.com/v/1.mp4", "license": "Pixabay Content License", "page": "p", "duration": 12.0, "size": 1000, "source": "Pixabay"}
    resolve = lambda host: ["10.0.0.5"] if host == "internal.example" else ["151.101.1.1"]
    hops = [Hop(302, "https://internal.example/secret")]
    got = fr.fetch_segment(cand, tmp_path / "r.mp4", get=lambda *a, **k: hops.pop(0) if hops else pytest.fail("the private hop must not be fetched"),
                           run=lambda *a, **k: pytest.fail("must not cut"), resolve=resolve)
    assert got is None and not list(tmp_path.glob("*.mp4"))
    assert fr.fetch_segment({**cand, "url": "http://cdn.pixabay.com/v/1.mp4"}, tmp_path / "h.mp4", get=lambda *a, **k: pytest.fail("plain http must not be fetched"), resolve=resolve) is None


def test_nasa_and_pixabay_searches_that_fail_find_nothing_and_raise_nothing(monkeypatch):
    def boom(*a, **k):
        raise fr.requests.RequestException("down")
    import pixabay
    monkeypatch.setattr(pixabay, "key", lambda: "k")
    assert fr.nasa_candidates("Antikythera", ["Antikythera"], get=boom) == []
    assert fr.pixabay_candidates("Antikythera", ["Antikythera"], get=boom) == []
    assert fr.all_candidates("Antikythera", ["Antikythera"], get=boom) == []


def test_a_length_probe_that_fails_or_prints_nonsense_reads_as_zero(tmp_path):
    def missing(*a, **k):
        raise FileNotFoundError("no ffprobe")
    class Out:
        stdout = "N/A"
    assert fr._probe_seconds(tmp_path / "x.dl", run=missing) == 0.0
    assert fr._probe_seconds(tmp_path / "x.dl", run=lambda *a, **k: Out()) == 0.0
