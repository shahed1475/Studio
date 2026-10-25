"""Nightly backup of what cannot be rebuilt: every video's saved record (`meta.json`, claim ledger, caption words), the settings files and `data/`.

Left out on purpose: secrets (`.env`, `settings.json`, `token*.json`, `client_secret*.json`, and in `data/` the dashboard login, its signing secret, sessions and user-studio list: after a restore the logins are made again; `data/` is copied from an allowlist), the videos themselves
and the picture cache (they can be rebuilt, and they are most of the 1.6 GB). The copy stays on the same server in `backups/` (seven kept); to keep one
off the server, pull it from the PC: `scp deploy@<server>:studio/backups/backup-<date>.tar.gz .`"""
import datetime as dt
import os
import tarfile
from pathlib import Path

import config

KEEP = 7
SECRET_NAMES = {".env", "settings.json"}
SECRET_PARTS = ("token", "client_secret")
PER_VIDEO = {"meta.json", "claims.json", "words.json", "captions.srt"}
SETTINGS = ("llm.json", "autopilot.json", "agent.json", "niche.json", "topics.json", "pinned_topics.json", "news_topics.json", "edit_profile.json",
            "reference_channels.json", "reference_meta.json")


def _is_secret(path: Path) -> bool:
    n = path.name.lower()
    return path.name in SECRET_NAMES or any(p in n for p in SECRET_PARTS)


# `data/` holds the dashboard's login record, its cookie-signing secret and live sessions next to harmless records, so it is an ALLOWLIST: a new file in
# `data/` is left out of the backup until it is named here (a denylist would copy it the day it appears).
DATA_ALLOWED = {"agent", "channels", "newswatch", "trends", "research", "llm_usage.json", "video_costs.json", "titletest.json", "playlists.json",
                "youtube_login.json", "worker_state.json", "money_digest.json", "topic_fails.json", "removed_topics.json", "pending_doc.json",
                "guard_off.json", "daily_report.json", "free_models.json", "image_judge.json"}
NEVER = ("secret", "session", "auth", "oauth", "invite", "cookie", "password", "tenant", "token", "credential")  # defence in depth inside the allowed folders


def _files(root: Path):
    for name in SETTINGS:
        f = root / name
        if f.is_file() and not _is_secret(f):
            yield f
    data = root / "data"
    if data.is_dir():
        for top in sorted(data.iterdir()):
            if top.name not in DATA_ALLOWED:
                continue
            for f in ([top] if top.is_file() else sorted(top.rglob("*"))):
                rel = str(f.relative_to(data)).lower()
                if f.is_file() and f.suffix != ".lock" and "cache" not in f.parts and not any(w in rel for w in NEVER):
                    yield f
    out = root / "output"
    if out.is_dir():
        for f in sorted(out.glob("*/*")):
            if f.is_file() and f.name in PER_VIDEO:
                yield f


def run(now: dt.datetime | None = None, root: Path | None = None, dest: Path | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    root, dest = root or config.ROOT, dest or config.ROOT / "backups"
    dest.mkdir(parents=True, exist_ok=True)
    dest.chmod(0o700)
    path = dest / f"backup-{now.strftime('%Y%m%d')}.tar.gz"
    n = 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # private from the first byte, never world-readable while it is written
    with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as t:
        for f in _files(root):
            t.add(f, arcname=str(f.relative_to(root)))
            n += 1
    path.chmod(0o600)
    for old in sorted(dest.glob("backup-*.tar.gz"))[:-KEEP]:
        old.unlink()
    return {"path": str(path), "files": n, "bytes": path.stat().st_size}


def newest_age_hours(now: dt.datetime | None = None, dest: Path | None = None) -> float | None:
    """Hours since the newest backup was made (by its file date), None when there is none."""
    now = now or dt.datetime.now(dt.timezone.utc)
    names = sorted((dest or config.ROOT / "backups").glob("backup-*.tar.gz"))
    if not names:
        return None
    made = dt.datetime.strptime(names[-1].stem.removesuffix(".tar").split("-")[1], "%Y%m%d").replace(tzinfo=dt.timezone.utc, hour=3, minute=30)
    return round((now - made).total_seconds() / 3600, 1)


PUSH_MARKER = "last_push.txt"   # written by deploy/backup_push.sh after a successful push: "<UTC time> <archive name>"


def pushed_age_hours(now: dt.datetime | None = None, dest: Path | None = None) -> float | None:
    """Hours since the newest backup was pushed off the server (from the marker the push script writes), None when it never was or the marker is unreadable."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        first = (dest or config.ROOT / "backups").joinpath(PUSH_MARKER).read_text().split()[0]
        at = dt.datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError, IndexError):
        return None
    hours = (now - at).total_seconds() / 3600
    return round(hours, 1) if hours >= -1 else None   # a time in the future is not believed
