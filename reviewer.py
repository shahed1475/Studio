"""Reviewer agent: rule checks on the finished files plus a local-model read of the script. Gate before any upload."""
import datetime as dt
import difflib
import json
import re
import subprocess
from pathlib import Path

import scriptgen

LIMITS = {"doc": {"duration": (180, 900), "size": (1920, 1080), "words": 400},
          "short": {"duration": (20, 180), "size": (1080, 1920), "words": 100}}


def _c(name: str, ok: bool, detail: str, severity: str = "block") -> dict:
    return {"name": name, "ok": bool(ok), "severity": severity, "detail": detail}


HEDGES = re.compile(r"\b(legends? says?|it is said|some (say|believe|historians|scholars)|people (say|believe)|according to|"
                    r"(historians|scholars|experts) (disagree|debate|believe|argue|suggest|think)|may have|might have|perhaps|"
                    r"allegedly|supposedly|rumou?rs?|claimed|claims?|story goes|tradition holds|is believed|was believed)\b", re.I)
SPECIFICS = [re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b"), re.compile(r"\b\d{1,2}(st|nd|rd|th) century\b", re.I),
             re.compile(r"\b(named|called|known as)\s+[A-Z][a-z]+(\s+(von|van|de|of|the)?\s*[A-Z][a-z]+)*"),
             re.compile(r"[\"\u201c][^\"\u201d]{20,}[\"\u201d]")]


def _in_source(claim: str, source: str) -> bool:
    """True when the name or year of a claim appears in the source text the script was built from."""
    key = re.sub(r"^(named|called|known as)\s+", "", claim, flags=re.I).strip()
    return bool(source) and bool(key) and key.lower() in source.lower()


def unhedged_claims(lines: list[str], source: str = "") -> list[str]:
    """Specific names, years, centuries and quotes stated without any hedging word in the same line.
    With the source article given, a specific that the article itself contains is verified and not counted."""
    found = []
    for line in lines:
        if HEDGES.search(line):
            continue
        for rx in SPECIFICS:
            m = rx.search(line)
            if m and not _in_source(m.group(0).strip(), source):
                found.append(m.group(0).strip())
    return found


def source_title(meta: dict) -> str:
    """The Wikipedia article a script was built from, read from its source line ("Wikipedia: Delphi (CC BY-SA 4.0), ...")."""
    for s in meta.get("sources") or []:
        m = re.match(r"Wikipedia:\s*(.+?)\s*\(CC", str(s))
        if m:
            return m.group(1)
    return ""


def source_text(meta: dict) -> str:
    """The text of the video's source article, cached on disk. Empty for a script with no source."""
    title = source_title(meta)
    if not title or meta.get("grounded") is not True:
        return ""
    import config
    import wikipedia

    f = config.CACHE / "wiki" / (re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:60] + ".txt")
    if f.exists():
        return f.read_text()
    text = wikipedia.article_text(title)
    if text:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return text


def _chapters(description: str) -> list[tuple[int, str]]:
    found = []
    for m in re.finditer(r"^(\d+):(\d\d)\s+(.+)$", description.partition("Chapters:")[2], re.M):
        found.append((int(m.group(1)) * 60 + int(m.group(2)), m.group(3).strip()))
    return found


def footage_checks(meta: dict) -> list[dict]:
    """Documentary pictures and sourcing: every scene needs an on-topic image, and the script needs a source."""
    f = meta.get("footage")
    if not f:
        out = [_c("images", False, "pictures were never checked for relevance (made before this check existed)", "warn")]
    else:
        ok = f.get("missing", 0) == 0 and f.get("unique", 0) >= (6 if meta.get("format") == "doc" else 4)
        out = [_c("images", ok, f"{f.get('unique', 0)} different on-topic images, {f.get('missing', 0)} scenes without one"
                  if ok else f"only {f.get('unique', 0)} on-topic images and {f.get('missing', 0)} scenes without a picture")]
    grounded = meta.get("grounded") is True
    out.append(_c("grounded", grounded, "script built from a source article" if grounded else
                  "script is not tied to a source, so facts need a human check",
                  "human" if meta.get("format") == "doc" else "warn"))
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def metadata_checks(meta: dict) -> list[dict]:
    """Things YouTube ignores or frowns on: over 15 hashtags (all are dropped) and shouting titles."""
    import config

    try:
        niche_tags = len(config.niche().get("hashtags", []))
    except (OSError, ValueError):
        niche_tags = 5
    n = len(re.findall(r"#\w+", f"{meta.get('title', '')} {meta.get('description', '')}")) + niche_tags
    out = [_c("hashtags", n <= 15, f"{n} hashtags (YouTube ignores all of them above 15)")]
    title = meta.get("title", "")
    letters = [ch for ch in title if ch.isalpha()]
    shouting = len(letters) > 10 and sum(ch.isupper() for ch in letters) / len(letters) > 0.6
    if shouting or "!!" in title:
        out.append(_c("title_style", False, "title shouts (capital letters or !!), which reads as clickbait", "warn"))
    return out


