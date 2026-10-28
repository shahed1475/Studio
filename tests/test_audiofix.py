import json
import shutil
import subprocess

import pytest

import audiofix
import config
import reviewer

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def make_video(folder, volume):
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=8", "-f", "lavfi", "-i",
                    f"sine=frequency=220:duration=8,volume={volume}", "-c:v", "libx264" if shutil.which("ffmpeg") and "libx264" in subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True).stdout else "mpeg4",
                    "-c:a", "aac", "-shortest", str(folder / "video.mp4")], check=True)
    (folder / "meta.json").write_text(json.dumps({"title": "T", "review": {"verdict": "pass"}, "approved": True}))


@pytest.fixture(autouse=True)
def backups(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)


def test_a_quiet_video_is_brought_to_the_target_without_touching_the_picture(tmp_path):
    f = tmp_path / "out" / "quiet"
    make_video(f, 0.03)
    before = reviewer.probe_video(f / "video.mp4")
    assert before["lufs"] < -24
    res = audiofix.normalize(f, -16.0)
    after = reviewer.probe_video(f / "video.mp4")
    assert res["changed"] and abs(after["lufs"] + 16.0) <= audiofix.TOLERANCE and abs(after["duration"] - before["duration"]) < 0.3
    assert (after["width"], after["height"]) == (before["width"], before["height"])
    meta = json.loads((f / "meta.json").read_text())
    assert "review" not in meta and not meta.get("approved") and meta["loudness_fixed"]["to"] == round(after["lufs"], 1)  # the old verdict measured the old file
    assert (tmp_path / "backups" / "quiet.video.pre-loudness.mp4").exists() and not (f / "video.loudfix.mp4").exists()


def test_a_video_already_at_the_target_or_already_uploaded_is_left_alone(tmp_path):
    f = tmp_path / "out" / "ok"
    make_video(f, 0.03)
    audiofix.normalize(f, -16.0)
    again = audiofix.normalize(f, -16.0)
    assert not again["changed"] and "within" in again["why"]
    up = tmp_path / "out" / "public"
    make_video(up, 0.03)
    m = json.loads((up / "meta.json").read_text())
    (up / "meta.json").write_text(json.dumps({**m, "video_id": "abc"}))
    size = (up / "video.mp4").stat().st_size
    assert audiofix.normalize(up, -16.0) == {"changed": False, "why": "already uploaded: not touched"} and (up / "video.mp4").stat().st_size == size


def test_a_result_that_misses_the_target_keeps_the_original(tmp_path, monkeypatch):
    f = tmp_path / "out" / "bad"
    make_video(f, 0.03)
    size = (f / "video.mp4").stat().st_size
    real = reviewer.probe_video
    calls = []
    monkeypatch.setattr(reviewer, "probe_video", lambda p: (calls.append(p), {**real(p), "lufs": -30.0 if len(calls) == 2 else real(p)["lufs"]})[1])
    res = audiofix.normalize(f, -16.0)
    assert not res["changed"] and "original is kept" in res["why"] and (f / "video.mp4").stat().st_size == size and not (f / "video.loudfix.mp4").exists()
