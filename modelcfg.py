"""Which OpenRouter model does which job, in one place.

The defaults were checked against OpenRouter's public lists on 27 Oct 2026 (docs/studio/MODELS_2026-10-27.md). A studio may override single jobs in
`config/models.json`; an id that is not a plain model id, or a value of the wrong type, is ignored and the default is used, so a typo never reaches the API.
The text roles (script, review, cheap) stay in llm.json and the Settings page: they are the owner's switches."""
import json

import config
import llm

FILE = config.ROOT / "config" / "models.json"
DEFAULTS = {
    "thumbnail_art": "google/gemini-3.1-flash-image",        # draws the thumbnail picture: $0.067 each, the clearest of three tested (Pro $0.140 no better, Lite $0.034 too dim)
    "scene_art": "google/gemini-3.1-flash-lite-image",       # draws in-video storybook scenes (many per video: the cheap one)
    "scene_art_3d": "google/gemini-3.1-flash-image",          # the 3D-look scenes that become first frames of animated clips: the clearer model (27 Oct spike)
    "thumbnail_score": "anthropic/claude-sonnet-5.5",        # reads candidate thumbnails and scores them (vision)
    "video_analysis": "google/gemini-3.1-pro-preview",       # watches one of our own videos through video_url
    "audio_listen": "google/gemini-3.1-flash-lite",          # writes down what it hears in our own finished audio, blind, so voicecheck can compare it with the script (a fraction of a cent a film)
    "video_generation": "google/veo-3.1-lite",               # the footage tool's clip model
    "video_generation_allowed": ["google/veo-3.1-lite", "google/veo-3.1-fast", "google/veo-3.1", "alibaba/wan-3.0", "alibaba/wan-3.0-prime", "alibaba/wan-2.7"],
}


def _ok(v) -> bool:
    return isinstance(v, str) and bool(llm.MODEL_ID.match(v))


def load() -> dict:
    out = {k: list(v) if isinstance(v, list) else v for k, v in DEFAULTS.items()}
    try:
        raw = json.loads(FILE.read_text())
    except (OSError, ValueError):
        return out
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if k not in DEFAULTS:
            continue
        if isinstance(DEFAULTS[k], list):
            good = [m for m in v if _ok(m)] if isinstance(v, list) else []
            if good:
                out[k] = good
        elif _ok(v):
            out[k] = v
    return out


def get(capability: str):
    """The model id for a job (a list of ids for video_generation_allowed). An unknown job is a KeyError: a typo must not pick a model."""
    return load()[capability]
