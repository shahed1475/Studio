import json

import pytest

import config
import openmedia


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    for k in ("PIXABAY_KEY", "SMITHSONIAN_KEY", "PEXELS_KEY"):
        monkeypatch.setattr(config, k, "")


def router(table):
    def get(url, params=None, headers=None, timeout=0):
        for frag, data in table.items():
            if frag in url:
                return Resp(data)
        raise AssertionError("unexpected url " + url)
    return get


def test_museum_items_use_their_own_licence_flags():
    met = router({"v1.1/search": {"objectIDs": [1, 2]}, "objects/1": {"isPublicDomain": True, "primaryImage": "u1", "title": "A", "objectURL": "p1"},
                  "objects/2": {"isPublicDomain": False, "primaryImage": "u2", "title": "B"}})
    r = openmedia.search("met", "helmet", "image", 5, met)
    assert [x["url"] for x in r] == ["u1"] and r[0]["accepted"] and "CC0" in r[0]["licence"]
    aic = router({"artic.edu/api": {"data": [{"id": 1, "title": "T", "image_id": "abc", "is_public_domain": True}, {"id": 2, "title": "N", "image_id": "x", "is_public_domain": False}]}})
    r = openmedia.search("aic", "x", "image", 5, aic)
    assert len(r) == 1 and "iiif/2/abc/" in r[0]["url"]
    cle = router({"clevelandart": {"data": [{"title": "T", "url": "p", "share_license_status": "CC0", "images": {"web": {"url": "w"}}}, {"title": "U", "share_license_status": "Copyrighted", "images": {"web": {"url": "z"}}}]}})
    assert [x["url"] for x in openmedia.search("cleveland", "x", "image", 5, cle)] == ["w"]


def test_platform_and_nasa_licences_are_shown_but_not_accepted(monkeypatch):
    monkeypatch.setattr(config, "PIXABAY_KEY", "k" * 20)
    pix = router({"pixabay.com/api/videos": {"hits": [{"id": 1, "pageURL": "p", "user": "u", "duration": 5, "videos": {"medium": {"url": "m", "width": 1, "height": 1}}}]}})
    r = openmedia.search("pixabay", "sea", "video", 3, pix)
    assert r[0]["licence"] == "Pixabay Content License" and r[0]["accepted"] is False
    nasa = router({"images-api.nasa.gov/search": {"collection": {"items": [{"data": [{"nasa_id": "N1", "title": "Moon"}], "links": [{"rel": "canonical", "href": "img"}], "href": "assets"}]}}})
    r = openmedia.search("nasa", "moon", "image", 3, nasa)
    assert r[0]["url"] == "img" and r[0]["accepted"] is False and "NASA" in r[0]["credit"]


def test_openverse_no_derivatives_are_not_accepted():
    ov = router({"openverse": {"results": [{"title": "a", "license": "by-nd", "license_version": "2.0", "url": "u1"}, {"title": "b", "license": "by", "license_version": "2.0", "url": "u2"}]}})
    r = openmedia.search("openverse", "x", "image", 5, ov)
    assert [x["url"] for x in r] == ["u2", "u1"] and [x["accepted"] for x in r] == [True, False]


def test_smithsonian_needs_a_key_and_only_cc0_is_returned(monkeypatch):
    with pytest.raises(RuntimeError, match="no key"):
        openmedia.search("smithsonian", "x", "image", 3, router({}))
    monkeypatch.setattr(config, "SMITHSONIAN_KEY", "s" * 20)
    seen = {}

    def get(url, params=None, headers=None, timeout=0):
        seen.update(params)
        row = lambda acc, link: {"title": "T", "unitCode": "NMNH", "content": {"descriptiveNonRepeating": {"record_link": "rl", "metadata_usage": {"access": acc}, "online_media": {"media": [{"content": link}]}}}}
        return Resp({"response": {"rows": [row("CC0", "ok.jpg"), row("Usage conditions apply", "no.jpg")]}})

    r = openmedia.search("smithsonian", "coin", "image", 5, get)
    assert [x["url"] for x in r] == ["ok.jpg"] and seen["api_key"] == "s" * 20
    assert not any("s" * 20 in f.read_text() for f in (config.CACHE / "openmedia").iterdir())  # the key never reaches a cache file


def test_wrong_kind_and_selftest_never_raise(monkeypatch):
    with pytest.raises(ValueError):
        openmedia.search("met", "x", "video")
    bad = lambda url, params=None, headers=None, timeout=0: Resp({}, 403)
    rows = openmedia.selftest("x", bad)
    states = {(r["id"], r["kind"]): r["state"] for r in rows}
    assert states[("met", "image")] == "failed" and states[("pixabay", "image")] == "needs key" and states[("smithsonian", "image")] == "needs key"
    assert len(rows) == 14 and "k" * 20 not in json.dumps(rows)


def test_dashboard_saves_smithsonian_key_and_runs_the_test(tmp_path, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "SETTINGS", tmp_path / "settings.json")
    assert dashboard.H.route(None, "/api/key/save", {"which": "smithsonian", "value": "abcdefghij1234"}) == {"ok": True}
    assert json.loads((tmp_path / "settings.json").read_text())["smithsonian_key"] == "abcdefghij1234"
    monkeypatch.setattr(openmedia, "selftest", lambda q: [{"id": "met", "label": "Met", "kind": "image", "state": "ok", "detail": "d"}])
    assert dashboard.H.route(None, "/api/sources/test", {"query": "x"})["rows"][0]["id"] == "met"
