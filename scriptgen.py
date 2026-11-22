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


def _chat(prompt: str, role: str = "cheap", strict: bool = False, avoid=None) -> dict:
    return llm.chat(prompt, role, fallback=_ollama_chat, strict=strict, **({"avoid": avoid} if avoid else {}))


def _script_chat(prompt: str) -> dict:
    """Writing where facts and storytelling matter."""
    return _chat(prompt, "script")


def _review_chat(prompt: str, avoid=None) -> dict:
    """Fact-check: a different model from the writer. Every caller is a judge prompt whose larger number, true flag or longer list means a worse video, so two free models may answer it (llm.strictest).
    `avoid`: the writers recorded with the video, for a review in another process than the writing (the writers of this process are avoided anyway)."""
    return _chat(prompt, "review", strict=True, avoid=avoid)


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
    case = case_rules(topic)
    src += f"- {case}\n" if case else ""  # a real case or unsolved crime: documented facts, attribution, nothing graphic, no accusation
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


def script(topic: str, grounded: str | None = None, note: str = "") -> dict:
    """`note` is what went wrong with the last try (run._cmd_make): free writers undershoot the word budget by about 15 percent and a retry that repeats the same prompt repeats the mistake."""
    base = short_prompt(topic, grounded) + (f"\n{note}\n" if note else "")
    llm.begin_script()
    data = _script_chat(base)
    if not case_rules(topic) and case_rules(topic, title=str(data.get("title", "")), anchors=data.get("anchors") or []):
        data = _script_chat(base + "\n" + CASE_RULES)  # the title shows it is a real case: written again once, with the rules
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
        "topic": topic, "grounded": bool(grounded), "script_model": _writer_model(), "script_writers": llm.writers(),
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


CHECK_CHUNK = 30  # lines per fact-check request (20 Nov 2026: a 90-line film in one request made the free judges' answers run past their output limit again and again)


def unsupported(lines: list[dict], sources: str) -> dict[int, str]:
    """Line number -> why, for every narration line stating something SOURCES do not support. A judge that cannot answer raises: an unchecked script is not passed on.
    A long script is checked CHECK_CHUNK lines at a time against the same SOURCES (one cached block): each judge's answer stays inside its output limit. Within a part
    the judge also looks for lines that contradict each other; across parts that is left to the AI review of the finished video."""
    found: dict[int, str] = {}
    for start in range(0, len(lines), CHECK_CHUNK):
        part = lines[start:start + CHECK_CHUNK]
        numbered = "\n".join(f"{start + i}: {l['text']}" for i, l in enumerate(part))
        span = f" (lines {start} to {start + len(part) - 1} of a {len(lines)}-line script)" if len(lines) > CHECK_CHUNK else ""
        asked_at = __import__("time").time()
        try:
            out = _review_chat(llm.cached(
                "SOURCES:\n" + sources + "\n\n",
                "You are a strict fact-checker. SOURCES is the only truth. List every narration line that states a fact, date, number, place, quote, "
                "name, tradition or event that SOURCES do not support, or that contradicts SOURCES or another line. Knowledge from outside SOURCES counts as "
                f"unsupported even when it is true. Atmospheric wording without a factual claim is fine.\n\nLINES{span}:\n" + numbered +
                '\n\nReturn JSON: {"unsupported": [{"n": line number, "why": "one short sentence"}]}'))
        except Exception as e:
            tried = llm.attempts_since(asked_at)  # which judges were asked and how each failed, so the log says why (22 Nov 2026: it said only ModelUnavailable)
            raise ValueError(f"the script could not be fact-checked ({type(e).__name__}{'; judges: ' + tried if tried else ''})") from e
        if not isinstance(out, dict) or not isinstance(out.get("unsupported"), list):  # a reply without the verdict is no verdict: it never passes as "nothing
            raise ValueError("the script could not be fact-checked (the judges' reply had no 'unsupported' list)")  # unsupported" (22 Nov 2026 audit)
        for item in out["unsupported"]:
            n = item.get("n") if isinstance(item, dict) else item
            if str(n).lstrip("-").isdigit() and start <= int(n) < start + len(part):
                found[int(n)] = str(item.get("why", "")) if isinstance(item, dict) else ""
    return found


