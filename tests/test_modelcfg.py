import json

import pytest

import modelcfg


@pytest.fixture
def cfgfile(tmp_path, monkeypatch):
    f = tmp_path / "models.json"
    monkeypatch.setattr(modelcfg, "FILE", f)
    return f


def test_every_job_has_a_verified_default_model(cfgfile):
    for cap in ("thumbnail_art", "scene_art", "thumbnail_score", "video_analysis", "video_generation"):
        assert modelcfg.get(cap) == modelcfg.DEFAULTS[cap] and "/" in modelcfg.get(cap)
    assert modelcfg.get("thumbnail_score").startswith("anthropic/") and modelcfg.get("video_analysis").startswith("google/gemini")
    assert "google/veo-3.1-lite" in modelcfg.get("video_generation_allowed") and "alibaba/wan-3.0" in modelcfg.get("video_generation_allowed")


def test_a_studio_file_overrides_one_job_and_leaves_the_rest(cfgfile):
    cfgfile.write_text(json.dumps({"thumbnail_score": "anthropic/claude-opus-5.5"}))
    assert modelcfg.get("thumbnail_score") == "anthropic/claude-opus-5.5"
    assert modelcfg.get("thumbnail_art") == modelcfg.DEFAULTS["thumbnail_art"]


def test_a_bad_id_or_type_in_the_file_is_ignored_and_the_default_is_used(cfgfile):
    cfgfile.write_text(json.dumps({"thumbnail_score": "not a model id; rm -rf", "video_analysis": 7, "video_generation_allowed": ["google/veo-3.1-lite", "bad id", 3]}))
    assert modelcfg.get("thumbnail_score") == modelcfg.DEFAULTS["thumbnail_score"] and modelcfg.get("video_analysis") == modelcfg.DEFAULTS["video_analysis"]
    assert modelcfg.get("video_generation_allowed") == ["google/veo-3.1-lite"]  # only the good entries of a list stay


def test_a_missing_or_broken_file_means_the_defaults(cfgfile):
    assert modelcfg.load() == modelcfg.DEFAULTS
    cfgfile.write_text("{not json")
    assert modelcfg.load() == modelcfg.DEFAULTS


def test_an_unknown_job_is_an_error_not_a_guess(cfgfile):
    with pytest.raises(KeyError):
        modelcfg.get("write_poetry")
