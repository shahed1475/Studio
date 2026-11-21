"""Blender as a production component of a video (20 Nov 2026, owner's order: "Blender must be a real production component").

What it adds, and only where it is true to the narration:
- a GLOBE: a moving clip from space down to the story's place, from the coordinates of the video's own source article on Wikipedia (never guessed), with a marker
  and the article's name on it. One per video, never on the opening lines (the hook keeps the strongest picture), on the first line that names the place, else on
  the first line of the second chapter. NASA Blue Marble (public domain) on the planet.
- ENVIRONMENT stills with an exact depth map (so parallax.py moves them with the real depth): desert dunes, a stone circle, a Greco-Roman colonnade or open sea, only on a
  line whose own words name that kind of place (whole words, a fixed list, no model). Never on a line whose picture is meant to show a person, never next to another
  Blender scene, at most one per chapter and a few per video.
Everything renders headless on the CPU (Cycles) through ccrender.py; a scene that fails is recorded and the line keeps its usual picture: a video is never stopped by
Blender. What was rendered, how long it took and what failed goes into the video's record (`blender`). The night template is not used automatically: its CC0 night sky
holds a bright point of light on the horizon that may be modern."""
import re
import time
from pathlib import Path

TEMPLATES = {  # the words in a line (its text or its picture search words) that make this scene a true picture of what is said
    "dunes": ("desert", "deserts", "dune", "dunes", "sand sea", "sahara", "oasis", "caravan", "caravans"),
    "stones": ("standing stone", "standing stones", "stone circle", "stone circles", "megalith", "megaliths", "megalithic", "menhir", "menhirs", "dolmen", "henge", "monolith"),
    "temple": ("colonnade", "colonnades", "acropolis", "parthenon", "agora", "roman forum", "greek temple", "roman temple", "marble columns"),
    "sea": ("open sea", "the sea", "the ocean", "ocean", "voyage", "voyages", "sailed", "sailing", "shipwreck", "across the sea", "crossed the sea"),
}
MAX_STILLS = {"doc": 6, "short": 1}
HOOK_LINES = {"doc": 2, "short": 1}
GLOBE_MAX_S = 16.0  # a longer line holds the last frame (the place itself) for the rest
CREDIT_STILL = "3D scene rendered in Blender by the studio (drawn by code (original work)); skies and textures: Poly Haven, CC0"
CREDIT_GLOBE = "3D globe rendered in Blender by the studio; Earth picture: NASA Blue Marble (NASA Earth Observatory), public domain"


def match(line: dict) -> str | None:
    """The environment template whose words this line names, or None."""
    text = f" {line.get('text', '')} {line.get('visual', '')} ".lower()
    for name, words in TEMPLATES.items():
        if any(re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text) for w in words):
            return name
    return None


PERSON = re.compile(r"\b(king|queen|emperor|empress|pharaoh|prince|princess|priest|priestess|monk|nun|warrior|soldiers?|general|sultan|chief|ruler|portrait|face|"
                    r"man|men|woman|women|boy|girl|child|children|people|crowd|he|she|his|her)\b", re.I)


def person_scene(line: dict) -> bool:
    """True when the line's picture is meant to show a person (its picture search words, or a portrait or face in its text): an empty 3D place would not be its picture."""
    return bool(PERSON.search(str(line.get("visual", "")))) or bool(re.search(r"\b(portrait|face)\b", str(line.get("text", "")), re.I))


def source_titles(data: dict) -> list[str]:
    """The titles of the video's Wikipedia sources in order ("Wikipedia: Hampi (CC BY-SA 4.0), retold in our own words" -> "Hampi")."""
    out = []
    for s in data.get("sources") or []:
        m = re.match(r"\s*Wikipedia:\s*(.+?)\s*\(CC BY-SA", str(s))
        if m and m.group(1).strip() not in out:
            out.append(m.group(1).strip())
    return out


def source_title(data: dict) -> str:
    """The source article the globe is about: the first of the video's Wikipedia sources that has coordinates (20 Nov 2026: "Seven Sleepers" is a legend with
    none, its second source "Cave of the Seven Sleepers" has the place), else the first source, else ''. The answer is kept in the record, so the plan and the
    label agree and the lookup is made once."""
    if data.get("_place_title") is not None:
        return data["_place_title"]
    titles = source_titles(data)
    pick = next((t for t in titles if coordinates(t)), titles[0] if titles else "")
    data["_place_title"] = pick
    return pick


