"""Free footage: Pexels stock video when a key is set, otherwise public-domain archive images from Wikimedia Commons."""
import hashlib
import json
import re
import time
from pathlib import Path

import requests

import archive_video
import config
import licences
import wikipedia


def clip_for(query: str) -> Path | None:
    if not query:
        return None
    if not config.PEXELS_KEY:  # no stock-video key: public-domain film from the Internet Archive, else an archive image
        if config.ARCHIVE_VIDEO:
            clip = archive_video.fetch_clip(query)
            if clip:
                return clip
        hit = image_for(query)
        return hit[0] if hit else None
    config.CACHE.mkdir(exist_ok=True)
    dest = config.CACHE / f"{hashlib.md5(query.lower().encode()).hexdigest()[:12]}.mp4"
    if dest.exists():
        return dest
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_KEY},
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 5},
            timeout=30,
        )
        r.raise_for_status()
        for v in r.json().get("videos", []):
            files = [f for f in v["video_files"] if f.get("file_type") == "video/mp4" and f.get("height", 0) >= 1280]
            if not files:
                continue
            best = min(files, key=lambda f: f["height"])
            data = requests.get(best["link"], timeout=120)
            data.raise_for_status()
            dest.write_bytes(data.content)
            return dest
    except requests.RequestException as e:
        print(f"  footage lookup failed for '{query}': {e}")
    return None


def credit_for(path: Path) -> str | None:
    """Credit line stored beside a cached clip or image, if any."""
    f = Path(path).with_suffix(".txt")
    return f.read_text() if f.exists() else None


def credit_lines(credits: list[str], assets=()) -> list[str]:
    """The credit lines the description carries (compliance.final_description): every item whose licence needs a credit (CC BY, CC BY-SA, NASA media, Pixabay) in full, a count of the
    public-domain and CC0 items (their address and licence stay in the video's record) and the AI-art label. Keeps the description inside YouTube's size limit.
    A credit needs its line when its text names a credit-needing licence OR its stored licence (`assets`, from the library's own field) does: words in a title never lower that."""
    stored = {a.get("credit"): a.get("licence") for a in assets if isinstance(a, dict)}
    unique = list(dict.fromkeys(c for c in credits if c))
    needed = [c for c in unique if licences.needs_credit(c) or licences.needs_credit(stored.get(c, ""))]
    ai = [c for c in unique if c not in needed and "ai-generated" in c.lower()]
    others = [c for c in unique if c not in needed and c not in ai]
    lines = list(needed)
    if others:
        plural = "s" if len(others) != 1 else ""
        lines.append(f"{len(others)} more real picture{plural} or clip{plural}: public domain or CC0 (address and licence kept in the video's record).")
    return lines + ai


def collect_credits(clips: list) -> list[str]:
    out: list[str] = []
    for c in clips:
        line = credit_for(c) if c else None
        if line and line not in out:
            out.append(line)
    return out


def enough_footage(clips: list, min_ratio: float = 0.6) -> bool:
    """A Short where most scenes have no picture is just coloured screens: not worth publishing."""
    return bool(clips) and sum(c is not None for c in clips) / len(clips) >= min_ratio


_PD = ("public domain", "cc0", "pd-", "pd ")


JUDGE_CACHE = config.ROOT / "data" / "image_judge.json"


def cached_judge(topic: str, ask):
    """Wrap a model check ("which of these picture titles show the subject?") so every title is judged once per topic.
    ask(titles) returns the titles to keep and may raise; a failed check keeps everything and is not remembered."""
    key = hashlib.md5(topic.lower().encode()).hexdigest()[:10]

    def judge(titles: list[str]) -> list[str]:
        try:
            cache = json.loads(JUDGE_CACHE.read_text())
        except (OSError, ValueError):
            cache = {}
        known = cache.get(key, {})
        new = [t for t in dict.fromkeys(titles) if t not in known]
        if new:
            try:
                kept = set(ask(new))
            except Exception:
                return list(titles)
            known.update({t: t in kept for t in new})
            cache[key] = known
            JUDGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            JUDGE_CACHE.write_text(json.dumps(cache))
        return [t for t in titles if known.get(t)]

    return judge


