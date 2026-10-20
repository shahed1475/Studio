"""Risk register and live monitor.

Eight standing risks, each with a measured indicator, a level (ok, watch, act), the evidence behind the level, the controls already in place and the
decision that belongs to the owner. The indicators read real files and numbers (claim ledgers, review records, spend history, running jobs, file
permissions); nothing here is a guess. Run it:  python risk.py   (or see the Risks card on the dashboard home page).

Levels: ok = inside the limits; watch = look at it this week; act = a decision or fix is needed now.
guard() applies the one automatic protection that is safe to automate: when OpenRouter credit runs low it switches off AI drawing (which needs a $1 balance)
and, lower still, paid models, so a render never dies half-way on a 402. Everything is logged to the activity feed and can be switched back on in Settings.
"""
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

import config

LEVELS = ("ok", "watch", "act")
CREDIT_ACT, CREDIT_WATCH = 1.5, 4.0  # dollars left
RUNWAY_ACT, RUNWAY_WATCH = 3, 7  # days of spend left at the recent daily average
PACE_WATCH, PACE_ACT = 10, 15  # uploads (made or scheduled) in a week
_credit_cache: dict = {}


def ind(rid: str, name: str, level: str, evidence: str, controls: str, owner: str = "") -> dict:
    return {"id": rid, "name": name, "level": level, "evidence": evidence, "controls": controls, "owner_decision": owner}


def worst(*levels: str) -> str:
    return max(levels, key=LEVELS.index)


def videos(out: Path | None = None) -> list[tuple[Path, dict]]:
    out = out or config.OUT
    rows = []
    for m in sorted(out.glob("*/meta.json")) if out.exists() else []:
        try:
            rows.append((m.parent, json.loads(m.read_text())))
        except ValueError:
            continue
    return rows


def _pending(vs):
    """Videos that are approved or scheduled and not public yet: what could go out next."""
    return [(f, m) for f, m in vs if not m.get("video_id") and (m.get("approved") or m.get("publish_at")) and not m.get("hold")]


# ---- R1 facts ----
def facts(vs) -> dict:
    conflicts, unverified, ungrounded = [], [], []
    for folder, m in _pending(vs):
        try:
            rows = json.loads((folder / "claims.json").read_text())
        except (OSError, ValueError):
            rows = []
        c = [r for r in rows if r["verification_status"] == "CONFLICTING"]
        u = [r for r in rows if r["verification_status"] == "UNVERIFIED"]
        if c:
            conflicts.append(f"{folder.name} ({len(c)})")
        if u:
            unverified.append(f"{folder.name} ({len(u)})")
        if m.get("grounded") is not True:
            ungrounded.append(folder.name)
    level = "act" if conflicts else "watch" if unverified or ungrounded else "ok"
    ev = (f"contradicted claims in: {', '.join(conflicts)}. " if conflicts else "") + (f"unverified claims in: {', '.join(unverified)}. " if unverified else "") + \
         (f"no source article: {', '.join(ungrounded)}. " if ungrounded else "")
    return ind("facts", "Wrong or unsupported facts", level, ev or f"{len(_pending(vs))} videos waiting to go out: no open claims, all built from a source",
               "source-grounded scripts, claim ledger, web check with cited pages, fixer agent, AI review that sees the source",
               "Wikipedia is secondary and the web check is a model with search: for a topic where facts matter, add a primary source by hand.")


# ---- R2 rights ----
def rights(vs) -> dict:
    import studiochecks

    bad, missing = [], []
    for folder, m in _pending(vs):
        rows = studiochecks.check_licenses(m)
        if any(not r["ok"] and r["severity"] == "block" for r in rows):
            bad.append(folder.name)
        elif not m.get("credits"):
            missing.append(folder.name)
    level = "act" if bad else "watch" if missing else "ok"
    return ind("rights", "Copyright and licensing", level,
               (f"license problems in: {', '.join(bad)}. " if bad else "") + (f"no credits recorded for: {', '.join(missing)}. " if missing else "") or "every pending video credits only public-domain, CC0 or AI-generated pictures, with the Wikipedia credit",
               "public-domain and CC0 pictures only, labelled AI art, license check, Wikipedia credit, no music, no third-party video",
               "Wikimedia's public-domain tags are the uploader's claim: if a rights holder objects, remove the video at once.")


