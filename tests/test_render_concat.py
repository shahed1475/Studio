"""The plain (no crossfade) render path with real ffmpeg: the picture track is silent, so music must be mixed with the narration (input 1)."""
import json
import shutil
import subprocess

import pytest

import render

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg missing")


def _tone(path, freq, seconds):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-ar", "44100", str(path)], check=True)


def _streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("with_music,loudness", [(True, -16.0), (False, -16.0), (False, None)])
def test_concat_render_has_picture_and_voice(tmp_path, with_music, loudness):
    narration, music = tmp_path / "narration.wav", tmp_path / "music.wav"
    _tone(narration, 440, 2)
    _tone(music, 220, 1)
    out = render._render_ungated([None, None], [1.0, 1.0], narration, None, tmp_path, tmp_path / "out.mp4", size=(160, 90),
                                 music=music if with_music else None, loudness=loudness)
    info = _streams(out)
    kinds = sorted(s["codec_type"] for s in info["streams"])
    assert kinds == ["audio", "video"]
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (160, 90)
    assert 1.8 <= float(info["format"]["duration"]) <= 2.3


def test_a_gif_saved_with_a_jpg_name_still_renders(tmp_path):
    """19 Nov 2026: an archive picture saved as .jpg was really a GIF; ffmpeg's GIF reader has no -loop option and the film failed at its last step."""
    from PIL import Image

    fake_jpg, webp, real_jpg = tmp_path / "gif-named.jpg", tmp_path / "picture.webp", tmp_path / "real.jpg"
    Image.new("P", (64, 48), 3).save(fake_jpg, "GIF")
    Image.new("RGB", (64, 48), (20, 30, 40)).save(webp, "WEBP")
    Image.new("RGB", (64, 48), (90, 10, 10)).save(real_jpg, "JPEG")
    work = tmp_path / "work"
    work.mkdir()
    narration = work / "narration.wav"  # the pipeline keeps the narration in the work folder
    _tone(narration, 440, 3)
    out = render._render_ungated([fake_jpg, webp, real_jpg], [1.0, 1.0, 1.0], narration, None, work, tmp_path / "out.mp4", size=(160, 90))
    info = _streams(out)
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"] and 2.7 <= float(info["format"]["duration"]) <= 3.4
    assert render.still_for_ffmpeg(real_jpg, work, 9) == real_jpg  # a real JPEG is used as it is, never copied
