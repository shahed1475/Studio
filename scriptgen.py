"""Topic ideas and video scripts. Models are chosen per job by llm.py; the local Ollama model is the fallback."""
import json
import re

import requests

import config
import llm


def _ollama_chat(prompt: str) -> dict:
    r = requests.post(
        f"{config.OLLAMA_URL}/api/chat",
        json={
            "model": config.MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0.8},
        },
        timeout=600,
    )
    r.raise_for_status()
    text = r.json()["message"]["content"]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return json.loads(text)


def _chat(prompt: str, role: str = "cheap") -> dict:
    return llm.chat(prompt, role, fallback=_ollama_chat)


def _script_chat(prompt: str) -> dict:
    """Writing where facts and storytelling matter."""
    return _chat(prompt, "script")


def _review_chat(prompt: str) -> dict:
    """Fact-check: a different model from the writer."""
    return _chat(prompt, "review")


def ideas(n: int = 10) -> list[str]:
    nc = config.niche()
    data = _chat(
        f"You plan YouTube Shorts for a US audience.\nNiche: {nc['name']}\nAudience: {nc['audience']}\n"
        f"Angle: {nc['channel_angle']}\n\nGive {n} specific, different story topics: "
        + ("public-domain folk tales, fables and legends from around the world, or well-documented historical events and mysteries that have a surprising twist. "
           if config._owner_niche() else "well-documented subjects of this niche that each have an encyclopedia article, each with a surprising or little-known angle. ")
        + f"Never pick modern copyrighted stories or characters. Return JSON: {{\"topics\": [\"...\"]}}"
    )
    return [t.strip() for t in data["topics"] if isinstance(t, str) and t.strip()]


def script(topic: str, grounded: str | None = None) -> dict:
    nc = config.niche()
    src = (
        "- Use ONLY the facts in SOURCES below, in your own words. Add no people, places, dates or details they do not "
        "state; say so plainly when they call something uncertain.\nSOURCES:\n" + grounded + "\n"
    ) if grounded else ""
    data = _script_chat(
        f"Write a YouTube Short script for a US audience.\nTopic: {topic}\nNiche: {nc['name']}\n"
        f"Style: {nc['style']}\n\nRules:\n"
        "- Tell it as a short story in 12 to 14 lines of 10 to 16 words each, 140 to 180 words in total.\n"
        "- Story arc: a hook that raises a question, the setting, rising tension, the twist or turning point, a closing line that lingers.\n"
        "- Line 1 is a hook that creates curiosity in under 12 words.\n"
        "- Retell it entirely in your own original words. Never copy sentences from any book, article or film.\n"
        "- If the story is real history or a real mystery, use only well-documented facts and say 'legend says' or 'some historians believe' for anything uncertain. Invent no names, dates or quotes.\n"
        "- Use only stories whose source is public domain (old folk tales, myths, fables, pre-1930 works) or real history.\n"
        "- Only state facts you are sure are true. No invented statistics, prices or quotes.\n"
        "- Plain American English, short sentences, no emojis, no hashtags in narration.\n"
        "- The last line is a short invitation to follow for the next story.\n"
        "- For every line give 'visual': 2 to 3 words to search for a picture of (e.g. 'Knossos palace'); name the real place, person or object.\n"
        f"{src}\n"
        'Return JSON: {"title": "under 70 chars, no clickbait lies", "description": "2 sentences", '
        '"tags": ["..."], "anchors": ["3 to 5 real names at the heart of the story, as in archive image titles"], "lines": [{"text": "...", "visual": "..."}]}'
    )
    lines = [
        {"text": str(l["text"]).strip(), "visual": str(l.get("visual", "")).strip()}
        for l in data["lines"]
        if str(l.get("text", "")).strip()
    ]
    words = sum(len(l["text"].split()) for l in lines)
    if len(lines) < 9 or words < 85:
        raise ValueError(f"script too thin ({len(lines)} lines, {words} words)")
    return {
        "topic": topic, "grounded": bool(grounded),
        "anchors": [str(a).strip() for a in data.get("anchors", []) if str(a).strip()][:5],
        "title": str(data["title"]).strip()[:95],
        "description": str(data.get("description", "")).strip(),
        "tags": [str(t) for t in data.get("tags", [])][:15],
        "lines": lines,
    }


