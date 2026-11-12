"""One door to the free picture and footage libraries (9 Nov 2026, owner's list). Reads only: it searches and returns addresses, licence text and a credit line in ONE shape.
It downloads nothing and puts nothing into a video: whether an item may be used is decided per item by `accepted` (the studio's own licence check, footage_real.licence_ok:
public domain, CC0, CC BY with a credit line; never non-commercial or no-derivatives). Since 10 Nov 2026 the owner's decision applies (licences.py): NASA media and the Pixabay Content License are accepted too, with a credit; Pexels is shown as
they are and are NOT accepted until the owner decides. The licence comes from each item's own fields, not from a general claim about the library.
Keys: pixabay, smithsonian (and pexels, already in Settings) come from .env or the dashboard Settings; the others need none. Results are cached 24 hours on disk, keys never reach a cache file."""
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

import config
import footage_real
import pixabay

UA = {"User-Agent": "StoryStudio/1.0 (history channel; picture search; github.com/shahed1475/Studio)"}
CACHE_HOURS, TIMEOUT = 24, 40  # Internet Archive and Openverse can take 10 to 30 seconds
SECRET_PARAMS = {"api_key", "key"}
NASA_LICENCE = "NASA media (credit NASA; no NASA logos)"  # NASA's media guidelines, accepted by the owner's decision of 10 Nov 2026; the word "copyright" is left out because the licence gate forbids it in a credit


def _cache_file(url: str, params: dict) -> Path:
    stable = url + json.dumps({k: v for k, v in (params or {}).items() if k not in SECRET_PARAMS}, sort_keys=True, default=str)
    return config.CACHE / "openmedia" / (hashlib.md5(stable.encode()).hexdigest()[:16] + ".json")


def fetch(url: str, params: dict | None = None, headers: dict | None = None, get=requests.get, now=time.time):
    """JSON from a library, cached for a day. A refusal or a bad reply raises with a plain message."""
    f = _cache_file(url, params or {})
    if f.exists() and now() - f.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(f.read_text())
    r = get(url, params=params, headers={**UA, **(headers or {})}, timeout=TIMEOUT)
    if r.status_code == 429:
        raise RuntimeError("too many requests, try again in a minute")
    if r.status_code in (401, 403):
        raise RuntimeError(f"refused (HTTP {r.status_code}): the key may be wrong or missing")
    r.raise_for_status()
    reply = r.json()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(reply))
    return reply


def _plain(text, limit: int = 80) -> str:
    """A name or title from a library as plain text: markup removed, spaces folded, cut at a word."""
    t = " ".join(re.sub(r"<[^>]+>", " ", str(text or "")).replace("&amp;", "&").split())
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0].rstrip(",;:- ") + "..."


def _item(source: str, kind: str, title, page, url, licence, credit, preview=None, author=None) -> dict:
    return {"source": source, "kind": kind, "title": str(title or "")[:200], "page": page, "url": url, "preview": preview or url, "licence": licence, "credit": credit,
            "author": _plain(author, 60), "accepted": footage_real.licence_ok(licence)}


