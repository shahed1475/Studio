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
import re

import config
import llm

MODEL = "google/gemini-3.1-flash-lite-image"
STYLE = ("Antique storybook illustration, muted watercolour and ink, warm candlelit palette, soft paper texture, painterly, "
         "no text, no letters, no captions, no watermark")
STYLES = [  # one per video, chosen by its topic: every video no longer looks like the same template
    STYLE,
    ("Black and white woodcut engraving, fine cross-hatching, aged cream paper, dramatic light and shadow, antique book plate, "
     "no text, no letters, no captions, no watermark"),
    ("Soft gouache and pastel illustration, dusty teal and ochre palette, gentle grain, hand-painted, calm and still, "
     "no text, no letters, no captions, no watermark"),
    ("Dark sepia ink wash and charcoal drawing, moody twilight, rough paper, sketchbook feel, "
     "no text, no letters, no captions, no watermark"),
]
CREDIT = "Illustration: AI-generated storybook art (Google Gemini image model via OpenRouter)"
MAX_PER_VIDEO = {"doc": 16, "short": 6}
EXTRA_FOR_VARIETY = 12  # more drawings allowed when a documentary would otherwise show the same pictures again and again
PRICE_EACH = 0.034  # dollars per picture, measured 20 Oct 2026: $3.19 for 95 pictures
_off_until: dict = {}  # a failed call (no credit) pauses drawing for the rest of the day


def enabled(now: dt.datetime | None = None) -> bool:
    now = now or llm._now()
    cfg = llm.load_config()
    return bool(cfg.get("ai_art") and llm.api_key() and _off_until.get("day") != now.strftime("%Y-%m-%d"))


def _clean(text: str, limit: int = 220) -> str:
    return " ".join(str(text).split())[:limit]


# An image model draws letters as garbled pseudo-text, and the picture check then flags the scene (an "inscription" with fake German, map labels in
# no language): for scenes about writing the picture is told to keep any writing illegible, so there is nothing to garble.
TEXTY = re.compile(r"inscription|manuscript|\bmaps?\b|letter|document|\bsigns?\b|\bbooks?\b|scroll|chronicle|parchment|plaque|tablet|newspaper|register|writing|poster|banner", re.I)
NO_WRITING = " Show it at an angle or from a distance with no legible writing, letters, symbols or map labels: any writing is only a texture."


def style_for(topic: str) -> str:
    return STYLES[int(hashlib.md5(str(topic).lower().encode()).hexdigest(), 16) % len(STYLES)]


def prompt_for(line: str, visual: str, topic: str, vertical: bool) -> str:
    shape = "vertical 9:16 composition" if vertical else "16:9 widescreen composition"
    text = f"{style_for(topic)}, {shape}. Story: {_clean(topic, 120)}. Scene: {_clean(line)}. Show: {_clean(visual, 80) or 'the setting of the scene'}."
    return text + (NO_WRITING if TEXTY.search(f"{visual} {line}") else "")


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


THUMB_STYLE = ("YouTube thumbnail illustration, 16:9 widescreen. Dramatic cinematic lighting, high contrast, rich saturated colours (deep teal shadows with warm amber light), "
               "painterly digital illustration with a subtle storybook texture, ONE clear focal subject with a strong mood, subject in the right two thirds, "
               "darker uncluttered space on the left and bottom. Do not invent architecture or details that are not in the scene description. "
               "No text, no letters, no numbers, no logos, no watermark, no real person likeness.")


def thumbnail_art(scene: str, now: dt.datetime | None = None):
    """(file, credit) for a 1280x720 thumbnail picture of one scene, or None when drawing is off, over the dollar cap, or failed. Competitors' best thumbnails
    show one clear subject with a strong mood, which archive photos and old maps rarely do; the picture is always labelled as AI art (the credit)."""
    now = now or llm._now()
    if not enabled(now) or llm.spent_today(now) >= llm.load_config()["daily_budget_usd"]:
        return None
    prompt = f"{THUMB_STYLE} Subject: {_clean(scene, 220)}."
    dest = config.CACHE / "art" / ("thumb-" + hashlib.md5(prompt.encode()).hexdigest()[:16] + ".jpg")
    if dest.exists():
        return dest, CREDIT
    try:
        body = llm._post({"model": MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": prompt}]}, llm.api_key())
        raw = base64.b64decode(body["choices"][0]["message"]["images"][0]["image_url"]["url"].split(",", 1)[1])
        from PIL import Image, ImageOps

        im = ImageOps.fit(Image.open(io.BytesIO(raw)).convert("RGB"), (1280, 720), method=Image.LANCZOS, centering=(0.6, 0.5))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=92)
        llm._account(now, "art", MODEL, body)
    except Exception as e:  # no credit (402), a refused prompt, a network error: the thumbnail keeps using the video's own frames
        if "402" in str(e):
            _off_until["day"] = now.strftime("%Y-%m-%d")
        return None
    return dest, CREDIT
