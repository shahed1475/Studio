"""The crisis channel's review agent. It FAILS CLOSED: a video passes only when every check holds. Any failed check, any uncertainty (a model error, a malformed answer, two
reviewers who disagree, a bad input) and any missing evidence means the verdict is "hold" and a person is told. Pure logic: the two model reviewers are passed in as functions,
so tests use mocks and nothing here calls a paid service. Evidence for every verdict is written next to the video (crisis_review.json).

`video`, `sources` and the file hashes must be built by the PIPELINE from what it really rendered and fetched, never copied from a model's own claims. A source counts as
official only when its address is on the channel's `official_domains` list (empty list: nothing counts, so any video with a number is held)."""
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import assetledger

GRAPHIC = re.compile(r"\b(gore|gory|mutilat\w*|dismember\w*|decapitat\w*|corpses?|bloodbath)\b", re.I)
NUMBER = re.compile(r"\d[\d,.]*")
WORD_NUMBER = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million|billion|trillion|dozen|half|percent|per cent)\b|%", re.I)
STOP = {"that", "this", "with", "from", "were", "have", "been", "their", "about", "which", "after", "into", "over", "than", "also", "more", "most", "some"}
BAD_VERIFIED = {"", "unknown", "n/a", "na", "none", "null", "tbd"}
CONTEXT_MIN_WORDS, CONTEXT_WITHIN_LINES = 12, 3


def check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": str(detail)}


def nums(text: str) -> set[str]:
    return {n.strip(".,").replace(",", "") for n in NUMBER.findall(text) if n.strip(".,")}


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


def valid_input(video, sources, passed) -> str:
    if not isinstance(video, dict) or not isinstance(video.get("lines"), list) or not video["lines"]:
        return "video needs a non-empty list of lines"
    for l in video["lines"]:
        if not isinstance(l, dict) or not isinstance(l.get("text"), str) or not isinstance(l.get("claims", []), list) or not all(isinstance(c, str) for c in l.get("claims", [])):
            return "every line needs text (string) and claims (a list of ids)"
    if not isinstance(sources, dict) or not all(isinstance(s, dict) and isinstance(s.get("passage", ""), str) for s in sources.values()):
        return "sources must be a mapping of id to a record with a text passage"
    for k in ("manifest", "footage"):
        if not isinstance(video.get(k, []), list):
            return f"{k} must be a list"
    if not isinstance(passed, int) or isinstance(passed, bool) or passed < 0:
        return "the weekly count must be a whole number, zero or more"
    return ""


def source_ok(s: dict, official_domains) -> bool:
    try:
        host = (urlsplit(s.get("url", "")).hostname or "").lower()
        dt.date.fromisoformat(str(s.get("date", "")))
    except ValueError:
        return False
    return s.get("url", "").startswith("https://") and any(host == d or host.endswith("." + d) for d in official_domains)


def numbers_sourced(video: dict, sources: dict, official_domains) -> dict:
    """Every number (digits, number words, % and quantity words) in the title, description and lines must be backed: lines by a cited, official, dated source whose passage
    holds the same whole number (or word) AND shares key words with the line; title and description numbers must appear in a sourced line."""
    bad, sourced = [], set()
    for i, line in enumerate(video["lines"]):
        text = line["text"]
        n, w = nums(text), {m.group(0).lower() for m in WORD_NUMBER.finditer(text)}
        if not n and not w:
            continue
        cited = [sources[c] for c in line.get("claims", []) if isinstance(sources.get(c), dict) and source_ok(sources[c], official_domains)]
        key = words(text)
        for token in sorted(n) + sorted(w):
            ok = False
            for s in cited:
                p = s.get("passage", "")
                has = token in nums(p) if token[0].isdigit() else token in {m.group(0).lower() for m in WORD_NUMBER.finditer(p)}
                if has and len(key & words(p)) >= 2:
                    ok = True
            if not ok:
                bad.append(f"line {i}: '{token}' is not in an official, dated source passage that matches the line")
            else:
                sourced.add(token)
    for field in ("title", "description"):
        text = str(video.get(field, ""))
        for token in sorted(nums(text)) + sorted({m.group(0).lower() for m in WORD_NUMBER.finditer(text)}):
            if token not in sourced:
                bad.append(f"{field}: '{token}' is not backed by a sourced line")
    return check("numbers_sourced", not bad, "; ".join(bad[:5]))


