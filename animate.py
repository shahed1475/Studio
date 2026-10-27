"""Turns some of a video's drawn scenes into short moving clips (image to video), so a documentary is animation mixed with documented real pictures.

Only the scenes the studio drew itself (never a real archive picture) can be animated: the drawn picture is the first frame and the prompt says how it gently moves.
Each clip costs money (about $0.24 for 8 seconds on Veo 3.1 Lite), so a video gets a clip count and a dollar budget; a clip made before is reused from the cache; a
failed clip leaves the picture in place and two failures in a row stop the buying. The clips are AI-generated video and are credited as such."""
import base64
import hashlib
import io
import shutil
from pathlib import Path

from PIL import Image

import config

CLIP_ESTIMATE = 0.24      # dollars for one 8-second clip on the default model, used to stop before a clip would pass the budget
MAX_FAILS_IN_A_ROW = 2


def _drawn(path) -> bool:
    return bool(path) and (Path(config.CACHE) / "art") in Path(path).parents and Path(path).suffix.lower() in (".jpg", ".jpeg", ".png")


def pick_scenes(clips: list, n: int) -> list[int]:
    """The indexes of up to n drawn scenes, spread from the first to the last so the animation is not bunched at the start."""
    drawn = [i for i, c in enumerate(clips) if _drawn(c)]
    if n <= 0 or not drawn:
        return []
    if n >= len(drawn):
        return drawn
    if n == 1:
        return drawn[:1]
    return [drawn[round(k * (len(drawn) - 1) / (n - 1))] for k in range(n)]


def motion_prompt(line: str, visual: str = "") -> str:
    import seo

    scene = seo.clean_sentences(str(line))[:220] or seo.plain(visual)[:80] or "the scene"
    return (f"Gentle cinematic animation of this 3D animated storybook scene: {scene} Slow camera push-in, soft mist or water or air drifting, warm light flickering, subtle natural "
            "movement of the characters, hair and cloth. No text, no cuts, no sudden changes.")


def frame_url(path, size: tuple[int, int] = (1280, 720)) -> str:
    """The picture as a JPEG data URL of this size (1280x720, or 720x1280 for a Short), the first frame of the clip."""
    from PIL import ImageOps

    buf = io.BytesIO()
    ImageOps.fit(Image.open(path).convert("RGB"), size, method=Image.LANCZOS).save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def animate_scenes(clips: list, lines: list[dict], n: int, budget_usd: float, gen, estimate: float = CLIP_ESTIMATE, size: tuple[int, int] = (1280, 720)) -> tuple[list, dict]:
    """(new clips list, stats). gen(prompt, first_frame_data_url) -> (mp4 path, dollars spent) or raises. The input list is not changed."""
    out = list(clips)
    stats = {"animated": 0, "cached": 0, "failed": 0, "spent": 0.0, "scenes": []}
    cache = Path(config.CACHE) / "anim"
    fails = 0
    for i in pick_scenes(clips, n):
        prompt = motion_prompt(lines[i].get("text", "") if i < len(lines) else "", lines[i].get("visual", "") if i < len(lines) else "")
        key = hashlib.sha256(Path(clips[i]).read_bytes() + prompt.encode()).hexdigest()[:20]
        hit = cache / f"{key}.mp4"
        if hit.exists():
            out[i] = hit
            stats["cached"] += 1
            stats["scenes"].append(i)
            continue
        if stats["spent"] + estimate > budget_usd:
            break
        try:
            clip, cost = gen(prompt, frame_url(clips[i], size))
            cache.mkdir(parents=True, exist_ok=True)
            shutil.copy(clip, hit)
        except Exception:
            stats["failed"] += 1
            fails += 1
            if fails >= MAX_FAILS_IN_A_ROW:
                break
            continue
        fails = 0
        out[i] = hit
        stats["animated"] += 1
        stats["spent"] = round(stats["spent"] + float(cost), 4)
        stats["scenes"].append(i)
    stats["scenes"].sort()
    return out, stats


def clip_config(base: dict, vertical: bool = False) -> dict:
    """The footage tool's settings for animation: the registry's video model, its own cost scope, and the picture shape (9:16 for a Short)."""
    import modelcfg

    return {**base, "model": modelcfg.get("video_generation"), "cost_scope": "animation", "aspect_ratio": "9:16" if vertical else "16:9"}


def clip_generator(vertical: bool = False):
    """gen(prompt, first_frame) for animate_scenes: one clip through the footage tool (price check, caps, ledger, run record)."""
    import footagestore
    import llm
    from tools.footage import clipgen

    cfg = clip_config(clipgen.load_config(config.ROOT / "config" / "footage.json"), vertical)

    def gen(prompt: str, first_frame: str):
        run = footagestore.create(cfg["cost_scope"], status="running", model=cfg["model"])
        res = clipgen.generate(cfg, llm.api_key(), prompt, run, first_frame=first_frame)
        return Path(res["clip"]), float(run.read().get("cost_booked") or 0.0)

    return gen


def credit(model: str) -> str:
    return f"Animation: AI-generated video clips ({model} via OpenRouter)"
