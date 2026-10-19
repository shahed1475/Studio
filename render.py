"""Assemble a video with ffmpeg: stock clips, slow-zoom images or colour backgrounds."""
import subprocess
from pathlib import Path

import config

PALETTE = ["0x16213e", "0x1b4332", "0x3d2c8d", "0x7a1f3d", "0x0f4c5c", "0x4a3b1e"]
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}


def _venc(crf: str, preset: str) -> list[str]:
    """libx264 when this ffmpeg has it; Fedora's build only ships openh264 (bitrate-based)."""
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "libx264" in enc:
        return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p"]
    return ["-c:v", "libopenh264", "-b:v", "8M", "-pix_fmt", "yuv420p"]


def _ff(*args: str, cwd: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def render(clips, durations, narration: Path, ass: Path | None, work: Path, out: Path,
           size: tuple[int, int] | None = None, music: Path | None = None, loudness: float | None = None) -> Path:
    w, h = size or (config.WIDTH, config.HEIGHT)
    work = work.resolve()
    segs = []
    for i, (clip, dur) in enumerate(zip(clips, durations)):
        seg = work / f"seg{i:02d}.mp4"
        enc = ["-an", *_venc("22", "veryfast"), "-t", f"{dur:.3f}", seg.name]
        if clip and Path(clip).suffix.lower() in IMAGES:
            frames = int(dur * config.FPS) + 1
            zoom = "min(zoom+0.0007,1.25)" if i % 2 == 0 else "if(eq(on,0),1.25,max(zoom-0.0007,1.0))"
            vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                  f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={config.FPS},"
                  "setsar=1,eq=brightness=-0.05:saturation=0.85")
            _ff("-loop", "1", "-i", str(clip), "-vf", vf, *enc, cwd=work)
        elif clip:
            vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                  f"fps={config.FPS},setsar=1,eq=brightness=-0.08")
            _ff("-stream_loop", "-1", "-i", str(clip), "-vf", vf, *enc, cwd=work)
        else:
            _ff("-f", "lavfi", "-i", f"color=c={PALETTE[i % len(PALETTE)]}:s={w}x{h}:r={config.FPS}", *enc, cwd=work)
        segs.append(seg)
    (work / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    _ff("-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4", cwd=work)
    out = out.resolve()
    args = ["-i", "video.mp4", "-i", narration.name]
    norm = f"loudnorm=I={loudness:g}:TP=-1.5:LRA=11" if loudness is not None else ""
    if music:
        args += ["-stream_loop", "-1", "-i", str(Path(music).resolve()),
                 "-filter_complex", "[2:a]volume=0.07[m];[1:a][m]amix=inputs=2:duration=first:normalize=0" + (f",{norm}" if norm else "") + "[a]",
                 "-map", "0:v", "-map", "[a]"]
    elif norm:
        args += ["-af", norm]
    if ass:
        args += ["-vf", f"subtitles={ass.name}"]
    _ff(*args, *_venc("21", "medium"), "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(out), cwd=work)
    return out