def footage_ok(video: dict, ledger_rows: list[dict], file_hashes) -> dict:
    bad = []
    manifest = video.get("manifest", [])
    if not manifest or not all(isinstance(f, str) and f for f in manifest):
        bad.append("the render manifest (every file used) is missing or empty")
    for f in video.get("footage", []):
        if not isinstance(f, dict) or not f.get("file"):
            bad.append("a footage entry has no file name")
            continue
        if f.get("real") is not False:  # anything not plainly "not real" is treated as real footage
            v = f.get("verified") or {}
            if not all(isinstance(v.get(k), str) and v[k].strip().lower() not in BAD_VERIFIED for k in ("date", "place", "publisher")):
                bad.append(f"{f['file']}: real footage needs a verified date, place and publisher")
    if not isinstance(file_hashes, dict):
        bad.append("file hashes were not computed by the pipeline")
    footage_files = [f["file"] for f in video.get("footage", []) if isinstance(f, dict) and isinstance(f.get("file"), str) and f["file"]]
    bad += [f"{f}: footage file is not in the render manifest" for f in footage_files if f not in manifest]
    if not isinstance(file_hashes, dict):
        bad.append("file hashes were not computed by the pipeline")
    bad += assetledger.problems(ledger_rows, [f for f in manifest if isinstance(f, str)] + [f for f in footage_files if f not in manifest], file_hashes if isinstance(file_hashes, dict) else None)
    return check("footage_and_licences", not bad, "; ".join(bad[:5]))


def flags_ok(video: dict) -> list[dict]:
    text = " ".join(l["text"] for l in video["lines"])
    head = video["lines"][:CONTEXT_WITHIN_LINES]
    ctx = any(l.get("role") == "context" and len(l["text"].split()) >= CONTEXT_MIN_WORDS for l in head)
    m = GRAPHIC.search(text)
    return [check("not_made_for_kids", video.get("made_for_kids") is False), check("ai_content_disclosed", video.get("ai_disclosed") is True),
            check("evergreen_topic", video.get("topic_kind") == "evergreen", "never breaking news"),
            check("context_inside_the_video", ctx, f"a context line of at least {CONTEXT_MIN_WORDS} words in the first {CONTEXT_WITHIN_LINES} lines"),
            check("no_graphic_wording", not m, m.group(0) if m else "")]


def model_review(name: str, ask, video: dict, sources: dict) -> dict:
    """ask(video, sources) -> {"ok": True, "issues": []}. Anything else, or an error, is uncertainty and counts as a failure."""
    try:
        r = ask(video, sources)
        ok = isinstance(r, dict) and r.get("ok") is True and isinstance(r.get("issues", []), list) and not r.get("issues")
        return check(name, ok, "; ".join(map(str, r.get("issues", [])))[:300] if isinstance(r, dict) else "malformed answer")
    except Exception as e:
        return check(name, False, f"reviewer failed: {type(e).__name__}")


def safe(name: str, fn, *args):
    try:
        out = fn(*args)
        return out if isinstance(out, list) else [out]
    except Exception as e:  # a crash is never a pass
        return [check(name, False, f"check crashed: {type(e).__name__}")]


def review(video, ledger_rows, sources, ask_a, ask_b, passed_last_7_days=0, weekly_limit=1, now=None, official_domains=(), file_hashes=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    problem = valid_input(video, sources, passed_last_7_days)
    if problem:
        return {"verdict": "hold", "at": stamp, "checks": [check("input_valid", False, problem)], "held_because": [f"input_valid: {problem}"]}
    rows = ledger_rows if isinstance(ledger_rows, list) else []
    checks = [*safe("numbers_sourced", numbers_sourced, video, sources, official_domains), *safe("footage_and_licences", footage_ok, video, rows, file_hashes),
              *safe("flags", flags_ok, video), check("weekly_limit", passed_last_7_days < weekly_limit, f"{passed_last_7_days} already this week, limit {weekly_limit}"),
              check("two_distinct_reviewers", callable(ask_a) and callable(ask_b) and ask_a is not ask_b, "reviewer A and B must be different functions"),
              model_review("reviewer_a", ask_a, video, sources), model_review("reviewer_b", ask_b, video, sources)]
    failed = [c for c in checks if not c["ok"]]
    return {"verdict": "pass" if not failed else "hold", "at": stamp, "checks": checks, "held_because": [f"{c['name']}: {c['detail']}".strip(": ") for c in failed]}


def write_evidence(folder, result: dict) -> Path:
    p = Path(folder) / "crisis_review.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2))
    os.replace(tmp, p)
    return p