def support_filter(lines: list[dict], chapters: list[dict], sources: str) -> tuple[list[dict], list[dict]]:
    """Drop narration lines the source article does not support; keep everything if the judge condemns too much."""
    numbered = "\n".join(f"{i}: {l['text']}" for i, l in enumerate(lines))
    try:
        out = _review_chat(
            "You are a strict fact-checker. SOURCES is the only truth. List the numbers of narration lines that state a "
            "fact, date, number, place, quote or event that SOURCES do not support or that contradicts SOURCES or another "
            "line. Atmospheric wording without a factual claim is fine.\nSOURCES:\n" + sources + "\n\nLINES:\n" + numbered +
            '\n\nReturn JSON: {"unsupported": [numbers]}'
        )
        bad = {int(n) for n in out.get("unsupported", []) if str(n).lstrip("-").isdigit() and 0 <= int(n) < len(lines)}
    except Exception:
        return lines, chapters
    if not bad or len(bad) > len(lines) * 0.25:
        return lines, chapters
    return _drop_lines(lines, chapters, bad)


MOST_UNSUPPORTED = 0.4  # a first judgement flagging more of the script than this means the writer ignored the sources: write it again, do not patch it
REVISE_ROUNDS = 2


def unsupported(lines: list[dict], sources: str) -> dict[int, str]:
    """Line number -> why, for every narration line stating something SOURCES do not support. A judge that cannot answer raises: an unchecked script is not passed on."""
    numbered = "\n".join(f"{i}: {l['text']}" for i, l in enumerate(lines))
    try:
        out = _review_chat(
            "You are a strict fact-checker. SOURCES is the only truth. List every narration line that states a fact, date, number, place, quote, "
            "name, tradition or event that SOURCES do not support, or that contradicts SOURCES or another line. Knowledge from outside SOURCES counts as "
            "unsupported even when it is true. Atmospheric wording without a factual claim is fine.\nSOURCES:\n" + sources + "\n\nLINES:\n" + numbered +
            '\n\nReturn JSON: {"unsupported": [{"n": line number, "why": "one short sentence"}]}')
        found = {}
        for item in out.get("unsupported", []):
            n = item.get("n") if isinstance(item, dict) else item
            if str(n).lstrip("-").isdigit() and 0 <= int(n) < len(lines):
                found[int(n)] = str(item.get("why", "")) if isinstance(item, dict) else ""
        return found
    except Exception as e:
        raise ValueError(f"the script could not be fact-checked ({type(e).__name__})") from e


def verify_and_revise(lines: list[dict], chapters: list[dict], sources: str, rounds: int = REVISE_ROUNDS) -> tuple[list[dict], list[dict]]:
    """Draft, check against the sources, rewrite what is flagged from the sources only, check again (chain-of-verification: the judge sees the sources,
    not the writer's reasoning). A line the writer cannot support is dropped. A script the sources mostly do not support is refused outright, so
    the writer is asked again before any voice or picture is paid for."""
    lines = [dict(l) for l in lines]
    for r in range(rounds + 1):
        bad = unsupported(lines, sources)
        if not bad:
            return lines, chapters
        if r == 0 and len(bad) > len(lines) * MOST_UNSUPPORTED:
            raise ValueError(f"the sources do not support {len(bad)} of {len(lines)} lines")
        if r == rounds:
            return _drop_lines(lines, chapters, set(bad))
        listing = "\n".join(f"{n}: {lines[n]['text']}  (problem: {bad[n] or 'not in SOURCES'})" for n in sorted(bad))
        got = _script_chat(
            "Rewrite each flagged narration line so it says only what SOURCES state, in your own words, 16 to 24 words, with a 'visual' (2 to 4 words naming a real "
            "place, person or object in the line). If SOURCES hold no fact that fits the place of that line, return an empty text and it is removed. Add nothing "
            "from outside SOURCES.\nSOURCES:\n" + sources + "\n\nFLAGGED LINES:\n" + listing +
            '\n\nReturn JSON: {"lines": [{"n": line number, "text": "...", "visual": "..."}]}')
        drop = set(bad)  # a flagged line the writer did not answer is not kept either
        for item in got.get("lines", []) if isinstance(got, dict) else []:
            n, text = item.get("n"), str(item.get("text", "")).strip()
            if str(n).lstrip("-").isdigit() and int(n) in bad and text and text != lines[int(n)]["text"]:
                lines[int(n)] = {"text": text, "visual": str(item.get("visual", "")).strip() or lines[int(n)].get("visual", "")}
                drop.discard(int(n))
        if drop:
            lines, chapters = _drop_lines(lines, chapters, drop)
    return lines, chapters


