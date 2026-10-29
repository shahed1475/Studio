"""Deterministic checks behind the project's quality skills. Each check returns rows {name, ok, severity, detail} and nothing here
publishes, approves or changes a video. Run them from the command line:

    .venv/bin/python studiochecks.py <script|sources|licenses|video|gate|publish> <slug> [--llm] [--quick] [--visual]

Exit code 0 means every blocking row passed, 1 means one failed, 2 means the video or a needed file is missing.
A passing check is evidence about what it measured, not proof that the whole video is good.
"""
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

import config
import ledger
import reviewer

ALLOWED_LICENSES = ("public domain", "cc0", "pdm", "ai-generated")
CAUTION_LICENSES = ("cc by-sa", "cc by 4.0", "cc by 3.0", "cc by 2.0", "cc by")  # allowed with attribution, which the credits provide
FORBIDDEN_WORDS = ("all rights reserved", "copyright", "fair use", "used with permission", "non-commercial", "cc by-nc", "cc by-nd")


def row(name: str, ok: bool, detail: str, severity: str = "block") -> dict:
    return {"name": name, "ok": bool(ok), "severity": severity, "detail": detail}


def load(slug: str) -> tuple[Path, dict]:
    folder = config.OUT / slug
    p = folder / "meta.json"
    if not p.exists():
        raise FileNotFoundError(f"no video named {slug} in {config.OUT}")
    return folder, json.loads(p.read_text())