def rewrite_words(lines: list[dict]) -> tuple[int, int]:
    """Words for a rewritten line: the script's own typical line length (at least 16 to 24, the Short and 8 to 10 minute size), so a long film's 30 to 39 word lines are
    not cut to 24 each time a judge flags one (20 Nov 2026)."""
    counts = sorted(len(str(l.get("text", "")).split()) for l in lines) or [20]
    mid = counts[len(counts) // 2]
    return max(16, mid - 4), max(24, mid + 4)


JUDGE_WAITS = (120, 300)  # seconds to wait for a free judge before checking the SAME draft again


def checked(lines: list[dict], chapters: list[dict], sources: str, sleep=None) -> tuple[list[dict], list[dict]]:
    """verify_and_revise, patient with judges: when no free judge can answer, wait and check the same draft again instead of throwing it away (20 Nov 2026: a
    finished 90-line draft, about 40 writing requests, was discarded after 39 minutes because the judges were busy, and the writer started over). The draft is still
    never passed on unchecked: after the waits the error stands."""
    import time

    sleep = sleep or time.sleep
    for wait in (*JUDGE_WAITS, None):
        try:
            return verify_and_revise(lines, chapters, sources)
        except ValueError as e:
            if "could not be fact-checked" not in str(e) or wait is None:
                raise
            print(f"  no free judge could answer ({e}); checking the same draft again in {wait} s")
            sleep(wait)
    raise ValueError("the script could not be fact-checked")


def verify_and_revise(lines: list[dict], chapters: list[dict], sources: str, rounds: int = REVISE_ROUNDS, patient: bool | None = None) -> tuple[list[dict], list[dict]]:
    """Draft, check against the sources, rewrite what is flagged from the sources only, check again (chain-of-verification: the judge sees the sources,
    not the writer's reasoning). A line the writer cannot support is dropped. A script the sources mostly do not support is refused outright, so
    the writer is asked again before any voice or picture is paid for."""
    lines = [dict(l) for l in lines]
    patient = llm.free_only() if patient is None else patient  # free judges are noisy (17 Nov 2026: 48 of 56 lines flagged, script discarded): the flagged lines are rewritten from the sources first and the refusal comes after the rewrites
    for r in range(rounds + 1):
        bad = unsupported(lines, sources)
        if not bad:
            return lines, chapters
        if r == 0 and not patient and len(bad) > len(lines) * MOST_UNSUPPORTED:
            raise ValueError(f"the sources do not support {len(bad)} of {len(lines)} lines")
        if r == rounds:
            if patient and len(bad) > len(lines) * MOST_UNSUPPORTED:
                raise ValueError(f"the sources do not support {len(bad)} of {len(lines)} lines")
            return _drop_lines(lines, chapters, set(bad))
        listing = "\n".join(f"{n}: {lines[n]['text']}  (problem: {bad[n] or 'not in SOURCES'})" for n in sorted(bad))
        lo, hi = rewrite_words(lines)
        got = _script_chat(llm.cached(
            "SOURCES:\n" + sources + "\n\n",
            f"Rewrite each flagged narration line so it says only what SOURCES state, in your own words, {lo} to {hi} words, with a 'visual' (2 to 4 words naming a real "
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


# the story-shape words of our own prompts, narrated as a heading: "The payoff: they are twin storm gods..." (21 Nov 2026, Raijin and Fujin Short)
STRUCTURE_LABEL = re.compile(r"^\s*(?:the\s+)?(?:hook|cold open|setting|rising tension|twist|turning point|payoff|pay-off|climax|resolution|conclusion|"
                             r"closing value|curiosity|story|outro|intro(?:duction)?)\s*[:\u2013\u2014-]\s+", re.I)


def label_of(text: str) -> str | None:
    """The 'Chapter 5' or 'The payoff:' style label a narration line starts with, or None."""
    m = LABEL.match(text) or STRUCTURE_LABEL.match(text)
    return m.group(0).strip(" :.)-\u2013\u2014") if m else None


def strip_labels(lines: list[dict], chapters: list[dict]) -> tuple[list[dict], list[dict], int]:
    """The writer sometimes narrates its own outline ('Chapter 5: The Temples of Apollo', 'Chapter 6 examines ...'). A 'Chapter N:' prefix on a real
    sentence is cut off; a line that is only a heading, or that talks about the chapter instead of the story, is dropped. Returns (lines, chapters, lines changed)."""
    out, bad, changed = [], set(), 0
    for i, l in enumerate(lines):
        m = LABEL.match(l["text"]) or STRUCTURE_LABEL.match(l["text"])
        if not m:
            out.append(l)
            continue
        rest = l["text"][m.end():].strip()
        separated = m.re is STRUCTURE_LABEL or bool(m.group(1))  # a story-shape label always has its colon or dash
        if separated and len(rest.split()) >= MIN_STRIPPED_WORDS:
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


# measured on our films: 1,150 words made about 9 minutes (many short lines, a pause after each). A long film joins short lines, so it has fewer pauses:
# the 81-line Seven Sleepers film (21 Nov 2026) was 2,839 words in 1,148.7 s = 148.3 words a minute, and the old rate (127.8) had let its script pass
# the 20-minute minimum while the film ran 19.1 minutes. The long films' measured rate is used.
DOC_WORDS_PER_MINUTE = 2839 / (1148.7 / 60)  # long films (15 minutes and more)
SHORT_DOC_WORDS_PER_MINUTE = 1150 / 9  # 8 to 10 minute films: many short lines, a pause after each


def words_per_minute(minutes: float) -> float:
    """The measured narration pace for a film of this length (the pace depends on how many lines, so on the length)."""
    return SHORT_DOC_WORDS_PER_MINUTE if minutes < 15 else DOC_WORDS_PER_MINUTE
LINE_CAP = 100  # one picture per narration line: about one free Cloudflare day of drawings (58 to 86) plus the real photos found first


def doc_budget(lo_min: float, hi_min: float) -> dict:
    """Lines, words and shape for a documentary of lo_min to hi_min minutes (the owner's rules.json long_min_minutes and long_max_minutes, the same pair
    the reviewer's doc_length warning reads). Calibrated so 8 to 10 minutes gives exactly the numbers used from 30 Oct to 20 Nov 2026 (42 to 58 lines,
    1,150 words, 6 to 9 chapters of 5 to 7 lines, lines of at most 30 words). A longer film gets more chapters and longer lines rather than more
    pictures than a free day can draw: 20 to 26 minutes is 84 to 100 lines of about 30 to 39 words, 10 to 13 chapters, about 2,940 words."""
    words = round((lo_min + hi_min) / 2 * words_per_minute(lo_min))
    max_lines = min(LINE_CAP, round(hi_min * 5.8))
    min_lines = min(round(lo_min * 5.25), max_lines - 16)
    long_film = max_lines > 64
    return {"min_lines": min_lines, "max_lines": max_lines, "words": words, "chapters": (10, 13) if long_film else (6, 9),
            "per": (7, 9) if long_film else (5, 7), "line_words_max": 44 if long_film else 30}


def _owner_minutes() -> tuple[float, float]:
    """The owner's documentary length in minutes (rules.json benchmarks, through rulesfile so an approved change counts). Each job is a new process,
    so a changed setting reaches the next video without a restart."""
    try:
        import rulesfile

        lo, hi = float(rulesfile.get("benchmarks", "long_min_minutes")), float(rulesfile.get("benchmarks", "long_max_minutes"))
        if 1 <= lo < hi <= 60:
            return lo, hi
    except Exception:
        pass
    return 8.0, 10.0


DOC_MINUTES = _owner_minutes()
_BUDGET = doc_budget(*DOC_MINUTES)
MIN_DOC_LINES, MAX_DOC_LINES, DOC_WORDS_TARGET = _BUDGET["min_lines"], _BUDGET["max_lines"], _BUDGET["words"]
DOC_CHAPTERS, DOC_PER, LINE_WORDS_MAX = _BUDGET["chapters"], _BUDGET["per"], _BUDGET["line_words_max"]


def shape_for(topic: str) -> tuple[int, int]:
    """(chapters, lines per chapter) for this topic, inside DOC_CHAPTERS and DOC_PER, fixed by the topic so a retry keeps it. Videos stop sharing one skeleton,
    which is part of what YouTube's 'repetitive or mass-produced' rule looks at."""
    import hashlib

    h = int(hashlib.md5(topic.lower().encode()).hexdigest(), 16)
    (c0, c1), (p0, p1) = DOC_CHAPTERS, DOC_PER
    chapters, per = c0 + h % (c1 - c0 + 1), p0 + (h // 7) % (p1 - p0 + 1)
    per = min(p1, max(per, -(-MIN_DOC_LINES // chapters)))  # 11 Nov 2026: a 30-line shape made the Antikythera film 7.2 minutes against the owner's 8 to 10
    while chapters * per > MAX_DOC_LINES and per > p0:
        per -= 1
    while chapters * per > MAX_DOC_LINES and chapters > c0:
        chapters -= 1
    return chapters, per


def line_words(chapters: int, per: int) -> tuple[int, int]:
    """(low, high) words for each narration line so the whole film lands near DOC_WORDS_TARGET whatever its shape: a short shape gets longer lines."""
    mid = DOC_WORDS_TARGET / max(1, chapters * per)
    return max(16, round(mid - 3)), min(LINE_WORDS_MAX, round(mid + 4))


# The owner's shape for a documentary (30 Oct 2026): the hook, then curiosity, then the story, and it finishes with value.
CASE_RULES = ("This is a real case with real victims and possibly living suspects. Use only documented facts and attribute each claim ('police said', 'the court found', 'the report states'). "
              "Never call a named person guilty, the killer or the culprit unless a court did, and then say that a court did; say plainly what is still unproven. No graphic detail of injuries or "
              "bodies and nothing meant to shock. Treat the victim with respect and never speak as the victim. Say once, early, that this is a documentary account of a real case built on the "
              "public record, and say what remains unknown. (YouTube's own rules, read 30 Oct 2026: no shock violence, no realistic simulation of a victim describing their death, documentary context "
              "must be in the video's own audio or pictures.)")


def case_rules(topic: str, title: str = "", anchors=(), chapters=()) -> str:
    """The extra writing rules for a real case or unsolved crime; empty for every other kind of topic. The topic decides first; the title, anchors and chapter titles the writer produced decide
    again (a topic such as "The Isdal Woman" has no crime word, its title may), so the rules are not keyed on one narrow input."""
    import kinds

    return CASE_RULES if kinds.classify({"topic": topic, "title": title, "anchors": list(anchors), "chapters": list(chapters)}) == "case" else ""


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


def source_budget() -> tuple[int, int]:
    """(characters per Wikipedia article, articles) a documentary of the owner's length is written from. 8 to 10 minutes keeps the old 7,000 characters of 2 articles;
    20 to 26 minutes reads about 18,000 of 3 (20 Nov 2026: "Seven Sleepers" was written from 12,400 characters, about 2,000 words, for 2,600 to 3,300 words of
    narration; the fact-check then rightly struck what the sources did not say and the film came out at 12.9 minutes, while the articles hold 25,600)."""
    mid = sum(DOC_MINUTES) / 2
    return min(24000, max(7000, round(7000 * mid / 9))), (3 if mid > 12 else 2)


DRAFT_FILE = config.ROOT / "data" / "pending_draft.json"
MAX_DRAFT_USES = 3


def _draft_key(topic: str, sources: str | None) -> str:
    import hashlib

    return hashlib.sha1(f"{topic}\n{sources or ''}".encode()).hexdigest()[:16]


def _save_draft(topic: str, sources: str | None, outline: dict, lines: list[dict], chapters: list[dict], rules: str) -> None:
    """The written draft, saved before its fact-check (20 Nov 2026: a draft of two hours' writing was lost twice when no free judge could answer, and the next attempt
    wrote everything again). Its writers are saved with it, so a later process still never lets them judge it."""
    import filelock

    try:
        DRAFT_FILE.parent.mkdir(parents=True, exist_ok=True)
        filelock.write_atomic(DRAFT_FILE, json.dumps({"key": _draft_key(topic, sources), "topic": topic, "outline": outline, "lines": lines, "chapters": chapters,
                                                      "rules": rules, "writers": llm.writers(), "uses": 0}))
    except OSError:
        pass


def _unuse_draft() -> None:
    import filelock

    try:
        d = json.loads(DRAFT_FILE.read_text())
        d["uses"] = max(0, int(d.get("uses", 0)) - 1)
        filelock.write_atomic(DRAFT_FILE, json.dumps(d))
    except (OSError, ValueError):
        pass


def _load_draft(topic: str, sources: str | None) -> dict | None:
    """The saved draft for this topic and these exact sources, counted as one more use; None when there is none, it is for other sources, or it was checked
    MAX_DRAFT_USES times already (then a new one is written)."""
    import filelock

    try:
        d = json.loads(DRAFT_FILE.read_text())
    except (OSError, ValueError):
        return None
    if d.get("key") != _draft_key(topic, sources) or int(d.get("uses", 0)) >= MAX_DRAFT_USES or not d.get("lines"):
        return None
    d["uses"] = int(d.get("uses", 0)) + 1
    try:
        filelock.write_atomic(DRAFT_FILE, json.dumps(d))
    except OSError:
        pass
    return d


MIN_SHARE = 1.1   # before the fact-check a script is grown to 10% above the owner's shortest length: the check rewrites and drops lines (20 Nov 2026: 83 lines,
                  # 1,973 words, 15.4 minutes after the check against the owner's 20 to 26)
MAX_EXTENSIONS = 6
LENGTH_ROUNDS = 3  # after the check: grow and check again at most this many times


def min_doc_words() -> int:
    """Words the owner's shortest documentary length needs (rules.json long_min_minutes), at the measured narration pace."""
    return round(DOC_MINUTES[0] * words_per_minute(DOC_MINUTES[0]))


def drop_retold(lines: list[dict], chapters: list[dict]) -> tuple[list[dict], list[dict]]:
    """The lines that retell an earlier one removed (video_packaging_rules.script_repeats, the same rule run.py applies), inside the writer so the length loop can make
    up for them (20 Nov 2026: removed after the line join, six 36-word lines took about 200 words, more than the spare left for it)."""
    import video_packaging_rules

    pairs = video_packaging_rules.script_repeats([l["text"] for l in lines])
    return remove_lines(lines, chapters, {j for _, j in pairs}) if pairs else (lines, chapters)


_END = re.compile(r"[.!?\u2026][\"'\u201d\u2019)\]]*$")
_LAST_SENTENCE = re.compile(r"^(.*[.!?\u2026][\"'\u201d\u2019)\]]*)\s+\S.*$", re.S)


def finish_lines(lines: list[dict], chapters: list[dict]) -> tuple[list[dict], list[dict]]:
    """Every narration line ends a sentence. A line that stops mid-sentence is cut back to its last whole sentence; a line with no whole sentence (a run of notes
    such as "No site empirically proven as original cave Homily draws on earlier lost Greek source") is dropped. Words are only taken away, never added, so the
    fact-check still stands (20 Nov 2026: the free writer's checked 82-line script for "Seven Sleepers" had 4 such note lines and several lines cut off
    mid-sentence, and the script reviewer held it for its last line)."""
    out, drop = [], set()
    for i, l in enumerate(lines):
        text = str(l.get("text", "")).strip()
        if _END.search(text):
            out.append(l)
            continue
        m = _LAST_SENTENCE.match(text)
        if m and len(m.group(1).split()) >= 6:
            out.append({**l, "text": m.group(1).strip()})
        else:
            drop.add(i)
            out.append(l)
    return remove_lines(out, chapters, drop) if drop else (out, chapters)


def join_short_lines(lines: list[dict], chapters: list[dict], short: int | None = None, longest: int | None = None) -> tuple[list[dict], list[dict]]:
    """Adjacent lines of one chapter joined while the line is short, up to LINE_WORDS_MAX words (20 Nov 2026: a free writer gave a 20-26 minute film 119 lines of
    about 18 words, and every line is one picture: 119 drawings, two days of the free allowance, against the budget's 84 to 100 lines of 30 to 39 words).
    Only checked sentences are joined, never changed; a joined line keeps its first part's picture words. A film of 8 to 10 minutes (lines up to 30 words) is
    left alone below 16 words, so its pacing does not change."""
    short = short if short is not None else (30 if LINE_WORDS_MAX > 30 else 16)  # the long-film budget asks for lines of 30 to 39 words
    longest = longest or LINE_WORDS_MAX
    if not chapters:
        return lines, chapters
    out, starts = [], []
    bounds = [(c["start_line"], chapters[n + 1]["start_line"] if n + 1 < len(chapters) else len(lines)) for n, c in enumerate(chapters)]
    for a, b in bounds:
        starts.append(len(out))
        cur = None
        for l in lines[a:b]:
            if cur and len(cur["text"].split()) < short and len(cur["text"].split()) + len(l["text"].split()) <= longest:
                cur = {**cur, "text": cur["text"].rstrip() + " " + l["text"].lstrip()}
            else:
                if cur:
                    out.append(cur)
                cur = dict(l)
        if cur:
            out.append(cur)
    return out, [{**c, "start_line": starts[n]} for n, c in enumerate(chapters)]


def extend_to_length(lines: list[dict], chapters: list[dict], outline: dict, topic: str, rules: str, style: str, chat=None, share: float | None = None) -> tuple[list[dict], list[dict]]:
    """A script well under the owner's length (20 Nov 2026: 20 to 26 minutes asks for lines of 30 to 39 words, which a free writer may cut short) gets more lines in its
    shortest chapters: facts from SOURCES the story has not told yet, in the same voice, never a retelling. At most MAX_EXTENSIONS requests; a chapter is extended once.
    The added lines go through the same fact-check as the rest. A script that is long enough, or a writer that adds nothing, leaves the script as it was."""
    chat = chat or _script_chat
    words = lambda ls: sum(len(str(l.get("text", "")).split()) for l in ls)
    need = round(min_doc_words() * (MIN_SHARE if share is None else share))
    if not chapters or words(lines) >= need:
        return lines, chapters
    lo, hi = line_words(len(chapters), max(1, len(lines) // max(1, len(chapters))))
    spans = [(n, c["start_line"], chapters[n + 1]["start_line"] if n + 1 < len(chapters) else len(lines)) for n, c in enumerate(chapters)]
    order = sorted(spans, key=lambda t: words(lines[t[1]:t[2]]))  # the shortest chapters first
    typical = max(12, sorted(len(str(l.get("text", "")).split()) for l in lines)[len(lines) // 2]) if lines else 20  # what this writer really gives a line
    reach = min(len(order), max(MAX_EXTENSIONS, -(-(need - words(lines)) // (typical * 5))))  # as many chapters as the gap needs (20 Nov 2026: 6 chapters of 3 to 5 short
    per = max(3, min(8, -(-(need - words(lines)) // max(1, reach * typical))))                 # lines added about 430 words a round against a gap of 800)
    added: dict[int, list[dict]] = {}
    for n, start, end in order[:reach]:
        if words(lines) + sum(words(v) for v in added.values()) >= need:
            break
        told = " ".join(l["text"] for l in lines)
        try:
            part = chat(llm.cached(
                f"You are narrating a documentary titled '{outline.get('title', topic)}' about: {topic}.\nStyle: {style}\n{rules}\n\n",
                f"The whole narration so far:\n{told[-9000:]}\n\nChapter '{chapters[n].get('title', '')}' is too short. Write {per} to {per + 2} more narration lines of {lo} to {hi} words "
                "that continue THIS chapter with facts from SOURCES the narration has not told yet. Never repeat a name, date or event already told, never summarise, "
                "never add a fact SOURCES do not state; if SOURCES have nothing new for this chapter, return an empty list. For every line give 'visual': 2 to 4 words "
                'naming the place, person, object or artwork to show. Return JSON: {"lines": [{"text": "...", "visual": "..."}]}'))
        except Exception:
            continue
        got = [{"text": str(l["text"]).strip(), "visual": str(l.get("visual", "")).strip()} for l in (part.get("lines") or []) if isinstance(l, dict) and str(l.get("text", "")).strip()]
        if got:
            added[n] = got[:per + 2]
    if not added:
        return lines, chapters
    out, starts = [], []
    for n, start, end in spans:
        starts.append(len(out))
        out += lines[start:end] + added.get(n, [])
    return out, [{**c, "start_line": starts[n]} for n, c in enumerate(chapters)]


def doc_script(topic: str, facts: str | None = None, grounded: str | None = None) -> dict:
    """Outline first, then one request per chapter: small local models undershoot a one-shot long script.

    With `facts` (news explainers) or `grounded` (a source article for a story) the script may use ONLY those facts."""
    nc = dict(config.niche())
    n_chapters, n_lines = shape_for(topic)
    llm.begin_script()
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
    draft = _load_draft(topic, grounded or facts)
    if draft:  # a draft written earlier for this topic and these sources waits at its checkpoint: check it, do not write it again
        outline, lines, chapters, rules = draft["outline"], draft["lines"], draft["chapters"], draft.get("rules", rules)
        llm._WRITERS.update(draft.get("writers") or [])  # its writers are still never its judges
        print(f"  resuming the saved draft ({len(lines)} lines, check {draft['uses']} of {MAX_DRAFT_USES})")
    else:
        outline = _script_chat(
            f"Plan a {DOC_MINUTES[0]:g} to {DOC_MINUTES[1]:g} minute YouTube documentary for a US audience.\nTopic: {topic}\nChannel: {nc['name']}\n"
            f"Style: {nc['style']}\n{rules}\n\nGive {n_chapters} chapters in story order. {DOC_STRUCTURE}"
            "The first sentence is the strangest fact or the central question. Use only what the sources support. "
            "End on the story: no thanks, no subscribe line. "
            'Return JSON: {"title": "under 70 chars", "description": "3 sentences", '
            '"tags": ["..."], "anchors": ["3 to 6 real names of the places, people and things at the heart of this '
            'story, as they appear in archive image titles"], "chapters": [{"title": "...", "summary": "one sentence of what this chapter covers"}]}'
        )
        if not case and case_rules(topic, title=str(outline.get("title", "")), anchors=outline.get("anchors") or [], chapters=outline.get("chapters") or []):
            rules += "\n" + CASE_RULES  # the outline's own title and chapters show it is a real case: every chapter is written under the rules
        chapters, lines, told = [], [], ""
        for n, ch in enumerate(outline["chapters"][:n_chapters], 1):
            for _ in range(3):
                part = _script_chat(llm.cached(
                    f"You are narrating a documentary titled '{outline['title']}' about: {topic}.\n"
                    f"Style: {nc['style']}\n{rules}\n\n",  # the same for every chapter, source article included: sent once as a cache block
                    f"Story so far: {told or '(nothing yet, this is the opening)'}\n\n"
                    f"Write chapter {n}: '{ch.get('title', '')}' - {ch.get('summary', '')}\n"
                    f"Write {n_lines} narration lines of {line_words(n_chapters, n_lines)[0]} to {line_words(n_chapters, n_lines)[1]} words each. Do not repeat earlier chapters: a name, date or event already told in the story so far is never told again, "
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
        lines, chapters = extend_to_length(lines, chapters, outline, topic, rules, nc["style"])  # before the fact-check, so every added line is checked too
        _save_draft(topic, grounded or facts, outline, lines, chapters, rules)
    if grounded:
        before = sum(len(l["text"].split()) for l in lines)
        try:
            lines, chapters = checked(lines, chapters, grounded)  # busy judges: the same draft waits and is checked again, it is not written again
        except ValueError as e:
            if "could not be fact-checked" not in str(e):
                DRAFT_FILE.unlink(missing_ok=True)  # the sources do not support this draft: the next attempt writes a new one
            else:
                _unuse_draft()  # no judge could answer: not the draft's fault, so this check does not count against its three
            raise
        lines, chapters = drop_retold(lines, chapters)  # before the length loop, so the loop makes up for what it removes (run.py's removal then finds none)
        kept = sum(len(l["text"].split()) for l in lines) / max(1, before)  # the share of words the check left: the next growth aims above the target by that much
        for _ in range(LENGTH_ROUNDS):  # the check rewrites and drops lines: a checked script under the owner's length grows again, and the new lines are checked too
            if sum(len(l["text"].split()) for l in lines) >= min_doc_words() * 1.04:  # 4% spare
                break
            grown, grown_ch = extend_to_length(lines, chapters, outline, topic, rules, nc["style"], share=min(1.6, 1.06 / max(0.5, kept)))  # 20 Nov 2026: aiming at 1.06 with
            if len(grown) == len(lines):                                                                                                 # a check that keeps 80% never arrived
                break  # the writer has nothing more from the sources: the film stays as long as its sources allow
            before = sum(len(l["text"].split()) for l in grown)
            lines, chapters = drop_retold(*checked(grown, grown_ch, grounded))
            kept = sum(len(l["text"].split()) for l in lines) / max(1, before)
    lines, chapters = join_short_lines(lines, chapters)  # one picture a line: a long film's lines are 30 to 44 words, not 18
    lines, chapters = finish_lines(lines, chapters)  # no line ends mid-sentence: trimmed to its last whole sentence, or dropped
    words = sum(len(l["text"].split()) for l in lines)
    DRAFT_FILE.unlink(missing_ok=True)  # checked (or never needed checking): the checkpoint is spent
    if len(chapters) < 5 or words < 400:
        raise ValueError(f"documentary too thin ({len(chapters)} chapters, {words} words)")
    return {
        "topic": topic, "format": "doc", "grounded": bool(facts or grounded), "script_model": _writer_model(), "script_writers": llm.writers(),
        "anchors": [str(a).strip() for a in outline.get("anchors", []) if str(a).strip()][:6],
        "title": str(outline["title"]).strip()[:95],
        "description": str(outline.get("description", "")).strip(),
        "tags": [str(t) for t in outline.get("tags", [])][:15],
        "lines": lines, "chapters": chapters,
    }
