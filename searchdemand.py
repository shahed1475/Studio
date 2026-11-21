"""Search demand for a topic, from three free sources (21 Nov 2026; plan: docs/superpowers/plans/2026-11-21-search-demand-comments-click-rate.md).

- YouTube autocomplete (`seo.suggest`, already used by the studio): how many suggestions contain the subject, and what people type after it.
- Wikipedia pageviews (the official Wikimedia REST API, free, with the studio's Wikipedia User-Agent): daily views of the topic's own source article,
  the last 30 days against the 30 before. Google Trends is not used: its robots.txt disallows /explore and its official API is a closed alpha.
- The top YouTube results for the subject (`seo.competitors`, cached a week, 100 quota units a search): proven demand and how crowded it is.

`score` is the studio's own estimate from those parts, 0 to 1, never presented as a YouTube or Google number. Every source can fail: a failure is
"no signal" (the part is missing and the score uses what answered), never an exception and never a reason to drop a topic."""
import datetime as dt
import json
import math
import re
import statistics
import time
import urllib.parse
from pathlib import Path

import config

DIR = config.ROOT / "data" / "research" / "demand"
CACHE_DAYS = 7          # a demand reading this fresh is reused (autocomplete is unofficial: few calls; a YouTube search costs 100 quota units)
YT_SEARCHES_A_DAY = 5   # the YouTube part, for the best topics only: at most 500 of the 10,000 daily units (trendwatch uses about 1,100)
PAUSE = 0.6             # seconds between outside calls of one refresh
WEIGHTS = {"autocomplete": 0.35, "wikipedia": 0.35, "youtube": 0.30}
VERSION = 2  # a reading made by an older rule is read again (2: no-suggestion is 0 hits, key-word retry, off-topic suggestions not counted)
PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/{start}/{end}"
RECENT_DAYS = 365
SMALL_CHANNEL = 100_000  # a channel under this many subscribers whose video beat its own size shows the subject can still be won


def subject(topic: str) -> str:
    """The name someone would type: the topic before a colon, comma, bracket or question mark."""
    return re.split(r"[:,(?]", str(topic))[0].strip()[:80]


def _key(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 3]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "topic"


def _clean_phrase(s) -> str | None:
    import seo

    t = seo.plain(s)[:80]
    if not t or seo.linky(t) or seo.INSTRUCTION_WORDS.search(t):
        return None
    return t


SUGGEST = "https://suggestqueries.google.com/complete/search?"
FILLER = {"the", "a", "an", "of", "and", "lost", "enigma", "mystery", "legend", "secret", "secrets", "story", "tale", "real", "true", "strange"}


def suggest_strict(q: str) -> list[str]:
    """The same YouTube autocomplete as seo.suggest, but a network failure raises (seo.suggest gives [] for both "no suggestion" and "no answer")."""
    import urllib.request

    url = SUGGEST + urllib.parse.urlencode({"client": "youtube", "ds": "yt", "hl": "en", "gl": "us", "q": q})
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read().decode()
    m = re.search(r"\((.*)\)\s*$", raw, re.S)
    return [x[0] for x in json.loads(m.group(1))[1]] if m else []


def _short(name: str) -> str:
    """A long subject's key words, the way people type it: "The Enigma of the 1947 Roswell Incident" -> "1947 roswell incident"."""
    words = [w for w in re.findall(r"[\w']+", name.lower()) if w not in FILLER]
    return " ".join(words[:3])


def autocomplete(name: str, suggest=None) -> dict | None:
    """{"hits": 0 to 10, "phrases": [...], "asked": what was typed} from YouTube autocomplete, or None when it did not answer (a network failure).
    No suggestion for a long title is asked again with its key words; still nothing is 0 hits (nobody types it), never "no answer"."""
    key = _key(name)
    if not key:
        return {"hits": 0, "phrases": [], "asked": name}
    ask = suggest or suggest_strict
    asked = name
    try:
        got = ask(name)
        short = _short(name)
        if not got and short and short != name.lower():
            asked, got = short, ask(short)
    except Exception:
        return None
    import seo

    need = _key(asked)[:2]
    typed = set(re.findall(r"[\w']+", asked.lower()))

    def added(p: str) -> str:  # only the words a suggestion adds are judged: a year in the subject itself ("1947 roswell") is not off topic
        return " ".join(w for w in re.findall(r"[\w']+", p.lower()) if w not in typed)

    hits = [p for p in (_clean_phrase(x) for x in got or []) if p and all(w in p.lower() for w in need)
            and not seo.OFF_TOPIC.search(added(p))]  # a film, game or song of the same name is not this subject
    return {"hits": min(len(hits), 10), "phrases": hits[:5], "asked": asked}


