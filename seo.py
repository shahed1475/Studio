"""Search-driven title, description and tags: YouTube autocomplete shows what people really type, the local model writes from it."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import config
import records
import reviewer
import scriptgen

OFF_TOPIC = re.compile(r"\b(cartoon|disney|movie|film|musical|animated|lyrics|songs?|karaoke|game|roblox|minecraft|19\d\d|20\d\d|trailer|full episodes?|for kids|read aloud|seasons?|episodes?|intro|theme|netflix|hbo|hulu|prime|hollywood|tv|series|reddit|wiki|pdf|download|cast|reaction|audiobook|asmr)\b|\b(chapters?|parts?|vol(ume)?|ep)\.? ?\d+\b")
SEEDS = ["history stories for sleep", "legends and folklore", "unsolved mysteries"]  # niche phrases people search


SMALL_WORDS = {"a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for", "vs", "with"}
GENERIC_TAG_WORDS = {"history", "histories", "stories", "story", "legend", "legends", "folklore", "mystery", "mysteries", "unsolved", "ancient", "documentary",
                     "explained", "true", "real", "sleep", "myth", "myths", "mythology", "facts", "secrets", "secret", "truth", "interesting", "for", "of", "the",
                     "and", "a", "in", "to", "what", "why", "how", "was", "is", "did", "about", "behind", "really", "lost", "forgotten", "world", "folktales"}


_A_BEFORE_VOWEL = re.compile(r"\b([Aa]) (?=(?!(?:one|once|ouija)\b)(?:[AIOaio][a-z]|[Ee](?![uw]))\w)", re.I)


def fix_a_an(text: str) -> str:
    """'A Author' becomes 'An Author' (a, i, o and e words; not 'a European' or 'a Eulogy'). Titles and chapter names are written by a model that sometimes slips."""
    return _A_BEFORE_VOWEL.sub(lambda m: ("An " if m.group(1) == "A" else "an "), text)


def polish_title(title: str, limit: int = 70) -> str:
    """Plain, properly capitalised title: no dashes or quote marks around it, no trailing full stop, cut at a word if too long."""
    t = re.sub(r"\s+", " ", re.sub(r"[\u2014\u2013]", "-", str(title))).strip().strip('"\u201c\u201d').rstrip(".")
    if t and not any(ch.isupper() for ch in t):  # all lower case: capitalise like a title
        words, out = t.split(" "), []
        for i, w in enumerate(words):
            starts = i == 0 or words[i - 1].endswith((":", "?", "!", "-"))
            out.append(w if w[:1].isdigit() else (w[:1].upper() + w[1:] if starts or w not in SMALL_WORDS else w))
        t = " ".join(out)
    elif t[:1].islower():
        t = t[:1].upper() + t[1:]
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(":,-")
    return fix_a_an(t)


def relevant_tags(tags: list[str], corpus: str, limit: int = 15) -> list[str]:
    """Keep a tag only when every word in it appears in the video's own title, topic, description or script, or is a plain niche word.
    This drops search suggestions that belong to other things (a game, a novel series, a song) whatever the model says."""
    words = set(re.findall(r"[a-z0-9']+", corpus.lower()))
    out: list[str] = []
    for t in tags:
        t = str(t).strip().lower()
        toks = re.findall(r"[a-z0-9']+", t)
        if toks and t not in out and len(t) <= 30 and not OFF_TOPIC.search(t) and all(w in words or w in GENERIC_TAG_WORDS for w in toks):
            out.append(t)
    return out[:limit]


def corpus_of(meta: dict) -> str:
    return " ".join([meta.get("title", ""), meta.get("topic", ""), meta.get("description", ""), " ".join(meta.get("anchors") or []),
                     " ".join(l.get("text", "") for l in meta.get("lines", []))])


def suggest(q: str) -> list[str]:
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "youtube", "ds": "yt", "hl": "en", "gl": "us", "q": q})
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read().decode()
        return [x[0] for x in json.loads(re.search(r"\((.*)\)\s*$", raw, re.S).group(1))[1]]
    except Exception:
        return []


def demand(topic: str) -> float:
    """0 to 1: how many YouTube autocomplete suggestions for the topic's name really contain that name. A subject people already type (Pied Piper,
    Minotaur) scores high; one nobody searches (an obscure account book) scores near 0. Network trouble counts as no signal, never as a failure."""
    subject = re.split(r"[:,(]", topic)[0].strip()
    key = [w for w in re.findall(r"[a-z0-9']+", subject.lower()) if len(w) > 3]
    if not key:
        return 0.0
    hits = [x for x in suggest(subject) if all(w in x.lower() for w in key[:2])]
    return round(min(len(hits), 10) / 10, 2)


def core_phrase(meta: dict) -> str:
    """The 2 to 4 words someone would type to find this story."""
    try:
        out = scriptgen._chat(
            f"What would a viewer type into YouTube search to find a video about: {meta['topic']}?\n"
            'Answer with the 2 to 4 word core subject only, lowercase, for example "pied piper of hamelin". Return JSON: {"phrase": "..."}')
        phrase = re.sub(r"[^a-z0-9' ]", "", str(out["phrase"]).lower()).strip()
        if 1 <= len(phrase.split()) <= 6:
            return phrase
    except Exception:
        pass
    return re.sub(r"^(the )?(legend|mystery|story|secret|myth) of (the )?", "", meta["topic"].lower().split(":")[0]).strip()


def keywords(core: str) -> list[str]:
    found: list[str] = []
    for q in [core, f"{core} story", f"{core} real story", f"{core} history", f"{core} explained", *config.search_seeds(SEEDS)]:
        for s in suggest(q):
            if s not in found and not OFF_TOPIC.search(s):
                found.append(s)
    return found


def rebuild_description(old: str, intro: str) -> str:
    """New intro, but keep the Sources and Chapters sections the video already has."""
    head, _, chapters = old.partition("Chapters:")
    sources = head.partition("Sources:")[2].strip()
    return intro + (f"\n\nSources:\n{sources}" if sources else "") + (f"\n\nChapters:{chapters}" if chapters else "")


def make(folder: Path) -> dict:
    p = folder / "meta.json"
    meta = json.loads(p.read_text())
    core = core_phrase(meta)
    kws = keywords(core)
    print(f"core phrase: {core}\nkeywords found: {len(kws)}")
    starts = [c["start_line"] for c in meta.get("chapters", [])]  # the whole video in brief: each chapter's title and first sentence, not only the opening
    outline = " ".join(f"[{c.get('title', '')}] {meta['lines'][c['start_line']]['text']}" for c in meta.get("chapters", []) if c["start_line"] < len(meta["lines"]))
    story = (outline if starts and len(outline) > 200 else " ".join(l["text"] for l in meta["lines"][:10]))[:2200]
    data = scriptgen._chat(
        f"You write YouTube metadata for {config.channel_blurb() if not config._owner_niche() else 'a calm storytelling channel (history, legends, mysteries)'} for US viewers.\n"
        f"Video topic: {meta['topic']}\nMain search phrase: {core}\nStory so far: {story}\n\n"
        f"Real search suggestions from YouTube: {json.dumps(kws[:30])}\n\n"
        "Rules:\n"
        "- Give 5 title options, each under 65 characters, with the main search phrase in the first 40 characters, honest about what the video covers, "
        "no ALL CAPS words, no em-dashes, no emojis. Vary the style: a question, a plain statement, a curiosity hook.\n"
        "- Make each title a promise of one specific thing the video shows: the well-known name first, then the twist, stake or mystery (for example "
        "'The Pied Piper of Hamelin: The Real Story Behind the Legend', 'Who Was the Minotaur? Inside the Labyrinth of Knossos'). Prefer words people type "
        "(real story, mystery, legend, who was, what happened). Never a vague question like 'What do the accounts actually describe?'; never a title that "
        "needs the viewer to already know the subject.\n"
        "- description_intro: 2 sentences that hook the viewer and use the main phrase once, naturally. Only facts the story supports, and promise only what the video covers: "
        "no question it does not answer, no debate, reveal or verdict it lacks.\n"
        "- tags: 12 search phrases people would type, taken from or close to the suggestions above, each under 30 characters.\n"
        'Return JSON: {"titles": ["..."], "description_intro": "...", "tags": ["..."]}')
    titles = [polish_title(t) for t in data["titles"] if 8 < len(str(t)) <= 70][:5]
    tags, total = [], 0
    for t in relevant_tags([str(x).strip().lower() for x in data["tags"]] + [core] + kws[:6], corpus_of(meta)):
        if total + len(t) < 450:
            tags.append(t)
            total += len(t)
    intro = re.sub(r"[—–]", "-", str(data["description_intro"]).strip())
    chapters = meta["description"].partition("Chapters:")[2]
    seo = {"core": core, "keywords": kws[:30], "titles": titles, "old_description": meta["description"], "old_tags": meta.get("tags", [])}
    new_description = rebuild_description(meta["description"], intro)

    def apply(d):
        d["seo"], d["tags"], d["description"] = seo, tags, new_description
        reviewer.invalidate(d)

    records.update(folder, apply)
    print("\n".join(f"- {t}" for t in titles))
    return seo
