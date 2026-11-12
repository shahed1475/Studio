"""Real moving footage in a film (30 Oct 2026, owner's order: use real footage, make AI pictures only where needed).

Sources, in order: Wikimedia Commons video, NASA's Image and Video Library, Pixabay videos (owner's licence decision of 10 Nov 2026; Pixabay only when a key is set). A file is used when ALL of this holds: its licence is one the studio's own check accepts (public domain, CC0, CC BY, CC BY-SA, always with a credit line;
never non-commercial, no-derivatives or all-rights-reserved); its own title, categories or description name one of the film's anchors (a live probe on 30 Oct 2026 showed Commons search
returns dolphins for "Delphi" and a video game for "Egypt desert", so relevance is checked here and never assumed); it is a video of a sensible size and length. Six seconds are cut from it,
silent, in the film's picture size. They go on scenes that are not the hook scene, may not show people (parallax.flat_scenes) and were not chosen for an animated clip, spread over the film.
Whatever is not found stays an AI picture, so the number of real clips is "as many as truly fit, up to the count asked for", often few. Any failure leaves the scene as it was. Pexels is
not used (the owner did not list it). NASA items whose title names a logo or insignia are skipped (NASA's media rules). Every download, from every source, goes only to public https addresses,
each redirect hop checked (realmedia._public_https), with the size limit applied while streaming."""
import hashlib
import os
import re
import subprocess
import time

import requests

import config
import licences

MAX_HOPS = 4
NASA_SKIP = re.compile(r"\blogo\b|\binsignia\b|\bmeatball\b|\bemblem\b", re.I)

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "StoryStudio/1.0 (history documentary channel; footage lookup)"}
MAX_BYTES = 80_000_000
MIN_DURATION, SECONDS = 4.0, 6.0
MAX_QUERIES, TIMEOUT = 8, 15
STOP = {"the", "and", "ii", "iii", "of", "in", "a", "an"}


def licence_ok(name: str) -> bool:
    """The studio's one licence rule (licences.py): public domain, CC0, CC BY, CC BY-SA, NASA media, Pixabay Content License; never non-commercial, no-derivatives or all rights reserved."""
    return licences.accepted(name)


def _tokens(anchors: list[str]) -> set[str]:
    return {t for a in anchors for t in re.findall(r"[a-z]{4,}", str(a).lower()) if t not in STOP}


def candidates(query: str, anchors: list[str], get=requests.get) -> list[dict]:
    """Free, relevant, sensible-sized video files for a query, public-domain ones first. A network failure finds nothing."""
    try:
        r = get(API, headers=UA, timeout=TIMEOUT, params={"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12, "gsrsearch": f"filetype:video {query}",
                                                          "prop": "imageinfo", "iiprop": "url|size|mediatype|extmetadata|duration"})
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages", {}).values()
    except (requests.RequestException, ValueError, AttributeError):
        return []
    want, out = _tokens(anchors), []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        lic = (md.get("LicenseShortName") or {}).get("value", "")
        title = str(p.get("title", "")).removeprefix("File:")
        hay = " ".join([title, (md.get("Categories") or {}).get("value", ""), (md.get("ImageDescription") or {}).get("value", "")]).lower().replace("_", " ")
        if (ii.get("mediatype") != "VIDEO" or not licence_ok(lic) or int(ii.get("size") or 0) > MAX_BYTES or float(ii.get("duration") or 0) < MIN_DURATION
                or not any(t in hay for t in want)):
            continue
        out.append({"title": title, "url": ii.get("url"), "license": lic, "page": ii.get("descriptionurl", ""), "duration": float(ii.get("duration") or 0), "size": int(ii.get("size") or 0)})
    out.sort(key=lambda c: 0 if re.search(r"public domain|cc0|^pd", c["license"], re.I) else 1)
    return out


def _relevant(text: str, anchors: list[str]) -> bool:
    hay = str(text or "").lower().replace("_", " ")
    return any(t in hay for t in _tokens(anchors))


