"""Every picture, clip, sound and font in a video needs a ledger row: where it came from, its licence, its date and a file hash. A missing row blocks the upload."""
import hashlib
from pathlib import Path

ALLOWED = {"public domain", "cc0", "cc by", "cc by-sa", "own work", "ai-generated", "stock licence"}
NEEDS_ATTRIBUTION = {"cc by", "cc by-sa", "ai-generated"}


def row(path, source: str, licence: str, fetched: str, author: str = "") -> dict:
    p = Path(path)
    return {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "source": source, "licence": licence.lower(), "fetched": fetched, "author": author}


def problems(rows: list[dict], files: list[str]) -> list[str]:
    """What stops the upload: a file without a row, a licence that is not allowed, a row without a source or date."""
    have = {r.get("file"): r for r in rows}
    out = []
    for f in files:
        r = have.get(f)
        if not r:
            out.append(f"{f}: no ledger row")
            continue
        if r.get("licence") not in ALLOWED:
            out.append(f"{f}: licence '{r.get('licence')}' is not allowed (no non-commercial, no-derivatives, unknown)")
        if not r.get("source") or not r.get("fetched"):
            out.append(f"{f}: source and date are required")
        if r.get("licence") in NEEDS_ATTRIBUTION and not r.get("author") and r.get("licence") != "ai-generated":
            out.append(f"{f}: this licence needs the author's name")
    return out
