"""Search-driven title, description and tags: YouTube autocomplete shows what people really type, the local model writes from it."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import reviewer
import scriptgen

OFF_TOPIC = re.compile(r"\b(cartoon|disney|movie|film|musical|animated|lyrics|songs?|karaoke|game|roblox|minecraft|19\d\d|20\d\d|trailer|full episodes?|for kids|read aloud|seasons?|episodes?|intro|theme|netflix|hbo|hulu|prime|hollywood|tv|series|reddit|wiki|pdf|download|cast|reaction|audiobook|asmr)\b")
SEEDS = ["history stories for sleep", "legends and folklore", "unsolved mysteries"]  # niche phrases people search


def suggest(q: str) -> list[str]:
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "youtube", "ds": "yt", "hl": "en", "gl": "us", "q": q})
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read().decode()
        return [x[0] for x in json.loads(re.search(r"\((.*)\)\s*$", raw, re.S).group(1))[1]]
    except Exception:
        return []


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
    for q in [core, f"{core} story", f"{core} real story", f"{core} history", f"{core} explained", *SEEDS]:
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
    story = " ".join(l["text"] for l in meta["lines"][:10])
    data = scriptgen._chat(
        f"You write YouTube metadata for a calm storytelling channel (history, legends, mysteries) for US viewers.\n"
        f"Video topic: {meta['topic']}\nMain search phrase: {core}\nStory so far: {story}\n\n"
        f"Real search suggestions from YouTube: {json.dumps(kws[:30])}\n\n"
        "Rules:\n"
        "- Give 5 title options, each under 65 characters, with the main search phrase in the first 40 characters, honest about what the video covers, "
        "no ALL CAPS words, no em-dashes, no emojis. Vary the style: a question, a plain statement, a curiosity hook.\n"
        "- description_intro: 2 sentences that hook the viewer and use the main phrase once, naturally. Only facts the story supports.\n"
        "- tags: 12 search phrases people would type, taken from or close to the suggestions above, each under 30 characters.\n"
        'Return JSON: {"titles": ["..."], "description_intro": "...", "tags": ["..."]}')
    titles = [re.sub(r"[—–]", "-", str(t)).strip().strip('"') for t in data["titles"] if 8 < len(str(t)) <= 70][:5]
    tags, total = [], 0
    for t in [str(x).strip().lower() for x in data["tags"]] + [core] + kws[:6]:
        if t and len(t) <= 30 and not OFF_TOPIC.search(t) and t not in tags and total + len(t) < 450:
            tags.append(t)
            total += len(t)
    intro = re.sub(r"[—–]", "-", str(data["description_intro"]).strip())
    chapters = meta["description"].partition("Chapters:")[2]
    seo = {"core": core, "keywords": kws[:30], "titles": titles, "old_description": meta["description"], "old_tags": meta.get("tags", [])}
    meta["seo"] = seo
    meta["tags"] = tags
    meta["description"] = rebuild_description(meta["description"], intro)
    reviewer.invalidate(meta)
    p.write_text(json.dumps(meta, indent=2))
    print("\n".join(f"- {t}" for t in titles))
    return seo