# ---- R3 platform policy: repetitive or mass-produced content ----
def _sig(m: dict) -> tuple:
    ch = m.get("chapters") or []
    return (m.get("format"), len(ch) if ch else len(m.get("lines", [])), round(len(m.get("lines", [])) / max(len(ch), 1)) if ch else 0)


def pattern(vs, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    recent = [m for _, m in sorted(vs, key=lambda x: x[1].get("made_at") or x[1].get("uploaded_at") or "")][-8:]
    sigs = [_sig(m) for m in recent]
    dup = max((sigs.count(s) for s in set(sigs)), default=0)
    same_structure = dup / len(sigs) if len(sigs) >= 4 else 0.0
    norm = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower())
    firsts = [norm((m.get("lines") or [{"text": ""}])[0]["text"]) for m in recent]
    pairs = sum(1 for i in range(len(firsts)) for j in range(i + 1, len(firsts)) if firsts[i] and difflib.SequenceMatcher(None, firsts[i], firsts[j]).ratio() >= 0.75)
    week = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ahead = (now + dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pace = sum(1 for _, m in vs if (str(m.get("uploaded_at", "")) >= week) or (m.get("publish_at") and now.strftime("%Y-%m-%dT%H:%M:%SZ") <= m["publish_at"] <= ahead))
    by_you = sum(1 for _, m in vs if m.get("approved_by") == "you")
    level = "act" if pace >= PACE_ACT or pairs >= 3 or same_structure >= 0.9 and len(sigs) >= 6 else \
            "watch" if pace >= PACE_WATCH or pairs >= 1 or same_structure >= 0.6 else "ok"
    ev = (f"{same_structure:.0%} of the last {len(sigs)} videos share one structure; {pairs} pairs of near-identical openings; {pace} videos out or scheduled in a 7-day window "
          f"(watch at {PACE_WATCH}, act at {PACE_ACT}); {by_you} of {len(vs)} approved by you, the rest by the reviewer agent")
    return ind("platform", "YouTube 'inauthentic content' (repetitive or mass-produced)", level, ev,
               "documentary length and chapter count vary per topic; openings and titles compared with recent videos; one new idea per video; review window; daily limit of 2",
               "YouTube says reviewers look at your main theme, most-viewed and newest videos, and titles. Every video should add something a template cannot: a source-based angle, a real question, what is known versus legend. A slower start (3 to 5 videos a week) is safer for a new channel.")


# ---- R4 money ----
def credit_left(key: str, get=None, now: float | None = None) -> float | None:
    """Dollars left on the OpenRouter account (bought minus used), read live and cached for half an hour. None when it cannot be read."""
    import requests

    get = get or requests.get
    t = now if now is not None else time.time()
    if _credit_cache.get("key") == key and t - _credit_cache.get("at", 0) < 1800:
        return _credit_cache["v"]
    try:
        r = get("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"}, timeout=15)
        r.raise_for_status()
        d = r.json()["data"]
        v = round(float(d["total_credits"]) - float(d["total_usage"]), 3)
    except Exception:
        return None
    _credit_cache.update(key=key, at=t, v=v)
    return v


def daily_spend(days: int = 7) -> float:
    import llm

    usage = llm._usage()
    last = sorted(usage.items())[-days:]
    return sum(v.get("usd", 0.0) for _, v in last) / max(len(last), 1)