# ---- script ----
def check_script(meta: dict, source: str = "") -> list[dict]:
    """The writing rules: long enough, no loops, a short hook, grounded, and no claim that is unsupported or in conflict."""
    kind = "doc" if meta.get("format") == "doc" else "short"
    lim = reviewer.LIMITS[kind]
    texts = [l["text"].strip() for l in meta.get("lines", []) if l.get("text")]
    words = sum(len(t.split()) for t in texts)
    out = [row("script_length", words >= lim["words"], f"{words} words (need {lim['words']})")]
    repeated = len(texts) - len({t.lower() for t in texts})
    out.append(row("no_repeated_lines", repeated <= max(1, len(texts) // 10), f"{repeated} repeated narration lines"))
    if kind == "short" and texts:
        hook = len(texts[0].split())
        out.append(row("short_hook", hook <= 14, f"the first line has {hook} words (14 or fewer)", "warn"))
    out.append(row("grounded", meta.get("grounded") is True, "built from a source article" if meta.get("grounded") is True else "not tied to a source article",
                   "block" if kind == "doc" else "warn"))
    rows = ledger.build(meta, source)
    bad = [r for r in rows if r["verification_status"] == "CONFLICTING"]
    open_ = [r for r in rows if r["verification_status"] == "UNVERIFIED"]
    out.append(row("no_conflicting_claims", not bad, f"{len(bad)} claims a reliable source contradicts: " + "; ".join(r["claim_text"] for r in bad[:5]) if bad else "none"))
    out.append(row("no_unverified_claims", not open_, f"{len(open_)} specific claims stated as fact with no evidence: " + "; ".join(r["claim_text"] for r in open_[:5]) if open_ else "none"))
    quotes = [r for r in rows if r["claim_text"][:1] in "\"“"]
    out.append(row("quotes_attributed", not quotes, f"{len(quotes)} direct quotations: confirm each against its source", "warn"))
    return out


# ---- sources ----
def check_sources(meta: dict, folder: Path, source: str = "") -> list[dict]:
    """Every VERIFIED claim has evidence, source links are https, and the ledger exists and is current."""
    rows = ledger.build(meta, source)
    out = []
    unsupported = [r for r in rows if r["verification_status"] == "VERIFIED" and not (r["source_url"] or r["evidence_excerpt"])]
    out.append(row("verified_has_evidence", not unsupported, f"{len(unsupported)} VERIFIED claims have neither a link nor a passage" if unsupported else "every VERIFIED claim has evidence"))
    links = [s for s in meta.get("sources", []) if str(s).startswith(("http", "Checked against: http"))]
    insecure = [s for s in links if "http://" in s]
    out.append(row("https_sources", not insecure, f"{len(insecure)} source links are not https" if insecure else f"{len(links)} source links, all https", "warn"))
    out.append(row("ledger_file", (folder / "claims.json").exists(), "claims.json present" if (folder / "claims.json").exists() else "claims.json missing: run the review to write it", "warn"))
    counts = {s: sum(1 for r in rows if r["verification_status"] == s) for s in ledger.STATUSES}
    out.append(row("ledger_summary", True, ", ".join(f"{n} {s}" for s, n in counts.items()), "info"))
    return out


# ---- licenses ----
def check_licenses(meta: dict) -> list[dict]:
    """Every picture credit names a license we may use; the Wikipedia text and any AI art are credited; no music without a license file."""
    out = []
    credits = meta.get("credits") or []
    bad, caution = [], []
    for c in credits:
        low = c.lower()
        if any(w in low for w in FORBIDDEN_WORDS):
            bad.append(c)
        elif any(a in low for a in ALLOWED_LICENSES):
            continue
        elif any(a in low for a in CAUTION_LICENSES):
            caution.append(c)
        else:
            bad.append(c)
    out.append(row("credits_present", bool(credits), f"{len(credits)} credit lines" if credits else "no image credits", "warn" if not meta.get("footage") else "block"))
    out.append(row("licenses_allowed", not bad, f"{len(bad)} credits without a license we can use: " + " | ".join(b[:80] for b in bad[:3]) if bad else "every credit is public domain, CC0 or AI-generated"))
    if caution:
        out.append(row("attribution_licenses", False, f"{len(caution)} credits need attribution (CC BY): the credit line in the description provides it", "warn"))
    drawn = (meta.get("footage") or {}).get("drawn", 0)
    ai_credited = any("ai-generated" in c.lower() for c in credits)
    out.append(row("ai_art_labelled", not drawn or ai_credited, f"{drawn} AI illustrations, credited as AI-generated" if drawn and ai_credited else ("no AI illustrations" if not drawn else "AI illustrations are not credited")))
    if meta.get("grounded"):
        text = " ".join(str(s) for s in meta.get("sources", [])) + " " + meta.get("description", "")
        out.append(row("wikipedia_attribution", "CC BY-SA" in text, "article credited with its license" if "CC BY-SA" in text else "Wikipedia text used without its CC BY-SA credit"))
    music = config.ROOT / "music"
    tracks = list(music.glob("*.mp3")) if music.exists() else []
    out.append(row("music_license", not tracks or (music / "LICENSE.txt").exists(), "no background music" if not tracks else f"{len(tracks)} tracks and a LICENSE.txt" if (music / "LICENSE.txt").exists() else f"{len(tracks)} tracks with no LICENSE.txt", "block"))
    return out


# ---- video and captions ----
def _fps(path: Path) -> float:
    try:
        r = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(path)], text=True).strip()
        a, _, b = r.partition("/")
        return float(a) / float(b or 1)
    except (subprocess.CalledProcessError, ValueError, ZeroDivisionError, OSError):
        return 0.0


def _decode_errors(path: Path) -> str:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    return (r.stderr or "").strip()[:300]


FREEZE_MAX = 1.5  # seconds a picture may stand perfectly still before it reads as lag


def frozen_stretches(path: Path, noise: float = 0.003, min_seconds: float = 0.5) -> list[float]:
    """The lengths in seconds of every stretch where the picture does not change at all (ffmpeg's freezedetect). [] when nothing stands still or ffmpeg gave no answer."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", f"freezedetect=n={noise}:d={min_seconds}", "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(x) for x in re.findall(r"freeze_duration:\s*([0-9.]+)", r.stderr or "")]


def freeze_checks(path: Path) -> list[dict]:
    got = frozen_stretches(path)
    worst = max(got, default=0.0)
    return [row("no_frozen_picture", worst <= FREEZE_MAX, f"the picture stands still for {worst:.1f} s at the longest ({len(got)} stretch(es) over 0.5 s; aim for {FREEZE_MAX:g} s or less)" if got else "the picture never stands still for half a second", "warn")]


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        m = re.search(r"(\d+):(\d\d):(\d\d)[,.](\d+)\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d+)\s*\n(.*)", block, re.S)
        if m:
            g = m.groups()
            t = lambda h, mi, s, ms: int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000
            cues.append((t(*g[:4]), t(*g[4:8]), " ".join(g[8].split())))
    return cues


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


DEAD_AIR_MAX = 0.9  # seconds between the last word of one Short line and the first of the next; the default voice breathes about 0.65 s, the untrimmed energetic voice left 1.1 to 1.2 s


def longest_gap(words: list[dict]) -> float:
    """The longest silence between the end of one narration line and the start of the next, from words.json."""
    ends, starts = {}, {}
    for w in words:
        i = w.get("i", 0)
        starts[i] = min(w["s"], starts.get(i, w["s"]))
        ends[i] = max(w["e"], ends.get(i, w["e"]))
    return max((starts[i] - ends[i - 1] for i in starts if i - 1 in ends), default=0.0)


def caption_checks(folder: Path, meta: dict, duration: float) -> list[dict]:
    """Captions in order, inside the video, and matching the final script word for word (burned-in captions are checked through the same words)."""
    out = []
    srt = folder / "captions.srt"
    script_words = _norm_words(" ".join(l["text"] for l in meta.get("lines", [])))
    if not srt.exists():
        return [row("captions_file", False, "no captions.srt beside the video", "warn")]
    cues = parse_srt(srt.read_text())
    out.append(row("captions_present", bool(cues), f"{len(cues)} caption cues"))
    ordered = all(a[1] <= b[0] + 0.01 and a[0] < a[1] for a, b in zip(cues, cues[1:])) and all(c[0] < c[1] for c in cues)
    out.append(row("captions_in_order", ordered, "cues are in order and do not overlap" if ordered else "cues overlap or run backwards"))
    inside = not cues or (cues[0][0] >= 0 and cues[-1][1] <= duration + 1.0)
    out.append(row("captions_inside_video", inside, f"last cue ends at {cues[-1][1]:.1f} s of {duration:.1f} s" if cues else "no cues"))
    cap_words = _norm_words(" ".join(c[2] for c in cues))
    if script_words and cap_words:
        have = {}
        for w in cap_words:
            have[w] = have.get(w, 0) + 1
        hit = 0
        for w in script_words:
            if have.get(w, 0) > 0:
                have[w] -= 1
                hit += 1
        cover = hit / len(script_words)
        out.append(row("captions_match_script", cover >= 0.95, f"{cover:.0%} of the script's words appear in the captions"))
    words_file = folder / "words.json"
    if words_file.exists():
        import subtitles

        words = json.loads(words_file.read_text())
        out.append(row("voice_timing_matches_length", subtitles.timings_match(words, duration, 1.5), f"speech ends at {words[-1]['e']:.1f} s of {duration:.1f} s" if words else "no word timings"))
        if meta.get("format") != "doc" and words:
            gap = longest_gap(words)
            out.append(row("no_dead_air", gap <= DEAD_AIR_MAX, f"the longest silence between two lines is {gap:.1f} s (aim for {DEAD_AIR_MAX:g} or less: a still picture and no voice reads as lag on a phone)", "warn"))
    return out


def check_video(folder: Path, meta: dict, quick: bool = False) -> list[dict]:
    """ffprobe facts and a full decode: size, frame rate, audio level, black frames, duration, readable stream, captions."""
    path = folder / "video.mp4"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    kind = "doc" if meta.get("format") == "doc" else "short"
    lim = reviewer.LIMITS[kind]
    probe = reviewer.probe_video(path)
    lo, hi = lim["duration"]
    out = [row("duration", lo <= probe["duration"] <= hi, f"{probe['duration']:.1f} s (allowed {lo} to {hi})"),
           row("resolution", (probe["width"], probe["height"]) == lim["size"], f"{probe['width']}x{probe['height']} (need {lim['size'][0]}x{lim['size'][1]})")]
    fps = _fps(path)
    out.append(row("frame_rate", 24 <= fps <= 60, f"{fps:.2f} fps", "warn"))
    out.append(row("audio", probe["has_audio"] and probe["mean_db"] is not None and -30 <= probe["mean_db"] <= -8,
                   f"mean volume {probe['mean_db']} dB (clear speech sits near -16)" if probe["has_audio"] else "no audio stream"))
    out.append(row("no_black_screens", probe["black_ratio"] < 0.15, f"{probe['black_ratio']:.0%} black"))
    if not quick:
        err = _decode_errors(path)
        out.append(row("decodes_cleanly", not err, err or "full decode finished without errors"))
        out += freeze_checks(path)
    out += caption_checks(folder, meta, probe["duration"])
    return out


# ---- the gate ----
def quality_gate(slug: str, use_llm: bool = False, quick: bool = False, visual: bool = False) -> dict:
    """Everything before approval: the reviewer, the script rules, sources, licenses, and the real file. PASS only when no blocking row failed."""
    folder, meta = load(slug)
    source = reviewer.source_text(meta)
    review = reviewer.review(folder, use_llm=use_llm, persist=use_llm)  # only a full review (with the AI part) is stored; a rules-only read changes nothing
    folder, meta = load(slug)
    rows = [{**c, "name": "review: " + c["name"]} for c in review["checks"]]
    for name, fn in (("script", lambda: check_script(meta, source)), ("sources", lambda: check_sources(meta, folder, source)),
                     ("licenses", lambda: check_licenses(meta)), ("video", lambda: check_video(folder, meta, quick)),
                     *((("visual", lambda: __import__("videoinspect").visual_review(folder)),) if visual else ())):
        try:
            rows += [{**r, "name": f"{name}: {r['name']}"} for r in fn()]
        except Exception as e:  # a check that cannot run is reported, never skipped silently
            rows.append(row(f"{name}: could not run", False, f"{type(e).__name__}: {e}"))
    blocking = [r for r in rows if not r["ok"] and r["severity"] in ("block", "human")]
    return {"slug": slug, "verdict": "PASS" if not blocking else "FAIL", "llm_review": use_llm, "rows": rows, "blocking": len(blocking)}


# ---- publishing ----
def check_publish_ready(meta: dict, now: dt.datetime | None = None, uploads_today: int = 0) -> list[dict]:
    """Safe to hand to the uploader? Approved, not held, reviewed and passed, scheduled in the future, not uploaded already."""
    now = now or dt.datetime.now(dt.timezone.utc)
    verdict = (meta.get("review") or {}).get("verdict")
    out = [row("approved", bool(meta.get("approved")), f"approved by {meta.get('approved_by', '?')}" if meta.get("approved") else "not approved"),
           row("not_on_hold", not meta.get("hold"), "on hold" if meta.get("hold") else "not on hold"),
           row("review_passed", verdict == "pass", f"review verdict: {verdict}"),
           row("not_uploaded_yet", not meta.get("video_id"), f"already uploaded as {meta.get('video_id')}" if meta.get("video_id") else "no video id yet"),
           row("daily_limit", uploads_today < config.MAX_UPLOADS_PER_DAY, f"{uploads_today} uploads today (limit {config.MAX_UPLOADS_PER_DAY})")]
    pub = meta.get("publish_at")
    try:
        when = dt.datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
    except ValueError:
        when = None
    out.append(row("scheduled_in_future", bool(when) and when > now + dt.timedelta(minutes=5), f"publish time {pub}" if pub else "no publish time set"))
    interrupted = bool(meta.get("upload_started")) and not meta.get("video_id")
    out.append(row("no_interrupted_upload", not interrupted, "an earlier upload attempt did not finish: the uploader will look for it before sending again" if interrupted else "no earlier attempt", "warn"))
    conflicting = [c for c in meta.get("conflicting_claims", []) if isinstance(c, dict)]
    out.append(row("no_open_conflicts", not conflicting or not meta.get("fix_gave_up"), f"{len(conflicting)} claims were contradicted" if conflicting else "none", "warn"))
    return out


def print_rows(rows: list[dict]) -> None:
    for r in rows:
        mark = "ok  " if r["ok"] else ("FAIL" if r["severity"] in ("block", "human") else "warn")
        print(f"{mark} {r['name']}: {r['detail']}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] not in ("script", "sources", "licenses", "video", "gate", "publish"):
        print(__doc__)
        return 2
    which, slug = argv[0], argv[1]
    try:
        folder, meta = load(slug)
        if which == "gate":
            result = quality_gate(slug, use_llm="--llm" in argv, quick="--quick" in argv, visual="--visual" in argv)
            print_rows(result["rows"])
            print(f"\n{result['verdict']} ({result['blocking']} blocking, AI review {'on' if result['llm_review'] else 'off'})")
            return 0 if result["verdict"] == "PASS" else 1
        source = reviewer.source_text(meta)
        if which == "script":
            rows = check_script(meta, source)
        elif which == "sources":
            rows = check_sources(meta, folder, source)
        elif which == "licenses":
            rows = check_licenses(meta)
        elif which == "video":
            rows = check_video(folder, meta, quick="--quick" in argv)
        else:
            import upload

            rows = check_publish_ready(meta, uploads_today=upload.uploads_today(config.OUT, dt.datetime.now(dt.timezone.utc)))
    except FileNotFoundError as e:
        print(e)
        return 2
    print_rows(rows)
    return 0 if all(r["ok"] or r["severity"] not in ("block", "human") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
