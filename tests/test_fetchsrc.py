import json

import pytest

from tools import fetchsrc


def page(extract="Alpha won in 1990."):
    return lambda url: json.dumps({"query": {"pages": {"1": {"title": "Alpha Cup", "extract": extract}}}}).encode()


def test_an_article_is_saved_as_plain_text_with_its_address(tmp_path, capsys):
    dest = fetchsrc.save("alpha cup", tmp_path / "src", page())
    assert dest.name == "Alpha_Cup.txt" and dest.read_text() == "Alpha won in 1990."
    assert "https://en.wikipedia.org/wiki/Alpha_Cup" in capsys.readouterr().out


def test_a_missing_article_is_an_error_not_an_empty_file(tmp_path):
    miss = lambda url: json.dumps({"query": {"pages": {"-1": {"title": "x", "missing": ""}}}}).encode()
    with pytest.raises(ValueError):
        fetchsrc.save("nothing", tmp_path, miss)
    assert not list(tmp_path.glob("*.txt"))