def money(left: float | None, avg: float) -> dict:
    if left is None:
        return ind("money", "Running out of money", "watch", "the account balance could not be read", "daily dollar cap, free-model fallback, AI drawing and paid models switch off by themselves when credit is low")
    runway = left / avg if avg > 0 else 999
    level = "act" if left < CREDIT_ACT or runway < RUNWAY_ACT else "watch" if left < CREDIT_WATCH or runway < RUNWAY_WATCH else "ok"
    return ind("money", "Running out of money", level, f"${left:.2f} left, about ${avg:.2f} a day over the last days, roughly {min(runway, 99):.0f} days",
               "daily dollar cap, free-model fallback on any 402, AI drawing and paid models switch off by themselves when credit is low (guard)",
               "Top up OpenRouter before it reaches about $1.50, or accept free models and no AI drawings.")


def guard(left: float | None, apply: bool = True, now: dt.datetime | None = None) -> list[str]:
    """Switch off what needs money before the money is gone. Returns what it changed."""
    import agentlog
    import llm

    if left is None:
        return []
    cfg, changed = llm.load_config(), []
    if cfg.get("ai_art") and left < CREDIT_ACT:
        changed.append(f"AI drawing switched off (${left:.2f} left; image output needs $1)")
        cfg["ai_art"] = False
    if cfg.get("enabled") and left < 0.3:
        changed.append(f"paid models switched off (${left:.2f} left); free models take over")
        cfg["enabled"] = False
    if changed and apply:
        llm.save_config(cfg)
        agentlog.event("applied", "Credit is low: " + "; ".join(changed), "Switch them back on in Settings after a top-up.", notify=True, now=now)
    return changed


# ---- R5 process: deploys and restarts kill renders ----
def running_jobs(proc: Path = Path("/proc")) -> list[str]:
    out = []
    for p in proc.glob("[0-9]*/cmdline"):
        try:
            argv = p.read_bytes().split(b"\0")
        except OSError:
            continue
        txt = " ".join(a.decode(errors="ignore") for a in argv)
        m = re.search(r"run\.py (doc|make|redo|clip|newsvideo|batch)\b", txt)
        if m and "risk.py" not in txt:
            out.append(m.group(0))
    return out


def process(running: list[str], restarts: int) -> dict:
    level = "watch" if running or restarts >= 4 else "ok"
    ev = (f"{len(running)} render{'s' if len(running) != 1 else ''} running now ({', '.join(running[:3])}): a worker restart or deploy would kill {'it' if len(running) == 1 else 'them'}. " if running else "no render running. ") + f"{restarts} worker starts in the last 24 hours"
    return ind("process", "Deploys and restarts killing renders", level, ev,
               "deploy.sh refuses to restart the worker while a render runs (unless FORCE=1) and only recreates containers when the image or compose file changed; CLAUDE.md says to pull --rebase and never restart mid-render",
               "Tell the other session to use deploy/deploy.sh and never `docker compose restart worker` while a render is running.")


def worker_starts(now: dt.datetime, log: Path | None = None) -> int:
    log = log or config.ROOT / "logs" / "worker.log"
    cutoff = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return sum(1 for line in log.read_text().splitlines() if "worker started" in line and line[:20] >= cutoff)
    except OSError:
        return 0


# ---- R6 third-party skills ----
def skills() -> dict:
    root = config.ROOT / ".claude" / "skills" / "watch"
    try:
        pinned = json.loads((root / "VENDORED.sha256.json").read_text())["files"]
    except (OSError, ValueError, KeyError):
        return ind("skills", "Third-party skills and plugins", "watch", "no pinned fingerprint for the vendored skill", "static scanner (vetskill.py), copy instead of auto-update, pinned hashes")
    actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*"))
              if p.is_file() and p.name not in ("VENDORED.md", "VENDORED.sha256.json") and "__pycache__" not in p.parts}
    changed = sorted(k for k in set(pinned) | set(actual) if pinned.get(k) != actual.get(k))
    return ind("skills", "Third-party skills and plugins", "act" if changed else "ok",
               f"changed since review: {', '.join(changed[:4])}" if changed else f"{len(pinned)} vendored files match the reviewed fingerprint",
               "read before install, scanned with vetskill.py, copied (never auto-updated), hashes pinned and tested; publishing code from third parties not installed",
               "Re-read the upstream diff before accepting any update.")