def nasa_candidates(query: str, anchors: list[str], get=requests.get) -> list[dict]:
    """NASA videos whose own title names one of the film's anchors; never one about a logo or insignia. NASA gives no length or size up front: both are checked at download."""
    import openmedia

    try:
        items = openmedia.nasa(query, "video", 6, get)
    except (requests.RequestException, RuntimeError, ValueError, KeyError, AttributeError):
        return []
    out = []
    for it in items:
        title = str(it.get("title") or "")
        if not it.get("url") or NASA_SKIP.search(title) or not _relevant(title, anchors) or not licence_ok(it.get("licence", "")):
            continue
        out.append({"title": title, "url": it["url"], "license": it["licence"], "page": it.get("page", ""), "duration": 0.0, "size": 0,
                    "source": "NASA Image and Video Library", "credit": it.get("credit") or "NASA"})
    return out


def pixabay_candidates(query: str, anchors: list[str], get=requests.get) -> list[dict]:
    """Pixabay videos whose own tags name one of the film's anchors, of a sensible length. Nothing without a key; Pixabay's own rule of 100 requests a minute and a 24 hour cache is kept by pixabay.py."""
    import pixabay

    if not pixabay.key():
        return []
    try:
        rows = pixabay.search_videos(query, 6, get)
    except (requests.RequestException, RuntimeError, ValueError, KeyError, AttributeError):
        return []
    lic = "Pixabay Content License"
    out = []
    for r in rows:
        secs = float(r.get("seconds") or 0)
        if not r.get("url") or secs < MIN_DURATION or int(r.get("size") or 0) > MAX_BYTES or not _relevant(r.get("tags", ""), anchors) or not licence_ok(lic):
            continue
        out.append({"title": f"Pixabay video {r.get('id')} ({r.get('tags', '')})", "url": r["url"], "license": lic, "page": r.get("page", ""), "duration": secs,
                    "size": int(r.get("size") or 0), "source": "Pixabay", "credit": r.get("credit") or f"Video via Pixabay ({r.get('page', '')})"})
    return out


def all_candidates(query: str, anchors: list[str], get=requests.get) -> list[dict]:
    """Commons first (public domain first within it), then NASA, then Pixabay: the order of licence preference in licences.PREFERENCE."""
    out, seen = [], set()
    for source in (candidates, nasa_candidates, pixabay_candidates):
        for c in source(query, anchors, get=get):
            if c["url"] not in seen:
                seen.add(c["url"])
                out.append(c)
    return out


def _open(url: str, get, resolve):
    """The response for a public https address, following at most MAX_HOPS redirects, each hop checked before it is fetched. Wikimedia's 429 is handled by the caller."""
    import realmedia
    from urllib.parse import urljoin

    for _ in range(MAX_HOPS + 1):
        if not realmedia._public_https(url, resolve):
            raise ValueError("not a public https address")
        r = get(url, headers={**UA, "Range": "bytes=0-"}, stream=True, timeout=60, allow_redirects=False)  # 11 Nov 2026: Wikimedia answers a plain GET of a video with 429 (from the server and from the PC) but a Range request with 206 and the whole file
        if getattr(r, "status_code", 200) in (301, 302, 303, 307, 308):
            url = urljoin(url, (getattr(r, "headers", {}) or {}).get("Location") or "")
            continue
        return r
    raise ValueError("too many redirects")


def _probe_seconds(path, run=subprocess.run) -> float:
    try:
        r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], check=True, capture_output=True, text=True, timeout=60)
        return float(str(r.stdout).strip() or 0)
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0.0


def credit_text(cand: dict) -> str:
    """The credit line stored beside a clip: what it is, where it is from, its licence and its address."""
    source = cand.get("source") or "Wikimedia Commons"
    if source == "Wikimedia Commons":
        return f"Footage: {cand['title']} (Wikimedia Commons, {cand['license']}, {cand['page']})"
    return f"Footage: {cand.get('credit') or cand['title']} ({source}, {cand['license']}, {cand['page']})"


