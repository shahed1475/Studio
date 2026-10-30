"""Topic ideas and video scripts. Models are chosen per job by llm.py; the local Ollama model is the fallback."""
import json
import re

import requests

import config
import llm


def _writer_model() -> str:
    """The model assigned to the writer role when a script is made, recorded so training data can honour that model's licence (trainset.py). A free fallback that
    answered instead is recorded as the assigned model: that errs toward excluding the example, never toward using it."""
    try:
        return str(llm.load_config()["models"].get("script", ""))
    except Exception:
        return ""


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


WORDS_PER_SECOND = 2.17  # measured on our own narration: about 130 words a minute


def short_word_range(lines: int = 11, pause: float | None = None) -> tuple[int, int]:
    """Words a Short's script may have so that the finished video stays inside the Short length target (config/rules.json), once the breath after each line
    is counted. 28 Oct 2026: 14 of 15 Shorts ran over 58 seconds because the script asked for 110 to 135 words and the render added 0.6 s after each line."""
    import editprofile
    import rulesfile

    pause = editprofile.short_pause() if pause is None else pause
    top = rulesfile.get("benchmarks", "shorts_max_seconds")
    hi = int((top - 2 - lines * pause) * WORDS_PER_SECOND)  # 2 seconds of margin for the first and last line
    return max(70, hi - 20), max(90, hi)


def short_prompt(topic: str, grounded: str | None = None) -> str:
    """The Short script prompt, one place for production and the writer bench (writerbench.py)."""
    nc = config.niche()
    lo_words, hi_words = short_word_range()
    src = (
        "- Use ONLY the facts in SOURCES below, in your own words. Add no people, places, dates or details they do not "
        "state; say so plainly when they call something uncertain.\nSOURCES:\n" + grounded + "\n"
    ) if grounded else ""
    return (
        f"Write a YouTube Short script for a US audience.\nTopic: {topic}\nNiche: {nc['name']}\n"
        f"Style: {nc['style']}\n\nRules:\n"
        f"- Tell it as a short story in 10 to 12 lines of 8 to 12 words each, {lo_words} to {hi_words} words in total, never more (it must run under a minute: competitor Shorts that reached 20,000 views ran 51 seconds at the median).\n"
        "- Story arc: a hook that raises a question, the setting, rising tension, the twist or turning point, then the payoff.\n"
        "- Line 1 is the hook: the most startling concrete fact or the central question, in under 12 words, no greeting, never 'imagine' or 'have you ever'. Ask it openly (who, what, where, why or how), never as a yes/no question, and name who or what the story is about so a stranger understands it at once; keep the explanation out of the hook (\"Where did an army of fifty thousand Persian soldiers go?\", not \"Did a sandstorm swallow them?\").\n"
        "- Curiosity: keep the answer back. Each middle line adds ONE new specific fact from SOURCES (a name, a year, a number or a place) that makes the viewer need the next line, and one middle line raises a second, smaller question.\n"
        "- Retell it entirely in your own original words. Never copy sentences from any book, article or film.\n"
        "- If the story is real history or a real mystery, use only well-documented facts and say 'legend says' or 'some historians believe' for anything uncertain. Invent no names, dates or quotes.\n"
        "- Use only stories whose source is public domain (old folk tales, myths, fables, pre-1930 works) or real history.\n"
        "- Only state facts you are sure are true. No invented statistics, prices or quotes. Name who says each disputed claim and when ('Herodotus wrote', 'Kaper argued in 2015'): never present a legend or one scholar's theory as settled fact, and never in the hook (ask it as a question or say 'supposedly').\n"
        "- Where SOURCES say who told the story or how we know it, use that as a curiosity line: how we know it is part of the answer.\n"
        "- Write for the ear, as a lively storyteller who has just found something astonishing: plain American English, short punchy sentences, one idea per line, rhythm that builds; no emojis, no hashtags in narration.\n"
        "- The payoff is the line before the last and it is the strongest specific finding in SOURCES that answers line 1: the newest or best-supported explanation, with who said it and when. Never a vague 'experts doubt it' or 'it remains a mystery'. Only if SOURCES truly give no answer, say exactly what each side claims. Never end on a new question.\n"
        "- The last line is a short invitation to subscribe to the channel for the next story. Say 'subscribe': YouTube has subscribers, not followers, so never 'follow'.\n"
        "- For every line give 'visual': 2 to 3 words to search for a picture of (e.g. 'Knossos palace'); name the real place, person or object.\n"
        f"{src}\n"
        'Return JSON: {"title": "under 70 chars, no clickbait lies", "description": "2 sentences", '
        '"tags": ["..."], "anchors": ["3 to 5 real names at the heart of the story, as in archive image titles"], "lines": [{"text": "...", "visual": "..."}]}'
    
    )


