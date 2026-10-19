"""Settings. Override any of them with environment variables."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent


def load_env(path: Path | None = None) -> None:
    """Read KEY=value lines from .env into the environment; variables already set win."""
    f = path or ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("\"'")
        if k and k.replace("_", "").isalnum():
            os.environ.setdefault(k, v)


load_env()
OUT = ROOT / "output"
CACHE = ROOT / "cache"
NICHE_FILE = ROOT / "niche.json"
TOPICS_FILE = ROOT / "topics.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("YT_MODEL", "qwen3:8b")
VOICE = os.getenv("YT_VOICE", "en-US-AndrewNeural")  # also: en-US-AriaNeural, en-US-GuyNeural
VOICE_RATE = os.getenv("YT_VOICE_RATE", "-6%")  # slower = storyteller pace
VOICE_PITCH = os.getenv("YT_VOICE_PITCH", "-3Hz")  # slightly deeper
_saved = ROOT / "settings.json"  # written by the dashboard
PEXELS_KEY = os.getenv("PEXELS_API_KEY") or (json.loads(_saved.read_text()).get("pexels_key", "") if _saved.exists() else "")  # free key: https://www.pexels.com/api/
WIDTH, HEIGHT, FPS = 1080, 1920, 30
DOC_SUBTITLES = os.getenv("YT_DOC_SUBS", "1") == "1"  # burn subtitles into documentaries
ARCHIVE_VIDEO = os.getenv("YT_ARCHIVE_VIDEO", "1") == "1"  # moving public-domain footage for scenes
DOC_VIDEO_CLIPS = os.getenv("YT_DOC_VIDEO", "0") == "1"  # also use it in documentaries (slower, off by default)
MAX_UPLOADS_PER_DAY = 2  # growth research: 1 a day is strong, 2 is the ceiling; above ~3 quality drops and YouTube's inauthentic-content check looks at the pattern (the API itself allows 100 uploads a day)


def niche() -> dict:
    return json.loads(NICHE_FILE.read_text())
