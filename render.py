"""Assemble a video with ffmpeg: stock clips, picture shots with camera moves, colour backgrounds, optional crossfades and film grain."""
import functools
import os
import subprocess
from pathlib import Path

import checkpoint
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


# SDR for YouTube (23 Nov 2026): every encode is BT.709 and says so. Untagged, this ffmpeg converted RGB pictures with the BT.601 matrix while YouTube and
# browsers read untagged HD as BT.709, so a red 200,60,40 played as 212,72,36. With these tags ffmpeg 7.1 converts with BT.709 (measured: 199,58,39).
BT709 = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         # the options alone reached only the matrix (a filter graph's frames overrode primaries and transfer): the stream's own VUI flags are written too
         "-bsf:v", "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0"]
# The film's one restrained grade (23 Nov 2026), applied to every still and every clip that is not already graded (parallax clips are graded when made):
# a gentle S-curve that keeps highlights under clipping and blacks above crushing, a small cool-shadow / warm-highlight split, slightly less saturation,
# a soft vignette. Measured on three real pictures: 0% clipped, 0% crushed, mean brightness about 10% lower, saturation within 10% of the source.
# The grade it replaces (eq=brightness=-0.05:saturation=0.85) crushed up to 21% of a picture to black and RAISED saturation (0.34 to 0.50).
GRADE = ("eq=contrast=1.03:saturation=0.9,curves=all='0/0.018 0.25/0.24 0.5/0.52 0.8/0.83 1/0.97',"
         "colorbalance=rs=-0.02:bs=0.025:rh=0.025:gh=0.008:bh=-0.025,vignette=angle=PI/7")
AUDIO = ["-c:a", "aac", "-b:a", "320k", "-ar", "48000"]  # YouTube's upload advice: AAC, 48 kHz, 384 kb/s stereo or less (320 kb/s here)


def _venc(crf: str, preset: str) -> list[str]:
    """libx264 when this ffmpeg has it; Fedora's build only ships openh264 (bitrate-based). Always BT.709."""
    if _encoder_flags():
        return ["-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", *BT709]
    return ["-c:v", "libopenh264", "-b:v", "8M", "-pix_fmt", "yuv420p", *BT709]


