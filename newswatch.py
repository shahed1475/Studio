"""Weekly YouTube watch: security and policy news from official sources -> digest + draft video topics.

The digest only restates what the sources say. News videos always wait for a human (reviewer verdict needs_human).
"""
import datetime as dt
import email.utils
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import config
import scriptgen

DATA_DIR = config.ROOT / "data" / "newswatch"
TOPICS_FILE = config.ROOT / "news_topics.json"   # proposals made by the agent
NEWS_QUEUE = config.ROOT / "news_queue.json"     # topics a human (or the dashboard) chose to make
FEEDS = {
    "YouTube Official Blog": "https://blog.youtube/rss/",
    "YouTube Creators": "https://www.youtube.com/feeds/videos.xml?channel_id=UCkRfArvrzheW2E7b6SVT7vQ",
    "Google Security Blog": "https://security.googleblog.com/feeds/posts/default",
    "Google Safety and Security": "https://blog.google/technology/safety-security/rss/",
}
POLICY_PAGES = {  # YouTube's own rule pages: any change here can affect the channel
    "Monetization policies": "https://support.google.com/youtube/answer/1311392?hl=en",
    "Channel monetization (YPP) overview": "https://support.google.com/youtube/answer/72851?hl=en",
    "Spam, deceptive practices and scams": "https://support.google.com/youtube/answer/2801973?hl=en",
    "Altered or synthetic content": "https://support.google.com/youtube/answer/14328491?hl=en",
    "Made for kids": "https://support.google.com/youtube/answer/9527654?hl=en",
    "Community Guidelines": "https://support.google.com/youtube/answer/9288567?hl=en",
    "API: upload a video": "https://developers.google.com/youtube/v3/docs/videos/insert?hl=en",
    "API: revision history": "https://developers.google.com/youtube/v3/revision_history?hl=en",
    "API: developer policies": "https://developers.google.com/youtube/terms/developer-policies?hl=en",
}
RELEVANT = re.compile(r"\b(security|secure|scam|scams|phishing|hijack\w*|account|passkeys?|2-?step|two-step|impersonat\w+|spam|"
                      r"policy|policies|monetization|copyright|ai-generated|synthetic|safety|children|verification|"
                      r"privacy|fraud|malware|abuse|takedown|inauthentic|reused|repetitive|mass-produced|quota|"
                      r"disclos\w+|labels?|strikes?|demonetiz\w+|guidelines)\b", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _iso(raw: str) -> str:
    try:
        d = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_feed(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):  # RSS
        items.append({"title": _clean(it.findtext("title")), "link": (it.findtext("link") or "").strip(),
                      "published": _iso(it.findtext("pubDate") or ""), "summary": _clean(it.findtext("description"))})
    for en in root.iter(ATOM + "entry"):  # Atom
        link = next((l.get("href") for l in en.findall(ATOM + "link") if l.get("rel", "alternate") == "alternate"), "")
        items.append({"title": _clean(en.findtext(ATOM + "title")), "link": link or "",
                      "published": _iso(en.findtext(ATOM + "published") or en.findtext(ATOM + "updated") or ""),
                      "summary": _clean(en.findtext(ATOM + "summary") or en.findtext(ATOM + "content"))})
    return items


def is_relevant(item: dict) -> bool:
    return bool(RELEVANT.search(f"{item['title']} {item['summary']}"))


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (StoryStudio newswatch)"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")


def fetch_items(days: int = 10, now: dt.datetime | None = None) -> list[dict]:
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=days)
    out = []
    for name, url in FEEDS.items():
        try:
            items = parse_feed(_get(url))
        except Exception:  # a dead feed must not stop the others
            continue
        for it in items:
            try:
                when = dt.datetime.fromisoformat(it["published"].replace("Z", "+00:00"))
            except ValueError:
                when = now
            if when >= since:
                out.append({**it, "feed": name})
    return out


def summarize(items: list[dict]) -> dict:
    text = "\n\n".join(f"[{i + 1}] {it['title']}\n{it['summary'][:900]}\nLink: {it['link']}" for i, it in enumerate(items[:12]))
    return scriptgen._script_chat(
        "You summarize official YouTube and Google security or policy news for small YouTube creators.\n"
        f"Use ONLY the text below. Invent nothing: no dates, numbers or features that are not written here.\n\n{text}\n\n"
        "For each item that matters to creators (account safety, scams, policy, monetization, AI content) give: title, "
        "what_changed (1 sentence), why_it_matters (1 sentence for creators), steps (0 to 3 things a creator can do), link. "
        "Then video_ideas: up to 3 short explainer video titles a creator channel could make from these items. "
        'Return JSON: {"items": [{"title": "", "what_changed": "", "why_it_matters": "", "steps": [], "link": ""}], "video_ideas": []}')


