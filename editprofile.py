"""Edit settings the renderer reads (loudness, pause between sentences). The growth agent may change them within fixed limits."""
import json

import config

FILE = config.ROOT / "edit_profile.json"
DEFAULTS = {"target_lufs": -14.0, "sentence_pause_ms": 120, "motion": 2, "caption_pos": "bottom"}  # motion: 0 plain, 1 camera shots and word captions, 2 also crossfades and film grain
LIMITS = {"target_lufs": (-17.0, -12.0), "sentence_pause_ms": (100, 900), "motion": (0, 2)}  # the quiet end stays inside what the reviewer accepts (reviewer.LOUD_RANGE is -17.5 to -12): on 27 Oct the growth agent's "calm bedtime voice" strategies took the target from -16 to -18, which the reviewer warned about on every new video
SHORT_PAUSE_MAX_MS = 250  # a Short must fit about 58 seconds: a 600 ms breath between 11 lines adds 6 seconds the script was not written for
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


def short_pause(profile: dict | None = None) -> float:
    """Seconds of breath after each line of a Short: the profile's pause, never more than SHORT_PAUSE_MAX_MS. A documentary keeps the profile's own pause."""
    return min((profile or load())["sentence_pause_ms"], SHORT_PAUSE_MAX_MS) / 1000


def lufs_for(meta: dict, profile: dict | None = None) -> float:
    """The loudness target of one video: its own `target_lufs` (a Short made loud on purpose) when it is a number inside LIMITS, else the profile's. The quiet end of
    LIMITS stays inside what the reviewer accepts, so a video's own choice can never fail the loudness check."""
    lo, hi = LIMITS["target_lufs"]
    own = (meta or {}).get("target_lufs")
    if isinstance(own, (int, float)) and not isinstance(own, bool) and lo <= own <= hi:
        return float(own)
    return (profile or load())["target_lufs"]
