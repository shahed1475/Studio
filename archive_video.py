"""Real moving footage from public-domain collections on the Internet Archive (CC0 / Public Domain Mark only).

Segments are cut over HTTP range requests (no full download), cached, and carry a credit line beside the file.
"""
import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests

import config

LICENSES = ["http://creativecommons.org/publicdomain/mark/1.0/", "https://creativecommons.org/publicdomain/mark/1.0/",
            "http://creativecommons.org/publicdomain/zero/1.0/", "https://creativecommons.org/publicdomain/zero/1.0/"]
COLLECTIONS = ["silent_films", "prelinger", "nasa"]  # archive film, educational ephemera, NASA: usable as scenery
FORMATS = ["h.264", "MPEG4", "512Kb MPEG4"]  # best first
MAX_BYTES = 150_000_000
STOP = {"the", "and", "with", "from", "that", "this", "old", "for", "into", "over"}
UA = {"User-Agent": "StoryStudio/1.0 (educational storytelling channel; public-domain footage)"}


def _words(text: str, min_len: int) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= min_len and w not in STOP]


def build_query(keywords: str) -> str:
    kw = " OR ".join(_words(keywords, 3)[:4]) or "history"
    lic = " OR ".join(f'licenseurl:"{u}"' for u in LICENSES)
    return (f"mediatype:movies AND ({lic}) AND collection:({' OR '.join(COLLECTIONS)}) AND ({kw}) "
            "AND NOT subject:(adult OR erotic OR nsfw OR porn)")


def relevant(doc: dict, keywords: str) -> bool:
    subject = doc.get("subject") or ""
    subject = " ".join(subject) if isinstance(subject, list) else subject
    text = f"{doc.get('title', '')} {subject}".lower()  # descriptions match too loosely ("an old flame" is not a candle)
    return any(w in text for w in _words(keywords, 4))


def pick_file(files: list[dict]) -> dict | None:
    ok = [f for f in files if f.get("name", "").lower().endswith(".mp4") and f.get("format") in FORMATS
          and 500_000 <= int(f.get("size") or 0) <= MAX_BYTES]
    return min(ok, key=lambda f: (FORMATS.index(f["format"]), int(f["size"]))) if ok else None


def clip_offset(length: float, seconds: float, seed: str) -> float:
    usable = max(0.0, length - seconds)
    if usable <= 0:
        return 0.0
    frac = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return usable * (0.15 + 0.45 * frac)


def _get_json(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def _license_name(url: str) -> str:
    return "CC0" if "zero" in (url or "") else "Public Domain Mark"


def fetch_clip(query: str, seconds: float = 10.0) -> Path | None:
    """A short silent segment of a public-domain film matching the query, or None."""
    import render

    config.CACHE.mkdir(exist_ok=True)
    key = hashlib.md5(f"arch:{query.lower()}:{seconds}".encode()).hexdigest()[:12]
    dest, none = config.CACHE / f"arch-{key}.mp4", config.CACHE / f"arch-{key}.none"
    if dest.exists():
        return dest
    if none.exists():
        return None
    try:
        docs = _get_json("https://archive.org/advancedsearch.php", {
            "q": build_query(query), "fl[]": ["identifier", "title", "subject", "description", "licenseurl", "downloads"],
            "sort[]": "downloads desc", "rows": 8, "output": "json"})["response"]["docs"]
    except (requests.RequestException, KeyError, ValueError):
        return None  # network trouble: do not remember it as "nothing found"
    tried = 0
    for doc in docs:
        if not relevant(doc, query) or tried >= 3:
            continue
        tried += 1
        try:
            meta = _get_json(f"https://archive.org/metadata/{doc['identifier']}")
        except (requests.RequestException, ValueError):
            continue
        f = pick_file(meta.get("files", []))
        if not f:
            continue
        offset = clip_offset(float(f.get("length") or 60), seconds, doc["identifier"])
        tmp = dest.with_suffix(".tmp.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.1f}", "-i",
               f"https://archive.org/download/{doc['identifier']}/{quote(f['name'])}", "-t", f"{seconds:.1f}",
               "-an", "-vf", "scale=-2:1280", *render._venc("23", "veryfast"), str(tmp)]
        try:
            ok = subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0 and tmp.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            tmp.unlink(missing_ok=True)
            continue
        tmp.replace(dest)
        lic = _license_name(doc.get("licenseurl") or meta.get("metadata", {}).get("licenseurl", ""))
        dest.with_suffix(".txt").write_text(f"{doc.get('title', doc['identifier'])} (Internet Archive, {lic})")
        return dest
    none.write_text("")
    return None
