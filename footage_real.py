"""Real moving footage in a film (30 Oct 2026, owner's order: use real footage, make AI pictures only where needed).

Wikimedia Commons video only for now. A file is used when ALL of this holds: its licence is one the studio's own check accepts (public domain, CC0, CC BY, CC BY-SA, always with a credit line;
never non-commercial, no-derivatives or all-rights-reserved); its own title, categories or description name one of the film's anchors (a live probe on 30 Oct 2026 showed Commons search
returns dolphins for "Delphi" and a video game for "Egypt desert", so relevance is checked here and never assumed); it is a video of a sensible size and length. Six seconds are cut from it,
silent, in the film's picture size. They go on scenes that are not the hook scene, may not show people (parallax.flat_scenes) and were not chosen for an animated clip, spread over the film.
Whatever is not found stays an AI picture, so the number of real clips is "as many as truly fit, up to the count asked for", often few. Any failure leaves the scene as it was. Stock video
(Pexels) is not used: it needs the owner's key and its licence is not one the credit check accepts."""
import hashlib
import os
import re
import subprocess

import requests

import config

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "StoryStudio/1.0 (history documentary channel; footage lookup)"}
GOOD = re.compile(r"public domain|cc0|^pd\b|^pd-|cc[- ]by", re.I)
BAD = re.compile(r"\bnc\b|\bnd\b|-nc|-nd|non-?commercial|no derivatives|all rights|fair use", re.I)
MAX_BYTES = 80_000_000
MIN_DURATION, SECONDS = 4.0, 6.0
MAX_QUERIES, TIMEOUT = 8, 15
STOP = {"the", "and", "ii", "iii", "of", "in", "a", "an"}


def licence_ok(name: str) -> bool:
    name = str(name or "").strip()
    return bool(GOOD.search(name)) and not BAD.search(name)


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


def fetch_segment(cand: dict, dest, get=requests.get, run=subprocess.run):
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
        r = get(cand["url"], headers=UA, stream=True, timeout=60)
        r.raise_for_status()
        total = 0
        with open(raw, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("too large")
                f.write(chunk)
        offset = max(0.0, min(cand["duration"] * 0.2, cand["duration"] - SECONDS))
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.2f}", "-i", str(raw), "-t", str(SECONDS), "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
             *render._venc("23", "veryfast"), str(out)], check=True, capture_output=True, timeout=300)
        os.replace(out, dest)
        dest.with_suffix(".txt").write_text(f"Footage: {cand['title']} (Wikimedia Commons, {cand['license']}, {cand['page']})")
        return dest
    except Exception:
        dest.unlink(missing_ok=True)
        dest.with_suffix(".txt").unlink(missing_ok=True)
        return None
    finally:
        raw.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def for_film(data: dict, clips: list, credits: list, count: int, flat=(), search=candidates, fetch=fetch_segment, credit_of=None, get=requests.get) -> tuple[list, list, dict]:
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
            path = fetch(c, config.CACHE / "real" / f"real-{hashlib.md5(c['title'].encode()).hexdigest()[:12]}.mp4", get=get)
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