def _ff(*args: str, cwd: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def still_for_ffmpeg(path: Path, work: Path, i: int) -> Path:
    """A picture ffmpeg can loop as a still. ffmpeg reads a file by its content, not its name: an archive picture saved as .jpg that is really a GIF
    is opened with the GIF reader, which has no -loop option, and the whole render failed at its last step (19 Nov 2026, "The Secret Code of the
    Pyramids", cache/e5ea9fed7777.jpg). Anything that is not really a JPEG or a PNG (GIF, WebP, an animated picture) is written once as a JPEG in the
    work folder, its first frame for an animation. A file PIL cannot read is passed on unchanged, so ffmpeg still reports it."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            if im.format in ("JPEG", "PNG"):
                return Path(path)
            im.seek(0)
            out = work / f"still{i:03d}.jpg"
            im.convert("RGB").save(out, "JPEG", quality=95)
            return out
    except Exception:
        return Path(path)


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
            f"zoompan={move}:d={frames}:s={w}x{h}:fps={config.FPS},setsar=1,{GRADE}")


def clip_fit(clip_s: float, scene_s: float, max_slow: float = 1.25) -> tuple[float, float]:
    """(slow-down factor for setpts, seconds to hold the last frame) so a clip fills its scene once and is never looped (a loop plays the same footage twice). A clip that is
    long enough is cut; a shorter one is slowed by at most max_slow and the rest is held on its last frame."""
    if clip_s <= 0 or scene_s <= clip_s:
        return 1.0, 0.0
    factor = min(scene_s / clip_s, max_slow)
    return factor, max(0.0, scene_s - clip_s * factor)


def _clip_seconds(path) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _segment_job(i: int, clip, length: float, w: int, h: int, shot: dict | None, work: Path) -> tuple[str, callable]:
    """(key of this scene's inputs, a function that writes the scene to a given file name). The key holds everything the scene's pixels depend on, so a scene saved
    by an earlier run is used again only when it would come out the same."""
    venc = _venc("22", "veryfast")
    if clip and Path(clip).suffix.lower() in IMAGES:
        frames = int(length * config.FPS) + 1
        key = checkpoint.key_of("still", checkpoint.file_stamp(clip), f"{length:.3f}", w, h, config.FPS, shot, i if not shot else None, venc)

        def make(name):
            _ff("-loop", "1", "-i", str(still_for_ffmpeg(Path(clip), work, i)), "-vf", _picture_filter(w, h, frames, shot, i), "-an", *venc, "-t", f"{length:.3f}", name, cwd=work)
    elif clip:
        anim = Path(clip).parent.name == "anim"
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"fps={config.FPS},setsar=1" + ("" if anim else f",{GRADE}"))  # real footage gets the film's grade (shots match); animation was graded when it was made
        if anim:  # generated animation and camera clips play once: slowed a little and held, never looped
            factor, hold = clip_fit(_clip_seconds(clip), length)
            vf += (f",setpts={factor:.4f}*PTS,framerate=fps={config.FPS}" if factor > 1.0001 else "") + (f",tpad=stop_mode=clone:stop_duration={hold:.3f}" if hold > 0.001 else "")
            pre = []
        else:
            pre = ["-stream_loop", "-1"]
        key = checkpoint.key_of("clip", checkpoint.file_stamp(clip), f"{length:.3f}", vf, pre, venc)

        def make(name):
            _ff(*pre, "-i", str(clip), "-vf", vf, "-an", *venc, "-t", f"{length:.3f}", name, cwd=work)
    else:
        colour = PALETTE[i % len(PALETTE)]
        key = checkpoint.key_of("colour", colour, f"{length:.3f}", w, h, config.FPS, venc)

        def make(name):
            _ff("-f", "lavfi", "-i", f"color=c={colour}:s={w}x{h}:r={config.FPS}", "-an", *venc, "-t", f"{length:.3f}", name, cwd=work)
    return key, make


SEGMENTS = "segments.json"  # in the work folder: one record per finished, checked scene (key, size, SHA-256, seconds)


def _content(path) -> str | None:
    """A small input's content hash (narration, captions): these are written again by every run, so their times say nothing."""
    try:
        return checkpoint.sha256(Path(path)) if path else None
    except OSError:
        return None


def _render_ungated(clips, durations, narration: Path, ass: Path | None, work: Path, out: Path,
           size: tuple[int, int] | None = None, music: Path | None = None, loudness: float | None = None,
           shots: bool = False, crossfade: float = 0.0, grain: bool = False) -> Path:
    """crossfade: seconds of dissolve between scenes (the video keeps the voice's length). grain: vignette and film grain.

    Power-cut safe (20 Nov 2026): every scene is written to a .part file, checked (ffprobe, length, a decode of its end), then renamed into place and recorded in
    work/segments.json with its size and SHA-256. A later run of the same job uses every recorded scene whose inputs and file are unchanged and renders only
    the rest. The finished video is written to <name>.part.mp4, decoded in full, and only then renamed over `out`; an interrupted final MP4 is never trusted.
    One render per work folder at a time (a lock the kernel drops when the process dies)."""
    w, h = size or (config.WIDTH, config.HEIGHT)
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    n = len(clips)
    fade = crossfade if crossfade > 0 and n > 1 else 0.0
    total = sum(durations) + fade * max(0, n - 1)
    in_parts = not fade and total >= PARTS_FROM
    need = int(total * (3.5e6 if in_parts else 2.5e6) * (w * h) / (1920 * 1080)) + 50_000_000  # scenes, the parts of a long film, the finished file: about 1 MB a second each at 1080p
    short = checkpoint.room(work, need)
    if short:
        raise RuntimeError(f"not rendering: {short}. Nothing was deleted; free some space and run the same job again (finished scenes are kept)")
    with checkpoint.lock(work):
        man_path = work / SEGMENTS
        man = checkpoint.read_json(man_path)
        done = man.get("segments") or {}
        segs, keys, seen, reused, made = [], [], {}, 0, 0
        why_not: dict[str, int] = {}  # 21 Nov 2026: the first real resume kept 22 of 81 scenes; every resume now says why a scene was made again
        for i, (clip, dur) in enumerate(zip(clips, durations)):
            seg = work / f"seg{i:02d}.mp4"
            length = dur + (fade if i < n - 1 else 0.0)  # each scene runs on under the dissolve into the next one
            shot = None
            if clip and Path(clip).suffix.lower() in IMAGES and shots:
                shot = shot_plan(seen.get(str(clip), 0))
                seen[str(clip)] = seen.get(str(clip), 0) + 1
            key, make = _segment_job(i, clip, length, w, h, shot, work)
            keys.append(key)
            if checkpoint.still_valid(seg, done.get(seg.name), key):
                reused += 1
                segs.append(seg)
                continue
            rec = done.get(seg.name)
            reason = "new" if not rec else ("inputs changed" if rec.get("key") != key else "file changed")
            if rec and rec.get("key") != key and rec.get("src") not in (None, str(clip)):
                reason = "another picture"
            why_not[reason] = why_not.get(reason, 0) + 1
            part = work / f"seg{i:02d}.part.mp4"
            part.unlink(missing_ok=True)
            make(part.name)
            bad = checkpoint.check_media(part, seconds=length, need=("video",), tol=max(0.25, 2.0 / config.FPS))
            if bad:
                raise RuntimeError(f"scene {i + 1} of {n} came out wrong ({bad}); it was not kept")
            os.replace(part, seg)
            done[seg.name] = {"key": key, **checkpoint.facts(seg), "at": checkpoint._now(), "src": str(clip) if clip else None,
                              "src_stamp": checkpoint.file_stamp(clip) if clip else None, "seconds_asked": round(length, 3)}
            man.update(segments=done, total=n, size=[w, h])
            checkpoint.write_json(man_path, man)
            made += 1
            segs.append(seg)
        if reused or (done and made):
            print(f"  scenes: {reused} of {n} kept from an earlier run, {made} rendered now"
                  + (f" ({', '.join(f'{k}: {v}' for k, v in sorted(why_not.items()))})" if why_not and done else ""))
        out = out.resolve()
        final_key = checkpoint.key_of(keys, _content(narration if Path(narration).is_absolute() else work / narration), _content(ass), checkpoint.file_stamp(music) if music else None,
                                      loudness, grain, fade, w, h)
        if checkpoint.still_valid(out, man.get("final"), final_key):
            print("  the finished video from an earlier run is complete and unchanged: kept")
            return out
        part = out.with_name(out.stem + ".part" + out.suffix)
        part.unlink(missing_ok=True)
        if in_parts:
            _assemble_in_parts(segs, keys, narration, ass, work, part, music, loudness, grain, man, man_path)
        else:
            _assemble(segs, durations, narration, ass, work, part, music, loudness, grain, fade, n)
        expect = min(total, checkpoint.media_seconds(work / Path(narration).name) or total)
        bad = checkpoint.check_media(part, seconds=expect, need=("video", "audio"), tol=max(1.0, expect * 0.02), full=True)
        if bad:
            raise RuntimeError(f"the assembled video came out wrong ({bad}); the scenes are kept and the old video, if any, is untouched")
        os.replace(part, out)
        man["final"] = {"key": final_key, **checkpoint.facts(out), "name": out.name, "at": checkpoint._now()}
        checkpoint.write_json(man_path, man)
        return out


PART_SECONDS = 120.0  # a long film's final pass is made in parts of about two minutes
PARTS_FROM = 240.0  # films at least this long (no dissolves); a Short keeps its single final pass


def frames_of(path) -> int:
    """The number of video frames the file's header states (0 when it cannot be read)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return int(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def part_groups(secs: list[float], size: float | None = None) -> list[list[int]]:
    """Scenes grouped into consecutive parts of about `size` seconds (PART_SECONDS); a short last group joins the one before it."""
    size = size or PART_SECONDS
    groups, cur, acc = [], [], 0.0
    for i, s in enumerate(secs):
        cur.append(i)
        acc += s
        if acc >= size:
            groups.append(cur)
            cur, acc = [], 0.0
    if cur:
        if groups and acc < size / 3:
            groups[-1].extend(cur)
        else:
            groups.append(cur)
    return groups


def _audio_filter(music, loudness) -> tuple[list[str], list[str]]:
    """(extra inputs, arguments) for the film's sound from input 0, the narration: the music bed under it and the loudness target, as the single pass does."""
    norm = f"loudnorm=I={loudness:g}:TP=-1.5:LRA=11" if loudness is not None else ""
    if music:
        return (["-stream_loop", "-1", "-i", str(Path(music).resolve())],
                ["-filter_complex", "[1:a]volume=0.07[m];[0:a][m]amix=inputs=2:duration=first:normalize=0" + (f",{norm}" if norm else "") + "[a]", "-map", "[a]"])
    return [], (["-af", norm] if norm else [])


def _assemble_in_parts(segs, keys, narration, ass, work, out, music, loudness, grain, man, man_path) -> None:
    """The final pass of a long film in parts (21 Nov 2026, load-shedding): the single pass of a 20 to 26 minute film runs for tens of minutes, and a cut inside
    it started that pass again from the first frame. Each part (about two minutes of checked scenes) is encoded with the burned captions and grain at its own
    place in the film's time (the captions are shifted by the part's start, so they land on the same frames as in one pass), written to a .part file, checked,
    renamed and recorded in segments.json with its inputs, size and SHA-256. The sound (narration, music bed, loudness) is made once for the whole film, audio
    only. The parts are then joined with a stream copy and the sound laid under them: seconds, not minutes. A later run keeps every part whose inputs and
    file are unchanged."""
    secs = [checkpoint.media_seconds(s) for s in segs]  # the lengths the join uses, measured as the single pass's concat would
    if any(s <= 0 for s in secs):
        raise RuntimeError("a scene's length cannot be read; nothing was assembled")
    done = man.get("parts") or {}
    venc = _venc("18", "medium")  # the final pass: visually lossless (23 Nov 2026: CRF 21 gave about 1.5 Mb/s for 1080p)
    post = ([GRAIN] if grain else []) + ([f"subtitles={ass.name}"] if ass else [])
    caption_key = _content(ass)
    names, offset, made, kept = [], 0.0, 0, 0
    groups = part_groups(secs)
    for k, idx in enumerate(groups):
        name, length = f"part{k:02d}.mp4", sum(secs[i] for i in idx)
        key = checkpoint.key_of("part", [keys[i] for i in idx], [segs[i].name for i in idx], f"{offset:.4f}", caption_key, grain, venc)
        path = work / name
        if checkpoint.still_valid(path, done.get(name), key):
            kept += 1
        else:
            (work / f"part{k:02d}.txt").write_text("".join(f"file '{segs[i].name}'\n" for i in idx))
            tmp = work / f"part{k:02d}.part.mp4"
            tmp.unlink(missing_ok=True)
            # the captions see the film's own clock; the shift back is the same constant, not STARTPTS: a scene in another pixel format (a Blender clip
            # among JPEG stills) makes ffmpeg rebuild the filters mid-part, and STARTPTS then restarted at zero and the rest of the part was dropped
            # (21 Nov 2026, Seven Sleepers: part 1 came out 60.1 s of 121.7 s)
            vf = ",".join([f"setpts=PTS+{offset:.6f}/TB", *post, f"setpts=PTS-{offset:.6f}/TB"])
            _ff("-f", "concat", "-safe", "0", "-i", f"part{k:02d}.txt", "-vf", vf, "-an", "-fps_mode", "cfr", "-r", str(config.FPS), *venc, "-movflags", "+faststart",
                tmp.name, cwd=work)  # a fixed rate: the time-shift filters drop the last frame's length, and the part then claimed to be one frame short
            bad = checkpoint.check_media(tmp, seconds=length, need=("video",), tol=max(0.25, 3.0 / config.FPS))
            if bad:
                raise RuntimeError(f"part {k + 1} of {len(groups)} of the final video came out wrong ({bad}); it was not kept, the parts before it are")
            os.replace(tmp, path)
            done[name] = {"key": key, **checkpoint.facts(path), "at": checkpoint._now()}
            man["parts"] = done
            checkpoint.write_json(man_path, man)
            made += 1
        names.append(name)
        offset += length
    print(f"  final video in {len(groups)} parts: {kept} kept from an earlier run, {made} made now")
    voice = narration if Path(narration).is_absolute() else work / narration
    sound, sound_key = work / "sound.m4a", checkpoint.key_of("sound", _content(voice), checkpoint.file_stamp(music) if music else None, loudness)
    if not checkpoint.still_valid(sound, man.get("sound"), sound_key):
        tmp = work / "sound.part.m4a"
        tmp.unlink(missing_ok=True)
        extra, args = _audio_filter(music, loudness)
        _ff("-i", Path(narration).name, *extra, *args, "-vn", *AUDIO, tmp.name, cwd=work)
        want = checkpoint.media_seconds(voice)
        bad = checkpoint.check_media(tmp, seconds=want or None, need=("audio",), tol=1.0)
        if bad:
            raise RuntimeError(f"the film's sound came out wrong ({bad}); the video parts are kept")
        os.replace(tmp, sound)
        man["sound"] = {"key": sound_key, **checkpoint.facts(sound), "at": checkpoint._now()}
        checkpoint.write_json(man_path, man)
    # each part's exact length (its frames at the film's rate) is written into the join list: the join never takes a part's own, possibly rounded, claim,
    # so a part's first frame can never land on the previous part's last one (21 Nov 2026 drill: "non monotonically increasing dts" at every join)
    (work / "parts.txt").write_text("".join(f"file '{n}'\nduration {frames_of(work / n) / config.FPS:.6f}\n" for n in names))
    _ff("-f", "concat", "-safe", "0", "-i", "parts.txt", "-i", sound.name, "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest", "-movflags", "+faststart", str(out), cwd=work)


def _assemble(segs, durations, narration, ass, work, out, music, loudness, grain, fade, n) -> None:
    norm = f"loudnorm=I={loudness:g}:TP=-1.5:LRA=11" if loudness is not None else ""
    venc = [*_venc("18", "medium"), *AUDIO, "-shortest", "-movflags", "+faststart", str(out)]
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
        return
    (work / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    _ff("-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4", cwd=work)  # a stream copy of checked scenes: written again every time, never trusted
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


def render(*args, **kwargs) -> Path:
    """The render, behind the server-wide gate of a user studio (STUDIO_RENDER_GATE): without that setting it runs at once, as before."""
    import tenantmode

    with tenantmode.render_gate():
        return _render_ungated(*args, **kwargs)
