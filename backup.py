"""Nightly backup of what cannot be rebuilt: every video's saved record (`meta.json`, claim ledger, caption words), the settings files and `data/`.

Left out on purpose: secrets (`.env`, `settings.json`, `token*.json`, `client_secret*.json`: after a restore the login is made again), the videos themselves
and the picture cache (they can be rebuilt, and they are most of the 1.6 GB). The copy stays on the same server in `backups/` (seven kept); to keep one
off the server, pull it from the PC: `scp deploy@<server>:studio/backups/backup-<date>.tar.gz .`"""
import datetime as dt
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
    return path.name in SECRET_NAMES or any(p in path.name for p in SECRET_PARTS)


def _files(root: Path):
    for name in SETTINGS:
        f = root / name
        if f.is_file() and not _is_secret(f):
            yield f
    data = root / "data"
    if data.is_dir():
        for f in sorted(data.rglob("*")):
            if f.is_file() and not _is_secret(f) and f.suffix != ".lock" and "cache" not in f.parts:
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
    path = dest / f"backup-{now.strftime('%Y%m%d')}.tar.gz"
    n = 0
    with tarfile.open(path, "w:gz") as t:
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
