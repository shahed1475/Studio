"""The crisis channel's review agent. It FAILS CLOSED: a video passes only when every check holds. Any failed check, any uncertainty (a model error, a malformed answer, two
reviewers who disagree) and any missing evidence means the verdict is "hold" and a person is told. Pure logic: the two model reviewers are passed in as functions, so tests
use mocks and nothing here calls a paid service. Evidence for every verdict is written next to the video (crisis_review.json)."""
import datetime as dt
import json
import os
import re
from pathlib import Path

import assetledger

GRAPHIC = re.compile(r"\b(gore|gory|mutilat\w*|dismember\w*|decapitat\w*|corpses?|bloodbath)\b", re.I)
NUMBER = re.compile(r"\d[\d,.]*")


def check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def numbers_sourced(video: dict, sources: dict) -> dict:
    """Every line with a number must cite claims; each claim needs an official, dated source whose passage contains that number."""
    bad = []
    for i, line in enumerate(video.get("lines", [])):
        nums = NUMBER.findall(line.get("text", ""))
        if not nums:
            continue
        ids = line.get("claims") or []
        if not ids:
            bad.append(f"line {i}: number without a claim")
            continue
        for n in nums:
            n = n.strip(".,")
            ok = any(sources.get(c, {}).get("official") is True and sources[c].get("date") and sources[c].get("url") and n in sources[c].get("passage", "").replace(",", "")
                     for c in ids)
            if not ok:
                bad.append(f"line {i}: '{n}' is not in an official, dated source passage")
    return check("numbers_sourced", not bad, "; ".join(bad[:5]))


def footage_ok(video: dict, ledger_rows: list[dict]) -> dict:
    bad = []
    for f in video.get("footage", []):
        if f.get("real") and not all((f.get("verified") or {}).get(k) for k in ("date", "place", "publisher")):
            bad.append(f"{f.get('file')}: real footage without a verified date, place and publisher")
    files = [f.get("file") for f in video.get("footage", [])] + list(video.get("assets", []))
    bad += assetledger.problems(ledger_rows, [f for f in files if f])
    return check("footage_and_licences", not bad, "; ".join(bad[:5]))


def flags_ok(video: dict) -> list[dict]:
    text = " ".join(l.get("text", "") for l in video.get("lines", []))
    return [check("not_made_for_kids", video.get("made_for_kids") is False), check("ai_content_disclosed", video.get("ai_disclosed") is True),
            check("evergreen_topic", video.get("topic_kind") == "evergreen", "never breaking news"),
            check("context_inside_the_video", any(l.get("role") == "context" for l in video.get("lines", []))),
            check("no_graphic_wording", not GRAPHIC.search(text), GRAPHIC.search(text).group(0) if GRAPHIC.search(text) else "")]


def model_review(name: str, ask, video: dict) -> dict:
    """ask(video) -> {"ok": bool, "issues": [...]}. Anything else, or an error, is uncertainty and counts as a failure."""
    try:
        r = ask(video)
        ok = isinstance(r, dict) and r.get("ok") is True and isinstance(r.get("issues", []), list) and not r.get("issues")
        return check(name, ok, "; ".join(map(str, (r or {}).get("issues", [])))[:300] if isinstance(r, dict) else "malformed answer")
    except Exception as e:
        return check(name, False, f"reviewer failed: {type(e).__name__}")


def review(video: dict, ledger_rows: list[dict], sources: dict, ask_a, ask_b, passed_last_7_days: int = 0, weekly_limit: int = 1, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    checks = [numbers_sourced(video, sources), footage_ok(video, ledger_rows), *flags_ok(video),
              check("weekly_limit", passed_last_7_days < weekly_limit, f"{passed_last_7_days} already this week, limit {weekly_limit}"),
              model_review("reviewer_a", ask_a, video), model_review("reviewer_b", ask_b, video)]
    failed = [c for c in checks if not c["ok"]]
    return {"verdict": "pass" if not failed else "hold", "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "checks": checks, "held_because": [f"{c['name']}: {c['detail']}".strip(": ") for c in failed]}


def write_evidence(folder, result: dict) -> Path:
    p = Path(folder) / "crisis_review.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2))
    os.replace(tmp, p)
    return p
