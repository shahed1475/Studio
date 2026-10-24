"""YouTube rules this channel can break: a sourced rule catalog and the deterministic checks behind it.

Every rule names the official page it comes from, the day it was read, and an honest status (VERIFIED, CONFLICTING, UNVERIFIED). Only verified rules are
enforced; the others are watched. The reviewer runs `checks` with every review, the fixer repairs what it can, and `risk.py` shows when a page a rule
depends on changed after the rule was last verified. Docs: docs/COMPLIANCE.md.
"""
import json
import re

import config

TITLE_MAX, DESCRIPTION_MAX_BYTES, TAGS_MAX = 100, 5000, 500  # developers.google.com/youtube/v3/docs/videos, snippet properties
COPY_WARN, COPY_BLOCK = 0.06, 0.15  # share of the narration's 8-word runs found in the source article; our videos measured 0 to 4.1% on 20 Oct 2026
GRAM = 8
VIDEOS_DOC = "https://developers.google.com/youtube/v3/docs/videos"

RULES = [  # page: the key in newswatch.POLICY_PAGES that watches the source for changes
    {"id": "metadata_valid", "rule": "Title at most 100 characters, description at most 5000 bytes, neither contains < or >, tags at most 500 characters counting commas and the quotes around multi-word tags.",
     "source": VIDEOS_DOC, "page": "API: upload a video", "verified": "2026-10-20", "status": "VERIFIED", "severity": "block", "remedy": "compliance.sanitize"},
    {"id": "title_matches", "rule": "A title or description must deliver what it promises (misleading metadata is a deceptive practice).",
     "source": "https://support.google.com/youtube/answer/2801973", "page": "Spam, deceptive practices and scams", "verified": "2026-10-24", "status": "VERIFIED", "severity": "block", "remedy": "fixer: new title, rewritten description"},
    {"id": "thumbnail_matches", "rule": "A thumbnail must not promise what the video does not deliver.",
     "source": "https://support.google.com/youtube/answer/2801973", "page": "Spam, deceptive practices and scams", "verified": "2026-10-24", "status": "VERIFIED", "severity": "block", "remedy": "fixer: new hook, thumbnails made again"},
    {"id": "originality", "rule": "No reading aloud of text we did not write, no scraped or templated mass-produced content: the narration must be our own words.",
     "source": "https://support.google.com/youtube/answer/1311392", "page": "Monetization policies", "verified": "2026-10-20", "status": "VERIFIED", "severity": "block", "remedy": "fixer: reword the copied lines"},
    {"id": "template_variety", "rule": "Videos must not share one template (openings, endings, structure, titles).",
     "source": "https://support.google.com/youtube/answer/1311392", "page": "Monetization policies", "verified": "2026-10-20", "status": "VERIFIED", "severity": "human", "remedy": "fixer: vary the script"},
    {"id": "ai_disclosure", "rule": "Realistic synthetic content must be disclosed; animation and clearly unrealistic art need not be. Our art is storybook illustration and the upload still sets containsSyntheticMedia.",
     "source": "https://support.google.com/youtube/answer/14328491", "page": "Altered or synthetic content", "verified": "2026-10-20", "status": "VERIFIED", "severity": "info", "remedy": "test guards the art style"},
    {"id": "kids_signals", "rule": "Content clearly directed at children must be set 'made for kids'; a wrong setting can be overridden. We set not-for-kids, so kid-directed wording is flagged.",
     "source": "https://support.google.com/youtube/answer/9527654", "page": "Made for kids", "verified": "2026-10-20", "status": "VERIFIED", "severity": "warn", "remedy": "owner decides"},
    {"id": "api_private_lock", "rule": "Uploads from unverified API projects may be locked private. Search results say yes; the official videos page read on 20 Oct 2026 says they are not restricted.",
     "source": VIDEOS_DOC, "page": "API: upload a video", "verified": "2026-10-20", "status": "CONFLICTING", "severity": "info", "remedy": "safety.check reports a video still private after its slot"},
    {"id": "phone_verification", "rule": "Custom thumbnails and videos over 15 minutes may need a phone-verified channel (third-party guides only).",
     "source": "https://www.youtube.com/verify", "page": None, "verified": "2026-10-20", "status": "UNVERIFIED", "severity": "info", "remedy": "upload keeps going and reports a thumbnail that was refused"},
]


def _c(name: str, ok: bool, detail: str, severity: str = "block") -> dict:
    return {"name": name, "ok": bool(ok), "severity": severity, "detail": detail}


def tags_length(tags: list[str]) -> int:
    """YouTube counts every character, the commas between tags, and the two quotes it puts around a tag that contains a space."""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def _cta(path=None) -> str:
    """One labelled link to the owner's playlist ("cta" in data/playlists.json), for the line before the credits. Empty for a studio without the file."""
    try:
        text = str(json.loads((path or config.ROOT / "data" / "playlists.json").read_text()).get("cta", "")).strip()
    except (OSError, ValueError, AttributeError):
        return ""
    return f"\n\n{text}" if text else ""


def final_description(meta: dict) -> str:
    """The description exactly as it is sent to YouTube: ours, the image credits, the channel's hashtags and the AI narration note."""
    is_doc = meta.get("format") == "doc"
    tags = " ".join(h for h in config.niche()["hashtags"] if not (is_doc and h == "#Shorts"))
    credits = "\n\nFootage and image credits:\n" + "\n".join(meta["credits"]) if meta.get("credits") else ""
    return f"{meta.get('description', '')}{_cta()}{credits}\n\n{tags}\n\nNarration is AI-generated."


