"""Real pictures from the free libraries for a film or a Short (owner's order, 10 Nov 2026). Fake libraries and fake downloads: nothing here touches the network."""
import io
import json

import pytest
from PIL import Image

import config
import footage
import licences
import openmedia
import realmedia


def png(w=1000, h=700, colour=(120, 90, 60)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(b, "PNG")
    return b.getvalue()


class Resp:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}

    def iter_content(self, n):
        for i in range(0, len(self.content), n):
            yield self.content[i:i + n]

    def raise_for_status(self):
        pass

    def close(self):
        pass


class Net:
    """A fake download function that records what it was asked for, can redirect, and takes the arguments the real requests.get takes."""

    def __init__(self, sizes=None, redirects=None):
        self.calls, self.sizes, self.redirects, self.kwargs = [], sizes or {}, redirects or {}, []

    def __call__(self, url, headers=None, timeout=None, stream=False, allow_redirects=True, **kw):
        self.calls.append(url)
        self.kwargs.append({"stream": stream, "allow_redirects": allow_redirects})
        if url in self.redirects:
            return Resp(302, b"", {"Location": self.redirects[url]})
        w, h = self.sizes.get(url, (1000, 700))
        return Resp(200, png(w, h, (len(url) % 200, 80, 90)))


PUBLIC = lambda host: ["93.184.216.34"]  # a public address, whatever the name


def item(source, title, licence, n, page=None):
    return openmedia._item(source, "image", title, page or f"https://{source}.example/{n}", f"https://{source}.example/img/{n}.jpg", licence, f"{title}, {source.title()}")


@pytest.fixture()
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    return tmp_path


def finder(tmp_cache, table, net=None, judge=None, cap=12, topic="The Antikythera Mechanism", anchors=("Antikythera",), resolve=PUBLIC):
    def search(source, query, kind, n, get):
        got = table.get(source)
        if isinstance(got, Exception):
            raise got
        return list(got or [])

    net = net or Net()
    return realmedia.Finder(topic, list(anchors), judge=judge, credit_cap=cap, search=search, get=net, folder=tmp_cache / "real", resolve=resolve), net


def test_only_accepted_licences_are_downloaded_and_each_keeps_its_credit_address_and_licence(tmp_cache):
    table = {"commons": [item("commons", "Antikythera fragment A", "CC BY-SA 4.0", 1), item("commons", "Antikythera fragment B", "CC BY-NC 4.0", 2), item("commons", "Antikythera X-ray", "All rights reserved", 3)]}
    f, net = finder(tmp_cache, table)
    hits = f("Antikythera mechanism", ["Antikythera"], 5)
    assert [h[1].split(",")[0] for h in hits] == ["Antikythera fragment A"]
    credit = hits[0][1]
    assert "CC BY-SA 4.0" in credit and "https://commons.example/1" in credit and licences.accepted(credit) and licences.needs_credit(credit)
    assert net.calls == ["https://commons.example/img/1.jpg"]  # a refused item is never even downloaded
    row = f.assets[0]
    assert {"file", "source", "page", "url", "licence", "credit", "fetched", "sha256"} <= set(row) and row["page"] == "https://commons.example/1" and len(row["sha256"]) == 64


def test_the_picture_is_a_normal_rgb_jpeg_on_disk(tmp_cache):
    f, _ = finder(tmp_cache, {"commons": [item("commons", "Antikythera fragment A", "CC0", 1)]})
    path = f("Antikythera", ["Antikythera"], 1)[0][0]
    with Image.open(path) as im:
        assert im.format == "JPEG" and im.mode == "RGB" and im.width >= realmedia.MIN_WIDTH


def test_a_tiny_picture_is_refused(tmp_cache):
    f, _ = finder(tmp_cache, {"commons": [item("commons", "Antikythera icon", "CC0", 1)]}, net=Net({"https://commons.example/img/1.jpg": (120, 90)}))
    assert f("Antikythera", ["Antikythera"], 1) == []