PERSON_PHOTO = re.compile(r"\b(portrait|headshot|selfie|bust of|photo of)\b|\b(professor|prof|dr|mr|mrs|ms)\b\.?", re.I)
PERSON_WORDS = {"portrait", "headshot", "selfie", "professor", "photo", "image", "picture", "jpeg"}


def unrelated_portrait(title: str, query: str) -> bool:
    """A photo of a real, identifiable person is shown only for a scene about that person: it names the person in its title and the scene's own search words do. Anywhere else it would
    suggest that person has to do with the line (found on the Antikythera Short: a researcher's face over a line about Corinth)."""
    if not PERSON_PHOTO.search(str(title)):
        return False
    names = {w for w in re.findall(r"[a-z]{5,}", str(title).lower()) if w not in PERSON_WORDS}
    return not (names & set(re.findall(r"[a-z]{5,}", str(query).lower())))


def image_relevant(title: str, categories: str, anchors: list[str]) -> bool:
    """An image only counts when its title or Commons categories name the subject (no anchors known: no filter)."""
    if not anchors:
        return True
    text = f"{title} {categories}".lower()
    return any(a.lower() in text for a in anchors)


def _told_wait(r, cap: float = 45.0) -> float:
    """Seconds Wikimedia asked us to wait after an HTTP 429 (Retry-After), at most `cap`."""
    try:
        return min(max(float((getattr(r, "headers", None) or {}).get("Retry-After", 5)), 1.0), cap)
    except (TypeError, ValueError):
        return 5.0


def _download(info: dict, page: dict, meta: dict, key: str) -> tuple[Path, str] | None:
    dest, credit_file = config.CACHE / f"{key}.jpg", config.CACHE / f"{key}.txt"
    if dest.exists() and credit_file.exists():
        return dest, credit_file.read_text()
    img = None
    for wait in (2, 8, 20):  # the image server rate-limits too
        time.sleep(wait)
        img = requests.get(info["thumburl"], headers=wikipedia.UA, timeout=60)
        if img.status_code != 429:
            break
        time.sleep(_told_wait(img))
    if img is None or not img.ok:
        return None
    dest.write_bytes(img.content)
    credit = f"{page.get('title', '').removeprefix('File:')} (Wikimedia Commons, {meta['LicenseShortName']['value']})"
    credit_file.write_text(credit)
    return dest, credit