_NUMBER = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
LABEL = re.compile(rf"^\s*(?:chapter|part|section)\s+{_NUMBER}\b\s*([:.)\u2013\u2014-]?)\s*", re.I)
MIN_STRIPPED_WORDS = 6  # what is left after a "Chapter 5:" prefix must still be a real sentence, else the line was only a heading


def _drop_lines(lines: list[dict], chapters: list[dict], bad: set[int]) -> tuple[list[dict], list[dict]]:
    """Remove the lines at these indexes; each chapter starts on its first kept line, and a chapter left with no line is left out."""
    keep = [i for i in range(len(lines)) if i not in bad]
    new_index = {old: new for new, old in enumerate(keep)}
    fixed, seen = [], set()
    for k, c in enumerate(chapters):
        end = chapters[k + 1]["start_line"] if k + 1 < len(chapters) else len(lines)
        start = next((new_index[i] for i in range(c["start_line"], end) if i in new_index), None)  # only lines of this chapter, never the next one's
        if start is not None and start not in seen:
            seen.add(start)
            fixed.append({**c, "start_line": start})
    return [lines[i] for i in keep], fixed


def label_of(text: str) -> str | None:
    """The 'Chapter 5' style label a narration line starts with, or None."""
    m = LABEL.match(text)
    return m.group(0).strip(" :.)-\u2013\u2014") if m else None


def strip_labels(lines: list[dict], chapters: list[dict]) -> tuple[list[dict], list[dict], int]:
    """The writer sometimes narrates its own outline ('Chapter 5: The Temples of Apollo', 'Chapter 6 examines ...'). A 'Chapter N:' prefix on a real
    sentence is cut off; a line that is only a heading, or that talks about the chapter instead of the story, is dropped. Returns (lines, chapters, lines changed)."""
    out, bad, changed = [], set(), 0
    for i, l in enumerate(lines):
        m = LABEL.match(l["text"])
        if not m:
            out.append(l)
            continue
        rest = l["text"][m.end():].strip()
        if m.group(1) and len(rest.split()) >= MIN_STRIPPED_WORDS:
            out.append({**l, "text": rest[:1].upper() + rest[1:]})
        else:
            out.append(l)
            bad.add(i)
        changed += 1
    kept, fixed = _drop_lines(out, chapters, bad)
    return kept, fixed, changed


def country_ideas(country: str, signals: list[str], n: int = 4) -> list[str]:
    seen = "\n".join(f"- {s}" for s in signals) or "(no live data)"
    data = _chat(
        f"You plan original YouTube story videos for a US audience.\nCountry to draw from: {country}\n"
        f"Popular recent video titles there (for theme signals only; never copy them):\n{seen}\n\n"
        f"Suggest {n} different story topics from {country}: public-domain folk tales and legends, or "
        "well-documented history and mysteries with a surprising twist. Not modern copyrighted stories. "
        "Give each topic as a short subject name of 2 to 8 words, like 'The Jersey Devil' or 'Mohenjo-daro', that has its own encyclopedia article: "
        "no description, no dates, no details after the name. Prefer subjects many people already know or search for (famous legends, "
        "mysteries, ancient places and figures) over obscure ones. "
        'Return JSON: {"topics": ["..."]}'
    )
    return [t.strip() for t in data["topics"] if isinstance(t, str) and t.strip()]


def chapter_title(ch: dict, lines: list[dict]) -> str:
    """The model's chapter title, or (when it left it empty) the first words of the chapter's summary or opening line, never a 'Part 3' placeholder."""
    t = str(ch.get("title", "")).strip()
    if t:
        return t
    src = str(ch.get("summary", "")).strip() or (lines[0]["text"] if lines else "")
    words = re.sub(r"[^\w' -]", "", src.split(".")[0]).split()
    return " ".join(words[:6]).capitalize() if words else ""


