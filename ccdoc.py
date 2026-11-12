"""A documentary made in a Claude Code session (1 Nov 2026): a spec with the script, the sources and a picture for every line goes in; a held draft comes out. No language-model call is made here.

The 16:9 sister of ccbuild.py (which makes 9:16 Shorts). The script and its evidence are written by the person (or assistant) who builds the spec; this module refuses a spec that breaks
the studio's rules, then hands the documentary producer (`run._produce_doc`) the pictures, the chapters and the motion switches, so the voice, word-timed captions, free 2.5D camera
motion, chapter cards, date badges, subscribe pop-up, corner mark, loudness and chapter list in the description are the studio's own. Pictures come from files made elsewhere for free
(tools/zimage_batch.py, ccrender.py). A claim counts only when a source passage was found in the saved page it names (`numbershort.passage_in_page`); the ledger names that source.
The result is held and unapproved: only the owner releases it. Usage: python ccdoc.py docs/studio/ronaldo/doc.json [--check] [--mix] (--mix: Z-Image versions of the scenes that have one)."""
import json
import re
import sys
from pathlib import Path

import config
import ledger
import numbershort
import records
import reviewer
import run

FORBIDDEN = ("video", "clips", "footage", "source_video", "youtube_url", "download", "images", "image")  # no third-party footage or pictures, ever (CLAUDE.md B and D)
MAX_TITLE, MIN_LINES, MIN_WORDS, MAX_WORDS, HOOK_WORDS = 70, 8, 400, 1500, 14
CREDIT = "AI-generated illustrations (FLUX.1 schnell and Z-Image-Turbo, Apache-2.0), drawn on the owner's own computer; not photographs. Voice: synthetic."
OUTRO = re.compile(r"thanks? for watching|like and subscribe|subscribe|see you (next|in the)|until next time", re.I)  # a documentary ends on its story: the pop-ups invite the subscribe


def _meta(spec: dict) -> dict:
    return {"format": "doc", "title": spec.get("title", ""), "sources": numbershort.mark_checked(spec.get("sources") or []),
            "lines": [{"text": l.get("text", ""), "visual": ""} for l in spec.get("lines") or []]}


