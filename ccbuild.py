"""A Short made in a Claude Code session (1 Nov 2026): a spec with the script, the sources and the pictures goes in; a held draft comes out. No language-model call is made here.

The script and the evidence are written by the person (or assistant) who builds the spec; this module only refuses a spec that breaks the studio's rules, then does the same steps as
run._produce_short: voice and word-timed captions (edge-tts, free), the pictures fitted to 9:16, free 2.5D camera motion, the render, the Gloamtale subscribe pop-up and corner mark, the
claim ledger and a held record (`hold` true: only the owner releases it). Pictures come from files made elsewhere for free (tools/zimage_batch.py, ccrender.py): a line names its picture
by job id (docs/studio/<name>/pictures.json) or by path. Usage: python ccbuild.py docs/studio/flannan/short.json [--replace]."""
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

import config
import records

SIZE = (1080, 1920)
FORBIDDEN = ("video", "clips", "footage", "source_video", "youtube_url", "download")  # no third-party footage, ever (CLAUDE.md B and D)
STATUSES = {"VERIFIED", "PARTIALLY_VERIFIED", "CONFLICTING", "UNVERIFIED"}
MAX_TITLE, MAX_WORDS, HOOK_WORDS = 70, 150, 14
NORM = lambda t: re.sub(r"\s+", " ", t).strip()