# ---- museums (images only) ----
def met(q, kind, n, get):
    ids = (fetch("https://collectionapi.metmuseum.org/public/collection/v1.1/search", {"q": q, "hasImages": "true", "isPublicDomain": "true", "limit": n * 2}, get=get).get("objectIDs") or [])
    out = []
    for i in ids:
        if len(out) >= n:
            break
        o = fetch(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{i}", get=get)
        if o.get("isPublicDomain") and o.get("primaryImage"):  # the item's own flag, checked again
            out.append(_item("met", "image", o.get("title"), o.get("objectURL"), o["primaryImage"], "CC0 (Met Open Access)", f"{o.get('title')}, The Metropolitan Museum of Art ({o.get('creditLine', '')})", o.get("primaryImageSmall")))
    return out


def aic(q, kind, n, get):
    d = fetch("https://api.artic.edu/api/v1/artworks/search", {"q": q, "query[term][is_public_domain]": "true", "limit": n, "fields": "id,title,image_id,is_public_domain,artist_display"},
              {"AIC-User-Agent": "StoryStudio (github.com/shahed1475/Studio)"}, get)
    return [_item("aic", "image", h.get("title"), f"https://www.artic.edu/artworks/{h['id']}", f"https://www.artic.edu/iiif/2/{h['image_id']}/full/843,/0/default.jpg", "CC0 (Art Institute of Chicago)",
                  f"{h.get('title')}, Art Institute of Chicago") for h in d.get("data", []) if h.get("is_public_domain") and h.get("image_id")][:n]


def cleveland(q, kind, n, get):
    d = fetch("https://openaccess-api.clevelandart.org/api/artworks/", {"q": q, "cc0": 1, "has_image": 1, "limit": n}, get=get)
    return [_item("cleveland", "image", h.get("title"), h.get("url"), ((h.get("images") or {}).get("web") or {}).get("url"), "CC0 (Cleveland Museum of Art)", f"{h.get('title')}, Cleveland Museum of Art")
            for h in d.get("data", []) if h.get("share_license_status") == "CC0" and ((h.get("images") or {}).get("web") or {}).get("url")][:n]


def smithsonian(q, kind, n, get):
    d = fetch("https://api.si.edu/openaccess/api/v1.0/search", {"q": f"{q} online_media_type:Images", "rows": n * 2, "api_key": config.SMITHSONIAN_KEY or _saved("smithsonian_key")}, get=get)
    out = []
    for r in (d.get("response") or {}).get("rows", []):
        dn = (r.get("content") or {}).get("descriptiveNonRepeating") or {}
        media = ((dn.get("online_media") or {}).get("media") or [{}])[0]
        if (dn.get("metadata_usage") or {}).get("access") == "CC0" and media.get("content"):
            out.append(_item("smithsonian", "image", r.get("title"), dn.get("record_link"), media["content"], "CC0 (Smithsonian Open Access)", f"{r.get('title')}, Smithsonian Institution ({r.get('unitCode', '')})", media.get("thumbnail")))
    return out[:n]


# ---- space, general ----
def nasa(q, kind, n, get):
    d = fetch("https://images-api.nasa.gov/search", {"q": q, "media_type": kind, "page_size": n}, get=get)
    out = []
    for it in (d.get("collection") or {}).get("items", [])[:n]:
        m = (it.get("data") or [{}])[0]
        links = it.get("links") or []
        pic = next((x["href"] for x in links if x.get("rel") == "canonical"), None) or (links[0]["href"] if links else None)
        url = pic
        if kind == "video":
            try:
                files = fetch(it["href"], get=get)
                mp4 = [u for u in files if u.endswith(".mp4")]
                url = next((u for u in mp4 if "~medium" in u), None) or next((u for u in mp4 if "~mobile" in u), None) or (mp4[0] if mp4 else None)
            except (requests.RequestException, RuntimeError, ValueError, KeyError):
                url = None
        out.append(_item("nasa", kind, m.get("title"), f"https://images.nasa.gov/details/{m.get('nasa_id')}", url, NASA_LICENCE, f"NASA ({m.get('nasa_id')})", pic))
    return out


def openverse(q, kind, n, get):
    d = fetch("https://api.openverse.org/v1/images/", {"q": q, "page_size": n, "license_type": "commercial"}, get=get)  # the combined filter took 10 s; no-derivatives items are caught by accepted
    out = []
    for h in d.get("results", [])[:n]:
        code, ver = str(h.get("license", "")), h.get("license_version") or ""
        lic = "CC0" if code == "cc0" else "Public Domain Mark" if code == "pdm" else f"CC {code.upper()} {ver}".strip()
        out.append(_item("openverse", "image", h.get("title"), h.get("foreign_landing_url"), h.get("url"), lic, f"{h.get('title')} by {h.get('creator') or 'unknown'} ({lic}, {h.get('license_url', '')})", h.get("thumbnail"), author=h.get("creator")))
    out.sort(key=lambda i: not i["accepted"])
    return out


def commons(q, kind, n, get):
    ft = "video" if kind == "video" else "bitmap"
    d = fetch("https://commons.wikimedia.org/w/api.php", {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": n * 2, "gsrsearch": f"filetype:{ft} {q}",
                                                          "prop": "imageinfo", "iiprop": "url|extmetadata|mediatype"}, get=get)
    out = []
    for p in ((d.get("query") or {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        lic = (md.get("LicenseShortName") or {}).get("value", "unknown")
        title = str(p.get("title", "")).removeprefix("File:")
        out.append(_item("commons", kind, title, ii.get("descriptionurl"), ii.get("url"), lic, f"{title}, Wikimedia Commons ({lic})",
                         author=(md.get("Artist") or {}).get("value")))
    out.sort(key=lambda i: not i["accepted"])  # usable ones first
    return out[:n]


def internet_archive(q, kind, n, get):
    import archive_video

    d = fetch("https://archive.org/advancedsearch.php", {"q": archive_video.build_query(q), "fl[]": ["identifier", "title", "licenseurl"], "sort[]": "downloads desc", "rows": n, "output": "json"}, get=get)
    return [_item("archive", "video", h.get("title"), f"https://archive.org/details/{h['identifier']}", None, archive_video._license_name(h.get("licenseurl") or ""),
                  f"{h.get('title')} (Internet Archive)") for h in d.get("response", {}).get("docs", [])][:n]


# ---- platform licences (shown, never accepted automatically) ----
def pixabay_src(q, kind, n, get):
    rows = (pixabay.search_videos if kind == "video" else pixabay.search_images)(q, n, get)
    return [_item("pixabay", kind, r.get("tags") or q, r["page"], r.get("url") or r.get("preview"), "Pixabay Content License", r["credit"], r.get("preview")) for r in rows]


def pexels(q, kind, n, get):
    key = config.PEXELS_KEY or _saved("pexels_key")
    if kind == "video":
        d = fetch("https://api.pexels.com/videos/search", {"query": q, "per_page": n}, {"Authorization": key}, get)
        out = []
        for v in d.get("videos", [])[:n]:
            f = next((x for x in v.get("video_files", []) if x.get("file_type") == "video/mp4"), {})
            out.append(_item("pexels", "video", q, v.get("url"), f.get("link"), "Pexels License", f"Video by {(v.get('user') or {}).get('name')} via Pexels", v.get("image")))
        return out
    d = fetch("https://api.pexels.com/v1/search", {"query": q, "per_page": n}, {"Authorization": key}, get)
    return [_item("pexels", "image", p.get("alt") or q, p.get("url"), (p.get("src") or {}).get("large"), "Pexels License", f"Photo by {p.get('photographer')} via Pexels", (p.get("src") or {}).get("medium")) for p in d.get("photos", [])[:n]]


def _saved(field: str) -> str:
    try:
        return str(json.loads((config.ROOT / "settings.json").read_text()).get(field, ""))
    except (OSError, ValueError):
        return ""


def _have(field: str, env_value: str) -> bool:
    return bool(env_value or _saved(field))


# name: (label, kinds, key field or None, function)
SOURCES = {
    "commons": ("Wikimedia Commons", ("image", "video"), None, commons),
    "met": ("The Met Museum", ("image",), None, met),
    "aic": ("Art Institute of Chicago", ("image",), None, aic),
    "cleveland": ("Cleveland Museum of Art", ("image",), None, cleveland),
    "nasa": ("NASA Image & Video Library", ("image", "video"), None, nasa),
    "archive": ("Internet Archive", ("video",), None, internet_archive),
    "smithsonian": ("Smithsonian Open Access", ("image",), "smithsonian_key", smithsonian),
    "openverse": ("Openverse", ("image",), None, openverse),
    "pixabay": ("Pixabay", ("image", "video"), "pixabay_key", pixabay_src),
    "pexels": ("Pexels", ("image", "video"), "pexels_key", pexels),
}


def key_present(field: str | None) -> bool:
    if not field:
        return True
    env = {"pixabay_key": config.PIXABAY_KEY, "smithsonian_key": config.SMITHSONIAN_KEY, "pexels_key": config.PEXELS_KEY}.get(field, "")
    return _have(field, env)


def status() -> list[dict]:
    return [{"id": k, "label": v[0], "kinds": list(v[1]), "needs_key": bool(v[2]), "ready": key_present(v[2])} for k, v in SOURCES.items()]


def search(source: str, query: str, kind: str = "image", n: int = 5, get=requests.get) -> list[dict]:
    label, kinds, keyf, fn = SOURCES[source]
    if kind not in kinds:
        raise ValueError(f"{label} has no {kind}")
    if not key_present(keyf):
        raise RuntimeError("no key saved: add it in Settings")
    return fn(re.sub(r"\s+", " ", query).strip()[:100], kind, max(1, min(n, 10)), get)


def selftest(query: str = "pyramids", get=requests.get) -> list[dict]:
    """One image search (and one video search where the library has video) per library, in parallel. Says plainly what worked; never raises, never shows a key."""
    jobs = [(k, kind) for k, v in SOURCES.items() for kind in v[1]]

    def one(job):
        k, kind = job
        row = {"id": k, "label": SOURCES[k][0], "kind": kind}
        if not key_present(SOURCES[k][2]):
            return {**row, "state": "needs key", "detail": "no key saved yet"}
        try:
            hits = search(k, query, kind, 3, get)
        except Exception as e:  # reported, not hidden
            return {**row, "state": "failed", "detail": re.sub(r"(api_)?key=[^&\s']+", "key=***", str(e))[:160]}
        if not hits:
            return {**row, "state": "empty", "detail": "the library answered, nothing matched"}
        ok = sum(h["accepted"] for h in hits)
        return {**row, "state": "ok", "detail": f"{len(hits)} results, {ok} with a licence the studio accepts", "first": hits[0]["page"], "licence": hits[0]["licence"]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, jobs))


def format_selftest(rows: list[dict]) -> str:
    return "\n".join(f"{'ok  ' if r['state'] == 'ok' else r['state'].upper():9} {r['label']} ({r['kind']}): {r['detail']}" + (f"\n          first: {r['first']}" if r.get("first") else "") for r in rows)
