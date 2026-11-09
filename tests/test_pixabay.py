import json

import pytest

import config
import pixabay


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
    monkeypatch.setattr(config, "PIXABAY_KEY", "k" * 20)


def test_images_and_credit():
    seen = {}

    def fake(url, params, timeout):
        seen.update(params)
        return Resp({"hits": [{"id": 1, "pageURL": "https://pixabay.com/p/1", "webformatURL": "u", "user": "ann", "tags": "a"}]})

    hits = pixabay.search_images("pyramids", 1, fake)
    assert seen["key"] == "k" * 20 and hits[0]["credit"].startswith("Image by ann via Pixabay")


def test_videos_pick_a_size():
    fake = lambda url, params, timeout: Resp({"hits": [{"id": 2, "pageURL": "p", "user": "bo", "duration": 9, "videos": {"medium": {"url": "m", "width": 1280, "height": 720}}}]})
    v = pixabay.search_videos("sea", 1, fake)[0]
    assert v["url"] == "m" and v["seconds"] == 9


def test_cache_means_one_request_and_no_key_in_file(tmp_path):
    calls = []

    def fake(url, params, timeout):
        calls.append(1)
        return Resp({"hits": []})

    pixabay.search_images("x", 3, fake)
    pixabay.search_images("x", 3, fake)
    assert len(calls) == 1
    assert all("k" * 20 not in f.name and "k" * 20 not in f.read_text() for f in (config.CACHE / "pixabay").iterdir())


def test_no_key_and_bad_key(monkeypatch):
    monkeypatch.setattr(config, "PIXABAY_KEY", "")
    assert pixabay.selftest().startswith("FAIL: no Pixabay key")
    monkeypatch.setattr(config, "PIXABAY_KEY", "k" * 20)
    out = pixabay.selftest("q", lambda url, params, timeout: Resp({}, 400))
    assert out.count("FAIL") == 2 and "k" * 20 not in out


def test_rate_limit_message():
    with pytest.raises(RuntimeError, match="too many"):
        pixabay.search_images("z", 3, lambda url, params, timeout: Resp({}, 429))


def test_dashboard_saves_pixabay_key(tmp_path, monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "SETTINGS", tmp_path / "settings.json")
    assert dashboard.H.route(None, "/api/key/save", {"which": "pixabay", "value": "abcdefghij1234"}) == {"ok": True}
    assert json.loads((tmp_path / "settings.json").read_text())["pixabay_key"] == "abcdefghij1234"