def script(topic: str, grounded: str | None = None) -> dict:
    data = _script_chat(short_prompt(topic, grounded))
    lines = [
        {"text": str(l["text"]).strip(), "visual": str(l.get("visual", "")).strip()}
        for l in data["lines"]
        if str(l.get("text", "")).strip()
    ]
    words = sum(len(l["text"].split()) for l in lines)
    if len(lines) < 9 or words < 85:
        raise ValueError(f"script too thin ({len(lines)} lines, {words} words)")
    lines, _ = subscribe_invitation(lines)
    return {
        "topic": topic, "grounded": bool(grounded), "script_model": _writer_model(),
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
        out = _review_chat(llm.cached(
            "SOURCES:\n" + sources + "\n\n",
            "You are a strict fact-checker. SOURCES is the only truth. List the numbers of narration lines that state a "
            "fact, date, number, place, quote or event that SOURCES do not support or that contradicts SOURCES or another "
            "line. Atmospheric wording without a factual claim is fine.\n\nLINES:\n" + numbered +
            '\n\nReturn JSON: {"unsupported": [numbers]}'
        ))
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
        out = _review_chat(llm.cached(
            "SOURCES:\n" + sources + "\n\n",
            "You are a strict fact-checker. SOURCES is the only truth. List every narration line that states a fact, date, number, place, quote, "
            "name, tradition or event that SOURCES do not support, or that contradicts SOURCES or another line. Knowledge from outside SOURCES counts as "
            "unsupported even when it is true. Atmospheric wording without a factual claim is fine.\n\nLINES:\n" + numbered +
            '\n\nReturn JSON: {"unsupported": [{"n": line number, "why": "one short sentence"}]}'))
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
        got = _script_chat(llm.cached(
            "SOURCES:\n" + sources + "\n\n",
            "Rewrite each flagged narration line so it says only what SOURCES state, in your own words, 16 to 24 words, with a 'visual' (2 to 4 words naming a real "
            "place, person or object in the line). If SOURCES hold no fact that fits the place of that line, return an empty text and it is removed. Add nothing "
            "from outside SOURCES.\n\nFLAGGED LINES:\n" + listing +
            '\n\nReturn JSON: {"lines": [{"n": line number, "text": "...", "visual": "..."}]}'))
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


# YouTube has subscribers, not followers. The Short prompt once asked the writer for "an invitation to follow", and nine Shorts ended "Follow for the next story."
# Only the closing invitation is rewritten: a story line ("the children follow the piper", "Mammy Water will follow") is never touched.
INVITE_CUE = re.compile(r"\b(?:next|more|stor(?:y|ies)|tales?|mysteries|channel|updates?|episodes?)\b", re.I)
INVITE_MAX_WORDS = 30
FOLLOW_ASK = re.compile(
    r"(?P<pre>^|[.!?,;:]\s+|\b(?:and|please|hit|just|then|so|to|do|now)\s+)(?P<word>follow)"
    r"(?:(?P<drop>\s+(?:along|us)\b)|(?P<chan>\s+(?:this|our|the)\s+channel\b))?"
    r"(?=\s*(?:[.!?,;:]|$)|\s+(?:for|so|and|to|if|or)\b)", re.I)


def _subscribe_for_follow(text: str) -> str:
    if len(text.split()) > INVITE_MAX_WORDS or not INVITE_CUE.search(text):
        return text

    def swap(m: re.Match) -> str:
        w = m.group("word")
        word = "SUBSCRIBE" if w.isupper() else "Subscribe" if w[0].isupper() else "subscribe"
        chan = m.group("chan")
        return m.group("pre") + word + (" to" + chan if chan else "")

    return FOLLOW_ASK.sub(swap, text)


def follow_invitation(text: str) -> bool:
    """True when a closing line asks people to 'follow' (a story line that merely uses the word is not an invitation)."""
    return _subscribe_for_follow(text) != text


def subscribe_invitation(lines: list[dict]) -> tuple[list[dict], int]:
    """A Short's closing invitation says 'subscribe', never 'follow'. Returns (lines, changed): only the last line can change, the input is not changed in place, and
    a second pass changes nothing."""
    if not lines:
        return lines, 0
    last = str(lines[-1].get("text", ""))
    fixed = _subscribe_for_follow(last)
    if fixed == last:
        return lines, 0
    return [*lines[:-1], {**lines[-1], "text": fixed}], 1


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
        import seo

        return seo.fix_a_an(t)
    src = str(ch.get("summary", "")).strip() or (lines[0]["text"] if lines else "")
    words = re.sub(r"[^\w' -]", "", src.split(".")[0]).split()
    return " ".join(words[:6]).capitalize() if words else ""


def shape_for(topic: str) -> tuple[int, int]:
    """(chapters, lines per chapter) for this topic: 6 to 9 chapters of 5 to 7 lines, fixed by the topic so a retry keeps it. Videos stop sharing one skeleton,
    which is part of what YouTube's 'repetitive or mass-produced' rule looks at."""
    import hashlib

    h = int(hashlib.md5(topic.lower().encode()).hexdigest(), 16)
    chapters, per = 6 + h % 4, 5 + (h // 7) % 3
    while chapters * per > MAX_DOC_LINES and per > 5:  # about 8 minutes at 140 words a minute: longer videos lost viewers and picture quality (La Llorona, 9:44)
        per -= 1
    while chapters * per > MAX_DOC_LINES and chapters > 6:
        chapters -= 1
    return chapters, per


MAX_DOC_LINES = 58  # about 9 minutes at 138 words a minute with the pauses (30 Oct 2026: the owner asked for 8 to 10; the old cap of 50 made 7.6)
# The owner's shape for a documentary (30 Oct 2026): the hook, then curiosity, then the story, and it finishes with value.
CASE_RULES = ("This is a real case with real victims and possibly living suspects. Use only documented facts and attribute each claim ('police said', 'the court found', 'the report states'). "
              "Never call a named person guilty, the killer or the culprit unless a court did, and then say that a court did; say plainly what is still unproven. No graphic detail of injuries or "
              "bodies and nothing meant to shock. Treat the victim with respect and never speak as the victim. Say once, early, that this is a documentary account of a real case built on the "
              "public record, and say what remains unknown. (YouTube's own rules, read 30 Oct 2026: no shock violence, no realistic simulation of a victim describing their death, documentary context "
              "must be in the video's own audio or pictures.)")


def case_rules(topic: str) -> str:
    """The extra writing rules for a real case or unsolved crime; empty for every other kind of topic."""
    import kinds

    return CASE_RULES if kinds.classify({"topic": topic}) == "case" else ""


DOC_STRUCTURE = (
    "Shape: chapter 1 is the hook: open cold on the strangest fact or the central question, no greeting, no channel name and no 'in this video'. Chapter 2 builds curiosity: in two or "
    "three lines make the viewer a promise (the two or three questions this film will answer, and that by the end they will have a simple way to weigh a claim like this one) and "
    "name what is still unknown. The middle chapters are the story: background and the main competing theories told fairly, each explanation labelled as legend, eyewitness claim, "
    "historical record or scholarly theory, with a new question or turn about every 60 to 90 seconds of narration ('but that is not the strangest part'). One chapter near the end "
    "says plainly what is documented, what is legend and what historians dispute. The LAST chapter gives value: two or three questions the viewer can use to weigh any claim like this "
    "one (who is telling it and how do we know; does the physical evidence match; who gains from the story), each answered with facts already told in the film, never a new fact, "
    "ending on the most reasonable reading of the evidence and one question left open. "
    "The first two lines (about five seconds) must hold the film's central question as a real question that ends in a question mark, and line two must raise the stakes (what is missing, who "
    "was at risk, what does not add up) and promise what the viewer will know by the end. "
    "When the opening is a legend or a disputed claim, frame it as a claim in that same first sentence ('is said to have', 'the legend tells of', 'according to'), never as plain fact. "
)
THIN = re.compile(r"(my|our|the)\s+(sources?|records?)\s+(say|tell|give|offer|have|contain)s?\s+(very\s+)?(little|nothing|almost nothing|few details)|"
                  r"(i|we)\s+(won'?t|will not|cannot|can'?t)\s+invent|my sources", re.I)  # first-person admissions only: "little is known" is honest history


def thin_script(lines: list[dict]) -> bool:
    """True when the narration itself admits its sources have little to say. That is a video nobody should wait for: it is refused before a voice
    and pictures are paid for (the Thunderbird Short said 'I won't invent details about it, because my sources say very little')."""
    return any(THIN.search(l.get("text", "")) for l in lines)


def remove_lines(lines: list[dict], chapters: list[dict], drop: set[int]) -> tuple[list[dict], list[dict]]:
    """The script without the lines at these indexes; each chapter's start_line moves up by the number of removed lines before it."""
    kept = [l for i, l in enumerate(lines) if i not in drop]
    moved = []
    for n, c in enumerate(chapters):
        end = chapters[n + 1]["start_line"] if n + 1 < len(chapters) else len(lines)
        if all(i in drop for i in range(c["start_line"], end)):
            continue  # every line of this chapter was removed
        moved.append({**c, "start_line": c["start_line"] - sum(1 for d in drop if d < c["start_line"])})
    return kept, moved


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
    case = case_rules(topic)
    if case:
        rules += "\n" + case  # an unsolved crime or case: documented facts, attribution, nothing graphic, no accusation (the outline and every chapter share these rules)
    outline = _script_chat(
        f"Plan an 8 to 10 minute YouTube documentary for a US audience.\nTopic: {topic}\nChannel: {nc['name']}\n"
        f"Style: {nc['style']}\n{rules}\n\nGive {n_chapters} chapters in story order. {DOC_STRUCTURE}"
        "The first sentence is the strangest fact or the central question. Use only what the sources support. "
        "End on the story: no thanks, no subscribe line. "
        'Return JSON: {"title": "under 70 chars", "description": "3 sentences", '
        '"tags": ["..."], "anchors": ["3 to 6 real names of the places, people and things at the heart of this '
        'story, as they appear in archive image titles"], "chapters": [{"title": "...", "summary": "one sentence of what this chapter covers"}]}'
    )
    chapters, lines, told = [], [], ""
    for n, ch in enumerate(outline["chapters"][:n_chapters], 1):
        for _ in range(3):
            part = _script_chat(llm.cached(
                f"You are narrating a documentary titled '{outline['title']}' about: {topic}.\n"
                f"Style: {nc['style']}\n{rules}\n\n",  # the same for every chapter, source article included: sent once as a cache block
                f"Story so far: {told or '(nothing yet, this is the opening)'}\n\n"
                f"Write chapter {n}: '{ch.get('title', '')}' - {ch.get('summary', '')}\n"
                f"Write {n_lines} narration lines of 16 to 24 words each. Do not repeat earlier chapters: a name, date or event already told in the story so far is never told again, "
                "and an opening only teases its payoff in one line, saving the details for the chapter where they belong. "
                "Never write chapter numbers, headings or phrases like 'this chapter' in a line: every line is story the listener hears. "
                "For every line give 'visual': 2 to 4 words to search an archival image for (a real place, person, "
                "object, map or artwork named in the line; always include the name of the place or subject, for example "
                "'Hamelin church', never just 'old manuscript'). "
                'Return JSON: {"lines": [{"text": "...", "visual": "..."}]}'
            ))
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
        "topic": topic, "format": "doc", "grounded": bool(facts or grounded), "script_model": _writer_model(),
        "anchors": [str(a).strip() for a in outline.get("anchors", []) if str(a).strip()][:6],
        "title": str(outline["title"]).strip()[:95],
        "description": str(outline.get("description", "")).strip(),
        "tags": [str(t) for t in outline.get("tags", [])][:15],
        "lines": lines, "chapters": chapters,
    }
