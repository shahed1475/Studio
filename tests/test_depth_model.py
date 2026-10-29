"""The server can make its own depth maps (30 Oct 2026, with the owner's yes to installing numpy and onnxruntime there). The model is Depth Anything V2 Small (Apache-2.0), one 27 MB
ONNX file, downloaded once by `run.py depth-setup` and refused unless its SHA-256 is the checked one. Without the runtime or the model, depth_for falls back to the approximate map
exactly as before."""
import hashlib

import pytest
from PIL import Image

import config
import depth


@pytest.fixture(autouse=True)
def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "cache" / "art").mkdir(parents=True)
    depth._session.cache_clear()


def picture(tmp_path, size=(320, 180)):
    p = tmp_path / "cache" / "art" / "a.jpg"
    Image.new("RGB", size, (200, 120, 60)).save(p, "JPEG")
    return p


def test_the_model_is_downloaded_once_and_only_kept_when_its_hash_is_the_checked_one(tmp_path, monkeypatch):
    blob = b"pretend onnx bytes"
    monkeypatch.setattr(depth, "MODEL_SHA256", hashlib.sha256(blob).hexdigest())
    monkeypatch.setattr(depth, "_download", lambda url, dest: dest.write_bytes(blob))
    got = depth.ensure_model()
    assert got == depth.model_path() and got.read_bytes() == blob
    calls = []
    monkeypatch.setattr(depth, "_download", lambda url, dest: calls.append(url))
    assert depth.ensure_model() == got and calls == []  # already there and correct: no second download


def test_a_download_with_the_wrong_hash_is_refused_and_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(depth, "_download", lambda url, dest: dest.write_bytes(b"something else"))
    with pytest.raises(RuntimeError, match="SHA-256"):
        depth.ensure_model()
    assert not depth.model_path().exists() and not list(depth.model_path().parent.glob("*.part"))


def test_the_download_only_comes_from_the_one_host_the_model_was_checked_on():
    assert depth.MODEL_URL.startswith("https://huggingface.co/onnx-community/depth-anything-v2-small/")
    with pytest.raises(RuntimeError, match="host"):
        depth._download("https://example.com/model.onnx", depth.model_path())


def test_without_the_runtime_or_the_model_depth_for_is_the_approximate_map_as_before(tmp_path, monkeypatch):
    p = picture(tmp_path)
    monkeypatch.setattr(depth, "_runtime", lambda: None)
    assert depth.make_and_store(p) is None and depth.depth_for(p)[1] == "approximate"
    monkeypatch.setattr(depth, "_runtime", lambda: object())  # a runtime but no model file
    assert depth.make_and_store(p) is None and depth.depth_for(p)[1] == "approximate"
    assert not (config.CACHE / "depth").exists() or not list((config.CACHE / "depth").glob("*.png"))


def test_a_model_file_that_is_not_the_checked_one_is_never_loaded(tmp_path, monkeypatch):
    p = picture(tmp_path)
    depth.model_path().parent.mkdir(parents=True)
    depth.model_path().write_bytes(b"tampered")
    monkeypatch.setattr(depth, "_runtime", lambda: object())
    assert depth.make_and_store(p) is None


def test_a_map_made_by_the_model_is_stored_and_found_next_time_without_running_it_again(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    p = picture(tmp_path)
    runs = []

    class FakeSession:
        def get_inputs(self):
            return [type("I", (), {"name": "pixel_values"})()]

        def run(self, names, feed):
            runs.append(feed["pixel_values"].shape)
            h, w = feed["pixel_values"].shape[2:]
            ramp = np.tile(np.linspace(0, 5, h, dtype=np.float32)[:, None], (1, w))  # nearer toward the bottom
            return [ramp[None]]

    monkeypatch.setattr(depth, "_session", lambda: FakeSession())
    m = depth.make_and_store(p)
    assert m.mode == "L" and m.size[0] == depth.MAP_WIDTH and runs and runs[0][2] % 14 == 0 and runs[0][3] % 14 == 0  # the model reads multiples of 14 pixels
    w, h = m.size
    assert m.getpixel((w // 2, h - 3)) > m.getpixel((w // 2, 3)) + 100
    got, how = depth.depth_for(p)
    assert how == "model" and len(runs) == 1  # the second call read the stored map
    assert (config.CACHE / "depth" / f"{depth.depth_key(p)}.png").exists()
