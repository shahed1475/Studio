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
RELEVANT = re.compile(r"\b(security|secure|scam|scams|phishing|hijack\w*|account|passkeys?|2-?step|two-step|impersonat\w+|spam|"
                      r"policy|policies|monetization|copyright|ai-generated|synthetic|safety|children|verification|"
                      r"privacy|fraud|malware|abuse|takedown)\b", re.I)
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
    week = _week(now)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{week}.json"
    path.write_text(json.dumps({"week": week, "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "sources_checked": list(FEEDS), "found": len(items), **digest}, indent=2))
    topics = json.loads(TOPICS_FILE.read_text()) if TOPICS_FILE.exists() else []
    known = {t["topic"] for t in topics}
    links = [i["link"] for i in digest["items"] if i.get("link")]
    for idea in digest["video_ideas"]:
        if idea not in known:
            topics.append({"topic": idea, "week": week, "status": "proposed", "sources": links})
    TOPICS_FILE.write_text(json.dumps(topics, indent=2))
    return path


def latest_digest() -> dict | None:
    files = sorted(DATA_DIR.glob("*.json")) if DATA_DIR.exists() else []
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
