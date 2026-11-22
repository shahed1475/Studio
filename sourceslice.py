"""Source excerpts for a judge that should read less (22 Nov 2026, the owner's order: fewer tokens for OpenRouter's free judges, no loss of strictness).

The excerpts are the article's opening (its lead), then every passage that holds a name, date, number or quoted word the narration uses (a greedy set cover:
the passage that adds the most missing terms per character first), then the passages that share the most other words with the narration, in their
original order, up to a cap. No model is asked and nothing is fetched.

`lossless` is True only when every checkable term of the narration that the full source contains is still in the excerpts. A judge reading a lossy slice
could call a supported fact invented (it happened with cut sources on 2 Nov and 21 Nov 2026), so the judge cascade gives that judge the full source instead.
Limit: a fact with no name, date, number or quotation in it is not a "term"; its passage is kept only if it shares enough words with the narration.
"""
import re

CAP = 9000        # characters of excerpts (the owner's 6,000 to 9,000)
MAX_CAP = 12000   # tried once when CAP cannot hold every term's passage
LEAD = 1200       # characters of the article's opening always kept
FILL = 6000       # passages that only share words with the narration are added up to this size (the cover itself may use the whole cap)

_WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|['\-])*[^\W\d_]|[^\W\d_]")  # letters of any alphabet: Lübeck, Ōkuninushi and Þingvellir are names too
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_QUOTE = re.compile(r"[\"“]([^\"”]{8,400})[\"”]")
_STOP = set("""the a an and of to in on at for with from by is was were are be been it its this that these those as but or not no yet then there their they he she
his her him which who whom whose what when where while than into over under after before about also had has have one two three first second however
though although because since until unless if so such some many most more much other another each every both either neither all any few several
legend legends story stories myth myths tale tales today now later once still even only just perhaps maybe nobody someone something everyone
here why how did does do could would should might may must can will shall long ago year years century centuries day days night nights
historians scholars archaeologists people men women king queen city god gods""".split())


def _norm_num(s: str) -> str:
    return s.replace(",", "").rstrip(".")


def _plain(text) -> str:
    return str(text or "").replace("’", "'").replace("‘", "'")  # a curly apostrophe is an apostrophe ("Cambyses’s")


def _words(text: str) -> set:
    return {re.sub(r"'s$", "", w.lower()) for w in _WORD.findall(_plain(text))}


def unit_terms(text: str) -> set:
    """Every word (lower case, no possessive) and number (no thousands commas) in a passage."""
    return _words(text) | {_norm_num(n) for n in _NUM.findall(_plain(text))}


def checkable_terms(narration: str) -> set:
    """The narration's names, dates, numbers and quoted words: what a judge checks for invented facts. Capitalised words that are not common words,
    numbers of two digits or more, and the longer words inside quotation marks."""
    narration = _plain(narration)
    out = set()
    for n in _NUM.findall(narration):
        n = _norm_num(n)
        if len(n.replace(".", "")) >= 2:
            out.add(n)
    for w in _WORD.findall(narration):
        if w[0].isupper():
            w = re.sub(r"'s$", "", w.lower())
            if len(w) >= 3 and w not in _STOP:
                out.add(w)
    for q in _QUOTE.findall(narration):
        out |= {w.lower() for w in _WORD.findall(q) if len(w) >= 5 and w.lower() not in _STOP}
    return out


def _units(source: str) -> list[str]:
    """Paragraphs; a block over 1,200 characters (an encyclopedia article is often one) is read in sentence windows of about 900, as relevant_source does."""
    units = []
    for p in (p.strip() for p in re.split(r"\n\s*\n|(?<=[.!?])\n", source)):
        if not p:
            continue
        if len(p) <= 1200:
            units.append(p)
            continue
        buf = ""
        for s in re.split(r"(?<=[.!?])\s+", p):
            if buf and len(buf) + len(s) + 1 > 900:
                units.append(buf)
                buf = s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            units.append(buf)
    return units


def _join(units: list[str], chosen: set) -> str:
    """The chosen passages in their original order; a gap is marked so the judge knows these are excerpts."""
    out, last = [], None
    for i in sorted(chosen):
        if last is not None and i != last + 1:
            out.append("[...]")
        out.append(units[i])
        last = i
    return "\n\n".join(out)


def _slice(source: str, narration: str, cap: int, lead: int, fill: int = FILL) -> dict:
    units = _units(source)
    per = [unit_terms(u) for u in units]
    full = set().union(*per) if per else set()
    need = checkable_terms(narration) & full
    chosen, used = set(), 0
    for i, u in enumerate(units):  # the lead: the opening passages up to `lead` characters (always at least the first one)
        if chosen and used + len(u) > lead:
            break
        if used + len(u) > cap:
            break
        chosen.add(i)
        used += len(u) + 2
    covered = set().union(*(per[i] for i in chosen)) & need if chosen else set()
    sep = len("\n\n[...]\n\n")  # the most a passage can add besides its own text
    while covered != need:  # greedy cover: the passage adding the most missing terms per character, among those that still fit
        best, best_rate = None, 0.0
        for i, u in enumerate(units):
            if i in chosen or used + len(u) + sep > cap:
                continue
            gain = len((per[i] & need) - covered)
            rate = gain / max(len(u), 80)
            if gain and rate > best_rate:
                best, best_rate = i, rate
        if best is None:
            break
        chosen.add(best)
        used += len(units[best]) + sep
        covered |= per[best] & need
    want = _words(narration) - _STOP
    if want:  # fill what is left with the passages sharing the most other words with the narration (rarer words weigh more, words in most passages not at all)
        df: dict = {}
        for ws in per:
            for w in ws & want:
                df[w] = df.get(w, 0) + 1
        n = len(units) or 1
        score = {i: sum(1.0 / df[w] for w in per[i] & want if df[w] < n * 0.6) / max(len(units[i]), 200) ** 0.5 for i in range(len(units)) if i not in chosen}
        for i in sorted(score, key=lambda i: -score[i]):
            if score[i] <= 0:
                break
            if used >= fill:
                break
            if used + len(units[i]) + sep > cap:
                continue
            chosen.add(i)
            used += len(units[i]) + sep
    text = _join(units, chosen)
    return {"text": text, "chars": len(text), "full_chars": len(source), "terms": len(need), "covered": len(covered),
            "missing": sorted(need - covered)[:20], "lossless": covered == need, "cap": cap}


def slice_source(source: str, narration: str, cap: int = CAP, max_cap: int = MAX_CAP, lead: int = LEAD, fill: int = FILL) -> dict:
    """{"text", "chars", "full_chars", "terms", "covered", "missing", "lossless", "cap"}. A source no longer than `cap` is returned whole (lossless).
    When `cap` cannot hold every term's passage, `max_cap` is tried once; the result says whether it is still lossy."""
    source = source or ""
    if len(source) <= cap:
        need = checkable_terms(narration) & unit_terms(source)
        return {"text": source, "chars": len(source), "full_chars": len(source), "terms": len(need), "covered": len(need), "missing": [],
                "lossless": True, "cap": cap}
    got = _slice(source, narration, cap, lead, fill)
    if not got["lossless"] and max_cap > cap:
        wider = _slice(source, narration, max_cap, lead, fill) if len(source) > max_cap else slice_source(source, narration, max_cap, max_cap, lead, fill)
        if wider["lossless"] or wider["covered"] > got["covered"]:
            return wider
    return got