def shape_for(topic: str) -> tuple[int, int]:
    """(chapters, lines per chapter) for this topic: 6 to 9 chapters of 5 to 7 lines, fixed by the topic so a retry keeps it. Videos stop sharing one skeleton,
    which is part of what YouTube's 'repetitive or mass-produced' rule looks at."""
    import hashlib

    h = int(hashlib.md5(topic.lower().encode()).hexdigest(), 16)
    return 6 + h % 4, 5 + (h // 7) % 3


def doc_script(topic: str, facts: str | None = None, grounded: str | None = None) -> dict:
    """Outline first, then one request per chapter: small local models undershoot a one-shot long script.

    With `facts` (news explainers) or `grounded` (a source article for a story) the script may use ONLY those facts."""
    nc = dict(config.niche())
    n_chapters, n_lines = shape_for(topic)
    rules = (
        "Retell it in your own original words and never copy sentences from any source. Use only well-documented "
        "facts or public-domain legends; say 'legend says' or 'historians disagree' for anything uncertain. "
        "Invent no names, dates, numbers or quotes."
    )
    if facts:
        rules = (
            "Use ONLY the facts in SOURCES below, in your own words. Add no other names, dates, numbers, quotes or "
            "claims; if the sources do not say it, leave it out. Say what changed, why it matters to YouTube creators "
            "and what to do about it.\nSOURCES:\n" + facts
        )
        nc["style"] = "clear, calm and practical, like a trusted friend explaining a safety update"
    elif grounded:
        rules = (
            "Use ONLY the facts in SOURCES below, retold in your own original words (never copy sentences). Add no "
            "people, places, dates, numbers, rituals, quotes or events that SOURCES do not state; if SOURCES call "
            "something uncertain, say so plainly. Every line must tell the listener something specific from SOURCES, "
            "never filler. Say 'historians disagree' at most once in the whole script and never repeat a sentence "
            "opening. Invent no details to make it more dramatic.\nSOURCES:\n" + grounded
        )
    outline = _script_chat(
        f"Plan a 6 to 8 minute YouTube documentary for a US audience.\nTopic: {topic}\nChannel: {nc['name']}\n"
        f"Style: {nc['style']}\n{rules}\n\nGive {n_chapters} chapters in story order: chapter 1 opens with a hook that raises "
        "the central question, the middle chapters cover background and the main competing theories fairly, the "
        'last has a closing thought. Return JSON: {"title": "under 70 chars", "description": "3 sentences", '
        '"tags": ["..."], "anchors": ["3 to 6 real names of the places, people and things at the heart of this '
        'story, as they appear in archive image titles"], "chapters": [{"title": "...", "summary": "one sentence of what this chapter covers"}]}'
    )
    chapters, lines, told = [], [], ""
    for n, ch in enumerate(outline["chapters"][:n_chapters], 1):
        for _ in range(3):
            part = _script_chat(
                f"You are narrating a documentary titled '{outline['title']}' about: {topic}.\n"
                f"Style: {nc['style']}\n{rules}\n\nStory so far: {told or '(nothing yet, this is the opening)'}\n\n"
                f"Write chapter {n}: '{ch.get('title', '')}' - {ch.get('summary', '')}\n"
                f"Write {n_lines} narration lines of 16 to 24 words each. Do not repeat earlier chapters: a name, date or event already told in the story so far is never told again, "
                "and an opening only teases its payoff in one line, saving the details for the chapter where they belong. "
                "Never write chapter numbers, headings or phrases like 'this chapter' in a line: every line is story the listener hears. "
                "For every line give 'visual': 2 to 4 words to search an archival image for (a real place, person, "
                "object, map or artwork named in the line; always include the name of the place or subject, for example "
                "'Hamelin church', never just 'old manuscript'). "
                'Return JSON: {"lines": [{"text": "...", "visual": "..."}]}'
            )
            got = [
                {"text": str(l["text"]).strip(), "visual": str(l.get("visual", "")).strip()}
                for l in part.get("lines", []) if str(l.get("text", "")).strip()
            ]
            if sum(len(l["text"].split()) for l in got) >= 70:
                break
        else:
            continue
        chapters.append({"title": chapter_title(ch, got), "start_line": len(lines)})
        lines += got
        told += f" Chapter {n} ({ch.get('title', '')}): {ch.get('summary', '')}"
    lines, chapters, _ = strip_labels(lines, chapters)  # the writer must not narrate its own outline
    if grounded:
        lines, chapters = verify_and_revise(lines, chapters, grounded)
    words = sum(len(l["text"].split()) for l in lines)
    if len(chapters) < 5 or words < 400:
        raise ValueError(f"documentary too thin ({len(chapters)} chapters, {words} words)")
    return {
        "topic": topic, "format": "doc", "grounded": bool(facts or grounded),
        "anchors": [str(a).strip() for a in outline.get("anchors", []) if str(a).strip()][:6],
        "title": str(outline["title"]).strip()[:95],
        "description": str(outline.get("description", "")).strip(),
        "tags": [str(t) for t in outline.get("tags", [])][:15],
        "lines": lines, "chapters": chapters,
    }
