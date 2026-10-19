"""Edit settings the renderer reads (loudness, pause between sentences). The growth agent may change them within fixed limits."""
import json

import config

FILE = config.ROOT / "edit_profile.json"
DEFAULTS = {"target_lufs": -16.0, "sentence_pause_ms": 120}
LIMITS = {"target_lufs": (-20.0, -12.0), "sentence_pause_ms": (100, 900)}


def validate(raw: dict) -> dict:
    out = {}
    for key, (lo, hi) in LIMITS.items():
        try:
            v = float(raw[key])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= v <= hi:
            out[key] = int(v) if key == "sentence_pause_ms" else v
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
