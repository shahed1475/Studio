"""What the owner typed or said, as a request: how many, newest or oldest, Shorts or long films, topic words, links.

Fixed rules only: no model, no cost, the same answer every time. A wrong guess is harmless because the page shows the list before anything downloads.
"""
import re
import unicodedata
from dataclasses import dataclass, field

MAX_BATCH = 200  # most videos one request may ask for
DEFAULT_COUNT = 5  # when no number is said

ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "dozen": 12, "couple": 2}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
ALL_WORDS = {"all", "every", "everything"}
OLDEST = {"oldest", "earliest", "first"}
NEWEST = {"newest", "latest", "recent", "last"}
SHORT = {"short", "shorts"}
LONG = {"long", "longform", "documentary", "documentaries"}
STOP = set("""download downloads downloading get grab fetch save give bring want need like would could can will please thanks thank you me my mine our i we the a an of to for from on in at by
about regarding related titled called named with containing and or also only just some those these that this them it is are was were be been which where who what how much many
video videos vid vids clip clips upload uploads work works own made make channel youtube any no not new old most top""".split())

SINGULAR = {"video", "short", "documentary", "clip", "vid", "upload"}
PLURAL = {"videos", "shorts", "documentaries", "clips", "vids", "uploads"}

URL = re.compile(r"(?:https?://)?(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/[^\s<>\"']+", re.I)
ANY_URL = re.compile(r"https?://\S+", re.I)
WORD = re.compile(r"[^\W_]+", re.U)


@dataclass
class Intent:
    count: int | None = DEFAULT_COUNT  # None means every match
    order: str = "newest"  # or "oldest"
    kind: str = "any"  # "short", "long" or "any"
    keywords: list = field(default_factory=list)
    urls: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def _links(text: str, notes: list):
    urls = []
    for m in URL.finditer(text):
        u = m.group(0).rstrip(".,;:!?)]}")
        urls.append(u if u.lower().startswith("http") else "https://" + u)
    rest = URL.sub(" ", text)
    if ANY_URL.search(rest):
        notes.append("I only download YouTube links, so I ignored a link to another site.")
    return urls, ANY_URL.sub(" ", rest)


def parse(text: str) -> Intent:
    notes: list = []
    urls, rest = _links(text or "", notes)
    words = WORD.findall(rest.lower())
    count, saw_all, order, kinds, keywords = None, False, "newest", set(), []
    singular = plural = False
    i = 0
    while i < len(words):
        w = words[i]
        n = None
        singular, plural = singular or w in SINGULAR, plural or w in PLURAL
        if w.isdigit():
            v = int(w)
            if 1900 <= v <= 2100:
                keywords.append(w)  # a year is part of what to look for
            elif v >= 1:
                n = min(v, MAX_BATCH)
                if v > MAX_BATCH and count is None:
                    notes.append(f"One request takes at most {MAX_BATCH} videos, so I will take {MAX_BATCH}.")
        elif w in TENS:
            n = TENS[w]
            if i + 1 < len(words) and words[i + 1] in ONES and ONES[words[i + 1]] < 10:
                n += ONES[words[i + 1]]
                i += 1
        elif w in ONES:
            n = ONES[w]
        elif w in ALL_WORDS:
            saw_all = True
        elif w in OLDEST:
            order = "oldest"
        elif w in NEWEST:
            order = "newest"
        elif w in SHORT:
            kinds.add("short")
        elif w in LONG:
            kinds.add("long")
        elif w not in STOP and len(w) >= 2 and w not in keywords:
            keywords.append(w)
        if n is not None and count is None:
            count = n
        i += 1
    if count is None:
        if saw_all or urls and not keywords:
            count = None
        elif singular and not plural:
            count = 1  # "my first short" means one
        else:
            count = DEFAULT_COUNT
            notes.append(f"You did not say how many, so I will take {DEFAULT_COUNT}. Say a number to change that.")
    kind = kinds.pop() if len(kinds) == 1 else "any"
    return Intent(count=count, order=order, kind=kind, keywords=keywords, urls=urls, notes=notes)


def describe(it: Intent) -> str:
    """The request in plain words, shown above the list so a misheard command is easy to spot."""
    if it.urls:
        return f"{len(it.urls)} link{'s' if len(it.urls) != 1 else ''} you pasted"
    noun, one = {"any": ("videos", "video"), "short": ("Shorts", "Short"), "long": ("long videos", "long video")}[it.kind]
    about = f" about “{' '.join(it.keywords)}”" if it.keywords else ""
    if it.count is None:
        return f"All of your {noun}{about}"
    if it.count == 1:
        return f"Your {it.order} {one}{about}"
    return f"The {it.count} {it.order} of your {noun}{about}"


def match_score(title: str, keywords) -> int:
    """How many of the topic words a title has. A word matches the start of a title word; a plural topic word also matches its singular."""
    words = re.findall(r"[a-z0-9]+", _fold(title or ""))
    score = 0
    for k in keywords:
        k = _fold(k)
        single = k[:-1] if k.endswith("s") and len(k) > 3 else None
        if any(w.startswith(k) or (single and w == single) for w in words):
            score += 1
    return score