def validate(spec: dict, base: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors stop the build."""
    e, w = [], []
    for k in FORBIDDEN:
        if k in spec:
            e.append(f"'{k}' is not allowed: a Short here uses no third-party footage")
    title = spec.get("title", "")
    if not title or len(title) > MAX_TITLE:
        e.append(f"the title must be 1 to {MAX_TITLE} characters")
    lines = spec.get("lines") or []
    if not 6 <= len(lines) <= 14:
        e.append("a Short needs 6 to 14 lines")
    else:
        words = sum(len(l["text"].split()) for l in lines)
        if words > MAX_WORDS:
            e.append(f"{words} words is too long for a Short (limit {MAX_WORDS})")
        if len(lines[0]["text"].split()) > HOOK_WORDS or not lines[0]["text"].rstrip().endswith("?"):
            e.append(f"line 1 must be a question of {HOOK_WORDS} words or fewer")
        if re.match(r"(?i)^(is|was|did|does|do|are|were|can|could|will|would|has|have|had)\b", lines[0]["text"].strip()):
            w.append("line 1 is a yes/no question; an open who/what/where/why/how question names the subject and hides the answer")
        if "subscribe" not in lines[-1]["text"].lower():
            e.append("the last line must invite the viewer to subscribe (YouTube has subscribers, not followers)")
        for i, l in enumerate(lines):
            if not l.get("text") or not l.get("picture"):
                e.append(f"line {i + 1} needs text and a picture")
    srcs = {s.get("id"): s for s in spec.get("sources") or []}
    if len(srcs) < 2:
        e.append("at least two sources are required")
    texts = {}
    for sid, s in srcs.items():
        if not (str(s.get("url", "")).startswith("https://") and s.get("title") and s.get("read")):
            e.append(f"source '{sid}' needs an https address, a title and the date it was read")
        f = base / s["file"] if s.get("file") else None
        if f and f.exists():
            texts[sid] = NORM(f.read_text())
        else:
            e.append(f"source '{sid}' has no saved text to check its passages against")
    claims = spec.get("claims") or []
    if not claims:
        e.append("the claim ledger is empty: every material claim needs a passage")
    for c in claims:
        if c.get("status") not in STATUSES:
            e.append(f"claim '{c.get('text', '')[:40]}' has no valid status")
        elif c["status"] == "VERIFIED" and (c.get("source") not in texts or NORM(c.get("passage", "")) not in texts[c["source"]]):
            e.append(f"claim '{c.get('text', '')[:40]}' is marked VERIFIED but its passage is not in the saved source text")
        if c["status"] in ("CONFLICTING", "UNVERIFIED"):
            e.append(f"claim '{c.get('text', '')[:40]}' is {c['status']}: resolve it or leave it out before building")
    if not spec.get("credits") or not any("AI" in c or "drawn" in c.lower() for c in spec["credits"]):
        w.append("credits should say the pictures are AI-generated or drawn")
    return e, w


def fit(src: Path, out: Path, flip: bool = False) -> Path:
    """The picture cover-fitted to 1080x1920 (Lanczos); the optional flip makes a second use of one picture look different."""
    im = Image.open(src).convert("RGB")
    if flip:
        im = ImageOps.mirror(im)
    ImageOps.fit(im, SIZE, Image.LANCZOS, centering=(0.5, 0.5)).save(out)
    return out


def load_jobs(base: Path) -> dict:
    """Every picture job from every pictures*.json beside the spec, by id."""
    return {j["id"]: j for f in sorted(base.glob("pictures*.json")) for j in json.loads(f.read_text())}


def claim_sources(spec: dict) -> list[dict]:
    """One source entry per VERIFIED claim, marked `passage_checked` (validate() already found the passage in the saved page): reviewer.source_text and the ledger read these."""
    srcs = {s["id"]: s for s in spec.get("sources") or []}
    return [{"title": srcs[c["source"]]["title"], "url": srcs[c["source"]]["url"], "passage": c["passage"], "passage_checked": True}
            for c in spec.get("claims") or [] if c.get("status") == "VERIFIED" and c.get("source") in srcs and c.get("passage")]


def fitted(src: Path, flip: bool = False) -> Path:
    """The picture fitted to the video's size, kept in cache/cc where animate.own_picture lets it have camera motion (in the video's folder it never did)."""
    import hashlib

    key = hashlib.sha256(Path(src).read_bytes() + repr((SIZE, flip)).encode()).hexdigest()[:16]
    out = Path(config.CACHE) / "cc" / f"fit-{key}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out if out.exists() else fit(Path(src), out, flip)


def resolve(pic: str, jobs: dict) -> Path:
    if pic in jobs:
        if jobs[pic].get("model") == "flux":
            import tools.flux_batch as fb

            return fb.path_for(jobs[pic])
        if jobs[pic].get("provider") == "cloudflare":
            import tools.cloudflare_batch as cb

            return cb.path_for(jobs[pic])
        if jobs[pic].get("provider") == "pollinations":
            import tools.pollinations_batch as pb

            return pb.path_for(jobs[pic])
        import tools.zimage_batch as zb

        return zb.path_for(jobs[pic])
    return Path(pic)


def ledger(spec: dict, srcs: dict) -> list[dict]:
    out = []
    for i, c in enumerate(spec["claims"], 1):
        s = srcs[c["source"]]
        out.append({"claim_id": f"c{i}", "claim_text": c["text"], "source_url": s["url"], "source_title": s["title"], "evidence_excerpt": c["passage"], "source_date": s.get("published", ""),
                    "verification_status": c["status"], "confidence": "high" if c["status"] == "VERIFIED" else "medium", "notes": c.get("note", "")})
    return out


def build(spec: dict, base: Path, out_root: Path | None = None, replace: bool = False) -> Path:
    """The held draft's folder. Raises ValueError for a spec that breaks the rules, FileNotFoundError for a missing picture."""
    import editprofile
    import render
    import run
    import subscribe
    import subtitles
    import tts

    errors, warns = validate(spec, base)
    if errors:
        raise ValueError("; ".join(errors))
    jobs = load_jobs(base)
    pics = [resolve(l["picture"], jobs) for l in spec["lines"]]
    missing = [str(p) for p in pics if not p.exists()]
    if missing:
        raise FileNotFoundError("pictures not drawn yet: " + ", ".join(Path(m).name for m in missing))
    slug = spec.get("slug") or re.sub(r"[^a-z0-9]+", "-", spec["title"].lower()).strip("-")[:50]
    folder = (out_root or config.OUT) / slug
    if folder.exists():
        mine = False
        try:
            mine = records.read(folder).get("built_by") == "ccbuild"
        except Exception:
            pass
        if not (replace and mine):
            raise FileExistsError(f"{folder.name} exists" + ("" if mine else " and was not made by this tool"))
        shutil.rmtree(folder)
    work = folder / "work"
    work.mkdir(parents=True)
    lines = [l["text"] for l in spec["lines"]]
    data = {"topic": spec["topic"], "format": "short", "kind": spec.get("kind", "mystery"), "title": spec["title"], "lines": [{"text": l["text"], "visual": l.get("visual", "")} for l in spec["lines"]],
            "parallax": True, "voice_style": spec.get("voice_style"), "subscribe_pop": spec.get("subscribe_pop", False),
            "brand_mark": spec.get("brand_mark", False)}  # owner, 1 Nov 2026: no logo in a video (corner mark and the branded pop-up are off unless the spec asks)
    data = {k: v for k, v in data.items() if v is not None}
    prof = editprofile.load()
    voice = {"style": data["voice_style"]} if data.get("voice_style") else {}
    print("Voice + captions...")
    narration, ass, durations = tts.narrate(lines, work, editprofile.short_pause(prof), prof["motion"], prof["caption_pos"], **voice)
    data["voice_used"] = tts.voice_used(data.get("voice_style"))
    clips = [fitted(p, bool(l.get("flip"))) for p, l in zip(pics, spec["lines"])]
    clips = run._parallax(data, clips, durations, SIZE)
    print("Rendering...")
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=editprofile.lufs_for(data, prof), shots=prof["motion"] >= 1,
                  crossfade=0.3 if prof["motion"] >= 2 and len(clips) <= 20 else 0.0, grain=prof["motion"] >= 2)
    subscribe.add_to(folder / "video.mp4", data, "short", durations, subtitles.load_words(work / "words.json"), SIZE)
    import sfx

    sfx.add_to(folder / "video.mp4", data, "short", durations)
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.with_punctuation(subtitles.load_words(work / "words.json"), lines))
    srcs = {s["id"]: s for s in spec["sources"]}
    (folder / "claims.json").write_text(json.dumps(ledger(spec, srcs), indent=1, ensure_ascii=False))
    shutil.rmtree(work)
    meta = {**data, "grounded": True, "anchors": spec.get("anchors", []), "description": spec["description"].rstrip() + "\n\nSources:\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in spec["sources"])
            + "\n\nPictures: AI-generated illustrations, not photographs of the real place. Voice: synthetic.",
            "tags": spec.get("tags", []), "sources": [{k: v for k, v in s.items() if k != "file"} | {"passages": [c["passage"] for c in spec["claims"] if c["source"] == s["id"]]} for s in spec["sources"]] + claim_sources(spec),
            "footage": {"scenes": len(clips), "unique": len({str(p) for p in pics}), "missing": 0}, "subtitles": "burned", "credits": spec["credits"], "limits": spec.get("limits", []),
            "approved": False, "hold": True, "hold_reason": "made in a Claude Code session by ccbuild.py: the owner watches it and releases it", "built_by": "ccbuild", "warnings": warns,
            "durations": [round(x, 2) for x in durations], "script_model": "claude-code-session"}
    records.create(folder, meta)
    print(f"\nDone: {folder / 'video.mp4'}\nTitle: {spec['title']}\nHeld draft: nothing is uploaded.")
    return folder


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
    build(spec, path.parent, replace="--replace" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