def test_public_domain_and_cc0_come_before_credit_needing_items(tmp_cache):
    table = {"commons": [item("commons", "Antikythera photo by someone", "CC BY 4.0", 1), item("commons", "Antikythera old engraving", "Public domain", 2)]}
    f, _ = finder(tmp_cache, table)
    assert f("Antikythera", ["Antikythera"], 1)[0][1].startswith("Antikythera old engraving")


def test_the_number_of_credit_needing_items_per_video_is_capped(tmp_cache):
    table = {"commons": [item("commons", f"Antikythera view {i}", "CC BY 4.0", i) for i in range(1, 6)] + [item("commons", "Antikythera PD drawing", "Public domain", 9)]}
    f, _ = finder(tmp_cache, table, cap=2)
    hits = f("Antikythera", ["Antikythera"], 6)
    titles = [h[1] for h in hits]
    assert sum(licences.needs_credit(c) for c in titles) == 2 and any("PD drawing" in t for t in titles) and f.credit_count == 2


def test_relevance_by_the_films_anchors_or_by_the_judge_only(tmp_cache):
    table = {"met": [item("met", "Bronze mirror with a relief", "CC0 (Met Open Access)", 1), item("met", "Antikythera related bronze gear", "CC0 (Met Open Access)", 2)]}
    f, _ = finder(tmp_cache, table)  # no judge: only the item that names the subject
    assert [h[1].split(",")[0] for h in f("gears", ["Antikythera"], 5, wide=True)] == ["Antikythera related bronze gear"]
    asked = []

    def judge(labels):
        asked.extend(labels)
        return [l for l in labels if "mirror" in l]

    f2, _ = finder(tmp_cache, table, judge=judge)
    got = [h[1].split(",")[0] for h in f2("gears", ["Antikythera"], 5, wide=True)]
    assert set(got) == {"Bronze mirror with a relief", "Antikythera related bronze gear"} and asked == ["Bronze mirror with a relief | met"]  # the judge only sees what the anchors did not already settle


def test_a_library_that_fails_is_skipped_and_the_run_goes_on(tmp_cache):
    table = {"commons": RuntimeError("too many requests, try again in a minute"), "openverse": [item("openverse", "Antikythera diagram", "CC BY 2.0", 1)]}
    f, _ = finder(tmp_cache, table)
    assert len(f("Antikythera", ["Antikythera"], 1)) == 1 and any("commons" in p for p in f.problems)


def test_narrow_searches_use_only_commons_and_openverse_wide_ones_use_every_library(tmp_cache):
    seen = []

    def search(source, query, kind, n, get):
        seen.append(source)
        return []

    f = realmedia.Finder("T", ["T"], search=search, get=Net(), folder=tmp_cache / "real", resolve=PUBLIC)
    f("a scene", ["T"], 1)
    narrow = list(seen)
    seen.clear()
    f("T", ["T"], 1, wide=True)
    assert narrow == ["commons", "openverse"] and set(seen) == {"commons", "smithsonian", "met", "aic", "cleveland", "openverse", "nasa", "pixabay"}


def test_nasa_logos_are_never_used_and_pexels_never_asked(tmp_cache):
    table = {"nasa": [item("nasa", "NASA logo worm Antikythera", openmedia.NASA_LICENCE, 1), item("nasa", "Antikythera data from orbit", openmedia.NASA_LICENCE, 2)]}
    f, _ = finder(tmp_cache, table)
    got = f("Antikythera", ["Antikythera"], 5, wide=True)
    assert [h[1].split(",")[0] for h in got] == ["Antikythera data from orbit"] and "pexels" not in realmedia.WIDE


def test_skip_list_and_repeats_are_respected(tmp_cache):
    table = {"commons": [item("commons", "Antikythera one", "CC0", 1), item("commons", "Antikythera two", "CC0", 2)]}
    f, _ = finder(tmp_cache, table)
    first = f("Antikythera", ["Antikythera"], 1)
    second = f("Antikythera", ["Antikythera"], 1, skip=[first[0][0]])
    assert first[0][0] != second[0][0] and f.credits() == [first[0][1], second[0][1]]


