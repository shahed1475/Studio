"""The music bed under a video's narration (musicbed.py, 20 Nov 2026): different public-domain tracks, never one looped, as long as the video, recorded in the video's record."""
import hashlib
import json
import subprocess

import musicbed


def tone(path, seconds, freq):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "96k", str(path)], check=True)


def library(tmp_path, n=3, seconds=12, licence="CC0", license_file=True):
    d = tmp_path / "music"
    d.mkdir(parents=True)
    ledger = []
    for i in range(n):
        f = d / f"t{i}.mp3"
        tone(f, seconds, 220 + 110 * i)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)
        ledger.append({"file": f.name, "title": f"Track {i}", "licence": licence, "page": f"https://commons.wikimedia.org/wiki/File:T{i}.ogg", "performer_or_author": "X",
                       "seconds": round(dur, 1), "sha256_mp3": hashlib.sha256(f.read_bytes()).hexdigest()})
    (d / "LEDGER.json").write_text(json.dumps(ledger))
    if license_file:
        (d / "LICENSE.txt").write_text("CC0\n")
    return d


def seconds_of(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)


def test_a_long_video_gets_different_tracks_one_after_another_never_one_looped(tmp_path, monkeypatch):
    monkeypatch.setattr(musicbed, "DIR", library(tmp_path, n=3, seconds=12))
    picked = musicbed.plan(30, "The Dancing Plague")
    assert len(picked) >= 3 and len({t["file"] for t in picked[:3]}) == 3  # every track plays once before any repeats
    assert musicbed.plan(30, "The Dancing Plague") == picked  # the order is fixed by the topic: a re-render hears the same music
    out, used = musicbed.bed(30, tmp_path, "The Dancing Plague")
    assert out is not None and abs(seconds_of(out) - 30) < 0.5
    rec = musicbed.record(used)
    assert [t["page"] for t in rec["tracks"]] == [t["page"] for t in picked] and all(t["licence"] == "CC0" for t in rec["tracks"])


def test_a_changed_file_an_unapproved_licence_or_no_licence_file_means_no_music(tmp_path, monkeypatch):
    d = library(tmp_path, n=2)
    monkeypatch.setattr(musicbed, "DIR", d)
    (d / "t0.mp3").write_bytes(b"changed")  # the checksum no longer matches the ledger
    assert [t["file"] for t in musicbed.tracks()] == ["t1.mp3"]
    (d / "LICENSE.txt").unlink()
    assert musicbed.tracks() == [] and musicbed.bed(20, tmp_path, "x") == (None, [])
    d2 = library(tmp_path / "b", n=1, licence="CC BY-NC 4.0")
    monkeypatch.setattr(musicbed, "DIR", d2)
    assert musicbed.tracks() == []


def test_no_music_is_a_valid_result_not_a_stopped_video(tmp_path, monkeypatch):
    monkeypatch.setattr(musicbed, "DIR", tmp_path / "missing")
    assert musicbed.bed(60, tmp_path, "x") == (None, []) and musicbed.record([]) == {"tracks": [], "mix": "none"}
