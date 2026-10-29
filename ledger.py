"""Claim ledger: every specific name, year or quote in a script, with the evidence behind it, saved as claims.json beside the video.

Statuses: VERIFIED (the source article or a web check supports it), PARTIALLY_VERIFIED (stated with a hedge such as "historians believe"),
CONFLICTING (a reliable source says otherwise), UNVERIFIED (nothing found yet). Confidence is a judgement, not proof.
The reviewer writes the ledger on every review, and the fixer records what the web check found, so a person can see at a glance
what was checked, against what, and what is still open.
"""
import hashlib
import json
import re
from pathlib import Path

import reviewer

STATUSES = ("VERIFIED", "PARTIALLY_VERIFIED", "CONFLICTING", "UNVERIFIED")
CONFIDENCE = {"VERIFIED": "high", "PARTIALLY_VERIFIED": "medium", "CONFLICTING": "high", "UNVERIFIED": "low"}


def excerpt(source: str, claim: str, width: int = 170) -> str:
    """The passage of the source around the claim, trimmed to whole words."""
    span = reviewer.claim_span(source, claim)  # the same finder that decided VERIFIED, so a verdict never comes without its passage
    if span is None:
        return ""
    a, b = max(0, span[0] - width // 2), min(len(source), span[1] + width // 2)
    return " ".join(source[a:b].split())


def build(meta: dict, source: str = "") -> list[dict]:
    """One row per specific claim in the narration."""
    verified = set(meta.get("verified_claims", []))
    conflicts = {c["claim"]: c for c in meta.get("conflicting_claims", []) if isinstance(c, dict) and "claim" in c}
    web_urls = [s.removeprefix("Checked against: ") for s in meta.get("sources", []) if str(s).startswith("Checked against: ")]
    article = reviewer.source_title(meta)
    rows = []
    for i, line in enumerate(l["text"] for l in meta.get("lines", [])):
        hedged = bool(reviewer.HEDGES.search(line))
        for rx in reviewer.SPECIFICS:
            m = rx.search(line)
            if not m:
                continue
            claim = m.group(0).strip()
            if claim in conflicts:
                status, url, title, ev, note = "CONFLICTING", (web_urls[:1] or [""])[0], "web check", "", f"A reliable source says: {conflicts[claim].get('fact', 'otherwise')}"
            elif reviewer._in_source(claim, source):
                status, url, title, ev, note = "VERIFIED", f"https://en.wikipedia.org/wiki/{article.replace(' ', '_')}", f"Wikipedia: {article}", excerpt(source, claim), ""
            elif claim in verified:
                status, url, title, ev, note = "VERIFIED", (web_urls[:1] or [""])[0], "web check", "", "supported by a web check (pages are in the video's sources)"
            elif hedged:
                status, url, title, ev, note = "PARTIALLY_VERIFIED", "", "", "", "stated with a hedge in the narration; not found in a source"
            else:
                status, url, title, ev, note = "UNVERIFIED", "", "", "", "not in the source article and not checked on the web yet"
            rows.append({"claim_id": hashlib.sha1(f"{i}:{claim}".encode()).hexdigest()[:8], "line": i, "claim_text": claim, "line_text": line,
                         "source_url": url, "source_title": title, "evidence_excerpt": ev, "source_date": "", "verification_status": status,
                         "confidence": CONFIDENCE[status], "notes": note})
    return rows


def write(folder: Path, meta: dict, source: str = "") -> dict:
    """Save claims.json and return the counts per status."""
    rows = build(meta, source)
    (folder / "claims.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    return {s: sum(1 for r in rows if r["verification_status"] == s) for s in STATUSES}
