"""The hub's research store: what the researcher found for one account, with where it came from.

Rule A of the studio applies: nothing here is ever labelled VERIFIED (that needs the claim ledger's source-passage check). A topic that has a stored https source and a
passage is PARTIALLY_VERIFIED (one secondary source, not cross-checked); anything else is UNVERIFIED. Text from the web is data: capped, stored and shown as text only.
Every function takes the account id from the session and every row carries it."""
import time

from . import auth, db

LABELS_ALLOWED = ("PARTIALLY_VERIFIED", "UNVERIFIED")
PASSAGE_MAX, TITLE_MAX = 600, 120
MAX_ARTICLES, RUNS_PER_HOUR = 6, 3  # Wikipedia answered HTTP 429 after bursts before (the studio's reader spaces calls); a run is small and rare


def _clean_source(source) -> dict | None:
    if not isinstance(source, dict):
        return None
    url, passage = str(source.get("url") or "").strip(), " ".join(str(source.get("passage") or "").split())
    if not url.startswith("https://") or not passage:
        return None
    return {"url": url[:500], "title": " ".join(str(source.get("title") or "").split())[:TITLE_MAX], "passage": passage[:PASSAGE_MAX],
            "revised": str(source.get("revised") or "")[:40]}


def add_topic(account_id: str, title: str, source: dict | None, now: float | None = None) -> dict:
    """Store a topic idea (once per title) and its source (once per address). Returns {id, title, label, source_id}."""
    now = time.time() if now is None else now
    title = " ".join(str(title or "").split())[:TITLE_MAX]
    if not title:
        raise ValueError("a topic needs a title")
    src = _clean_source(source)
    with db.tx() as con:
        source_id = None
        if src:
            con.execute("insert into sources(account_id,url,title,passage,revised,fetched_at) values(?,?,?,?,?,?) on conflict(account_id,url) do nothing",
                        (account_id, src["url"], src["title"], src["passage"], src["revised"], now))
            source_id = con.execute("select id from sources where account_id=? and url=?", (account_id, src["url"])).fetchone()["id"]
        label = "PARTIALLY_VERIFIED" if source_id else "UNVERIFIED"
        con.execute("insert into topics(account_id,title,source_id,label,created_at) values(?,?,?,?,?) on conflict(account_id,title) do nothing", (account_id, title, source_id, label, now))
        row = con.execute("select id,title,source_id,label from topics where account_id=? and title=?", (account_id, title)).fetchone()
    return {"id": row["id"], "title": row["title"], "label": row["label"], "source_id": row["source_id"]}


def overview(account_id: str) -> dict:
    with db.read() as con:
        sources = [dict(r) for r in con.execute("select id,url,title,passage,revised,fetched_at from sources where account_id=? order by id", (account_id,))]
        topics = [dict(r) for r in con.execute("select id,title,source_id,label,created_at from topics where account_id=? order by id", (account_id,))]
    return {"sources": sources, "topics": topics}


def fetch_article(title: str) -> dict | None:
    """One Wikipedia article as {title, url, text, revised}, or None. The studio's reader (spaced calls, patient with HTTP 429); a test replaces this one name."""
    import wikipedia

    return wikipedia.article_info(title, chars=3000)


def run_for_account(account_id: str, niche_id: str, max_articles: int = MAX_ARTICLES, now: float | None = None) -> dict:
    """Read the lead of the Wikipedia article for each starter topic of the account's ready-made niche and store topic, source, passage and date.
    No model and no cost. Answers {ok: False, error} for a niche without a ready-made match or when the hour's three runs are used."""
    import niche

    preset = niche.preset(niche_id) if niche_id else None
    if not preset:
        return {"ok": False, "error": "no_ready_made_niche"}
    if not auth.hit(f"research:{account_id}", RUNS_PER_HOUR, 3600, now):
        return {"ok": False, "error": "too_many"}
    stored, failed, topics = 0, 0, []
    for title in preset["starter_topics"][:max(1, min(int(max_articles), MAX_ARTICLES))]:
        try:
            info = fetch_article(title)
        except Exception:  # network trouble or a bad page: count it, go on
            info = None
        if not info:
            failed += 1
            continue
        lead = str(info.get("text") or "").strip().split("\n\n")[0]
        topics.append(add_topic(account_id, title, {"url": info.get("url"), "title": info.get("title"), "passage": lead, "revised": info.get("revised")}, now))
        stored += 1
    return {"ok": True, "stored": stored, "failed": failed, "topics": topics}