def images_for(query: str, anchors: list[str] | None = None, limit: int = 1, skip=(), judge=None) -> list[tuple[Path, str]]:
    """Public-domain / CC0 images from Wikimedia Commons whose title or categories name the subject. [(file, credit)]."""
    if not query:
        return []
    config.CACHE.mkdir(exist_ok=True)
    anchors = anchors or []
    found: list[tuple[Path, str]] = []
    try:
        for attempt in range(4):  # Wikimedia rate-limits bursts (429): wait and retry
            time.sleep(1.2 + attempt * 4)
            r = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                headers=wikipedia.UA,
                params={
                    "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                    "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": 30, "prop": "imageinfo",
                    "iiprop": "url|extmetadata", "iiurlwidth": 1920,
                },
                timeout=30,
            )
            if r.status_code != 429:
                break
            time.sleep(_told_wait(r))  # the pause Wikimedia asks for, not a guess
        r.raise_for_status()
        cands = []
        for page in (r.json().get("query", {}).get("pages", {}) or {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "").lower()
            if not info.get("thumburl") or not lic.startswith(_PD):
                continue
            title = page.get("title", "").removeprefix("File:")
            cats = meta.get("Categories", {}).get("value", "") + " " + re.sub(r"<[^>]+>", " ", meta.get("ImageDescription", {}).get("value", ""))
            if image_relevant(title, cats, anchors) and not unrelated_portrait(title, query):
                cands.append((title, page, info, meta))
        if judge and cands:  # a name match is not enough: "Apollo" also names a moon mission
            labels = {c[0]: f"{c[0]} | {' '.join(re.sub(r'<[^>]+>', ' ', c[3].get('Categories', {}).get('value', '')).split())[:140]}" for c in cands}  # a bare file name can be a ride or a brand; the categories tell
            keep = set(judge(list(labels.values())))
            cands = [c for c in cands if labels[c[0]] in keep]
        for title, page, info, meta in cands:
            key = hashlib.md5(info["thumburl"].encode()).hexdigest()[:12]
            hit = _download(info, page, meta, key)
            if hit and hit[0] not in skip and hit[0] not in [f[0] for f in found]:
                found.append(hit)
            if len(found) >= limit:
                break
    except requests.RequestException as e:
        print(f"  image lookup failed for '{query}': {e}")
    return found


def image_for(query: str, anchors: list[str] | None = None) -> tuple[Path, str] | None:
    hits = images_for(query, anchors, 1)
    return hits[0] if hits else None


def scene_images(lines: list[dict], topic: str, anchors: list[str], pool_size: int = 10, judge=None, art=None, art_limit: int = 0, art_first: bool = False, force_art: set[str] | None = None,
                 finder=None) -> tuple[list, list[str], dict]:
    """One relevant image per scene: a specific search first, then unused images about the subject, then reuse.
    When no real picture is left, art(line) may draw one illustration (up to art_limit per video) instead of repeating a picture.
    art_first: skip the generic reserve of subject pictures (the usual source of a ruin or map that is not quite the place) and draw instead.
    force_art: narration lines whose picture was judged wrong: they are drawn whatever a search finds, outside the art cap (the cache makes a repeat free).
    finder (realmedia.Finder, off by default): after the Commons public-domain search, the other approved libraries and licences are tried before any picture is drawn.
    A scene only goes blank when nothing about the subject can be found at all."""
    used: list[Path] = []
    drawn = forced = 0
    credit: dict[Path, str] = {}
    pool: list[tuple[Path, str]] = []

    def look(q: str, limit: int, skip, wide: bool = False) -> list[tuple[Path, str]]:
        hits = images_for(q, anchors, limit, skip=skip, judge=judge)
        if finder is not None and len(hits) < limit:
            hits = hits + finder(q, anchors, limit - len(hits), skip=[*skip, *[h[0] for h in hits]], wide=wide)
        return hits

    for q in dict.fromkeys([topic, *anchors]):  # the subject itself: a reserve of on-topic images
        pool += [h for h in look(q, pool_size, [p for p, _ in pool], wide=True) if h[0] not in [p for p, _ in pool]]
    clips: list[Path | None] = []
    for l in lines:
        hit = None
        if art and l.get("text") in (force_art or ()):
            hit = art(l)
            forced += bool(hit)
        if not hit and l.get("visual"):
            hits = look(l["visual"], 1, used)
            hit = hits[0] if hits else None
        if not hit and art_first and art and drawn < art_limit:
            hit = art(l)
            drawn += bool(hit)
        if not hit:
            hit = next((h for h in pool if h[0] not in used), None)
        if not hit and art and drawn < art_limit:
            hit = art(l)
            drawn += bool(hit)
        if hit:
            if hit[0] not in used:
                used.append(hit[0])
                credit[hit[0]] = hit[1]
            clips.append(hit[0])
        elif used:  # everything on-topic was already shown: show the least recently used one again
            clips.append(used[len([c for c in clips if c]) % len(used)])
        else:
            clips.append(None)
    stats = {"scenes": len(lines), "unique": len(used), "missing": sum(c is None for c in clips), "drawn": drawn + forced}
    return clips, list(dict.fromkeys(credit[p] for p in used)), stats