def variety_checks(meta: dict, recent: list[dict]) -> list[dict]:
    """YouTube's inauthentic-content rule looks at the pattern across recent uploads. Compare with the last few videos of the same kind."""
    out = []
    lines = [l["text"] for l in meta.get("lines", []) if l.get("text")]
    if lines and recent:
        same = []
        for r in recent:
            theirs = [l["text"] for l in r.get("lines", []) if l.get("text")]
            if not theirs:
                continue
            for label, a, b in (("opening", lines[0], theirs[0]), ("ending", lines[-1], theirs[-1])):
                if difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= 0.75:
                    same.append(f"{label} like '{r.get('title', '?')}'")
        out.append(_c("variety_script", not same, "; ".join(same[:2]) + ". Change the opening or ending so videos do not share a template." if same else "opening and ending are different from recent videos", "human"))
    head = " ".join(_norm(meta.get("title", "")).split()[:2])
    if head and recent:
        n = sum(1 for r in recent[:8] if " ".join(_norm(r.get("title", "")).split()[:2]) == head)
        if n >= 3:
            out.append(_c("variety_title", False, f"{n} of the last {min(len(recent), 8)} titles start with '{head}'. Vary the title pattern.", "warn"))
    return out


def rule_checks(meta: dict, probe: dict, existing_titles: list[str], thumb_bytes: int | None, recent: list[dict] | None = None, source: str = "") -> list[dict]:
    kind = "doc" if meta.get("format") == "doc" else "short"
    lim = LIMITS[kind]
    out = []
    lo, hi = lim["duration"]
    out.append(_c("duration", lo <= probe["duration"] <= hi, f"{probe['duration']:.0f} s (allowed {lo} to {hi})"))
    out.append(_c("resolution", (probe["width"], probe["height"]) == lim["size"], f"{probe['width']}x{probe['height']}"))
    loud = probe["has_audio"] and probe["mean_db"] is not None and probe["mean_db"] > -45
    out.append(_c("audio", loud, "no audio" if not probe["has_audio"] else f"mean volume {probe['mean_db']} dB"))
    out.append(_c("black_frames", probe["black_ratio"] < 0.15, f"{probe['black_ratio']:.0%} of the video is black"))

    title = meta.get("title", "")
    out.append(_c("title", 8 <= len(title) <= 100, f"{len(title)} characters"))
    if len(title) > 70:
        out.append(_c("title_length", False, f"{len(title)} characters, search shows about 60", "warn"))
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
    dup = [t for t in existing_titles if difflib.SequenceMatcher(None, norm(t), norm(title)).ratio() >= 0.85]
    out.append(_c("duplicate_title", not dup, f"too similar to: {dup[0]}" if dup else "unique"))

    desc = meta.get("description", "")
    out.append(_c("description", len(desc) >= 80, f"{len(desc)} characters"))
    if kind == "doc":
        ch = _chapters(desc)
        starts_ok = bool(ch) and ch[0][0] == 0 and len(ch) >= 3 and all(b[0] - a[0] >= 10 for a, b in zip(ch, ch[1:]))
        out.append(_c("chapters", starts_ok, f"{len(ch)} chapters, first at {ch[0][0] if ch else '-'} s"))
        if any(re.match(r"^(part|chapter)\s*\d*$", t, re.I) for _, t in ch):
            out.append(_c("chapters", False, "a chapter has a placeholder name", "warn"))
        out.append(_c("credits", bool(meta.get("credits")), "image credits present" if meta.get("credits") else "no image credits", "warn"))
        out += footage_checks(meta)
        out.append(_c("thumbnail", thumb_bytes is not None and thumb_bytes <= 1_950_000,
                      "missing" if thumb_bytes is None else f"{thumb_bytes} bytes (limit 2 MB)"))
    if kind == "short" and meta.get("footage"):
        out += footage_checks(meta)
    out.append(_c("subtitles", meta.get("subtitles") in ("burned", "srt"), "subtitles added" if meta.get("subtitles") else "no subtitles yet", "warn"))
    tags = meta.get("tags", [])
    out.append(_c("tags", len(tags) >= 5 and len(",".join(tags)) <= 450, f"{len(tags)} tags", "warn"))

    if kind == "short" and meta.get("lines"):  # viewers decide in the first seconds: a long first sentence loses them
        hook = len(meta["lines"][0]["text"].split())
        out.append(_c("hook", hook <= 14, f"the first line is {hook} words (aim for 12 or fewer)", "warn"))
    lines = [l["text"].strip().lower() for l in meta.get("lines", [])]
    words = sum(len(l.split()) for l in lines)
    out.append(_c("script_length", words >= lim["words"], f"{words} words (need {lim['words']})"))
    dupes = len(lines) - len(set(lines))
    out.append(_c("script_loop", dupes <= max(1, len(lines) // 10), f"{dupes} repeated narration lines"))
    claims = unhedged_claims([l["text"] for l in meta.get("lines", [])], source)
    out += metadata_checks(meta)
    out += variety_checks(meta, recent or [])
    out.append(_c("claims", len(claims) < 2, f"{len(claims)} specific claims stated as fact{' and not found in the source article' if source else ''}, check them: {'; '.join(claims[:5])}" if claims else ("every specific name and year is in the source article" if source else "no unhedged specifics"), "human"))
    return out


def verdict_from(checks: list[dict], source: str | None) -> str:
    if any(not c["ok"] and c["severity"] == "block" for c in checks):
        return "fail"
    human = any(not c["ok"] and c["severity"] == "human" for c in checks)
    return "needs_human" if human or source == "news" else "pass"


def llm_review(meta: dict, source: str = "") -> list[dict]:
    text = " ".join(l["text"] for l in meta.get("lines", []))[:7000]
    grounding = (f"SOURCE ARTICLE the script was built from (a detail this article supports is NOT invented; only count details it does not support):\n{source[:12000]}\n\n"
                 if source else "")
    try:
        r = scriptgen._review_chat(
            "You check a YouTube video script before it is published. Be strict.\n"
            f"{grounding}Title: {meta.get('title')}\nDescription: {meta.get('description', '')[:600]}\nNarration: {text}\n\n"
            "Score 0 to 10: invented_facts_risk (specific names, dates, numbers or quotes that look made up or are "
            "stated as certain when the history is uncertain), policy_risk (hateful, graphic, dangerous, medical or "
            "financial advice, or anything advertisers or YouTube policy would reject). misleading_title is true when "
            'the title promises something the narration does not deliver. Return JSON: {"invented_facts_risk": 0, '
            '"policy_risk": 0, "misleading_title": false, "issues": []}. Put a real, specific issue in issues, or leave it empty.')
        facts, policy = int(r["invented_facts_risk"]), int(r["policy_risk"])
        note = "; ".join(str(i) for i in r.get("issues", [])[:3])
    except Exception as e:  # cannot verify, so never auto-pass
        return [_c("llm_review", False, f"review unavailable: {type(e).__name__}")]
    out = [_c("invented_facts", facts < 7, f"risk {facts}/10. {note}"),
           _c("policy_risk", policy < 6, f"risk {policy}/10. {note}"),
           _c("title_matches", not r.get("misleading_title"), "title matches the story" if not r.get("misleading_title") else "title may mislead")]
    if 4 <= facts < 7:
        out.append(_c("invented_facts_watch", False, f"moderate risk {facts}/10", "warn"))
    if 4 <= policy < 6:
        out.append(_c("policy_watch", False, f"moderate risk {policy}/10", "warn"))
    return out


def probe_video(path: Path) -> dict:
    info = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(path)], text=True))
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    duration = float(info["format"]["duration"])
    vol = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", vol)
    blk = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-vf", "fps=1,scale=320:-2,blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    black = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", blk))
    return {"duration": duration, "width": v.get("width", 0), "height": v.get("height", 0),
            "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
            "mean_db": float(m.group(1)) if m else None, "black_ratio": black / duration if duration else 1.0}