def coordinates(title: str) -> tuple[float, float] | None:
    """The primary coordinates of a Wikipedia article (the article's own record), or None: no coordinates, no globe."""
    if not title:
        return None
    try:
        import wikipedia

        pages = (wikipedia._api({"action": "query", "prop": "coordinates", "titles": title, "coprimary": "primary", "redirects": 1}).get("query") or {}).get("pages") or {}
        for p in pages.values():
            for c in p.get("coordinates") or []:
                lat, lon = float(c["lat"]), float(c["lon"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
    except Exception:
        return None
    return None


def place_candidates(data: dict) -> list[tuple[str, tuple[float, float]]]:
    """(name, coordinates) for the video's source articles and named places (its anchors) whose own Wikipedia article has primary coordinates. Names in brackets are
    dropped from the label; people and ideas have no coordinates and so never become a pin."""
    seen, out = set(), []
    for n in [*source_titles(data), *(data.get("anchors") or [])]:
        name = re.sub(r"\s*\(.*?\)", "", str(n)).strip()
        if len(name) < 4 or name.lower() in seen:
            continue
        seen.add(name.lower())
        c = coordinates(str(n))
        if c:
            out.append((name, c))
    return out


def _chapter_of(i: int, chapters: list[dict]) -> int:
    k = 0
    for n, c in enumerate(chapters or []):
        if int(c.get("start_line", 0)) <= i:
            k = n
    return k


def plan(data: dict, fmt: str = "doc", coords: tuple[float, float] | None = None) -> list[dict]:
    """Which lines get a Blender scene: [{"line", "kind": "globe" or "still", "scene", "params"}], in line order."""
    lines, chapters = data.get("lines") or [], data.get("chapters") or []
    hook = HOOK_LINES.get(fmt, 2)
    out: list[dict] = []
    titles = source_titles(data)
    main_place = bool(coords) and bool(titles) and source_title(data) == titles[0]  # the film's own subject is a place: the whole film is about where the pin is
    if main_place and len(lines) > hook:
        label = re.sub(r"\s*\(.*?\)", "", source_title(data)).strip()[:30]
        names = [n.lower() for n in [label, *(data.get("anchors") or [])] if n and len(n) >= 4]
        first_third = max(hook + 1, len(lines) // 3)
        named = [i for i in range(hook, first_third) if any(n in lines[i].get("text", "").lower() for n in names)]
        second = int(chapters[1]["start_line"]) if len(chapters) > 1 else hook
        line = named[0] if named else max(hook, min(second, len(lines) - 1))
        out.append({"line": line, "kind": "globe", "scene": "globe", "params": {"lat": round(coords[0], 4), "lon": round(coords[1], 4), "label": label}})
    elif len(lines) > hook:  # otherwise only a line that names a place gets that place's globe (20 Nov 2026: the second source of "Seven Sleepers" is the cave near Amman,
        best = None          # while the legend itself is told at Ephesus: a Jordan pin on an Ephesus line would contradict the narration)
        for name, c in place_candidates(data):
            hit = next((i for i in range(hook, len(lines)) if re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", lines[i].get("text", "").lower())), None)
            if hit is not None and (best is None or hit < best[0]):
                best = (hit, name, c)
        if best:
            out.append({"line": best[0], "kind": "globe", "scene": "globe", "params": {"lat": round(best[2][0], 4), "lon": round(best[2][1], 4), "label": best[1][:30]}})
    taken = {p["line"] for p in out}
    chapters_used: set[int] = set()
    stills = 0
    for i, l in enumerate(lines):
        if stills >= MAX_STILLS.get(fmt, 0):
            break
        if i < hook or person_scene(l) or any(abs(i - j) <= 1 for j in taken):
            continue
        ch = _chapter_of(i, chapters)
        if ch in chapters_used:
            continue
        t = match(l)
        if t:
            out.append({"line": i, "kind": "still", "scene": t, "params": {"seed": 3 + i % 7}})
            taken.add(i)
            chapters_used.add(ch)
            stills += 1
    return sorted(out, key=lambda p: p["line"])


def render(planned: list[dict], durations: list[float], size: tuple[int, int] = (1920, 1080), renderer=None) -> tuple[dict, dict]:
    """({line: (path, credit)}, stats). A globe is a moving clip as long as its line allows (the renderer slows a clip by at most 1.25); a still comes with its exact depth map.
    A failure is recorded and that line keeps its usual picture."""
    if renderer is None:
        import ccrender as renderer
    got: dict[int, tuple[Path, str]] = {}
    stats = {"version": renderer.version() if planned else "", "engine": "Cycles on the CPU, headless", "scenes": [], "failed": []}
    for p in planned:
        t0 = time.monotonic()
        try:
            if p["kind"] == "globe":
                secs = min(GLOBE_MAX_S, max(4.0, durations[p["line"]] / 1.25 + 0.3))
                path, credit = Path(renderer.render_clip({"scene": "globe", "params": p["params"], "samples": 4}, secs, size)), CREDIT_GLOBE
            else:
                path, credit = Path(renderer.render({"scene": p["scene"], "params": p["params"], "width": size[0], "height": size[1], "samples": 32})), CREDIT_STILL
            got[p["line"]] = (path, credit)
            stats["scenes"].append({"line": p["line"], "kind": p["kind"], "scene": p["scene"], "file": path.name, "seconds": round(time.monotonic() - t0, 1),
                                    **({"place": p["params"].get("label"), "lat": p["params"]["lat"], "lon": p["params"]["lon"]} if p["kind"] == "globe" else {})})
        except Exception as e:
            stats["failed"].append({"line": p["line"], "scene": p["scene"], "reason": f"{type(e).__name__}: {str(e)[:200]}"})
    return got, stats


def place(clips: list, credits: list[str], got: dict) -> tuple[list, list[str]]:
    """The video's scene list with each rendered Blender scene in its line's place, and its credit line once in the credits."""
    clips = list(clips)
    credits = list(credits)
    for i, (path, credit) in sorted(got.items()):
        if 0 <= i < len(clips):
            clips[i] = path
            if credit not in credits:
                credits.append(credit)
    return clips, credits
