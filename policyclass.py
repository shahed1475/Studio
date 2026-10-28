"""What a change on one of YouTube's rule pages means for the channel, and what to do about it.

newswatch.policy_watch finds the change (a page's sentences differ from the saved copy). This module classifies it with fixed rules (no model: cheap, the same
answer every time, and text from a page cannot talk it into anything), then:
- writes the classification to data/newswatch/policy_class.json;
- for a medium or high change, PROPOSES a policy constraint for rules.json (rulesfile.propose): it applies only when the owner approves it;
- for a HIGH change to a monetization or content page, starts a policy hold: Autopilot keeps researching, writing and repairing, but does not schedule or upload
  until the owner has read the change and released the hold (`python run.py policy release`). The hold never turns Autopilot off and never touches a video;
- gives the owner one task and one notice.
Page text is data: it is cleaned, cut short, and only ever stored or shown, never followed. Agents never release the hold (agenteval checks that)."""
import datetime as dt
import json
import re
from pathlib import Path

import agentbus
import config
import filelock
import rulesfile

CLASS_FILE = config.ROOT / "data" / "newswatch" / "policy_class.json"
HOLD_FILE = config.ROOT / "data" / "policy_hold.json"
CONTENT_PAGES = ("Monetization policies", "Channel monetization (YPP) overview", "Spam, deceptive practices and scams", "Altered or synthetic content", "Made for kids",
                 "Community Guidelines")
API_PAGES = ("API: upload a video", "API: revision history")
STRONG = re.compile(r"(?i)demoneti[sz]|not (be )?eligible|ineligible|terminat|must (disclose|label)|required to|no longer (allowed|eligible|permitted)|effective (immediately|as of)|"
                    r"inauthentic|mass[- ]produced|repetitive|templated|synthetic|ai[- ]generated|reused content|penalt|\bstrikes?\b|will be removed")
DEPRECATION = re.compile(r"(?i)deprecat|no longer|removed|retire|sunset|discontinu|breaking change|will stop")


def _text(s, limit: int) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f​-‏ -‮<>]+", " ", str(s or ""))).strip()[:limit]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def _menu(sentence: str) -> bool:
    """A page's navigation or index line, not a rule: many mentions of policy names with no sentence structure, or mostly capitalised words in a long run
    (28 Oct 2026: the Community Guidelines menu was read as a medium change and proposed as a rule)."""
    words = sentence.split()
    return len(re.findall(r"(?i)\bpolic(?:y|ies)\b", sentence)) >= 3 or (len(words) >= 8 and sum(w[:1].isupper() for w in words) / len(words) > 0.55)


def classify(change: dict) -> dict:
    """{"affects": monetization | content | metrics | none, "severity": low | med | high, "summary", "patch" (a validated rules patch or None), "why"}."""
    page, added = str(change.get("page", "")), [t for t in (_text(s, 300) for s in change.get("added", [])) if not _menu(t)]  # menu lines are not rules
    if page in CONTENT_PAGES:
        affects = "monetization" if any(w in page.lower() for w in ("monetization", "spam")) else "content"
        strong = [s for s in added if STRONG.search(s)]
        severity, lead = ("high", strong[0]) if strong else (("med", added[0]) if added else ("low", ""))
        why = "a sentence with a strong rule word was added" if strong else ("text was added" if added else "text was only removed")
    elif page in API_PAGES:
        affects, hit = "metrics", [s for s in added if DEPRECATION.search(s)]
        severity, lead = ("med", hit[0]) if hit else ("low", added[0] if added else "")
        why = "a deprecation or removal is mentioned" if hit else "a minor change"
    else:
        affects, severity, lead, why = "none", "low", (added[0] if added else ""), "a page we do not classify"
    patch = None
    if severity in ("med", "high") and lead and affects in ("monetization", "content"):
        day = str(change.get("at", ""))[:10] or "undated"
        patch = {"policy_constraints_add": [{"id": f"policy-{_slug(page)}-{day}", "summary": lead[:200], "source": str(change.get("url", ""))[:200], "status": "UNVERIFIED"}]}
        if not rulesfile.validate_patch(patch)[0]:
            patch = None
    return {"affects": affects, "severity": severity, "summary": lead[:200], "patch": patch, "why": why}


def hold_active(path: Path | None = None) -> dict | None:
    try:
        h = json.loads(Path(path or HOLD_FILE).read_text())
        return h if isinstance(h, dict) and h.get("active") else None
    except (OSError, ValueError):
        return None


def start_hold(page: str, reason: str, now=None, path: Path | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    path = Path(path or HOLD_FILE)
    old = hold_active(path)
    h = old or {"active": True, "since": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "pages": [], "reasons": []}
    if page not in h["pages"]:
        h["pages"].append(page)
        h["reasons"].append(_text(reason, 200))
    path.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(path, json.dumps(h, indent=1))
    return h


def release_hold(note: str = "", now=None, path: Path | None = None) -> str:
    """Owner command: the owner has read the change, uploads and scheduling may continue."""
    path = Path(path or HOLD_FILE)
    h = hold_active(path)
    if not h:
        return "no policy hold is active"
    h.update(active=False, released=(now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"), note=_text(note, 200))
    filelock.write_atomic(path, json.dumps(h, indent=1))
    return "policy hold released: scheduling and uploads continue"


def handle(changes: list[dict], now=None, class_file: Path | None = None, hold_file: Path | None = None, tasks: Path | None = None, rules_path: Path | None = None) -> list[dict]:
    """Classify every changed page, propose rule updates, start a hold for a high change to a monetization or content page, and tell the owner once per page."""
    import agentlog

    now = now or dt.datetime.now(dt.timezone.utc)
    out = []
    for c in changes:
        k = classify(c)
        rec = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "page": c.get("page"), "url": c.get("url"), **{x: k[x] for x in ("affects", "severity", "summary", "why")}}
        if k["patch"]:
            rec["proposal"] = rulesfile.propose(k["patch"], f"{c.get('page')}: {k['summary'][:160]}", str(c.get("url", "")), now, rules_path)
        held = k["severity"] == "high" and k["affects"] in ("monetization", "content")
        if held:
            start_hold(str(c.get("page")), k["summary"], now, hold_file)
        rec["hold"] = held
        out.append(rec)
        if k["severity"] != "low":
            agentbus.post_to_owner_once("policy_change", "news", _slug(str(c.get("page"))), f"{c.get('page')}: {k['severity']} change ({k['why']}). {k['summary'][:160]}",
                                        "; ".join(_text(s, 200) for s in c.get("added", [])[:3]), "YouTube changed a rule page: read it", now, tasks,
                                        ["python run.py policy"] + (["python run.py policy release"] if held else []) + (["python run.py rules"] if rec.get("proposal") else []))
            agentlog.event("found", f"Policy change ({k['severity']}): {c.get('page')}",
                           (k["summary"] or "text was removed") + (" Scheduling and uploads are on hold until you run `python run.py policy release`." if held else ""), notify=True, now=now)
    if out:
        cf = Path(class_file or CLASS_FILE)
        try:
            old = json.loads(cf.read_text())
        except (OSError, ValueError):
            old = []
        cf.parent.mkdir(parents=True, exist_ok=True)
        filelock.write_atomic(cf, json.dumps((old + out)[-100:], indent=1))
    return out


def recent(n: int = 10, class_file: Path | None = None) -> list[dict]:
    try:
        return json.loads(Path(class_file or CLASS_FILE).read_text())[-n:][::-1]
    except (OSError, ValueError):
        return []
