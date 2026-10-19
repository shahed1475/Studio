"""Which caption words get a colour, so a viewer's eye lands on the people, places, numbers and tension of the story."""
import math
import re

COLORS = {"name": "&H28C8FF&", "number": "&HFFD14F&", "tension": "&H4F5AFF&"}  # gold, sky blue, red (ASS colour order)
TENSION = {
    "vanished", "vanish", "vanishes", "vanishing", "disappeared", "disappear", "disappearance", "secret", "secrets", "hidden", "mystery",
    "mysteries", "mysterious", "death", "dead", "died", "dies", "killed", "murder", "curse", "cursed", "danger", "dangerous", "dark",
    "darkness", "lost", "silence", "fear", "terror", "blood", "plague", "missing", "unsolved", "doom", "forgotten", "truth", "lie", "lies",
    "hoax", "betrayed", "trapped", "haunted", "ghost", "demon", "monster", "never", "forever", "impossible", "unexplained", "strange",
}
STOP = {"the", "and", "but", "for", "with", "from", "that", "this", "then", "when", "where", "what", "why", "how", "who", "his", "her",
        "their", "its", "our", "you", "they", "she", "he", "we", "was", "were", "some", "many", "one"}
NUMBER = re.compile(r"\d[\d,.]*(st|nd|rd|th|s)?")


def clean(text: str) -> str:
    """Narration is spliced into ASS subtitle lines: braces and backslashes would open override blocks, so they are dropped."""
    return re.sub(r"[{}\\]", "", text)


def _clean(token: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", token)


def kinds(tokens: list[str]) -> list[str | None]:
    """'number', 'tension', 'name' or None for each token. A capital letter only marks a name away from the start of a sentence."""
    out: list[str | None] = []
    for k, tok in enumerate(tokens):
        w = _clean(tok)
        low = w.lower()
        start = k == 0 or re.search(r"[.!?]\W*$", tokens[k - 1]) is not None
        if not w:
            out.append(None)
        elif NUMBER.fullmatch(low):
            out.append("number")
        elif low in TENSION:
            out.append("tension")
        elif not start and w[0].isupper() and len(w) > 2 and low not in STOP:
            out.append("name")
        else:
            out.append(None)
    return out


def limit(found: list[str | None], cap: int) -> list[str | None]:
    """Keep only the first `cap` coloured words: colour everywhere is no colour at all."""
    seen, out = 0, []
    for k in found:
        seen += k is not None
        out.append(k if k is None or seen <= cap else None)
    return out


def color(kind: str) -> str:
    return COLORS[kind]


def colorize(text: str) -> str:
    """ASS text with colour tags around the keywords of a subtitle cue. Spacing and line breaks stay as they are."""
    parts = re.split(r"(\s+)", text)
    tokens = parts[0::2]
    picked = limit(kinds(tokens), max(1, math.ceil(len(tokens) * 0.3)))
    for i, k in enumerate(picked):
        if k:
            parts[i * 2] = f"{{\\c{color(k)}}}{tokens[i]}{{\\r}}"
    return "".join(parts)