def page_sentences(page: str) -> list[str]:
    """The readable sentences of a policy page (scripts and styles dropped, fragments under 40 characters ignored)."""
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    seen, out = set(), []
    for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\b\d{9,}\b", " ", _clean(body))):  # long numbers are per-request ids, not policy
        s = s.strip()
        if 40 <= len(s) <= 700 and re.search(r"[.!?][\"')\]]?$", s) and not re.search(r"\b(true|false) (true|false)\b", s) and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def policy_watch(now: dt.datetime | None = None, get=None) -> list[dict]:
    """Compare YouTube's rule pages with the last copy we saved. The first run is only the baseline. Returns the pages that changed."""
    import agentlog

    get = get or _get
    now = now or dt.datetime.now(dt.timezone.utc)
    store = DATA_DIR / "pages.json"
    saved = json.loads(store.read_text()) if store.exists() else {}
    changes = []
    for name, url in POLICY_PAGES.items():
        try:
            now_s = page_sentences(get(url))
        except Exception:  # a page that cannot be read today is read tomorrow
            continue
        if len(now_s) < 5:  # an error page or a consent wall: never replace a good baseline with it
            continue
        before = saved.get(name, {}).get("sentences")
        if before is not None:
            added = [s for s in now_s if s not in set(before)]
            removed = [s for s in before if s not in set(now_s)]
            if added or removed:
                changes.append({"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "page": name, "url": url,
                                "added": [s[:300] for s in added[:8]], "removed": [s[:300] for s in removed[:8]]})
        saved[name] = {"sentences": now_s, "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(saved))
    if changes:
        log = DATA_DIR / "policy_log.json"
        old = json.loads(log.read_text()) if log.exists() else []
        log.write_text(json.dumps((old + changes)[-100:], indent=2))
        for c in changes:
            agentlog.event("found", f"YouTube changed its page: {c['page']}",
                           (c["added"][0] if c["added"] else "Some text was removed") + " Read it before the next upload.", notify=True, now=now)
    return changes


def recent_policy_changes(now: dt.datetime, days: int = 10) -> list[dict]:
    log = DATA_DIR / "policy_log.json"
    if not log.exists():
        return []
    since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [c for c in json.loads(log.read_text()) if c["at"] >= since]


def _week(now: dt.datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def run(now: dt.datetime | None = None) -> Path:
    now = now or dt.datetime.now(dt.timezone.utc)
    items = [i for i in fetch_items(10, now) if is_relevant(i)]
    digest = {"items": [], "video_ideas": []}
    if items:
        try:
            got = summarize(items)
            digest = {"items": list(got.get("items", [])), "video_ideas": [str(v) for v in got.get("video_ideas", [])]}
        except Exception as e:
            digest["error"] = f"summary failed: {type(e).__name__}"
    import safety

    digest["items"] = [{"title": f"Policy page changed: {c['page']}",
                        "what_changed": c["added"][0] if c["added"] else "Some text on this page was removed.",
                        "why_it_matters": "This is YouTube's own rule page. Read the change before the next upload.",
                        "steps": [], "link": c["url"]} for c in recent_policy_changes(now)] + digest["items"]
    week = _week(now)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{week}.json"
    path.write_text(json.dumps({"week": week, "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "sources_checked": list(FEEDS) + list(POLICY_PAGES), "found": len(items), **digest,
                                "self_audit": safety.local_audit()}, indent=2))
    topics = json.loads(TOPICS_FILE.read_text()) if TOPICS_FILE.exists() else []
    known = {t["topic"] for t in topics}
    links = [i["link"] for i in digest["items"] if i.get("link")]
    for idea in digest["video_ideas"]:
        if idea not in known:
            topics.append({"topic": idea, "week": week, "status": "proposed", "sources": links})
    TOPICS_FILE.write_text(json.dumps(topics, indent=2))
    return path


WEEK_FILE = re.compile(r"\d{4}-W\d{2}\.json")


def latest_digest() -> dict | None:
    """The newest weekly digest. The policy-page notes (pages.json, policy_log.json) live in the same folder and are not digests."""
    files = sorted(f for f in DATA_DIR.glob("*.json") if WEEK_FILE.fullmatch(f.name)) if DATA_DIR.exists() else []
    return json.loads(files[-1].read_text()) if files else None


def _facts_for(sources: list[str], week: str) -> str:
    f = DATA_DIR / f"{week}.json"
    if not f.exists():
        return ""
    items = [i for i in json.loads(f.read_text()).get("items", []) if i.get("link") in sources] or json.loads(f.read_text()).get("items", [])
    return "\n".join(f"- {i['title']}: {i['what_changed']} Why it matters: {i['why_it_matters']} Steps: {'; '.join(i.get('steps', []))} (source: {i['link']})" for i in items)


def queue_news_topic(topic: str, sources: list[str], week: str) -> None:
    q = json.loads(NEWS_QUEUE.read_text()) if NEWS_QUEUE.exists() else []
    if any(e["topic"] == topic and e["status"] == "queued" for e in q):
        return
    q.append({"topic": topic, "week": week, "sources": sources, "status": "queued", "facts": _facts_for(sources, week)})
    NEWS_QUEUE.write_text(json.dumps(q, indent=2))


def make_next_news_video(topic: str | None = None) -> Path | None:
    """Make the queued news video (the named topic, else the oldest). Two failed attempts retire the entry."""
    import autopilot
    import run as pipeline

    q = json.loads(NEWS_QUEUE.read_text())
    entry = next((e for e in q if e["status"] == "queued" and (topic is None or e["topic"] == topic)), None)
    if entry is None:
        return None
    try:
        if not entry.get("facts"):
            raise ValueError("no source facts for this topic, run newswatch first")
        data = None
        for _ in range(3):
            try:
                data = scriptgen.doc_script(entry["topic"], facts=entry["facts"])
                break
            except Exception:
                continue
        if not data:
            raise ValueError("could not write a usable script from the sources")
        data["source"] = "news"
        data["description"] += "\n\nSources:\n" + "\n".join(entry["sources"])
        folder = pipeline._produce_doc(data)
    except Exception:
        entry["attempts"] = entry.get("attempts", 0) + 1
        if entry["attempts"] >= 2:
            entry["status"] = "failed"
        NEWS_QUEUE.write_text(json.dumps(q, indent=2))
        raise
    entry["status"] = "made"
    NEWS_QUEUE.write_text(json.dumps(q, indent=2))
    autopilot.finish_video(folder)
    return folder
