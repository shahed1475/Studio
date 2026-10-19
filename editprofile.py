"""Edit settings the renderer reads (loudness, pause between sentences). The growth agent may change them within fixed limits."""
import json

import config

FILE = config.ROOT / "edit_profile.json"
DEFAULTS = {"target_lufs": -16.0, "sentence_pause_ms": 120, "motion": 2, "caption_pos": "bottom"}  # motion: 0 plain, 1 camera shots and word captions, 2 also crossfades and film grain
LIMITS = {"target_lufs": (-20.0, -12.0), "sentence_pause_ms": (100, 900), "motion": (0, 2)}
INTS = ("sentence_pause_ms", "motion")
CHOICES = {"caption_pos": ("bottom", "top")}  # where subtitles sit: never in the middle of the picture


def validate(raw: dict) -> dict:
    out = {}
    for key, (lo, hi) in LIMITS.items():
        try:
            v = float(raw[key])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= v <= hi:
            out[key] = int(v) if key in INTS else v
    for key, allowed in CHOICES.items():
        if raw.get(key) in allowed:
            out[key] = raw[key]
    return out


def load() -> dict:
    saved = {}
    if FILE.exists():
        try:
            saved = validate(json.loads(FILE.read_text()))
        except ValueError:
            saved = {}
    return {**DEFAULTS, **saved}


def update(changes: dict) -> dict:
    profile = {**load(), **validate(changes)}
    FILE.write_text(json.dumps(profile, indent=2))
    return profile
