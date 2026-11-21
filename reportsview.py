"""The dashboard's Reports page (the owner's studio only): the audit and production reports that Claude Code sessions
write to reports/, plus the master report at the studio root. Read only: nothing here writes, runs or deletes.

A report is opened by its file name, and only a name this module listed itself is served (no paths, no other files,
no symlinks), so the page can never be used to read .env, a token or anything outside reports/."""
import datetime as dt
from pathlib import Path

import config

DIR_NAME = "reports"
ROOT_REPORTS = ("YOUTUBE-AUTOMATION-MASTER-REPORT.md",)  # kept at the studio root by the audit sessions
START_HERE = "AUTOPILOT_MASTER_AUDIT.md"  # the summary the newest audit points the owner to first
MAX_BYTES = 400_000  # a report bigger than this is shown cut, with a note


def _root(root: Path | None) -> Path:
    return Path(root) if root is not None else config.ROOT


def _files(root: Path | None = None) -> dict[str, Path]:
    r = _root(root)
    found: dict[str, Path] = {}
    d = r / DIR_NAME
    if d.is_dir() and not d.is_symlink():
        for f in d.glob("*.md"):
            if f.is_file() and not f.is_symlink():
                found[f.name] = f
    for name in ROOT_REPORTS:
        f = r / name
        if f.is_file() and not f.is_symlink():
            found[name] = f
    return found


def _title(f: Path) -> str:
    try:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for _ in range(15):
                line = fh.readline()
                if not line:
                    break
                if line.startswith("# "):
                    return line[2:].strip()[:140]
    except OSError:
        pass
    return f.stem.replace("_", " ").replace("-", " ").title()


def _when(f: Path) -> str:
    return dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def listing(root: Path | None = None) -> dict:
    """Every report, newest first, and the one to open first."""
    files = _files(root)
    rows = []
    for name, f in files.items():
        try:
            rows.append({"name": name, "title": _title(f), "bytes": f.stat().st_size, "modified": _when(f), "_t": f.stat().st_mtime})
        except OSError:  # removed while listing
            continue
    rows.sort(key=lambda x: (-x["_t"], x["name"]))
    for x in rows:
        x.pop("_t")
    start = START_HERE if START_HERE in files else (rows[0]["name"] if rows else None)
    return {"reports": rows, "start": start, "folder": DIR_NAME}


def read(name: str, root: Path | None = None) -> dict | None:
    """One report's text, or None when the name is not one of the listed reports."""
    f = _files(root).get(str(name or ""))
    if f is None:
        return None
    raw = f.read_bytes()
    return {"name": f.name, "title": _title(f), "modified": _when(f), "bytes": len(raw),
            "cut": len(raw) > MAX_BYTES, "text": raw[:MAX_BYTES].decode("utf-8", errors="replace")}