def validate(spec: dict, base: Path | None = None) -> tuple[list[str], list[str]]:
    """(errors, warnings). An error stops the build."""
    e, w = [], []
    for k in spec:
        if k.lower() in FORBIDDEN:
            e.append(f"'{k}': a documentary here takes no third-party footage, picture or download")
    for real, said in (spec.get("say") or {}).items():  # how a name is SAID in this film: one word, so the captions (matched to the script word by word) keep their count
        if not isinstance(said, str) or len(said.split()) != 1 or len(real.split()) != 1:
            e.append(f"say '{real}': a respelling must be one word for one word, or the captions would drift")
    title = spec.get("title", "")
    if not title or len(title) > MAX_TITLE:
        e.append(f"the title must be 1 to {MAX_TITLE} characters")
    lines = spec.get("lines") or []
    if len(lines) < MIN_LINES:
        e.append(f"a documentary needs at least {MIN_LINES} lines, this has {len(lines)}")
        return e, w
    words = sum(len((l.get("text") or "").split()) for l in lines)
    if words < MIN_WORDS:
        e.append(f"{words} words is too short for a documentary (need {MIN_WORDS})")
    if words > MAX_WORDS:
        w.append(f"{words} words will run past 10 minutes")
    first = (lines[0].get("text") or "").strip()
    if not first.endswith("?") or len(first.split()) > HOOK_WORDS:
        e.append(f"line 1 must be a question of {HOOK_WORDS} words or fewer")
    if OUTRO.search(lines[-1].get("text") or ""):
        w.append("the last line reads like an outro: a documentary here ends on its story (the subscribe pop-up does the inviting)")
    srcs = {s.get("id"): s for s in spec.get("sources") or []}
    if len(srcs) < 2:
        e.append("at least two sources are required")
    for sid, s in srcs.items():
        if not (str(s.get("url", "")).startswith("https://") and s.get("title") and s.get("read") and (s.get("passage") or "").strip()):
            e.append(f"source '{sid}' needs an https address, a title, a passage and the date it was read")
        elif not numbershort.passage_in_page(s):
            e.append(f"the passage of source '{sid}' is not in the saved page {s.get('file')}")
    for i, l in enumerate(lines):
        if not (l.get("text") or "").strip():
            e.append(f"line {i + 1} has no text")
        if not l.get("picture"):
            e.append(f"line {i + 1} needs a picture")
        for sid in l.get("src") or []:
            if sid not in srcs:
                e.append(f"line {i + 1} names an unknown source '{sid}'")
        if i and i < len(lines) - 1 and not l.get("src"):
            w.append(f"line {i + 1} names no source")
    for r in ledger.build(_meta(spec), ""):
        if r["verification_status"] in ("UNVERIFIED", "CONFLICTING"):
            e.append(f"claim '{r['claim_text']}' on line {r['line'] + 1} is {r['verification_status']}: give it a source passage or take it out")
    if len({l.get("picture") for l in lines}) < max(4, len(lines) // 4):
        w.append("many lines share the same few pictures")
    return e, w


def chapters(spec: dict) -> list[dict]:
    out = []
    for i, l in enumerate(spec["lines"]):
        c = l.get("chapter") or ""
        if c and (not out or out[-1]["title"] != c):
            out.append({"title": c, "start_line": i})
    return out or [{"title": spec["title"], "start_line": 0}]


def load_jobs(base: Path) -> dict:
    """Every picture job from every pictures*.json beside the spec, by id."""
    return {j["id"]: j for f in sorted(base.glob("pictures*.json")) for j in json.loads(f.read_text())}


def mixed(spec: dict, jobs: dict) -> dict:
    """A copy of the spec where a scene that has a Z-Image version (id + "z") uses it: the hook and the key scenes drawn with the slower, more photographic model."""
    return {**spec, "lines": [{**l, "picture": l["picture"] + "z" if l["picture"] + "z" in jobs else l["picture"]} for l in spec["lines"]]}


def resolve(pic: str, base: Path, jobs: dict) -> Path:
    if pic in jobs:
        if jobs[pic].get("provider") == "cloudflare":
            import tools.cloudflare_batch as cb

            return cb.path_for(jobs[pic])
        if jobs[pic].get("provider") == "pollinations":
            import tools.pollinations_batch as pb

            return pb.path_for(jobs[pic])
        if jobs[pic].get("model") == "flux":
            import tools.flux_batch as fb

            return fb.path_for(jobs[pic])
        import tools.zimage_batch as zb

        return zb.path_for(jobs[pic])
    p = Path(pic)
    return p if p.is_absolute() else base / p


def source_lines(spec: dict) -> list[str]:
    """One "title: address" line per source PAGE (a page that supplies several passages is listed once: YouTube rejects a description over 5,000 bytes)."""
    return list(dict.fromkeys(f"{s['title']}: {s['url']}" for s in spec["sources"]))


def grade_pictures(pics: list, strength: float = 1.0) -> list:
    """The cinematic grade (grade.py) on the studio's own pictures (in cache/cc); an archive picture or any other file is returned untouched."""
    import animate
    import grade

    return [str(grade.graded(p, strength)) if strength and animate.own_picture(p) else str(p) for p in pics]


def build(spec: dict, base: Path, mix: bool = False) -> Path:
    """The held draft's folder. Raises ValueError for a spec that breaks the rules; the producer stops with SystemExit when a picture is not drawn yet."""
    errors, warns = validate(spec, base)
    if errors:
        raise ValueError("; ".join(errors))
    jobs = load_jobs(base)
    if mix:
        spec = {**mixed(spec, jobs), "_mix": True}
    pics = [str(resolve(l["picture"], base, jobs)) for l in spec["lines"]]
    if spec.get("grade") == "cinematic":  # owner, 1 Nov 2026: a film colour grade, not the over-saturated AI look
        pics = grade_pictures(pics, float(spec.get("grade_strength", 1.0)))
    wiki = [s for s in spec["sources"] if "wikipedia.org" in s["url"]]
    licence = "".join(f"\n\nText: Wikipedia, {s['title'].split(' - ')[0]} (CC BY-SA 4.0), retold in our own words." for s in wiki[:1])
    data = {"topic": spec.get("topic") or spec["title"], "format": "doc", "kind": spec.get("kind", "person"), "title": spec["title"], "voice_style": spec.get("voice_style"),
            "lines": [{"text": l["text"], "visual": l.get("visual", "")} for l in spec["lines"]], "chapters": chapters(spec), "anchors": [],
            "description": spec["description"].rstrip() + licence, "tags": spec.get("tags", []), "sources": source_lines(spec),
            "parallax": True, "graphics": True, "art_style": "local",
            "subscribe_pop": spec.get("subscribe_pop", False), "brand_mark": spec.get("brand_mark", False),  # owner, 1 Nov 2026: no logo in a video (the pop-up carries the Gloamtale mark)
            "local_pictures": pics, "local_credits": [spec.get("ai_credit", CREDIT), *spec.get("credits", [])]}
    data = {k: v for k, v in data.items() if v is not None}
    with numbershort.respelled(spec.get("say")):  # only for the length of this build; the shared list (tts.PRONUNCIATION) is put back
        folder = run._produce_doc(data)
    meta = records.read(folder)
    meta.update({"sources": numbershort.mark_checked(spec["sources"]), "grounded": True, "approved": False, "hold": True, "built_by": "ccdoc", "script_model": "claude-code-session", "look": "mixed" if mix else "flux",
                 "hold_reason": "made in a Claude Code session by ccdoc.py: the owner watches it and releases it", "warnings": warns})
    records.save(folder, meta)
    ledger.write(folder, meta, reviewer.source_text(meta))
    thumbs(folder, spec, base, jobs)
    return folder


def thumbs(folder: Path, spec: dict, base: Path, jobs: dict) -> list:
    """Thumbnail candidates drawn with Pillow (thumbstyle.py: no model call) on one of the film's own pictures, each in a different composition, checked against the title."""
    if not spec.get("thumb_picture"):
        return []
    import thumbstyle

    meta = records.read(folder)
    pid = spec["thumb_picture"]
    pic = resolve(pid + "z" if spec.get("_mix") and pid + "z" in jobs else pid, base, jobs)
    hooks = [h.upper() for h in spec.get("thumb_hooks") or []] or [spec["title"].split(":")[0].upper()]
    made = thumbstyle.variants(folder, meta, [pic], hooks[0], kind=meta.get("kind"), recent=thumbstyle.recent_archetypes(config.OUT, exclude=folder), title=meta.get("title", ""), hooks=hooks)
    if not made:
        return []
    names = [v["file"] for v in made]

    def apply(d):
        d["thumb_hook"], d["thumbnails"], d["thumbnail"] = made[0]["hook"], names, names[0]
        d["thumb_style"] = made[0]["archetype"]
        d["thumb_variants"] = [{"file": v["file"], "archetype": v["archetype"], "hook": v["hook"]} for v in made]
        d["thumb_art"] = "ai"

    records.update(folder, apply)
    return names


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    path = Path(argv[0]).resolve()
    spec = json.loads(path.read_text())
    errors, warns = validate(spec, path.parent)
    for x in warns:
        print("warning:", x)
    if errors:
        print("REFUSED:\n- " + "\n- ".join(errors))
        return 1
    if "--check" in argv:
        print("spec ok")
        return 0
    print("Held draft:", build(spec, path.parent, mix="--mix" in argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