# ---- R7 credentials and access ----
def access() -> dict:
    problems = []
    for name in ("token.json", "client_secret.json", ".env", "settings.json", "data/auth.json", "data/auth_secret"):
        p = config.ROOT / name
        if p.exists() and p.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            problems.append(f"{name} is readable by other users")
    try:
        import webauth

        login = webauth.enabled()
    except Exception:
        login = False
    level = "act" if problems else "watch" if not login else "ok"
    return ind("access", "Stolen or leaked access", level, "; ".join(problems) or ("secret files are owner-only and the dashboard login is on" if login else "the dashboard login is not set up"),
               "login with hashed password and server-side sessions, Tailscale-only address, owner-only secret files, keys never sent back to a browser, secrets never in git",
               "Keep the YouTube login and the OpenRouter key out of chat; rotate either if you ever paste it anywhere.")


# ---- R8 publishing ----
def publishing(vs, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    soon = (now + dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    bad, stuck, unseen = [], [], []
    for folder, m in vs:
        if (m.get("upload_check") or {}).get("ok") is False:
            bad.append(folder.name)
        if m.get("upload_started") and not m.get("video_id"):
            stuck.append(folder.name)
        if not m.get("video_id") and m.get("approved") and not m.get("hold") and m.get("publish_at") and stamp <= m["publish_at"] <= soon and not (m.get("visual_check") or {}).get("ok"):
            unseen.append(f"{folder.name} ({m['publish_at'][:16].replace('T', ' ')} UTC)")
    level = "act" if bad or stuck else "watch" if unseen else "ok"
    ev = (f"YouTube stored something different for: {', '.join(bad)}. " if bad else "") + (f"an upload attempt did not finish: {', '.join(stuck)}. " if stuck else "") + \
         (f"going public within 48 hours with no picture check: {', '.join(unseen)}. " if unseen else "")
    return ind("publishing", "A bad or duplicate upload, or an unvetted video going public", level, ev or "no upload problems; everything due within 48 hours has had a picture check",
               "private upload with scheduled time, 24-hour veto, daily limit, interrupted-upload detection, read-back from YouTube, visual check before auto-approval",
               "Use Hold on the Autopilot page for any video you do not want to go out; look at the first public video yourself.")


# ---- R9 next documentary ----
def supply(now: dt.datetime | None = None) -> dict:
    """Is the next documentary slot covered, or when does Autopilot start on it? Videos are made just in time (docs/AUTOPILOT.md), so 'nothing ready yet'
    is normal until the slot is due; the row only turns to action when a due slot is still uncovered close to its deadline."""
    import autopilot

    now = now or dt.datetime.now(dt.timezone.utc)
    view = autopilot.plan_view(now)
    docs = [r for r in view["rows"] if r["format"] == "doc" and r["status"] != "too_soon"]
    controls = "Autopilot prepares each video 36 hours before it posts, repairs the best draft first, makes a new one only when none is usable, and works on one at a time"
    if not docs:
        return ind("supply", "Next documentary", "watch", "no documentary slot is set for the coming days", controls, "Add documentary publish times under Rules on the Autopilot page.")
    nxt = docs[0]
    what = f"Next documentary slot {nxt['us']} (US Eastern)"
    if nxt["status"] in ("uploaded", "scheduled", "ready"):
        return ind("supply", "Next documentary", "ok", f"{what}: {nxt['title'] or 'a video'} is {'on YouTube' if nxt['status'] == 'uploaded' else nxt['status']}", controls)
    if nxt["status"] == "later":
        return ind("supply", "Next documentary", "ok", f"{what}: Autopilot starts on it {nxt['starts_us']}", controls)
    at = dt.datetime.fromisoformat(nxt["at"].replace("Z", "+00:00"))
    urgent = at - now < dt.timedelta(hours=24 + 6) and nxt["status"] == "empty"
    how = {"repairing": "a draft is being repaired", "checking": "a draft is being checked", "empty": "nothing is ready, a new documentary is being made"}[nxt["status"]]
    return ind("supply", "Next documentary", "act" if urgent else "watch", f"{what}: {how}", controls,
               "Check the Autopilot page: it should be working on this now. If money is the reason, top up OpenRouter." if urgent else "")


def rules(vs, now: dt.datetime | None = None) -> dict:
    """The compliance catalog (compliance.RULES): which rules are enforced, which source pages changed after a rule was last verified, and which waiting videos fail one."""
    import compliance
    import newswatch

    now = now or dt.datetime.now(dt.timezone.utc)
    by_status = {s: sum(1 for r in compliance.RULES if r["status"] == s) for s in ("VERIFIED", "CONFLICTING", "UNVERIFIED")}
    changed = {}
    for c in newswatch.recent_policy_changes(now, days=3650):
        for r in compliance.RULES:
            if r["page"] == c["page"] and c["at"][:10] > r["verified"]:
                changed.setdefault(c["page"], []).append(r["id"])
    names = {r["id"] for r in compliance.RULES}
    failing = [f"{f.name} ({n})" for f, m in vs if not m.get("video_id") for n in sorted({c["name"] for c in (m.get("review") or {}).get("checks", []) if not c["ok"] and c["name"] in names})]
    level = "watch" if changed or failing else "ok"
    ev = (f"{by_status['VERIFIED']} rules checked on every video (sources read 20 Oct 2026, status VERIFIED); {by_status['CONFLICTING']} conflicting and {by_status['UNVERIFIED']} unverified are watched, not enforced. "
          + (f"YouTube changed a page after a rule was verified: {'; '.join(f'{p} (rules: {sorted(set(ids))})' for p, ids in changed.items())}. " if changed else "")
          + (f"Waiting videos failing a rule: {', '.join(failing)}. " if failing else ""))
    return ind("rules", "YouTube rules checked on every video", level, ev.strip(),
               "documented metadata limits, copied-wording check, kid-directed wording, thumbnail and title judged against the narration, the fixer repairs what it can; daily policy-page watch; post-publish safety check",
               "When a page changes: read it (the Activity feed links it), then tell me to re-verify the rule. Conflicting items (the API private-upload rule) are settled by the first public video.")


def assess(now: dt.datetime | None = None, out: Path | None = None, left: float | None = -1.0, running: list[str] | None = None) -> list[dict]:
    """All indicators. left=-1 means: read the balance live."""
    import llm

    now = now or dt.datetime.now(dt.timezone.utc)
    vs = videos(out)
    if left == -1.0:
        key = llm.api_key()
        left = credit_left(key) if key else None
    run = running_jobs() if running is None else running
    rows = [facts(vs), rights(vs), pattern(vs, now), money(left, daily_spend()), process(run, worker_starts(now)), skills(), access(), publishing(vs, now), supply(now), rules(vs, now)]
    return rows


def summary(rows: list[dict]) -> dict:
    return {"act": [r["name"] for r in rows if r["level"] == "act"], "watch": [r["name"] for r in rows if r["level"] == "watch"], "ok": sum(r["level"] == "ok" for r in rows)}


def main(argv: list[str] | None = None) -> int:
    rows = assess()
    for r in rows:
        print(f"{r['level'].upper():5} {r['name']}\n      {r['evidence']}\n      controls: {r['controls']}" + (f"\n      owner: {r['owner_decision']}" if r["owner_decision"] and r["level"] != "ok" else ""))
    s = summary(rows)
    print(f"\n{len(s['act'])} need action, {len(s['watch'])} to watch, {s['ok']} ok")
    return 1 if s["act"] else 0


if __name__ == "__main__":
    sys.exit(main())
