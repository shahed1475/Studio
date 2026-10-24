"""Per-studio settings that decide how much a person must approve: `data/profile.json`, server only, never committed.

{"human_approval": true} makes Autopilot leave every reviewed video unapproved until the owner clicks approve (a new channel type, such as crisis explainers, starts like
this). A missing file, a missing key or a bad value means False: the owner's studio behaves exactly as before. The daily money cap and the weekly cap stay in
llm.json and autopilot.json, which every studio already has of its own (docs/architecture/05-target-design.md, step 4)."""
import json

import config

FILE = config.ROOT / "data" / "profile.json"


def load() -> dict:
    try:
        data = json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def human_approval() -> bool:
    return load().get("human_approval") is True