def apply_verdict(meta: dict, result: dict) -> None:
    """Store the result. A video the reviewer no longer passes loses the reviewer's own approval (never yours)."""
    meta["review"] = result
    meta["autopilot_fails"] = 0
    if result["verdict"] != "pass" and meta.get("approved_by") != "you":
        meta["approved"] = False
        meta.pop("approved_by", None)


def invalidate(meta: dict) -> None:
    """After any edit the old review means nothing: drop it, the reviewer's approval and the slot."""
    meta.pop("review", None)
    if meta.get("approved_by") != "you":
        meta["approved"] = False
        meta.pop("approved_by", None)
        meta.pop("publish_at", None)


def review(folder: Path, existing_titles: list[str] | None = None, use_llm: bool = True) -> dict:
    meta_path = folder / "meta.json"
    meta = json.loads(meta_path.read_text())
    thumb = folder / meta["thumbnail"] if meta.get("thumbnail") else None
    thumb_bytes = thumb.stat().st_size if thumb and thumb.exists() else None
    if existing_titles is None:
        existing_titles = [json.loads(m.read_text()).get("title", "") for m in folder.parent.glob("*/meta.json") if m.parent != folder]
    kind = "doc" if meta.get("format") == "doc" else "short"
    others = sorted((m for m in folder.parent.glob("*/meta.json") if m.parent != folder), key=lambda m: m.stat().st_mtime, reverse=True)
    recent = [d for d in (json.loads(m.read_text()) for m in others[:30]) if ("doc" if d.get("format") == "doc" else "short") == kind][:12]
    source = source_text(meta)
    checks = rule_checks(meta, probe_video(folder / "video.mp4"), existing_titles, thumb_bytes, recent, source)
    if use_llm:
        checks += llm_review(meta, source)
    result = {"verdict": verdict_from(checks, meta.get("source")), "checks": checks,
              "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    apply_verdict(meta, result)
    meta_path.write_text(json.dumps(meta, indent=2))
    return result
