import json

import config
import subtitles
import tts


def test_words_json_shape_and_roundtrip(tmp_path):
    p = tmp_path / "words.json"
    tts.words_to_json([(0.0, 0.4, "Hello", 0), (0.4, 0.9, "there.", 0), (1.2, 1.6, "Next", 1)], p)
    words = subtitles.load_words(p)
    assert words[0] == {"s": 0.0, "e": 0.4, "w": "Hello", "i": 0} and words[2]["i"] == 1


def test_write_files_creates_srt(tmp_path):
    words = [{"s": 0.0, "e": 0.4, "w": "Hello", "i": 0}, {"s": 0.4, "e": 0.9, "w": "there.", "i": 0}]
    path = subtitles.write_files(tmp_path, words)
    assert path == tmp_path / "captions.srt" and path.read_text().startswith("1\n00:00:00,000 --> ")
    assert "Hello there." in path.read_text()


def test_doc_subtitles_on_by_default():
    assert config.DOC_SUBTITLES is True