def test_the_assets_record_is_plain_json(tmp_cache):
    f, _ = finder(tmp_cache, {"commons": [item("commons", "Antikythera fragment A", "CC BY-SA 4.0", 1)]})
    f("Antikythera", ["Antikythera"], 1)
    assert json.loads(json.dumps(f.assets))[0]["licence"] == "CC BY-SA 4.0"


# ---- downloads are only made from public https addresses, with limits (security review, 10 Nov 2026: a library entry is third-party data, and the worker shares the host's network) ----
ONE = {"commons": [item("commons", "Antikythera fragment A", "CC0", 1)]}


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.9", "169.254.169.254", "0.0.0.0", "100.64.0.1", "::1", "fd00::1", "fe80::1", "not-an-address"])
def test_a_library_url_that_resolves_to_a_private_or_odd_address_is_never_fetched(tmp_cache, ip):
    f, net = finder(tmp_cache, ONE, resolve=lambda host: [ip])
    assert f("Antikythera", ["Antikythera"], 1) == [] and net.calls == [] and f.problems


def test_one_private_answer_among_public_ones_refuses_the_host(tmp_cache):
    f, net = finder(tmp_cache, ONE, resolve=lambda host: ["93.184.216.34", "10.0.0.1"])
    assert f("Antikythera", ["Antikythera"], 1) == [] and net.calls == []


def test_a_name_that_does_not_resolve_is_refused_quietly(tmp_cache):
    def boom(host):
        raise OSError("no such host")

    f, net = finder(tmp_cache, ONE, resolve=boom)
    assert f("Antikythera", ["Antikythera"], 1) == [] and net.calls == [] and f.problems


def test_plain_http_and_odd_schemes_are_refused(tmp_cache):
    for url in ("http://commons.example/img/1.jpg", "file:///etc/passwd", "ftp://x.example/a.jpg", "https:///nohost.jpg", "//commons.example/a.jpg"):
        it = item("commons", "Antikythera fragment A", "CC0", 1)
        it["url"] = url
        f, net = finder(tmp_cache, {"commons": [it]})
        assert f("Antikythera", ["Antikythera"], 1) == [] and net.calls == [], url


def test_redirects_are_followed_one_hop_at_a_time_and_each_hop_is_checked(tmp_cache):
    start, hop, end = "https://commons.example/img/1.jpg", "https://cdn.example/a.jpg", "https://cdn.example/b.jpg"
    net = Net(redirects={start: hop, hop: end})
    f, _ = finder(tmp_cache, ONE, net=net)
    assert len(f("Antikythera", ["Antikythera"], 1)) == 1 and net.calls == [start, hop, end]
    assert all(k == {"stream": True, "allow_redirects": False} for k in net.kwargs)  # redirects are never followed by requests itself


def test_a_redirect_into_a_private_address_stops_the_download(tmp_cache):
    start, inner = "https://commons.example/img/1.jpg", "https://internal.example/secret"
    net = Net(redirects={start: inner})
    f, _ = finder(tmp_cache, ONE, net=net, resolve=lambda host: ["10.0.0.9"] if host == "internal.example" else ["93.184.216.34"])
    assert f("Antikythera", ["Antikythera"], 1) == [] and net.calls == [start]  # the internal address was never requested


def test_too_many_redirects_stop_the_download(tmp_cache):
    urls = [f"https://cdn.example/{i}.jpg" for i in range(8)]
    net = Net(redirects={"https://commons.example/img/1.jpg": urls[0], **{urls[i]: urls[i + 1] for i in range(7)}})
    f, _ = finder(tmp_cache, ONE, net=net)
    assert f("Antikythera", ["Antikythera"], 1) == [] and len(net.calls) <= realmedia.MAX_HOPS + 1