def metadata_problems(meta: dict) -> list[str]:
    title, desc, tags = str(meta.get("title", "")), final_description(meta), [str(t) for t in meta.get("tags", [])]
    out = []
    if not title.strip():
        out.append("the title is empty")
    if len(title) > TITLE_MAX:
        out.append(f"the title is {len(title)} characters (limit {TITLE_MAX})")
    if re.search(r"[<>]", title):
        out.append("the title contains < or >")
    if len(desc.encode()) > DESCRIPTION_MAX_BYTES:
        out.append(f"the description is {len(desc.encode())} bytes (limit {DESCRIPTION_MAX_BYTES})")
    if re.search(r"[<>]", desc):
        out.append("the description contains < or >")
    if tags_length(tags) > TAGS_MAX:
        out.append(f"the tags use {tags_length(tags)} characters (limit {TAGS_MAX})")
    return out


def metadata_check(meta: dict) -> dict:
    problems = metadata_problems(meta)
    return _c("metadata_valid", not problems, "; ".join(problems) + " (YouTube rejects the upload)" if problems else "title, description and tags are inside YouTube's limits")


def sanitize(meta: dict) -> list[str]:
    """Repair the metadata problems that can be repaired without changing the meaning. Returns what was changed."""
    changes = []
    for key in ("title", "description"):
        if re.search(r"[<>]", str(meta.get(key, ""))):
            meta[key] = re.sub(r"[<>]", "", meta[key])
            changes.append(f"took < and > out of the {key}")
    if len(meta.get("title", "")) > TITLE_MAX:
        meta["title"] = meta["title"][:TITLE_MAX].rsplit(" ", 1)[0].rstrip(" -:,;")
        changes.append("shortened the title")
    tags = [str(t) for t in meta.get("tags", [])]
    if tags_length(tags) > TAGS_MAX:
        while tags and tags_length(tags) > TAGS_MAX:
            tags.pop()
        meta["tags"] = tags
        changes.append("dropped the last tags that did not fit")
    desc = meta.get("description", "")
    room = DESCRIPTION_MAX_BYTES - (len(final_description(meta).encode()) - len(desc.encode()))  # what is added around ours when it is sent
    if len(desc.encode()) > room:
        head, sep, chapters = desc.partition("\n\nChapters:\n")
        lines = chapters.split("\n") if sep else []
        while len(lines) > 3 and len(("\n".join([head, "", "Chapters:"] + lines)).encode()) > room:
            lines.pop()
        desc = head + (sep + "\n".join(lines) if sep else "")
        if len(desc.encode()) > room:
            desc = desc.encode()[:room - 3].decode("utf-8", "ignore").rstrip() + "..."
        meta["description"] = desc
        changes.append("shortened the description")
    return changes


def _grams(text: str, n: int = GRAM) -> list[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))]


def _overlap(lines: list[str], source: str) -> float:
    mine, theirs = _grams(" ".join(lines)), set(_grams(source))
    return sum(g in theirs for g in mine) / len(mine) if mine else 0.0


def originality(meta: dict, source: str) -> dict:
    """The narration must be our own words: how much of it runs word for word as the source article does."""
    lines = [l["text"] for l in meta.get("lines", [])]
    if not source or len(" ".join(lines).split()) < 50:
        return _c("originality", True, "no source article to compare with")
    share = _overlap(lines, source)
    if share >= COPY_BLOCK:
        return _c("originality", False, f"{share:.0%} of the narration's {GRAM}-word runs are copied from the source article (limit {COPY_BLOCK:.0%})")
    if share >= COPY_WARN:
        return _c("originality", False, f"{share:.0%} of the narration's {GRAM}-word runs are copied from the source article (watch from {COPY_WARN:.0%})", "warn")
    return _c("originality", True, f"{share:.1%} of the narration's {GRAM}-word runs also appear in the source article")


def copied_lines(meta: dict, source: str) -> list[int]:
    """Indexes of the narration lines that contain a run copied from the source."""
    theirs = set(_grams(source))
    return [i for i, l in enumerate(meta.get("lines", [])) if any(g in theirs for g in _grams(l["text"]))]


KIDS = re.compile(r"\b(for kids|kids?|children'?s|nursery|cartoons?|toddlers?|bedtime stories? for (?:kids|children))\b", re.I)


def kids_signals(meta: dict) -> dict:
    text = " ".join([str(meta.get("title", "")), str(meta.get("description", "")), " ".join(map(str, meta.get("tags", [])))])
    found = sorted({m.group(0).lower() for m in KIDS.finditer(text)})
    return _c("kids_signals", not found, f"wording aimed at children ({', '.join(found)}): YouTube may treat the video as made for kids, which turns comments off" if found
              else "nothing in the title, description or tags is aimed at children", "warn")


STOP = {"the", "and", "for", "with", "that", "this", "was", "were", "are", "from", "who", "what", "why", "how", "did", "does", "its", "his", "her", "their", "you", "your", "not", "but"}


def hook_supported(hook: str, text: str) -> bool:
    """At least half of a thumbnail hook's meaningful words (compared by their first five letters) occur in the narration or title."""
    words = [w for w in re.findall(r"[a-z]+", hook.lower()) if len(w) >= 3 and w not in STOP]
    if not words:
        return True
    have = {w[:5] for w in re.findall(r"[a-z]+", text.lower())}
    return sum(w[:5] in have for w in words) / len(words) >= 0.5


def checks(meta: dict, source: str = "") -> list[dict]:
    return [metadata_check(meta), originality(meta, source), kids_signals(meta)]
