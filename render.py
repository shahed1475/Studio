"""Assemble a video with ffmpeg: stock clips, picture shots with camera moves, colour backgrounds, optional crossfades and film grain."""
import functools
import subprocess
from pathlib import Path

import config

PALETTE = ["0x16213e", "0x1b4332", "0x3d2c8d", "0x7a1f3d", "0x0f4c5c", "0x4a3b1e"]
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
# Camera moves over a still picture. z = zoom, fx/fy = where the view sits (0 left/top, 1 right/bottom). A repeated picture gets the next shot,
# so one illustration can fill several scenes without looking like the same frame.
SHOTS = [
    dict(z0=1.00, z1=1.22, fx0=0.50, fy0=0.50, fx1=0.50, fy1=0.42),  # slow push in
    dict(z0=1.35, z1=1.35, fx0=0.12, fy0=0.40, fx1=0.88, fy1=0.40),  # close, pan left to right
    dict(z0=1.10, z1=1.45, fx0=0.75, fy0=0.70, fx1=0.85, fy1=0.80),  # push into the lower right
    dict(z0=1.50, z1=1.10, fx0=0.25, fy0=0.25, fx1=0.50, fy1=0.50),  # pull back from the upper left
    dict(z0=1.30, z1=1.30, fx0=0.60, fy0=0.10, fx1=0.40, fy1=0.90),  # drift downward
]
GRAIN = "vignette=PI/6,noise=alls=6:allf=t"


def shot_plan(k: int) -> dict:
    return dict(SHOTS[k % len(SHOTS)])


@functools.lru_cache(maxsize=1)
def _encoder_flags() -> bool:
    """True when this ffmpeg has libx264 (asked once, not once per scene)."""
    return "libx264" in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout


def _venc(crf: str, preset: str) -> list[str]:
    """libx264 when this ffmpeg has it; Fedora's build only ships openh264 (bitrate-based)."""
    if _encoder_flags():
        return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p"]
    return ["-c:v", "libopenh264", "-b:v", "8M", "-pix_fmt", "yuv420p"]


def _ff(*args: str, cwd: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def _picture_filter(w: int, h: int, frames: int, shot: dict | None, i: int) -> str:
    if shot:
        z = f"{shot['z0']}+({shot['z1']}-{shot['z0']})*on/{frames}"
        x = f"(iw-iw/zoom)*({shot['fx0']}+({shot['fx1']}-{shot['fx0']})*on/{frames})"
        y = f"(ih-ih/zoom)*({shot['fy0']}+({shot['fy1']}-{shot['fy0']})*on/{frames})"
        move = f"z='{z}':x='{x}':y='{y}'"
    else:  # the original slow zoom, alternating in and out
        zoom = "min(zoom+0.0007,1.25)" if i % 2 == 0 else "if(eq(on,0),1.25,max(zoom-0.0007,1.0))"
        move = f"z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    return (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
            f"zoompan={move}:d={frames}:s={w}x{h}:fps={config.FPS},setsar=1,eq=brightness=-0.05:saturation=0.85")


def _render_ungated(clips, durations, narration: Path, ass: Path | None, work: Path, out: Path,
           size: tuple[int, int] | None = None, music: Path | None = None, loudness: float | None = None,
           shots: bool = False, crossfade: float = 0.0, grain: bool = False) -> Path:
    """crossfade: seconds of dissolve between scenes (the video keeps the voice's length). grain: vignette and film grain."""
    w, h = size or (config.WIDTH, config.HEIGHT)
    work = work.resolve()
    n = len(clips)
    fade = crossfade if crossfade > 0 and n > 1 else 0.0
    segs, seen = [], {}
    for i, (clip, dur) in enumerate(zip(clips, durations)):
        seg = work / f"seg{i:02d}.mp4"
        length = dur + (fade if i < n - 1 else 0.0)  # each scene runs on under the dissolve into the next one
        enc = ["-an", *_venc("22", "veryfast"), "-t", f"{length:.3f}", seg.name]
        if clip and Path(clip).suffix.lower() in IMAGES:
            frames = int(length * config.FPS) + 1
            shot = None
            if shots:
                shot = shot_plan(seen.get(str(clip), 0))
                seen[str(clip)] = seen.get(str(clip), 0) + 1
            _ff("-loop", "1", "-i", str(clip), "-vf", _picture_filter(w, h, frames, shot, i), *enc, cwd=work)
        elif clip:
            vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                  f"fps={config.FPS},setsar=1,eq=brightness=-0.08")
            _ff("-stream_loop", "-1", "-i", str(clip), "-vf", vf, *enc, cwd=work)
        else:
            _ff("-f", "lavfi", "-i", f"color=c={PALETTE[i % len(PALETTE)]}:s={w}x{h}:r={config.FPS}", *enc, cwd=work)
        segs.append(seg)
    out = out.resolve()
    norm = f"loudnorm=I={loudness:g}:TP=-1.5:LRA=11" if loudness is not None else ""
    venc = [*_venc("21", "medium"), "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    if fade:  # dissolve chain: scene k+1 starts fading in exactly where its narration line starts
        a = n  # index of the narration input
        args = [x for s in segs for x in ("-i", s.name)] + ["-i", narration.name]
        graph, prev, t = [], "[0:v]", 0.0
        for i in range(n - 1):
            t += durations[i]
            graph.append(f"{prev}[{i + 1}:v]xfade=transition=fade:duration={fade:g}:offset={t:.3f}[x{i + 1}]")
            prev = f"[x{i + 1}]"
        post = ([GRAIN] if grain else []) + ([f"subtitles={ass.name}"] if ass else [])
        graph.append(f"{prev}{','.join(post) if post else 'null'}[v]")
        if music:
            args += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
            graph.append(f"[{a + 1}:a]volume=0.07[m];[{a}:a][m]amix=inputs=2:duration=first:normalize=0" + (f",{norm}" if norm else "") + "[a]")
            amap = ["-map", "[a]"]
        elif norm:
            graph.append(f"[{a}:a]{norm}[a]")
            amap = ["-map", "[a]"]
        else:
            amap = ["-map", f"{a}:a"]
        _ff(*args, "-filter_complex", ";".join(graph), "-map", "[v]", *amap, *venc, cwd=work)
        return out
    (work / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    _ff("-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4", cwd=work)
    args = ["-i", "video.mp4", "-i", narration.name]
    if music:
        args += ["-stream_loop", "-1", "-i", str(Path(music).resolve()),
                 "-filter_complex", "[2:a]volume=0.07[m];[1:a][m]amix=inputs=2:duration=first:normalize=0" + (f",{norm}" if norm else "") + "[a]",
                 "-map", "0:v", "-map", "[a]"]
    elif norm:
        args += ["-af", norm]
    vf = ([GRAIN] if grain else []) + ([f"subtitles={ass.name}"] if ass else [])
    if vf:
        args += ["-vf", ",".join(vf)]
    _ff(*args, *venc, cwd=work)
    return out


def render(*args, **kwargs) -> Path:
    """The render, behind the server-wide gate of a user studio (STUDIO_RENDER_GATE): without that setting it runs at once, as before."""
    import tenantmode

    with tenantmode.render_gate():
        return _render_ungated(*args, **kwargs)
