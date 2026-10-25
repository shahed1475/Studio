"""A channel profile: one JSON file per channel under config/channels/, checked when it is loaded (missing or wrong keys stop with a clear message).
It says what a studio may use (sources, visuals, voice, rules) and its limits. Secrets are never in it: only the NAME of an environment variable."""
import json
from pathlib import Path

import config

DIR = config.ROOT / "config" / "channels"
REQUIRED = {"id": str, "audience": str, "made_for_kids": bool, "language": str, "sources": list, "visuals": list, "voice": str, "human_approval": bool,
            "limits": dict, "rules": list, "prompt_template": str, "env": dict}
KNOWN_SOURCES = {"wikipedia", "github_api", "official_data"}
KNOWN_VISUALS = {"archive_images", "ai_art", "remotion_cards", "cartoon_scenes"}


class ChannelConfigError(ValueError):
    pass


def validate(data: dict, name: str = "channel") -> dict:
    for key, typ in REQUIRED.items():
        if key not in data:
            raise ChannelConfigError(f"{name}: missing '{key}'")
        if not isinstance(data[key], typ):
            raise ChannelConfigError(f"{name}: '{key}' must be {typ.__name__}")
    if set(data["sources"]) - KNOWN_SOURCES or set(data["visuals"]) - KNOWN_VISUALS:
        raise ChannelConfigError(f"{name}: unknown source or visual")
    lim = data["limits"]
    if not isinstance(lim.get("videos_per_week"), int) or not isinstance(lim.get("daily_budget_usd"), (int, float)) or lim["daily_budget_usd"] < 0:
        raise ChannelConfigError(f"{name}: limits need videos_per_week (int) and daily_budget_usd (number, not negative)")
    if any(not str(v).isidentifier() or not str(v).isupper() for v in data["env"].values()):
        raise ChannelConfigError(f"{name}: 'env' holds variable NAMES in capitals, never values")
    if not (config.ROOT / data["prompt_template"]).is_file():
        raise ChannelConfigError(f"{name}: prompt template {data['prompt_template']} not found")
    return data


def load(channel_id: str) -> dict:
    p = DIR / f"{channel_id}.json"
    if not p.is_file():
        raise ChannelConfigError(f"no channel profile named {channel_id}")
    try:
        data = json.loads(p.read_text())
    except ValueError as e:
        raise ChannelConfigError(f"{channel_id}: not valid JSON ({e})")
    return validate(data, channel_id)


def load_all() -> list[dict]:
    """Every profile file, sorted by name. A broken one is returned as {"id": name, "error": reason}, never raised, so a page listing them cannot fail on one bad file."""
    rows = []
    for p in sorted(DIR.glob("*.json")):
        try:
            rows.append(load(p.stem))
        except ChannelConfigError as e:
            rows.append({"id": p.stem, "error": str(e)})
    return rows


def prompt(data: dict, **values) -> str:
    return (config.ROOT / data["prompt_template"]).read_text().format(**values)
