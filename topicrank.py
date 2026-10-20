"""Which queued topic to make next: the one the research and growth data like best, among the ones that can be made well.

Score: how much of the topic's own wording appears in the titles of videos that did well (the weekly YouTube trend study and the reference
channels' top videos), weighted by their views. Viability comes first: a topic whose source article does not exist, is too short, does not mention
the subject, or (for a 'legend') never mentions a legend would make a video about nothing, so it is dropped before anything is made.
"""
import math
import re

import agentlog
import topicqueue

STOP = {"the", "and", "of", "in", "a", "an", "to", "for", "with", "from", "that", "this", "why", "how", "what", "did", "was", "were", "is", "are", "who",
        "story", "tale", "legend", "myth", "mystery", "secret", "secrets", "real", "true", "truth", "hidden", "unsolved", "history", "forgotten", "lost"}
FOLKLORE = re.compile(r"\b(legend|myth|folklore|folk|tale)\b", re.I)
MIN_ARTICLE_CHARS = 1500


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", (text or "").lower().replace("’", "'")) if len(w) > 3 and w not in STOP}


def signals() -> list[tuple[set[str], float]]:
    """(words, weight) for each well-viewed video title the studies found; weight grows with the logarithm of its views."""
    import channelwatch
    import trendwatch

    out = []
    for v in ((trendwatch.latest() or {}).get("videos") or []):
        out.append((words(v.get("title", "")), math.log10(int(v.get("views", 0)) + 10)))
    for c in ((channelwatch.latest() or {}).get("channels") or []):
        for v in c.get("top") or []:
            out.append((words(v.get("title", "")), math.log10(int(v.get("views", 0)) + 10)))
    return out


def score(topic: str, sig: list[tuple[set[str], float]]) -> float:
    mine = words(topic)
    if not mine:
        return 0.0
    total = 0.0
    for w, weight in sig:
        share = len(mine & w) / len(mine)
        if share >= 0.5:
            total += weight * share
    return round(total, 3)


def viable(topic: str, article: str | None) -> tuple[bool, str]:
    if not article or len(article) < MIN_ARTICLE_CHARS:
        return False, "no source article long enough to build a documented script from"
    lower = article.lower()
    mine = words(topic)
    if mine and sum(1 for w in mine if w in lower) / len(mine) < 0.5:
        return False, "the source article does not mention the subject"
    if FOLKLORE.search(topic) and not FOLKLORE.search(article):
        return False, "the source article describes no legend, myth or folk tale about it"
    return True, ""


def pop_best(fmt: str = "doc", sig=None, article_of=None) -> str | None:
    """Take the best viable topic out of the queue. Topics that cannot be made well are dropped with a note; None when nothing is left."""
    sig = signals() if sig is None else sig
    if article_of is None:
        import wikipedia

        def article_of(t):
            got = wikipedia.facts_for(t, chars=7000)
            if got:
                return got[1]
            wikipedia._api({"action": "query", "meta": "siteinfo"})  # raises when Wikipedia cannot be reached: an outage must not drop good topics
            return None
    queue = topicqueue.items()
    ranked = sorted(enumerate(queue), key=lambda x: (-score(x[1], sig), x[0]))
    for _, topic in ranked:
        ok, why = viable(topic, article_of(topic))
        if ok:
            topicqueue.remove_topic(topic)
            return topic
        topicqueue.remove_topic(topic)
        agentlog.event("info", f"Dropped a topic: {topic[:70]}", why + ". The queue moves on to the next one.")
    return None
