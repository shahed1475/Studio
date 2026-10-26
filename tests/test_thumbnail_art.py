import base64
import datetime as dt
import io
import json

import pytest
from PIL import Image

import aiart
import llm
import thumbnail

NOW = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.timezone.utc)
META = {"title": "Bell Witch Legend: What the 1817 Farm Accounts Really Describe", "topic": "The Bell Witch", "format": "doc",
        "chapters": [{"title": "The Bell Farm", "start_line": 0}], "lines": [{"text": "In 1817 a farm in Tennessee reported knocking sounds and a voice."}]}


def png_b64(size=(1376, 768), color=(30, 60, 70)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def art(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(aiart.config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": True, "daily_budget_usd": 5.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    monkeypatch.setattr(llm, "_account", lambda *a, **k: None)
    monkeypatch.setattr(aiart, "_off_until", {})

    def post(body, key):
        calls.append(body["messages"][0]["content"])
        return {"choices": [{"message": {"images": [{"image_url": {"url": png_b64()}}]}}]}

    monkeypatch.setattr(llm, "_post", post)
    return calls


def test_thumbnail_art_is_drawn_at_the_thumbnail_size_and_cached(art):
    got = aiart.thumbnail_art("a lone log farmhouse at night under a full moon", now=NOW)
    assert got and got[1] == aiart.CREDIT and Image.open(got[0]).size == (thumbnail.W, thumbnail.H)
    again = aiart.thumbnail_art("a lone log farmhouse at night under a full moon", now=NOW)
    assert again and again[0] == got[0] and len(art) == 1  # the same picture is never paid for twice
    prompt = art[0]
    assert "No text" in prompt and "no real person likeness" in prompt and "farmhouse" in prompt and "16:9" in prompt


def test_no_picture_is_bought_when_drawing_is_off_or_the_day_is_spent(art, monkeypatch):
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": False, "daily_budget_usd": 5.0, "models": {}, "enabled": True})
    assert aiart.thumbnail_art("x", now=NOW) is None
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": True, "daily_budget_usd": 1.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 1.0)
    assert aiart.thumbnail_art("x", now=NOW) is None and art == []


def test_a_failed_or_refused_drawing_gives_nothing_instead_of_an_error(art, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda body, key: (_ for _ in ()).throw(RuntimeError("HTTP 400")))
    assert aiart.thumbnail_art("x", now=NOW) is None


def test_the_scene_to_paint_comes_from_the_story_and_is_cleaned(monkeypatch):
    asked = []
    chat = lambda p: asked.append(p) or {"scene": "A lone log farmhouse at night, a pale figure in the fog. See evil.com/x"}
    scene = thumbnail.art_subject(META, chat=chat)
    assert "farmhouse" in scene and "evil.com" not in scene and len(scene) <= 220
    assert "never a real living person" in asked[0] and "Bell Witch" in asked[0]
    assert "The Bell Witch" in thumbnail.art_subject(META, chat=lambda p: 1 / 0)  # no answer: a plain scene from the topic, never an error


def test_the_art_thumbnails_use_the_hook_text_and_the_ai_credit(art, monkeypatch, tmp_path):
    folder = tmp_path / "v"
    folder.mkdir()
    names = thumbnail.make_art(folder, META, "BELL WITCH VOICE", now=NOW, chat=lambda p: {"scene": "A lone log farmhouse at night"})
    assert names == ["thumbs/art-a.jpg", "thumbs/art-b.jpg"]
    for n in names:
        im = Image.open(folder / n)
        assert im.size == (thumbnail.W, thumbnail.H) and (folder / n).stat().st_size < 1_900_000


def test_make_art_returns_nothing_when_nothing_could_be_drawn(art, monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": False, "daily_budget_usd": 5.0, "models": {}, "enabled": True})
    folder = tmp_path / "v"
    folder.mkdir()
    assert thumbnail.make_art(folder, META, "BELL WITCH VOICE", now=NOW, chat=lambda p: {"scene": "x"}) == []


def test_make_puts_the_art_first_and_adds_the_credit_once(art, monkeypatch, tmp_path):
    import records

    folder = tmp_path / "v"
    folder.mkdir()
    (folder / "video.mp4").write_bytes(b"x")
    (folder / "meta.json").write_text(json.dumps({**META, "subtitles": None, "credits": ["a.jpg (Wikimedia Commons, CC0)"]}))
    frames = []
    for i in range(3):
        p = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (thumbnail.W, thumbnail.H), (10 * i, 20, 30)).save(p)
        frames.append(p)
    monkeypatch.setattr(thumbnail, "_frames", lambda video, work, n=14, drop=None: (work.mkdir(parents=True, exist_ok=True), frames)[1])  # the real one makes its scratch folder
    monkeypatch.setattr(thumbnail, "_best", lambda fr, k=3: fr[:k])
    monkeypatch.setattr(thumbnail, "fit_frames", lambda *a, **k: None)
    monkeypatch.setattr(thumbnail, "art_subject", lambda meta, chat=None: "a lone log farmhouse")
    for _ in range(2):  # a second run must not add the credit again
        names = thumbnail.make(folder, hook="BELL WITCH VOICE")
    meta = json.loads((folder / "meta.json").read_text())
    assert names[:2] == ["thumbs/art-a.jpg", "thumbs/art-b.jpg"] and names[2:] == ["thumbs/thumb-1.jpg", "thumbs/thumb-2.jpg", "thumbs/thumb-3.jpg"]
    assert meta["thumbnail"] == "thumbs/art-a.jpg" and meta["credits"].count(aiart.CREDIT) == 1 and meta["thumb_art"] == "ai"