def fetch_segment(cand: dict, dest, get=requests.get, run=subprocess.run, sleep=time.sleep, resolve=None, probe=_probe_seconds):
    """A silent six-second clip of the candidate in `dest` (an mp4 in the film's size), its credit beside it, or None. Cached: a file that exists is reused."""
    import render
    from pathlib import Path

    dest = Path(dest)
    if dest.exists():
        return dest
    if int(cand.get("size") or 0) > MAX_BYTES:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw, out = dest.with_suffix(".dl"), dest.with_name(dest.stem + ".tmp.mp4")
    try:
        import realmedia

        resolve = resolve or realmedia.default_resolve
        for attempt in range(4):  # Wikimedia rate-limits downloads (HTTP 429: the Antikythera film got none of its clips that way): wait the pause it asks for, then try again
            r = _open(cand["url"], get, resolve)
            if getattr(r, "status_code", 200) != 429 or attempt == 3:
                break
            import footage

            sleep(footage._told_wait(r))
        r.raise_for_status()
        total = 0
        with open(raw, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("too large")
                f.write(chunk)
        length = float(cand.get("duration") or 0) or probe(raw, run=run)  # NASA gives no length up front
        if length < MIN_DURATION:
            raise ValueError("too short to cut a shot from")
        offset = max(0.0, min(length * 0.2, length - SECONDS))
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.2f}", "-i", str(raw), "-t", str(SECONDS), "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
             *render._venc("23", "veryfast"), str(out)], check=True, capture_output=True, timeout=300)
        os.replace(out, dest)
        dest.with_suffix(".txt").write_text(credit_text(cand))
        return dest
    except Exception:
        dest.unlink(missing_ok=True)
        dest.with_suffix(".txt").unlink(missing_ok=True)
        return None
    finally:
        raw.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def for_film(data: dict, clips: list, credits: list, count: int, flat=(), search=all_candidates, fetch=fetch_segment, credit_of=None, get=requests.get) -> tuple[list, list, dict]:
    """(clips, credits, stats): up to `count` scenes get a real clip. The input lists are not changed; any failure leaves the scenes as they were."""
    stats = {"asked": count, "used": 0, "queries": 0, "found": 0}
    out, credits = list(clips), list(credits)
    if count <= 0:
        return out, credits, stats
    try:
        import footage

        credit_of = credit_of or footage.credit_for
        anchors = [str(a) for a in (data.get("anchors") or [])]
        pool, seen = [], set()
        for a in anchors:
            if stats["queries"] >= MAX_QUERIES or len(pool) >= count * 2:
                break
            stats["queries"] += 1
            for c in search(a, anchors, get=get):
                if c["title"] not in seen:
                    seen.add(c["title"])
                    pool.append(c)
        stats["found"] = len(pool)
        taken = set(flat) | {int(i) for i in (data.get("animate_scenes") or [])}
        eligible = [i for i in range(1, len(out)) if i not in taken]
        picked = []
        for c in pool:
            if len(picked) >= count:
                break
            key = c["title"] if (c.get("source") or "Wikimedia Commons") == "Wikimedia Commons" else c["url"]  # Commons clips keep their old cache names
            path = fetch(c, config.CACHE / "real" / f"real-{hashlib.md5(key.encode()).hexdigest()[:12]}.mp4", get=get)
            if path:
                picked.append(path)
        if picked and eligible:
            step = len(eligible) / len(picked)
            for j, path in enumerate(picked):
                i = eligible[min(len(eligible) - 1, int(step * (j + 0.5)))]
                out[i] = path
                line = credit_of(path)
                if line and line not in credits:
                    credits.append(line)
                stats["used"] += 1
    except Exception:  # real footage is a bonus: a failure never stops a film
        return list(clips), list(credits), {**stats, "used": 0}
    return out, credits, stats
