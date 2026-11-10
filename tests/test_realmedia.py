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


class Net:
    """A fake download function that records what it was asked for."""

    def __init__(self, sizes=None):
        self.calls, self.sizes = [], sizes or {}

    def __call__(self, url, headers=None, timeout=None):
        self.calls.append(url)
        w, h = self.sizes.get(url, (1000, 700))
        content = png(w, h, (len(url) % 200, 80, 90))
        return type("R", (), {"status_code": 200, "content": content, "raise_for_status": lambda s: None})()


def item(source, title, licence, n, page=None):
    return openmedia._item(source, "image", title, page or f"https://{source}.example/{n}", f"https://{source}.example/img/{n}.jpg", licence, f"{title}, {source.title()}")


@pytest.fixture()
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    return tmp_path


def finder(tmp_cache, table, net=None, judge=None, cap=12, topic="The Antikythera Mechanism", anchors=("Antikythera",)):
    def search(source, query, kind, n, get):
        got = table.get(source)
        if isinstance(got, Exception):
            raise got
        return list(got or [])

    net = net or Net()
    return realmedia.Finder(topic, list(anchors), judge=judge, credit_cap=cap, search=search, get=net, folder=tmp_cache / "real"), net


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

    f = realmedia.Finder("T", ["T"], search=search, get=Net(), folder=tmp_cache / "real")
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
