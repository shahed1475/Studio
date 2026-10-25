"""The tech channel's script check. It FAILS CLOSED like crisisreview.py: a script passes only when every check holds; unknown facts, a bad input or any doubt means "hold".
Pure logic (no model, no network): `lines` are the script's {"text": ...} lines and `facts` are the dicts githubfacts.fetch_repo returned for the repositories it may talk about.

What it checks, and what it does not:
  - facts known: a repository whose facts are unknown (rate limit, outage, no such repository) may not be used.
  - star counts: a number next to "stars" must be the fetched count (exact, "1.2k" or "1.2 thousand" rounded, or "over N" with N at most the count) and the line must say "as of"; a count written in words ("ten thousand", "thousands of stars") cannot be checked and is held.
  - free / open source: such a claim needs every repository the line names to have a detected open-source licence; with no repository named, nothing may be unlicensed.
  - copied README: no run of 8 words of the README appears in the script.
It does NOT check other numbers, release claims or the meaning of a sentence: the studio's normal reviewer still runs, and a person approves (human_approval)."""
import re

import crisisreview

STARS = re.compile(r"(?:(?P<q>over|more than|at least)\s+)?(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<k>k|m|thousand|million|billion)?\b\s*(?:github\s+)?(?:stars?\b|★)|(?:stars?|★)\s*[:\-]?\s*(?P<n2>\d[\d,]*)", re.I)
UNITS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "billion": 1e9}
WORD_STARS = re.compile(r"(?<![\d.,])(?<![\d.,]\s)\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|dozens?|hundreds?|thousands?|millions?|billions?)\s+(?:(?:of|hundred|thousand|million|billion|and|[a-z]+-[a-z]+)\s+){0,3}?(?:github\s+)?stars\b", re.I)
FREE_CLAIM = re.compile(r"\b(open[- ]source|free software|free and open|free alternative|free to use|free to download|completely free|totally free|free forever)\b", re.I)
NOT_OPEN = {"SSPL-1.0", "BUSL-1.1", "Elastic-2.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-ND-4.0", "PolyForm-Noncommercial-1.0.0"}  # source-available or non-commercial, not open source
COPY_WORDS = 8


def _norm(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _star_ok(m: re.Match, stars) -> bool:
    if not isinstance(stars, int) or isinstance(stars, bool):
        return False
    raw = (m.group("n") or m.group("n2")).replace(",", "")
    try:
        n = float(raw)
    except ValueError:
        return False
    if m.group("k"):
        unit = UNITS[m.group("k").lower()]
        return n in (round(stars / unit, 1), float(round(stars / unit)))
    if m.group("q"):
        return n <= stars
    return n == stars


def _open(f: dict) -> bool:
    return bool(f.get("licensed")) and f.get("license") not in NOT_OPEN


def review(lines, facts) -> dict:
    """{"verdict": "pass" | "hold", "checks": [{name, ok, detail}]}. Every check always runs, so the report shows all the reasons."""
    bad = None
    if not isinstance(lines, list) or not lines or not all(isinstance(l, dict) and isinstance(l.get("text"), str) for l in lines):
        bad = "the script needs a non-empty list of lines with text"
    elif not isinstance(facts, list) or not facts or not all(isinstance(f, dict) and isinstance(f.get("repo"), str) and "/" in f["repo"] for f in facts):
        bad = "the facts need a non-empty list of repository facts"
    if bad:
        return {"verdict": "hold", "checks": [crisisreview.check("input", False, bad)]}
    checks = []
    unknown = [f"{f['repo']} ({f['unknown']})" for f in facts if f.get("unknown")]
    checks.append(crisisreview.check("facts_known", not unknown, "; ".join(unknown)))
    known = [f for f in facts if not f.get("unknown")]
    names = {f["repo"].split("/", 1)[1].lower(): f for f in facts}
    wrong, undated, unlicensed, in_words = [], [], [], []
    for i, l in enumerate(lines, 1):
        text = l["text"]
        in_words += [f"line {i}: {m.group(0).strip()}" for m in WORD_STARS.finditer(text)]
        for m in STARS.finditer(text):
            if not any(_star_ok(m, f.get("stars", {}).get("value")) for f in known):
                wrong.append(f"line {i}: {m.group(0).strip()}")
            if "as of" not in text.lower():
                undated.append(f"line {i}")
        if FREE_CLAIM.search(text):
            named = [f for n, f in names.items() if re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text.lower())]
            culprits = [f["repo"] for f in (named or facts) if not _open(f)]
            if culprits:
                unlicensed.append(f"line {i}: {', '.join(culprits)}")
    checks.append(crisisreview.check("star_counts_match", not wrong, "; ".join(wrong)))
    checks.append(crisisreview.check("star_counts_dated", not undated, "; ".join(undated)))
    checks.append(crisisreview.check("star_counts_in_digits", not in_words, "a star count written in words cannot be checked: " + "; ".join(in_words) if in_words else ""))
    checks.append(crisisreview.check("free_claims_have_an_open_licence", not unlicensed, "; ".join(unlicensed)))
    script = _norm(" ".join(l["text"] for l in lines))
    grams = {" ".join(script[i:i + COPY_WORDS]) for i in range(len(script) - COPY_WORDS + 1)}
    copied = []
    for f in known:
        words = _norm(f.get("readme_untrusted") or "")
        if any(" ".join(words[i:i + COPY_WORDS]) in grams for i in range(len(words) - COPY_WORDS + 1)):
            copied.append(f["repo"])
    checks.append(crisisreview.check("readme_not_copied", not copied, ", ".join(copied)))
    return {"verdict": "pass" if all(c["ok"] for c in checks) else "hold", "checks": checks}