def wiki_title(topic: str, api=None) -> str | None:
    """The English Wikipedia article the studio would use for the topic (the same search as wikipedia.facts_for); "" when Wikipedia has
    none, None when Wikipedia did not answer."""
    import wikipedia

    try:
        hits = (api or wikipedia._api)({"action": "query", "list": "search", "srsearch": wikipedia._terms(topic), "srlimit": 1}).get("query", {}).get("search", [])
    except Exception:
        return None
    return hits[0]["title"] if hits else ""


NO_ARTICLE = {"title": None, "avg_30": 0, "avg_prev_30": 0, "trend": None, "days": 0}


def pageviews(title: str, now: dt.datetime, get=None) -> dict | None:
    """Daily views of a Wikipedia article: the last 30 days and the 30 before (user views, all access). None when the API did not answer."""
    import requests

    import wikipedia

    end = (now - dt.timedelta(days=1)).date()
    start = end - dt.timedelta(days=59)
    url = PAGEVIEWS.format(title=urllib.parse.quote(title.replace(" ", "_"), safe=""), start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    try:
        r = (get or requests.get)(url, headers=wikipedia.UA, timeout=15)
        if r.status_code == 404:  # no views recorded for the article in the window
            return {"title": title, "avg_30": 0, "avg_prev_30": 0, "trend": None, "days": 0}
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception:
        return None
    by_day = {i["timestamp"][:8]: int(i.get("views", 0)) for i in items if isinstance(i, dict) and "timestamp" in i}
    cut = (end - dt.timedelta(days=29)).strftime("%Y%m%d")
    last = [v for d, v in by_day.items() if d >= cut]
    prev = [v for d, v in by_day.items() if d < cut]
    a, b = (sum(last) / 30), (sum(prev) / 30)
    return {"title": title, "avg_30": round(a, 1), "avg_prev_30": round(b, 1), "trend": round(a / b, 2) if b >= 1 else None, "days": len(by_day)}


def youtube_part(name: str, now: dt.datetime, rivals_of=None) -> dict | None:
    """What the top YouTube results for the subject say: median and top views, how many are recent, how many small channels beat their size."""
    import seo

    try:
        vids = (rivals_of or seo.competitors)(name)
    except Exception:
        return None
    if not vids:
        return None  # no login, quota or network trouble: seo.competitors gives [] and that is no signal
    views = [int(v.get("views") or 0) for v in vids]

    def recent(v) -> bool:
        try:
            return (now - dt.datetime.fromisoformat(str(v.get("published", "")).replace("Z", "+00:00"))).days <= RECENT_DAYS
        except ValueError:
            return False

    small = [v for v in vids if v.get("subs") and v["subs"] < SMALL_CHANNEL and (v.get("ratio") or 0) >= 1]
    return {"results": len(vids), "median_views": int(statistics.median(views)), "top_views": max(views), "recent": sum(1 for v in vids if recent(v)),
            "small_channel_wins": len(small)}


def score(parts: dict) -> float | None:
    """0 to 1 over the parts that answered. Autocomplete: hits / 10. Wikipedia: log10 of daily views over 4 (10,000 a day is full).
    YouTube: log10 of the results' median views over 7 (10 million is full), plus 0.1 when two or more small channels beat their size."""
    got = {}
    ac, wp, yt = parts.get("autocomplete"), parts.get("wikipedia"), parts.get("youtube")
    if ac is not None:
        got["autocomplete"] = ac["hits"] / 10
    if wp is not None:
        got["wikipedia"] = min(1.0, math.log10(wp["avg_30"] + 1) / 4)
    if yt is not None:
        got["youtube"] = min(1.0, math.log10(yt["median_views"] + 1) / 7 + (0.1 if yt["small_channel_wins"] >= 2 else 0))
    if not got:
        return None
    w = sum(WEIGHTS[k] for k in got)
    return round(sum(WEIGHTS[k] * v for k, v in got.items()) / w, 3)


def _file(name: str, directory: Path | None) -> Path:
    return (directory or DIR) / f"{_slug(name)}.json"


def _cached(name: str, now: dt.datetime, directory: Path | None) -> dict | None:
    try:
        d = json.loads(_file(name, directory).read_text())
        if d.get("v") == VERSION and (now - dt.datetime.fromisoformat(d["at"])).total_seconds() < CACHE_DAYS * 86400:
            return d
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def demand(topic: str, now: dt.datetime | None = None, with_youtube: bool = False, directory: Path | None = None,
           suggest=None, api=None, get=None, rivals_of=None) -> dict:
    """The demand reading for a topic, from the week's cache when it has what is asked; the YouTube part only when `with_youtube`."""
    now = now or dt.datetime.now(dt.timezone.utc)
    name = subject(topic)
    old = _cached(name, now, directory)
    if old and old["parts"].get("autocomplete") is not None and old["parts"].get("wikipedia") is not None \
            and (not with_youtube or old["parts"].get("youtube") is not None):
        return old  # complete for what is asked: a part that did not answer last time is asked again
    parts = dict((old or {}).get("parts") or {})
    if old is None or parts.get("autocomplete") is None:
        parts["autocomplete"] = autocomplete(name, suggest)
    if old is None or parts.get("wikipedia") is None:
        title = wiki_title(topic, api)
        parts["wikipedia"] = pageviews(title, now, get) if title else (dict(NO_ARTICLE) if title == "" else None)
    if with_youtube:
        parts["youtube"] = youtube_part(name, now, rivals_of)
    else:
        parts.setdefault("youtube", None)
    out = {"v": VERSION, "topic": str(topic)[:160], "subject": name, "at": (old or {}).get("at") or now.isoformat(),  # a reading is as old as its oldest part
           "parts": parts, "score": score(parts)}
    if any(p is not None for p in parts.values()):  # a reading with no answer at all is not cached: it is asked again next time
        try:
            f = _file(name, directory)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(out, indent=1))
        except OSError:
            pass
    return out


