"""Every picture, clip, sound and font in a video needs a ledger row: where it came from, its licence, its date and a file hash. A missing row blocks the upload."""
import hashlib
import re
from pathlib import Path

HEX64 = re.compile(r"[0-9a-f]{64}")
ALLOWED = {"public domain", "cc0", "cc by", "cc by-sa", "own work", "ai-generated", "stock licence"}
NEEDS_ATTRIBUTION = {"cc by", "cc by-sa", "ai-generated"}


def row(path, source: str, licence: str, fetched: str, author: str = "") -> dict:
    p = Path(path)
    return {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "source": source, "licence": licence.lower(), "fetched": fetched, "author": author}


def problems(rows: list[dict], files: list[str], hashes: dict | None = None) -> list[str]:
    """What stops the upload: a file without a row, a licence that is not allowed, a row without a source or date, and (when `hashes`, the sha256 of each file as it is NOW,
    is given) a file that is not the one the row describes. File names must be unique inside one video."""
    have = {r.get("file"): r for r in rows if isinstance(r, dict)}
    out = [f"{f}: listed twice (file names must be unique in a video)" for f in sorted({f for f in files if files.count(f) > 1})]
    for f in files:
        r = have.get(f)
        if not r:
            out.append(f"{f}: no ledger row")
            continue
        if hashes is not None:
            h, want = hashes.get(f), r.get("sha256")
            if not (isinstance(want, str) and HEX64.fullmatch(want)) or not (isinstance(h, str) and HEX64.fullmatch(h)) or h != want:
                out.append(f"{f}: the file does not match a valid 64-hex hash in its ledger row")
        if r.get("licence") not in ALLOWED:
            out.append(f"{f}: licence '{r.get('licence')}' is not allowed (no non-commercial, no-derivatives, unknown)")
        if not r.get("source") or not r.get("fetched"):
            out.append(f"{f}: source and date are required")
        if r.get("licence") in NEEDS_ATTRIBUTION and not r.get("author"):
            out.append(f"{f}: this licence needs the author's name (for AI art: the model)")
    return out
