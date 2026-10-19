"""AI storybook illustrations for scenes that have no real public-domain picture.

Real archive pictures come first. When a scene has none (an obscure topic, or every picture is already used) one illustration is drawn in a
single consistent style, so the video never repeats the same photo or turns into coloured screens. Every illustration is labelled as AI-generated
in the video credits, and the upload is already marked as containing synthetic media.

It goes through the same OpenRouter key, daily dollar cap and cache as the text models. OpenRouter needs a balance of at least $1 for image output:
with less, or when a call fails, nothing is drawn and the caller reuses real pictures instead.
"""
import base64
import datetime as dt
import hashlib
import io

import config
import llm

MODEL = "google/gemini-3.1-flash-lite-image"
STYLE = ("Antique storybook illustration, muted watercolour and ink, warm candlelit palette, soft paper texture, painterly, "
         "no text, no letters, no captions, no watermark")
CREDIT = "Illustration: AI-generated storybook art (Google Gemini image model via OpenRouter)"
MAX_PER_VIDEO = {"doc": 16, "short": 6}
_off_until: dict = {}  # a failed call (no credit) pauses drawing for the rest of the day


def enabled(now: dt.datetime | None = None) -> bool:
    now = now or llm._now()
    cfg = llm.load_config()
    return bool(cfg.get("ai_art") and llm.api_key() and _off_until.get("day") != now.strftime("%Y-%m-%d"))


def _clean(text: str, limit: int = 220) -> str:
    return " ".join(str(text).split())[:limit]


def prompt_for(line: str, visual: str, topic: str, vertical: bool) -> str:
    shape = "vertical 9:16 composition" if vertical else "16:9 widescreen composition"
    return f"{STYLE}, {shape}. Story: {_clean(topic, 120)}. Scene: {_clean(line)}. Show: {_clean(visual, 80) or 'the setting of the scene'}."


def generate(line: str, visual: str, topic: str, vertical: bool = False, now: dt.datetime | None = None):
    """(file, credit) for a new illustration of this scene, or None when drawing is off, over the dollar cap, or failed."""
    now = now or llm._now()
    if not enabled(now):
        return None
    cfg = llm.load_config()
    if llm.spent_today(now) >= cfg["daily_budget_usd"]:
        return None
    prompt = prompt_for(line, visual, topic, vertical)
    dest = config.CACHE / "art" / (hashlib.md5(prompt.encode()).hexdigest()[:16] + ".jpg")
    if dest.exists():
        return dest, CREDIT
    try:
        body = llm._post({"model": MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": prompt}]}, llm.api_key())
        url = body["choices"][0]["message"]["images"][0]["image_url"]["url"]
        raw = base64.b64decode(url.split(",", 1)[1])
        from PIL import Image

        im = Image.open(io.BytesIO(raw)).convert("RGB")
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=92)
        llm._account(now, "art", MODEL, body)
    except Exception as e:  # no credit (402), a refused prompt, a network error: draw nothing
        if "402" in str(e):
            _off_until["day"] = now.strftime("%Y-%m-%d")
        return None
    return dest, CREDIT