def value(topic: str, **kw) -> float:
    """What topicrank.pop_best adds to a topic's research score: 0 to 1, cache first, cheap parts only (never YouTube quota), never raises."""
    try:
        return float(demand(topic, with_youtube=False, **kw)["score"] or 0.0)
    except Exception:
        return 0.0


def refresh(queue: list[str] | None = None, now: dt.datetime | None = None, budget: int = YT_SEARCHES_A_DAY, directory: Path | None = None,
            pause: float = PAUSE, **kw) -> dict:
    """Daily (inside trendwatch.run): every queued topic gets the cheap parts; the best `budget` that lack a fresh YouTube part get it too.
    Writes latest.json for the dashboard and returns it."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if queue is None:
        try:
            queue = json.loads(config.TOPICS_FILE.read_text())
        except (OSError, ValueError):
            queue = []
    rows, searches = [], 0
    for t in [q for q in queue if isinstance(q, str) and q.strip()][:60]:
        cached = _cached(subject(t), now, directory)
        rows.append(demand(t, now, False, directory, **kw))
        if cached is None and pause:
            time.sleep(pause)
    for i in sorted(range(len(rows)), key=lambda i: -(rows[i]["score"] or 0)):
        if searches >= budget:
            break
        if rows[i]["parts"].get("youtube") is None:
            rows[i] = demand(rows[i]["topic"], now, True, directory, **kw)
            searches += 1
    rows.sort(key=lambda r: -(r["score"] or 0))
    out = {"updated": now.isoformat(), "youtube_searches": searches, "rows": rows,
           "note": "The studio's own estimate from YouTube autocomplete, Wikipedia pageviews and the top YouTube results; not a YouTube or Google number."}
    try:
        f = (directory or DIR) / "latest.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, indent=1))
    except OSError:
        pass
    return out


def latest(directory: Path | None = None) -> dict | None:
    try:
        return json.loads(((directory or DIR) / "latest.json").read_text())
    except (OSError, ValueError):
        return None
