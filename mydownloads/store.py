"""Where My Downloads keeps things: its settings, the list of the owner's channels, the saved queue, the log, and the Desktop folder.

Settings live in ~/.config/studio-mydownloads (MYDL_HOME overrides it); videos go to <Desktop>/My YouTube Downloads (MYDL_FOLDER overrides it).
Nothing here is secret and nothing here is inside the studio's own data.
"""
import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path

CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
FOLDER_NAME = "My YouTube Downloads"


def _config_root() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def home() -> Path:
    return Path(os.environ["MYDL_HOME"]) if os.environ.get("MYDL_HOME") else _config_root() / "studio-mydownloads"


def desktop() -> Path:
    me = Path.home()
    try:
        for line in (_config_root() / "user-dirs.dirs").read_text().splitlines():
            m = re.match(r'\s*XDG_DESKTOP_DIR="([^"]+)"', line)
            if m:
                return Path(m.group(1).replace("$HOME", str(me)))
    except OSError:
        pass
    return me / "Desktop" if (me / "Desktop").is_dir() else me


def folder() -> Path:
    return Path(os.environ["MYDL_FOLDER"]) if os.environ.get("MYDL_FOLDER") else desktop() / FOLDER_NAME


def _read(name: str, default):
    try:
        return json.loads((home() / name).read_text())
    except (OSError, ValueError):
        return default


def _write(name: str, data) -> None:
    home().mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=home(), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1)
            f.flush()
            os.fsync(f.fileno())  # a power cut must leave the old file or the new one, never half of one
        os.replace(tmp, home() / name)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def channels() -> list:
    d = _read("channels.json", [])
    return [c for c in d if isinstance(c, dict) and CHANNEL_ID.match(str(c.get("id", "")))] if isinstance(d, list) else []


def channel_ids() -> set:
    return {c["id"] for c in channels()}


def add_channel(cid: str, title: str, handle: str, how: str) -> dict:
    """Record a channel as the owner's. `how` says on what basis (the studio's own upload record, or the owner's statement)."""
    if not isinstance(cid, str) or not CHANNEL_ID.match(cid):
        raise ValueError("that is not a YouTube channel id")
    have = channels()
    for c in have:
        if c["id"] == cid:
            return c
    c = {"id": cid, "title": title or "", "handle": handle or "", "how": how, "added": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    _write("channels.json", have + [c])
    return c


def remove_channel(cid: str) -> bool:
    have = channels()
    keep = [c for c in have if c["id"] != cid]
    if len(keep) == len(have):
        return False
    _write("channels.json", keep)
    return True


def save_job(job: dict) -> None:
    _write("job.json", job)


def load_job():
    d = _read("job.json", None)
    return d if isinstance(d, dict) else None


def audit(event: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    row = dict(event, at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(home() / "downloads.log", "a") as f:
        f.write(json.dumps(row) + "\n")


def saved_path(video_id: str):
    """The finished video file for this id anywhere in the download folder, else None (a .part file is not a saved video)."""
    if not isinstance(video_id, str) or not VIDEO_ID.match(video_id) or not folder().is_dir():
        return None
    tag = f"[{video_id}]"
    for root, _dirs, files in os.walk(folder()):
        for name in sorted(files):
            if tag in name and Path(name).suffix.lower() in VIDEO_EXT:
                return Path(root) / name
    return None
