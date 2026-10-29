"""2.5D camera motion for the studio's own drawn pictures (free: no paid animation clip).

A depth map (depth.py: white near, black far) says how far each part of a picture is. While the camera drifts, the parts near the camera move across the frame more than
the parts far from it, with the middle of the picture staying put, which reads as depth. Each frame is a mesh warp of the picture (Pillow); ffmpeg encodes one clip per scene
into cache/anim/, and render.render already takes a video clip for a scene. The warp is small on purpose (the problem with this technique is the gap that opens behind a
near object, and a small move keeps it invisible). Only pictures in cache/art (drawn by the studio, credited as AI art) move: a real archive picture never does.
Nothing here needs more than Pillow and ffmpeg, which the server already has."""
import hashlib
import math
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

import animate
import config
import depth
import render

VERSION = 1
MIN_ZOOM = 1.06   # the window never shows the whole picture: the warp needs a margin at the edges
GAIN = 0.03       # sideways shift of the nearest parts against the farthest at full sway, as a fraction of the picture's width
CELL = 40         # output pixels per warp cell
MARGIN = 0.6      # seconds a clip runs past its scene, so it never loops
WORKERS = 3       # the server has 4 cores; one stays free for the dashboard


def camera(plan: dict, t: float, sway: int = 1) -> dict:
    """The camera at time t (0 to 1): zoom, where the view sits (0 left or top, 1 right or bottom, as in render.SHOTS) and the sideways sway u from -1 to 1 (eased)."""
    z = max(MIN_ZOOM, plan["z0"] + (plan["z1"] - plan["z0"]) * t)
    return {"z": z, "fx": plan["fx0"] + (plan["fx1"] - plan["fx0"]) * t, "fy": plan["fy0"] + (plan["fy1"] - plan["fy0"]) * t, "u": sway * -math.cos(math.pi * t)}


def mesh(src_size: tuple[int, int], out_size: tuple[int, int], dmap: Image.Image, cam: dict) -> list:
    """PIL mesh data: for every cell of the output frame, the four corners it is taken from in the picture."""
    ws, hs = src_size
    wo, ho = out_size
    if ws / hs > wo / ho:
        ww1, wh1 = hs * wo / ho, float(hs)
    else:
        ww1, wh1 = float(ws), ws * ho / wo
    ww, wh = ww1 / cam["z"], wh1 / cam["z"]
    x0, y0 = (ws - ww) * cam["fx"], (hs - wh) * cam["fy"]
    dw, dh = dmap.size
    dpx = dmap.load()
    xs = sorted({min(wo, i * CELL) for i in range(wo // CELL + 2)})
    ys = sorted({min(ho, j * CELL) for j in range(ho // CELL + 2)})
    amp = cam["u"] * GAIN * ws
    grid = []
    for yo in ys:
        row = []
        for xo in xs:
            sx, sy = x0 + xo / wo * ww, y0 + yo / ho * wh
            d = dpx[min(dw - 1, max(0, int(sx / ws * (dw - 1)))), min(dh - 1, max(0, int(sy / hs * (dh - 1))))] / 255.0
            row.append((min(float(ws), max(0.0, sx + amp * (d - 0.5))), min(float(hs), max(0.0, sy))))
        grid.append(row)
    data = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            nw, ne, sw, se = grid[j][i], grid[j][i + 1], grid[j + 1][i], grid[j + 1][i + 1]
            data.append(((xs[i], ys[j], xs[i + 1], ys[j + 1]), (*nw, *sw, *se, *ne)))
    return data


def frame(src: Image.Image, dmap: Image.Image, out_size: tuple[int, int], cam: dict) -> Image.Image:
    return src.transform(out_size, Image.MESH, mesh(src.size, out_size, dmap, cam), Image.BILINEAR)


def render_clip(path, dmap: Image.Image, seconds: float, out: Path, size: tuple[int, int], plan: dict, sway: int = 1, fps: int | None = None) -> Path:
    """One scene as a video clip of `seconds`. Written under a temporary name and moved into place, so a clip that stopped half way is never reused."""
    fps = fps or config.FPS
    w, h = size
    n = max(2, round(seconds * fps))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-vf", "eq=brightness=-0.05:saturation=0.85,setsar=1", "-an", *render._venc("18", "veryfast"), str(tmp)]  # the same grade the still-picture path gives
    with Image.open(path) as im:
        src = im.convert("RGB")
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for k in range(n):
            p.stdin.write(frame(src, dmap, size, camera(plan, k / (n - 1), sway)).tobytes())
    finally:
        p.stdin.close()
        code = p.wait()
    if code:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg stopped with code {code}")
    tmp.replace(out)
    return out


def _job(job: tuple) -> str:
    path, secs, out, size, plan, sway = job
    dmap, _ = depth.depth_for(path)
    render_clip(path, dmap, secs, Path(out), size, plan, sway)
    return out


def apply(clips: list, durations: list[float], size: tuple[int, int], workers: int = WORKERS) -> tuple[list, dict]:
    """(new clips list, stats). Each drawn picture becomes a clip as long as its scene (plus a margin); anything else is returned as it was. The input list is not changed.
    A clip made before is reused; a clip that fails leaves the picture in place (the still-picture path then gives it a plain camera move)."""
    out = list(clips)
    stats = {"scenes": len(clips), "made": 0, "cached": 0, "model": 0, "approximate": 0, "skipped": 0, "failed": 0}
    cache = Path(config.CACHE) / "anim"
    cache.mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, (clip, dur) in enumerate(zip(clips, durations)):
        if not animate._drawn(clip) or dur <= 0:
            stats["skipped"] += 1
            continue
        dmap, how = depth.depth_for(clip)
        stats[how] += 1
        plan, sway = render.shot_plan(i), 1 if i % 2 == 0 else -1
        secs = math.ceil((dur + MARGIN) * 2) / 2
        key = hashlib.md5(Path(clip).read_bytes() + dmap.tobytes() + repr((plan, sway, size, secs, VERSION, MIN_ZOOM, GAIN)).encode()).hexdigest()[:20]
        dest = cache / f"px-{key}.mp4"
        if dest.exists():
            out[i] = dest
            stats["cached"] += 1
        else:
            jobs.append((i, (str(clip), secs, str(dest), size, plan, sway), dest))
    if jobs:
        if workers <= 1 or len(jobs) == 1:
            results = []
            for _, job, dest in jobs:
                try:
                    results.append(_job(job))
                except Exception:
                    results.append(None)
        else:
            with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
                futures = [pool.submit(_job, job) for _, job, _ in jobs]
                results = []
                for f in futures:
                    try:
                        results.append(f.result())
                    except Exception:
                        results.append(None)
        for (i, _, dest), got in zip(jobs, results):
            if got and dest.exists():
                out[i] = dest
                stats["made"] += 1
            else:
                stats["failed"] += 1
    stats["made_at"] = round(time.time())
    return out, stats
