import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import filmshort
import numbershort
import tts

SPEC = json.loads((Path(__file__).parent.parent / "examples" / "numbershort" / "trip-to-the-moon.film.json").read_text())


def spec(**over):
    s = copy.deepcopy(SPEC)
    s.update(over)
    return s


def film(**over):
    f = copy.deepcopy(SPEC["film"])
    f.update(over)
    return f


def test_the_example_spec_is_valid_and_clean():
    assert filmshort.validate(SPEC) == ([], [])


def test_only_a_film_from_1930_or_earlier_is_allowed():
    assert any("1930 or earlier" in e for e in filmshort.validate(spec(film=film(year=1931)))[0])
    assert filmshort.validate(spec(film=film(year=1930)))[0] == []
    assert any("1930 or earlier" in e for e in filmshort.validate(spec(film=film(year="1902")))[0])


@pytest.mark.parametrize("page", ["https://www.youtube.com/watch?v=abc", "https://example.com/film", "http://commons.wikimedia.org/wiki/File:x", "https://evilarchive.org/x", ""])
def test_the_licence_page_must_be_commons_or_the_internet_archive(page):
    assert any("source_page" in e for e in filmshort.validate(spec(film=film(source_page=page)))[0])


@pytest.mark.parametrize("page", ["https://commons.wikimedia.org/wiki/File:x.webm", "https://archive.org/details/x", "https://upload.wikimedia.org/x"])
def test_the_allowed_hosts_pass(page):
    assert not any("source_page" in e for e in filmshort.validate(spec(film=film(source_page=page)))[0])


def test_the_reason_it_is_public_domain_is_written_down():
    assert any("pd_basis" in e for e in filmshort.validate(spec(film=film(pd_basis=" ")))[0])


def test_a_director_who_died_recently_is_refused_and_an_unknown_one_is_a_warning():
    assert any("71 years" in e for e in filmshort.validate(spec(film=film(director_death_year=1960)))[0])
    f = film()
    del f["director_death_year"]
    errors, warns = filmshort.validate(spec(film=f))
    assert errors == [] and any("death year" in w for w in warns)


def test_each_line_takes_a_film_time_or_a_card_not_both_and_not_neither():
    lines = copy.deepcopy(SPEC["lines"])
    lines[0]["card"] = {"type": "end", "text": "x", "small": "y"}
    assert any("line 0" in e and "either" in e for e in filmshort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    del lines[0]["start"]
    assert any("line 0" in e and "either" in e for e in filmshort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    lines[0]["start"] = -3
    assert any("line 0" in e for e in filmshort.validate(spec(lines=lines))[0])


@pytest.mark.parametrize("key", ["video", "clips", "footage", "source_video", "youtube_url", "download"])
def test_a_spec_cannot_carry_other_footage(key):
    assert any("public-domain" in e for e in filmshort.validate(spec(**{key: "x"}))[0])


def test_two_real_sources_are_needed():
    assert any("two sources" in e for e in filmshort.validate(spec(sources=SPEC["sources"][:1]))[0])


def _fake_ffmpeg_film(path: Path, seconds=3):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=24:duration={seconds}", "-c:v", "mpeg4", str(path)], check=True)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_film_clip_is_vertical_the_asked_length_and_holds_its_last_frame(tmp_path):
    src = tmp_path / "f.mp4"
    _fake_ffmpeg_film(src, 3)
    out = filmshort.film_clip(src, 2.0, 2.0, tmp_path / "anim" / "c.mp4")  # only 1 s of film is left: the last frame is held
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.split()
    assert "1080,1920" in probe[0] and abs(float(probe[-1]) - 2.0) < 0.25


def test_a_build_is_a_held_draft_that_credits_the_film(tmp_path, monkeypatch):
    src = tmp_path / "f.webm"
    src.write_bytes(b"x")
    s = spec(film=film(file=str(src)))

    def narrate(lines, work, *a, **k):
        work.mkdir(parents=True, exist_ok=True)
        ass = work / "captions.ass"
        ass.write_text("Dialogue: 0,0:00:00.00,0:00:01.00,Cap,MELYES")
        (work / "words.json").write_text(json.dumps([{"s": i, "e": i + 0.5, "w": f"w{i}", "i": i} for i in range(len(lines))]))
        return work / "narration.mp3", ass, [1.0] * len(lines)

    import render

    monkeypatch.setattr(tts, "narrate", narrate)
    monkeypatch.setattr(filmshort, "probe_seconds", lambda p: 766.0)
    monkeypatch.setattr(filmshort, "film_clip", lambda src, start, seconds, out, **k: out)
    monkeypatch.setattr(render, "render", lambda clips, durations, narration, ass, work, out, **k: (Path(out).write_bytes(b"x"), out)[1])
    folder = filmshort.build(s, out_root=tmp_path / "out")
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["hold"] is True and meta["kind"] == "film" and meta["built_by"] == "filmshort" and meta["film_seconds"] == 766.0
    assert "public domain" in meta["description"] and "commons.wikimedia.org" in meta["description"] and "file" not in meta["film"]
    assert "Méliès" in (folder / "work" / "captions.ass").read_text() or "MÉLIÈS" in (folder / "work" / "captions.ass").read_text()
    late = spec(film=film(file=str(src)))
    late["lines"][1]["start"] = 900
    with pytest.raises(ValueError, match="after the film ends"):
        filmshort.build(late, out_root=tmp_path / "out2")
    assert not (tmp_path / "out2").exists()


def test_a_missing_film_file_builds_nothing(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        filmshort.build(spec(film=film(file=str(tmp_path / "nope.webm"))), out_root=tmp_path / "o")
    assert not (tmp_path / "o").exists()


def test_the_card_check_uses_the_number_short_cards():
    assert set(numbershort.CARDS) >= {"end"}