def test_an_oversize_download_is_cut_off_and_refused(tmp_cache, monkeypatch):
    monkeypatch.setattr(realmedia, "MAX_BYTES", 500)  # the fake solid-colour picture is a few kilobytes
    f, _ = finder(tmp_cache, ONE)
    assert f("Antikythera", ["Antikythera"], 1) == [] and any("large" in p or "slow" in p for p in f.problems)


def test_a_picture_with_too_many_pixels_is_refused_before_it_is_decoded(tmp_cache, monkeypatch):
    monkeypatch.setattr(realmedia, "MAX_PIXELS", 500_000)  # the fake picture is 1000 x 700 = 700,000 pixels
    f, _ = finder(tmp_cache, ONE)
    assert f("Antikythera", ["Antikythera"], 1) == [] and any("pixels" in p for p in f.problems)


# ---- wiring into scene_images: real pictures from the libraries before any drawn picture ----
def test_scene_images_uses_the_finder_before_it_draws(tmp_cache, monkeypatch):
    monkeypatch.setattr(footage, "images_for", lambda *a, **k: [])  # Commons public-domain search finds nothing
    table = {"commons": [item("commons", f"Antikythera view {i}", "CC BY 4.0", i) for i in range(1, 5)]}
    f, _ = finder(tmp_cache, table)
    drawn = []
    clips, credits, stats = footage.scene_images([{"text": "a", "visual": "gears"}, {"text": "b", "visual": "bronze"}], "The Antikythera Mechanism", ["Antikythera"], art=lambda l: drawn.append(l) or None,
                                                 art_limit=5, finder=f)
    assert drawn == [] and stats["unique"] == 2 and stats["drawn"] == 0 and len(credits) == 2 and all("CC BY 4.0" in c for c in credits)


def test_scene_images_without_a_finder_behaves_as_before(tmp_cache, monkeypatch):
    monkeypatch.setattr(footage, "images_for", lambda *a, **k: [])
    drawn = []
    footage.scene_images([{"text": "a", "visual": "gears"}], "T", ["T"], art=lambda l: drawn.append(l) or None, art_limit=5)
    assert len(drawn) == 1


def test_a_credit_names_the_author_is_cut_at_a_word_and_never_holds_a_refused_word(tmp_cache):
    long_title = "Fragment of the Antikythera mechanism, photographed in the National Archaeological Museum of Athens in the gallery of bronze instruments"
    it = openmedia._item("openverse", "image", long_title, "https://openverse.example/1", "https://openverse.example/img/1.jpg", "CC BY 2.5", "raw",
                         author="<a href='x'>Marsyas assumed (based on copyright claims)</a>")
    f, _ = finder(tmp_cache, {"openverse": [it]})
    credit = f("gears", ["Antikythera"], 1)[0][1]
    assert "Marsyas assumed" in credit and "<" not in credit and "copyright" not in credit.lower()
    assert " by Marsyas" in credit and "CC BY 2.5" in credit and "https://openverse.example/1" in credit
    assert not credit.split(" by ")[0].endswith(("Athe", "gall")) and len(credit) < 260
    assert licences.accepted(credit) and licences.needs_credit(credit)


def test_a_portrait_of_a_real_person_is_used_only_when_the_scene_is_about_that_person(tmp_cache):
    portrait = item("commons", "Professor Mike Edmunds portrait 01.jpg", "Public domain", 1)
    gears = item("commons", "Antikythera gear fragment.jpg", "Public domain", 2)
    f, _ = finder(tmp_cache, {"commons": [portrait, gears]}, anchors=("Antikythera", "Edmunds"))
    got = f("Ancient Corinth", ["Antikythera", "Edmunds"], 2)
    assert len(got) == 1 and "Edmunds" not in got[0][1]  # the portrait names an anchor, but the scene is not about him
    f2, _ = finder(tmp_cache, {"commons": [portrait]}, anchors=("Antikythera", "Edmunds"))
    assert f2("Mike Edmunds", ["Antikythera", "Edmunds"], 1)  # a scene that names him may show him
