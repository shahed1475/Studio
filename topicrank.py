"""Which queued topic to make next: the one the research and growth data like best, among the ones that can be made well.

Score: how much of the topic's own wording appears in the titles of videos that did well (the weekly YouTube trend study and the reference
channels' top videos), weighted by their views. Viability comes first: a topic whose source article does not exist, is too short, does not mention
the subject, or (for a 'legend') never mentions a legend would make a video about nothing, so it is dropped before anything is made.
"""
import math
import re
import time

import agentlog
import config
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


def read_article(article_of, topic: str, tries: int = 3, pause: float = 2.0):
    """The source article, asked for again after a pause when the answer is empty: a rate-limited or timed-out request looks exactly like "no article"
    (wikipedia.facts_for swallows network errors), and on 21 Oct 2026 that read removed 17 good topics from the queue in one audit."""
    for i in range(tries):
        got = article_of(topic)
        if got:
            return got
        if i < tries - 1:
            time.sleep(pause * (i + 1))
    return None


def made_titles() -> list[str]:
    """Titles and topics of every video made so far (kept, set aside or archived), so a subject is not made twice."""
    import json

    import config

    out = []
    for root in (config.OUT, config.ROOT / "output_old"):
        for m in root.glob("*/meta.json") if root.exists() else []:
            try:
                d = json.loads(m.read_text())
            except ValueError:
                continue
            out += [str(d.get(k)) for k in ("title", "topic") if d.get(k)]
    return list(dict.fromkeys(out))[:60]


def premise_check(topic: str, article: str, made: list[str] | None = None, chat=None) -> tuple[bool, str]:
    """One cheap Claude call before a topic is made: does the subject's wording promise something the source does not state, is it a subject this calm
    history-and-legend channel should not retell as entertainment, or is it a story already made? A model that cannot answer lets the topic through:
    the script gate and the review still stand behind it."""
    import scriptgen

    chat = chat or scriptgen._review_chat
    made = made if made is not None else made_titles()
    try:
        out = chat(
            f"You screen story subjects for {'a calm history-and-folklore YouTube channel' if config._owner_niche() else config.channel_blurb()} for US viewers. A video will be written ONLY from the source article.\n"
            f"SUBJECT: {topic}\nSOURCE ARTICLE (start): {article[:1800]}\nALREADY MADE: {'; '.join(made) or 'nothing'}\n\n"
            "Answer ok=false when ANY of these is true: (1) the subject's wording assumes a fact, link or mystery the article does not state (an invented or false "
            "premise, such as tying two unrelated things together); (2) it is a real tragedy, war crime, trial, atrocity, living-person controversy or contested "
            "political dispute that should not be retold as bedtime entertainment; (3) it is the same story as one in ALREADY MADE; (4) "
            + ("it is neither a legend, myth, folktale nor a well-documented historical mystery" if config._owner_niche()
               else f"it does not belong to this channel's niche ({config.niche()['channel_angle']})") +
            '.\nReturn JSON: {"ok": true or false, "reason": "one short sentence"}')
    except Exception:
        return True, ""
    if not isinstance(out, dict) or "ok" not in out:
        return True, ""
    return bool(out["ok"]), str(out.get("reason", ""))[:200]


def pop_best(fmt: str = "doc", sig=None, article_of=None, premise_of=None, demand_of=None) -> str | None:
    """Take the best viable topic out of the queue. Topics that cannot be made well are dropped with a note; None when nothing is left."""
    sig = signals() if sig is None else sig
    if article_of is None and premise_of is None:
        premise_of = premise_check  # the real run asks Claude; a test that passes its own article_of opts out
        if demand_of is None:
            import seo

            demand_of = seo.demand  # a subject people already search for is worth more than an unknown one
    if article_of is None:
        import wikipedia

        def article_of(t):
            got = wikipedia.facts_for(t, chars=7000)
            if got:
                return got[1]
            wikipedia._api({"action": "query", "meta": "siteinfo"})  # raises when Wikipedia cannot be reached: an outage must not drop good topics
            return None
    queue = topicqueue.items()
    ranked = sorted(enumerate(queue), key=lambda x: (-(score(x[1], sig) + (demand_of(x[1]) if demand_of else 0.0)), x[0]))
    for _, topic in ranked:
        article = read_article(article_of, topic)
        ok, why = viable(topic, article)
        if ok and premise_of:
            ok, why = premise_of(topic, article)
            why = f"screened out: {why}" if not ok else why
        if ok:
            topicqueue.remove_topic(topic)
            agentlog.event("info", f"Chose a topic: {topic[:70]}", f"Highest research score among the queue's viable topics ({score(topic, sig)}); its source article has {len(article or '')} characters"
                           + ("; it passed the premise screen." if premise_of else "."))
            return topic
        topicqueue.remove_topic(topic)
        agentlog.event("info", f"Dropped a topic: {topic[:70]}", why + ". The queue moves on to the next one.")
    return None


def audit_queue(article_of=None, premise_of=None, now=None) -> list[dict]:
    """The same screening as pop_best, over the whole queue at once. Refused topics leave the queue and are kept in data/removed_topics.json with the reason
    (nothing is lost: put one back with `python run.py` queue tools or the Create page)."""
    import datetime as dt
    import json

    import config
    import filelock

    if article_of is None:
        import wikipedia

        def article_of(t):
            got = wikipedia.facts_for(t, chars=7000)
            return got[1] if got else None
    premise_of = premise_of or premise_check
    made = made_titles()
    removed = []
    for topic in list(topicqueue.items()):
        article = read_article(article_of, topic)
        if not article:
            continue  # unreadable is unknown, not "has no article": the topic stays and pop_best decides when it is picked
        ok, why = viable(topic, article)
        if ok:
            ok, why = premise_of(topic, article, made) if premise_of is premise_check else premise_of(topic, article)
            why = f"screened out: {why}" if not ok else why
        if not ok:
            topicqueue.remove_topic(topic)
            removed.append({"topic": topic, "why": why, "at": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if removed:
        path = config.ROOT / "data" / "removed_topics.json"
        with filelock.locked(path):
            old = json.loads(path.read_text()) if path.exists() else []
            filelock.write_atomic(path, json.dumps(old + removed, indent=2))
        agentlog.event("applied", f"Screened the topic queue: {len(removed)} removed", "; ".join(f"{r['topic'][:50]} ({r['why'][:60]})" for r in removed[:4]), now=now)
    return removed
