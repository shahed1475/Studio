#!/usr/bin/env python3
"""Local dashboard for the Shorts/documentary pipeline.  python dashboard.py  ->  http://127.0.0.1:8913

Stdlib only. Binds to localhost; POSTs must come from the dashboard page itself.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import config
import llm
import webauth

PORT = int(os.getenv("DASH_PORT", "8913"))
PY = sys.executable
LOGS = config.ROOT / "logs"
SETTINGS = config.ROOT / "settings.json"
SECRET = config.ROOT / "client_secret.json"
TOKEN = config.ROOT / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
YT_STATE = {"connecting": False, "error": ""}
AI_JOBS = {"make", "doc", "batch", "ideas", "research", "review", "seo", "newsvideo", "agent", "channels", "trends", "redo", "autopilot"}  # jobs that spend the user's AI key
ALLOWED_JOBS = {"branding", "channels", "trends", "subtitles", "newsvideo", "review", "autopilot", "agent", "newswatch", "seo", "thumbs", "ideas", "research", "make", "doc", "batch", "redo", "approve", "upload"}


# ---------- settings ----------
def load_settings() -> dict:
    return json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}


def save_settings(d: dict) -> None:
    SETTINGS.write_text(json.dumps(d, indent=2))
    SETTINGS.chmod(0o600)


def mask(s: str) -> str:
    return "" if not s else s[:4] + "…" + s[-3:] if len(s) > 10 else "set"


# ---------- data ----------
def videos() -> list[dict]:
    out = []
    for m in config.OUT.glob("*/meta.json"):
        d = json.loads(m.read_text())
        v = m.parent / "video.mp4"
        state = "uploaded" if d.get("video_id") else "approved" if d.get("approved") else "needs review"
        out.append({
            "slug": m.parent.name, "title": d.get("title", m.parent.name), "format": d.get("format", "short"),
            "state": state, "video_id": d.get("video_id"), "topic": d.get("topic", ""),
            "description": d.get("description", ""), "tags": d.get("tags", []),
            "subtitles": d.get("subtitles"), "has_srt": (m.parent / "captions.srt").exists(), "review": d.get("review"), "approved_by": d.get("approved_by"), "hold": bool(d.get("hold")), "publish_at": d.get("publish_at"), "seo": d.get("seo"), "tags": d.get("tags", []), "thumbs": d.get("thumbnails", []), "thumbnail": d.get("thumbnail", ""), "hook": d.get("thumb_hook", ""),
            "thumb_v": int((m.parent / "thumbs").stat().st_mtime) if (m.parent / "thumbs").exists() else 0,
            "mb": round(v.stat().st_size / 1e6, 1) if v.exists() else 0, "cost": round(__import__("llm").video_cost(m.parent.name), 2),
            "made": time.strftime("%Y-%m-%d %H:%M", time.localtime(v.stat().st_mtime)) if v.exists() else "",
            "mtime": v.stat().st_mtime if v.exists() else 0,
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(v.stat().st_mtime)) if v.exists() else "",
            "uploaded_at": d.get("uploaded_at"),
        })
        made = out[-1]["made_at"]  # the day a video belongs to: when it went up, when it goes public, or when it was made
        out[-1]["when"] = ({"kind": "uploaded", "at": d.get("uploaded_at") or made} if d.get("video_id")
                           else {"kind": "scheduled", "at": d["publish_at"]} if d.get("publish_at") else {"kind": "made", "at": made})
    return sorted(out, key=lambda x: -x["mtime"])


def queue() -> list[str]:
    return json.loads(config.TOPICS_FILE.read_text()) if config.TOPICS_FILE.exists() else []


def ollama_ok() -> bool:
    try:
        with urllib.request.urlopen(config.OLLAMA_URL + "/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def writer_status() -> tuple[bool, str]:
    """Is a model available for the script writer, and what is it? Cloud models first; the local one only when switched on."""
    import freemodels
    import llm

    cfg = llm.load_config()
    if llm.api_key() and cfg["free"]:
        q = freemodels.quota(llm.api_key())
        left = f", {q['remaining']} of {q['limit']} free requests left today" if q else ""
        return True, f"OpenRouter free models{left}"
    if llm.api_key() and cfg["enabled"]:
        return True, "OpenRouter paid models"
    if cfg.get("local_fallback") and ollama_ok():
        return True, f"local {config.MODEL}"
    return False, "no model set up"


def pexels_key() -> str:
    return config.PEXELS_KEY or load_settings().get("pexels_key", "")


def yt_status() -> dict:
    s = {"secret": SECRET.exists(), "token": TOKEN.exists(), "connecting": YT_STATE["connecting"], "error": YT_STATE["error"],
         "channel": None}
    if s["token"] and not s["connecting"]:
        try:
            s["channel"] = yt_channel()
        except Exception as e:
            s["error"] = f"{type(e).__name__}: {e}"[:300]
    return s


def yt_creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    return creds


def yt_channel() -> dict:
    from googleapiclient.discovery import build

    r = build("youtube", "v3", credentials=yt_creds(), cache_discovery=False).channels().list(
        part="snippet,statistics", mine=True).execute()
    if not r.get("items"):
        raise RuntimeError("signed in, but this Google account has no YouTube channel")
    c = r["items"][0]
    st = c["statistics"]
    return {"title": c["snippet"]["title"], "id": c["id"], "subs": st.get("subscriberCount", "hidden"),
            "views": st.get("viewCount", "0"), "videos": st.get("videoCount", "0")}


def yt_connect() -> None:
    """Runs Google's OAuth flow (opens a browser tab on this machine). Blocks, so call from a thread."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    YT_STATE.update(connecting=True, error="")
    try:
        creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0, timeout_seconds=300)
        TOKEN.write_text(creds.to_json())
        TOKEN.chmod(0o600)
        import datetime as dt

        import ytlogin

        ytlogin.stamp(dt.datetime.now(dt.timezone.utc))  # the 7-day clock of a Testing-mode login starts here
    except Exception as e:
        YT_STATE["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        YT_STATE["connecting"] = False


def llm_view() -> dict:
    """Settings for the AI models panel. The key itself is never included."""
    import aiart
    import autopilot
    import llm

    cfg, now = llm.load_config(), llm._now()
    usage = llm._usage()
    prices = llm.model_prices()
    role_prices = {r: (prices.get(cfg["models"][r]) if cfg["models"][r] else (0.0, 0.0)) for r in llm.ROLES}
    known = all(v is not None for v in role_prices.values())
    ap = autopilot.load_config()
    art = (aiart.MAX_PER_VIDEO["doc"] * aiart.PRICE_EACH, aiart.MAX_PER_VIDEO["short"] * aiart.PRICE_EACH) if cfg.get("ai_art") else (0.0, 0.0)
    est = llm.estimate({r: v for r, v in role_prices.items() if v}, ap["uploads_per_day"], ap["shorts_per_day"] if ap["shorts"] else 0, art=art) if known else None
    today = usage.get(llm._day(now), {})
    return {
        "config": cfg, "key_set": bool(llm.api_key()), "anthropic_key_set": bool(llm.anthropic_key()), "spent_today": round(llm.spent_today(now), 4), "calls_today": today.get("calls", 0),
        "fallbacks": today.get("fallbacks", [])[-5:], "by_role_today": today.get("by_role", {}),
        "history": [{"day": d, "usd": round(v["usd"], 4), "calls": v["calls"]} for d, v in sorted(usage.items())[-7:]],
        "role_prices": {r: v for r, v in role_prices.items()}, "estimate": est,
        "plan": {"docs_per_day": ap["uploads_per_day"], "shorts_per_day": ap["shorts_per_day"] if ap["shorts"] else 0},
        "free": {"on": cfg["free"], "limit": cfg["free_daily_limit"], "requests_today": __import__("freemodels").requests_today(now),
                 "openrouter": __import__("freemodels").quota(llm.api_key()) if llm.api_key() else None,
                 "chain": __import__("freemodels").choose("cheap", now)},
        "models": sorted(({"id": k, "in": round(v[0], 3), "out": round(v[1], 3)} for k, v in prices.items()
                          if v[0] > 0 and not any(t in k for t in (":free", ":batch", "image", "audio", "embed"))), key=lambda m: m["id"]),
    }


def autopilot_cfg() -> dict:
    import autopilot

    return autopilot.load_config()


def state() -> dict:
    vids = videos()
    return {
        "videos": vids, "queue": queue(), "niche": config.niche(),
        "counts": {k: sum(v["state"] == k for v in vids) for k in ("needs review", "approved", "uploaded")},
        "health": {
            "ollama": writer_status()[0], "model": writer_status()[1], "ffmpeg": bool(shutil.which("ffmpeg")),
            "pexels": bool(pexels_key()), "voice": config.VOICE, "disk_free_gb": round(shutil.disk_usage(config.ROOT).free / 1e9, 1),
        },
        "youtube": {"secret": SECRET.exists(), "token": TOKEN.exists(), "connecting": YT_STATE["connecting"], "error": YT_STATE["error"], "web": __import__("ytweb").available()},
        "jobs": sorted(({k: v for k, v in j.items() if k != "proc"} for j in JOBS.values()), key=lambda j: -j["started"])[:30],
        "autopilot": {"enabled": autopilot_cfg().get("enabled", False), "needs_you": len(autopilot_view()["needs_you"]), "next": next_slot_view(), "busy": __import__("autopilot").is_running()},
        "agent": {"unread": __import__("agentlog").unread()},
        "tenant": __import__("tenantmode").is_tenant(), "niche_confirmed": __import__("niche").current()["brief"] is not None and bool((__import__("niche").current()["brief"] or {}).get("confirmed")),
        "auth": {"on": webauth.enabled(), "email": webauth.owner_email()},
        "settings": {"pexels_key": "saved" if load_settings().get("pexels_key") else ""},
    }


def safe_slug(raw: str) -> str:
    """Video folder names are lowercase letters, digits, hyphens and underscores, never a path."""
    if not isinstance(raw, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", raw):
        raise ValueError("bad video name")
    return raw


def set_hold(meta: dict, hold: bool) -> None:
    meta["hold"] = hold
    if not hold:  # a released video gets a fresh slot instead of a stale or shared one
        meta.pop("publish_at", None)
        meta["autopilot_fails"] = 0


# ---------- autopilot ----------
def validate_autopilot_config(raw: dict) -> dict:
    """Accepts a partial settings dict; raises ValueError for anything out of range."""
    import scheduler

    rules = {"uploads_per_day": (1, 2), "review_window_hours": (6, 168), "upload_lead_hours": (1, 12),
             "min_queue": (1, 20), "prepare_hours": (0, 72), "max_waiting": (1, 5), "shorts_per_day": (1, 2), "max_waiting_shorts": (1, 10)}
    out = {}
    for k, v in raw.items():
        if k in rules:
            lo, hi = rules[k]
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise ValueError(f"{k} must be a whole number from {lo} to {hi}")
        elif k in ("enabled", "auto_approve", "news_videos", "shorts", "make_videos"):
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be on or off")
        elif k in ("slots", "short_slots"):
            if not isinstance(v, list) or not 1 <= len(v) <= 7:
                raise ValueError("choose between 1 and 7 publish slots")
            for sl in v:
                if sl.get("day") not in scheduler.DAYS or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(sl.get("time", ""))):
                    raise ValueError("each slot needs a weekday and a time like 18:00")
            v = [{"day": sl["day"], "time": sl["time"]} for sl in v]
        else:
            raise ValueError(f"unknown setting: {k}")
        out[k] = v
    return out


def timer_installed(unit: str) -> bool:
    import worker

    return worker.alive() or (Path.home() / ".config/systemd/user" / unit).exists()


_RISK = {"at": 0.0, "data": None}


def risk_view() -> dict:
    """The risk monitor's rows and summary, recomputed at most once a minute (it reads files and the OpenRouter balance)."""
    import risk

    if time.time() - _RISK["at"] > 60 or _RISK["data"] is None:
        rows = risk.assess()
        _RISK.update(at=time.time(), data={"rows": rows, "summary": risk.summary(rows)})
    return _RISK["data"]


def agent_view() -> dict:
    import agent
    import agentlog
    import channelwatch
    import discover
    import editprofile
    import growth
    import strategy

    import datetime as dt

    import monetization

    own = growth.load_snapshots(1)
    return {"monetization": monetization.progress(own[-1], dt.datetime.now(dt.timezone.utc), monetization.ready_count()) if own else None,
            "config": agent.load_config(), "events": agentlog.recent(50), "unread": agentlog.unread(), "strategies": strategy.load()[::-1],
            "report": agent.latest_report(), "discovered": discover.load(), "refs": channelwatch.load_refs(), "own": own[-1] if own else None,
            "profile": editprofile.load(), "timer_installed": timer_installed("story-agent.timer"),
            "refs_meta": channelwatch.load_meta()}


def agent_config(b: dict) -> dict:
    import agent

    cfg = agent.load_config()
    cfg.update({k: b[k] for k in ("mode", "auto_channels", "auto_per_day", "max_auto", "auto_topics", "topics_per_day") if k in b})
    return agent.save_config(cfg)


def agent_strategy(b: dict) -> dict:
    import strategy

    action = b.get("action")
    if action == "apply":
        return strategy.apply(b["id"])
    if action in ("dismiss", "restore"):
        return strategy.set_status(b["id"], "dismissed" if action == "dismiss" else "proposed")
    raise ValueError("unknown action")


def agent_profile(b: dict) -> dict:
    import editprofile

    clean = editprofile.validate(b)
    if not clean or set(clean) != set(b):
        raise ValueError("that is not a valid setting")
    return editprofile.update(clean)


def agent_read() -> dict:
    import agentlog

    agentlog.mark_read()
    return {"ok": True}


_NEXT = {"at": 0.0, "data": None}


def next_slot_view() -> dict | None:
    """The next slot that is not already too close, for the Home card; recomputed at most every 30 seconds."""
    import autopilot

    if time.time() - _NEXT["at"] > 30:
        rows = [r for r in autopilot.plan_view()["rows"] if r["status"] != "too_soon"]
        _NEXT.update(at=time.time(), data={k: rows[0][k] for k in ("us", "bd", "format", "status", "title", "starts_us", "at")} if rows else None)
    return _NEXT["data"]


def autopilot_view() -> dict:
    import datetime as dt

    import scheduler

    scheduled, needs, repairing = [], [], []
    for m in sorted(config.OUT.glob("*/meta.json")):
        d = json.loads(m.read_text())
        rv = d.get("review") or {}
        base = {"slug": m.parent.name, "format": d.get("format", "short"), "title": d.get("title", m.parent.name), "verdict": rv.get("verdict"), "source": d.get("source"),
                "hold": bool(d.get("hold")), "approved": bool(d.get("approved")), "approved_by": d.get("approved_by"),
                "fails": d.get("autopilot_fails", 0)}
        you_ok = d.get("approved") and d.get("approved_by") == "you" and rv.get("verdict") != "fail"
        if rv.get("verdict") in ("needs_human", "fail") and not d.get("video_id") and not you_ok:
            item = {**base, "why": [c["detail"] for c in rv.get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")][:3]}
            stale = any(c["name"] == "llm_review" and not c["ok"] for c in rv.get("checks", []))  # the AI part never ran: it is simply not reviewed yet
            still_fixable = not (d.get("fix_gave_up") or d.get("fix_attempts", 0) >= 2 or d.get("source") == "news" or d.get("hold"))  # a held video is waiting for your decision
            (repairing if (still_fixable or stale) and d.get("source") != "news" else needs).append(item)  # only what Autopilot cannot repair waits for you
        if d.get("publish_at"):
            when = dt.datetime.fromisoformat(d["publish_at"].replace("Z", "+00:00"))
            scheduled.append({**base, "publish_at": d["publish_at"], "uploaded": bool(d.get("video_id")), "final_check": ("passed" if (d.get("prelaunch") or {}).get("ok") else "failed" if d.get("prelaunch") else "pending"),
                              "bd": scheduler.fmt_local(when, "Asia/Dhaka"), "us": scheduler.fmt_local(when, "America/New_York")})
    scheduled.sort(key=lambda x: x["publish_at"])
    return {"scheduled": scheduled, "needs_you": needs, "repairing": repairing}


# ---------- jobs ----------
def start_job(cmd: str, args: list[str]) -> str:
    if cmd not in ALLOWED_JOBS:
        raise ValueError("unknown job")
    if any(j["status"] == "running" for j in JOBS.values()):
        raise RuntimeError("another job is still running")
    import autopilot

    if cmd != "autopilot" and autopilot.is_running():
        raise RuntimeError("autopilot is working right now, try again in a few minutes")
    LOGS.mkdir(exist_ok=True)
    jid = time.strftime("%H%M%S") + "-" + cmd
    log = LOGS / f"{jid}.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    if pexels_key():
        env["PEXELS_API_KEY"] = pexels_key()
    proc = subprocess.Popen([PY, "run.py", cmd, *args], cwd=config.ROOT, stdout=log.open("w"), stderr=subprocess.STDOUT, env=env)
    job = {"id": jid, "cmd": f"{cmd} {' '.join(args)}".strip(), "status": "running", "started": time.time(), "ended": None, "proc": proc}
    JOBS[jid] = job
    if cmd != "autopilot":  # tells the autopilot timer to stay out of the way
        autopilot.JOB_FILE.write_text(str(proc.pid))

    def watch():
        rc = proc.wait()
        if autopilot.JOB_FILE.exists() and autopilot.JOB_FILE.read_text().strip() == str(proc.pid):
            autopilot.JOB_FILE.unlink(missing_ok=True)
        job.update(status="done" if rc == 0 else "failed", ended=time.time())

    threading.Thread(target=watch, daemon=True).start()
    return jid


# ---------- http ----------
def allowed_hosts() -> set[str]:
    """Names the browser may use. Others (a rebinding page, a stray proxy) are refused. STUDIO_HOSTS adds e.g. the Tailscale address."""
    extra = {h.strip() for h in os.getenv("STUDIO_HOSTS", "").split(",") if h.strip()}
    named = {h for h in extra} | {f"{h}:{PORT}" for h in extra if ":" not in h}  # a name alone is what a browser sends on the standard HTTPS port, behind the proxy
    return {f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"studio.localhost:{PORT}"} | named


# ---------- niche page (user studios) ----------
NICHE_JOB = {"state": "idle", "step": "", "error": "", "fit": None}


def _niche_yt():
    """A YouTube client for niche research when the user has connected their channel, else None (the research then skips the trend study)."""
    try:
        import upload

        return upload._service() if TOKEN.exists() else None
    except Exception:
        return None


def niche_view() -> dict:
    import niche

    return {"presets": [{k: p[k] for k in ("id", "name", "audience", "channel_angle", "starter_topics")} for p in niche.PRESETS],
            "current": niche.current(), "job": dict(NICHE_JOB), "setup": {"key": bool(llm.api_key()), "youtube": TOKEN.exists()}}


def _niche_start(build) -> None:
    """Research a chosen niche in the background: the subjects are checked against Wikipedia and screened, then the niche and its brief are saved for the user to read."""
    import niche
    import topicrank

    if not llm.api_key():
        raise ValueError("Add your OpenRouter key in Settings first: the niche research uses your own key.")
    if NICHE_JOB["state"] == "working":
        raise ValueError("The niche research is already running.")
    NICHE_JOB.update(state="working", step="checking the subjects in Wikipedia and what viewers watch", error="")

    def work():
        try:
            n = build()
            brief = niche.research(n, yt=_niche_yt(), premise_of=lambda t, a: topicrank.premise_check(t, a))
            niche.apply(n, brief)
            NICHE_JOB.update(state="done", step="")
        except Exception as e:
            NICHE_JOB.update(state="error", error=f"{type(e).__name__}: {e}"[:300], step="")

    threading.Thread(target=work, daemon=True).start()


def client_ip(handler) -> str:
    """The visitor's address. Behind the studio's own web proxy (it connects from this machine) the proxy's X-Forwarded-For names the real visitor, so wrong
    passwords are counted per visitor and not for everybody at once; from anywhere else the header is not believed."""
    ip = handler.client_address[0]
    fwd = (handler.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()  # the last entry is the one our proxy added; earlier ones came from the visitor
    return fwd if _is_proxy(ip) and fwd else ip


def _is_proxy(ip: str) -> bool:
    """Our own web proxy: this machine, or (in a user studio, which runs in a container) the gateway of the container's network, which is how Docker shows
    a connection that came through the published port. Nothing else is believed about who the visitor is."""
    if ip in ("127.0.0.1", "::1"):
        return True
    import ipaddress

    import tenantmode

    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return tenantmode.is_tenant() and a.version == 4 and a in ipaddress.ip_network("172.16.0.0/12") and int(a) % 256 == 1


def listen_addresses(claimed: bool) -> list[str]:
    """Where the dashboard listens. The owner's studio: loopback, plus STUDIO_BIND once a login exists. A user studio (in a container behind a published port): only
    STUDIO_BIND, from the start, because the invite page has to be reachable; until the login exists the studio answers nothing else."""
    import tenantmode

    bind = os.getenv("STUDIO_BIND", "").strip()
    if tenantmode.is_tenant() and bind:
        return [bind]
    return ["127.0.0.1"] + ([bind] if bind and claimed else [])


def _tenant_unclaimed() -> bool:
    import tenantmode

    return tenantmode.is_tenant() and not webauth.enabled()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _authed(self) -> bool:
        if _tenant_unclaimed():
            return False  # a user studio that nobody has claimed yet is never open
        return not webauth.enabled() or webauth.check_token(webauth.cookie_from(self.headers.get("Cookie", ""))) is not None

    def _page(self, b, code=200, extra=()):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _redirect(self, where, extra=()):
        self.send_response(303)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def _login(self):
        ip = client_ip(self)
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(min(n, 4096)).decode(errors="replace"))
        if not webauth.LIMITER.reserve(ip):  # the slot is taken before the check; a right password gives it back
            return self._page(webauth.login_page("Too many wrong attempts. Wait ten minutes and try again."), 429)
        if webauth.verify(form.get("email", [""])[0], form.get("password", [""])[0]):
            webauth.LIMITER.clear(ip)
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            cookie = f"{webauth.COOKIE}={webauth.make_token(webauth.owner_email())}; HttpOnly; SameSite=Strict; Path=/; Max-Age={webauth.SESSION_DAYS * 86400}{secure}"
            return self._redirect("/", [("Set-Cookie", cookie)])
        time.sleep(0.6)
        self._page(webauth.login_page("That email or password is not right."), 401)

    def _claim(self):
        ip = client_ip(self)
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(min(n, 4096)).decode(errors="replace"))
        tok, email = form.get("token", [""])[0], form.get("email", [""])[0]
        pw, pw2 = form.get("password", [""])[0], form.get("password2", [""])[0]
        if not webauth.CLAIM_LIMITER.reserve(ip):
            return self._page(webauth.claim_page(tok, "Too many tries. Wait ten minutes."), 429)
        if pw != pw2:
            return self._page(webauth.claim_page(tok, "The two passwords are different."), 400)
        try:
            webauth.claim(tok, email, pw)
        except ValueError as e:
            return self._page(webauth.claim_page(tok, str(e)), 400)
        webauth.CLAIM_LIMITER.clear(ip)
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        cookie = f"{webauth.COOKIE}={webauth.make_token(webauth.owner_email())}; HttpOnly; SameSite=Strict; Path=/; Max-Age={webauth.SESSION_DAYS * 86400}{secure}"
        return self._redirect("/", [("Set-Cookie", cookie)])

    def do_GET(self):
        if self.headers.get("Host", "") not in allowed_hosts():
            return self.send_error(403)
        u = urlparse(self.path)
        if u.path == "/healthz":
            return self.send_bytes(b"ok", "text/plain")
        if u.path == "/oauth/callback":
            if not self._authed():
                return self._redirect("/login")
            import ytweb

            q = parse_qs(u.query)
            if q.get("error"):
                return self._page(b'<p>Google sign-in was not allowed or was cancelled.</p><p><a href="/#youtube">Back to the YouTube page</a></p>', 400)
            try:
                ytweb.finish((q.get("code") or [""])[0], (q.get("state") or [""])[0], ytweb.redirect_uri() or "")
            except Exception as e:
                import html

                return self._page(f'<p>{html.escape(str(e))}</p><p><a href="/#youtube">Back to the YouTube page</a></p>'.encode(), 400)
            return self._redirect("/#youtube")
        if u.path == "/claim":
            tok = (parse_qs(u.query).get("token") or [""])[0]
            if webauth.enabled() or not webauth.invite_valid(tok):
                return self._page(b"This invite link is not valid any more. Ask for a new one.", 400)
            return self._page(webauth.claim_page(tok))
        if _tenant_unclaimed() and not u.path.startswith("/static/"):
            return self._page(b"This studio is not set up yet. Open the invite link you were sent.", 403)
        if u.path == "/login":
            return self._redirect("/") if self._authed() else self._page(webauth.login_page())
        if not u.path.startswith("/static/") and not self._authed():
            if u.path.startswith("/api/"):
                return self.send_json({"error": "sign in again"}, 401)
            return self._redirect("/login")
        try:
            self._get()
        except ValueError:  # a malformed video name is just not found
            self.send_error(404)

    def _get(self):
        u = urlparse(self.path)
        if u.path == "/":
            b = (config.ROOT / "dashboard.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/state":
            self.send_json(state())
        elif u.path == "/api/autopilot":
            import autopilot
            import newswatch

            self.send_json({**autopilot_view(), "config": autopilot.load_config(), "status": autopilot.status(),
                            "news": newswatch.latest_digest(), "trends": __import__("trendwatch").latest(),
                            "agent_config": __import__("agent").load_config(),
                            "channels": {"refs": __import__("channelwatch").load_refs(), "digest": __import__("channelwatch").latest(),
                                         "meta": __import__("channelwatch").load_meta(), "max": __import__("channelwatch").MAX_REFS,
                                         "suggestions": __import__("channelwatch").suggest(__import__("trendwatch").latest())},
                            "timer_installed": timer_installed("story-autopilot.timer"),
                            "proposals": [t for t in (json.loads(newswatch.TOPICS_FILE.read_text()) if newswatch.TOPICS_FILE.exists() else []) if t["status"] == "proposed"],
                            "news_queue": [t for t in (json.loads(newswatch.NEWS_QUEUE.read_text()) if newswatch.NEWS_QUEUE.exists() else []) if t["status"] == "queued"]})
        elif u.path == "/api/risk":
            self.send_json(risk_view())
        elif u.path == "/api/agent":
            self.send_json(agent_view())
        elif u.path == "/api/llm":
            self.send_json(llm_view())
        elif u.path == "/api/youtube":
            self.send_json(yt_status())
        elif u.path == "/api/niche":
            import tenantmode

            self.send_json(niche_view()) if tenantmode.is_tenant() else self.send_json({"error": "only in a user studio"}, 404)
        elif u.path == "/api/log":
            jid = parse_qs(u.query).get("id", [""])[0]
            f = LOGS / f"{re.sub(r'[^A-Za-z0-9_-]', '', jid)}.log"
            self.send_json({"text": f.read_text(errors="replace")[-8000:] if f.exists() else ""})
        elif u.path.startswith("/branding/") and u.path[10:] in ("avatar.png", "banner.png", "description.txt"):
            f = config.ROOT / "branding" / u.path[10:]
            if not f.exists():
                return self.send_error(404)
            self.send_bytes(f.read_bytes(), "image/png" if f.suffix == ".png" else "text/plain; charset=utf-8")
        elif u.path.startswith("/captions/") and u.path.endswith(".srt"):
            f = config.OUT / safe_slug(u.path[10:-4]) / "captions.srt"
            if not f.exists():
                return self.send_error(404)
            b = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-subrip; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{f.parent.name}.srt"')
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path.startswith("/static/"):
            self.serve_static(u.path[8:])
        elif u.path.startswith("/thumbopt/"):
            slug, _, n = u.path[10:].partition("/")
            f = config.OUT / safe_slug(slug) / "thumbs" / f"thumb-{re.sub(r'[^0-9]', '', n)}.jpg"
            self.send_bytes(f.read_bytes(), "image/jpeg") if f.exists() else self.send_error(404)
        elif u.path.startswith("/thumb/"):
            self.serve_thumb(u.path[7:])
        elif u.path.startswith("/video/"):
            self.serve_video(u.path[7:])
        else:
            self.send_error(404)

    def serve_static(self, name):
        p = (config.ROOT / "static" / name).resolve()
        if not p.is_file() or config.ROOT / "static" not in p.parents:
            return self.send_error(404)
        kind = {".svg": "image/svg+xml", ".woff2": "font/woff2", ".css": "text/css"}.get(p.suffix, "application/octet-stream")
        self.send_bytes(p.read_bytes(), kind)

    def serve_thumb(self, slug):
        """First-seconds frame of the video, cached as a small jpg."""
        slug = safe_slug(slug)
        video, out = config.OUT / slug / "video.mp4", config.CACHE / "thumbs" / f"{slug}.jpg"
        if not video.exists():
            return self.send_error(404)
        if not out.exists() or out.stat().st_mtime < video.stat().st_mtime:
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "8", "-i", str(video), "-frames:v", "1", "-vf", "scale=640:-2", str(out)])
            if not out.exists():  # clip shorter than 8 s
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-frames:v", "1", "-vf", "scale=640:-2", str(out)])
        if not out.exists():
            return self.send_error(404)
        self.send_bytes(out.read_bytes(), "image/jpeg")

    def send_bytes(self, b, kind):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-cache" if kind == "text/css" else "max-age=3600")
        self.end_headers()
        self.wfile.write(b)

    def serve_video(self, slug):
        p = (config.OUT / safe_slug(slug) / "video.mp4")
        if not p.exists():
            return self.send_error(404)
        size = p.stat().st_size
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m:
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = min(int(m.group(2)), size - 1)
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if m:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with p.open("rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        if host not in allowed_hosts() or (origin and urlparse(origin).netloc != host):
            return self.send_json({"error": "forbidden"}, 403)
        path = urlparse(self.path).path
        if path == "/claim":
            return self._claim()
        if path == "/login":
            return self._login()
        if path == "/logout":
            webauth.revoke(webauth.cookie_from(self.headers.get("Cookie", "")))
            return self._redirect("/login", [("Set-Cookie", f"{webauth.COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")])
        if not self._authed():
            return self.send_json({"error": "sign in again"}, 401)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            self.send_json(self.route(urlparse(self.path).path, body))
        except Exception as e:
            self.send_json({"error": f"{e}"}, 400)

    def route(self, path, b):
        if path == "/api/job":
            import tenantmode

            if tenantmode.is_tenant() and b.get("cmd") in AI_JOBS and not sys.modules["llm"].api_key():
                raise ValueError("Add your own OpenRouter key in Settings first: this uses your key.")
            args = [str(a) for a in b.get("args", [])]
            return {"id": start_job(b["cmd"], args)}
        if path == "/api/queue/add":
            t = b["topic"].strip()
            if t:
                import topicqueue

                topicqueue.append_unique(t)
            return {"ok": True}
        if path == "/api/queue/remove":
            import topicqueue

            topicqueue.remove(b["index"])
            return {"ok": True}
        if path == "/api/autopilot/config":
            import autopilot

            cfg = autopilot.load_config()
            new = validate_autopilot_config(b)
            if new.get("enabled") and __import__("tenantmode").is_tenant():  # a user studio starts only with the user's own key and a plan they have confirmed
                if not sys.modules["llm"].api_key():
                    raise ValueError("Add your own OpenRouter key in Settings before turning Autopilot on.")
                if not __import__("niche").current()["brief"] or not __import__("niche").current()["brief"].get("confirmed"):
                    raise ValueError("Choose your niche and confirm the plan on the Niche page before turning Autopilot on.")
            cfg.update(new)
            autopilot.save_config(cfg)
            return {"ok": True}
        if path == "/api/agent/config":
            return {"config": agent_config(b)}
        if path == "/api/agent/strategy":
            return {"strategy": agent_strategy(b)}
        if path == "/api/agent/profile":
            return {"profile": agent_profile(b)}
        if path == "/api/agent/read":
            return agent_read()
        if path == "/api/autopilot/hold":
            p = config.OUT / safe_slug(b["slug"]) / "meta.json"
            d = json.loads(p.read_text())
            if d.get("video_id") and b["hold"]:
                raise ValueError("already uploaded: change or delete it in YouTube Studio")
            set_hold(d, bool(b["hold"]))
            p.write_text(json.dumps(d, indent=2))
            return {"ok": True}
        if path == "/api/llm/config":
            import llm

            b = dict(b)
            key = b.pop("key", None)
            clear = b.pop("clear_key", False)
            akey = b.pop("anthropic_key", None)
            aclear = b.pop("clear_anthropic_key", False)
            clean = llm.validate_config(b)
            cfg = llm.load_config()
            cfg.update({k: v for k, v in clean.items() if k != "models"})
            cfg["models"].update(clean.get("models", {}))
            if (cfg["enabled"] or cfg["free"]) and not (llm.api_key() or llm.anthropic_key() or (key or "").strip() or (akey or "").strip()):
                raise ValueError("save your OpenRouter or Anthropic key before turning it on")
            llm.save_config(cfg)
            st = load_settings()
            if aclear:
                st.pop("anthropic_key", None)
                save_settings(st)
            elif akey and akey.strip():
                akey = akey.strip()
                if not 10 <= len(akey) <= 300 or re.search(r"\s", akey):
                    raise ValueError("that does not look like an API key")
                st["anthropic_key"] = akey
                save_settings(st)
            if clear:
                st.pop("openrouter_key", None)
                save_settings(st)
            elif key and key.strip():
                key = key.strip()
                if not 10 <= len(key) <= 300 or re.search(r"\s", key):
                    raise ValueError("that does not look like an API key")
                st["openrouter_key"] = key
                save_settings(st)
            return {"ok": True}
        if path == "/api/llm/test":
            import llm

            return llm.test_call(str(b.get("role", "cheap")))
        if path == "/api/channels/add":
            import channelwatch

            channelwatch.add_ref(str(b["ref"]))
            return {"ok": True}
        if path == "/api/channels/remove":
            import channelwatch

            channelwatch.remove_ref(str(b["ref"]))
            return {"ok": True}
        if path == "/api/news/queue":
            import newswatch

            newswatch.queue_news_topic(str(b["topic"]), [str(x) for x in b.get("sources", [])], str(b.get("week", "")))
            topics = json.loads(newswatch.TOPICS_FILE.read_text()) if newswatch.TOPICS_FILE.exists() else []
            for t in topics:
                if t["topic"] == b["topic"]:
                    t["status"] = "queued"
            newswatch.TOPICS_FILE.write_text(json.dumps(topics, indent=2))
            return {"ok": True}
        if path == "/api/video/approve":
            p = config.OUT / safe_slug(b["slug"]) / "meta.json"
            d = json.loads(p.read_text())
            d["approved"] = True
            d["approved_by"] = "you"
            p.write_text(json.dumps(d, indent=2))
            return {"ok": True}
        if path == "/api/thumbs/choose":
            p = config.OUT / safe_slug(b["slug"]) / "meta.json"
            d = json.loads(p.read_text())
            if f"thumbs/thumb-{int(b['n'])}.jpg" not in d.get("thumbnails", []):
                raise ValueError("no such thumbnail")
            d["thumbnail"] = f"thumbs/thumb-{int(b['n'])}.jpg"
            import reviewer

            reviewer.invalidate(d)
            p.write_text(json.dumps(d, indent=2))
            return {"ok": True}
        if path == "/api/video/update":
            p = config.OUT / safe_slug(b["slug"]) / "meta.json"
            d = json.loads(p.read_text())
            if d.get("video_id"):
                raise ValueError("already uploaded")
            for k in ("title", "description"):
                if k in b:
                    d[k] = b[k]
            import reviewer

            reviewer.invalidate(d)
            p.write_text(json.dumps(d, indent=2))
            return {"ok": True}
        if path == "/api/key/save":
            which, value = str(b.get("which", "")), str(b.get("value", "")).strip()
            field = {"openrouter": "openrouter_key", "pexels": "pexels_key"}.get(which)
            if not field:
                raise ValueError("unknown key")
            if not 10 <= len(value) <= 300 or re.search(r"\s", value):
                raise ValueError("that does not look like an API key")
            st = load_settings()
            st[field] = value
            save_settings(st)  # owner-only file; the key is never sent back to a browser
            if which == "openrouter" and __import__("tenantmode").is_tenant():
                __import__("tenantmode").on_key_saved()
            return {"ok": True}
        if path == "/api/settings":
            s = load_settings()
            if b.get("pexels_key"):
                s["pexels_key"] = b["pexels_key"].strip()
            save_settings(s)
            return {"ok": True}
        if path == "/api/youtube/secret":
            try:
                d = json.loads(b["json"])
            except ValueError:
                raise ValueError("that text is not valid JSON; paste the whole downloaded file")
            if not ({"installed", "web"} & d.keys()):
                raise ValueError("this is not an OAuth client JSON (expected an 'installed' or 'web' section; create a Desktop app client)")
            if "installed" not in d:
                raise ValueError("the client type must be 'Desktop app', but this one is 'Web application'")
            SECRET.write_text(json.dumps(d, indent=2))
            SECRET.chmod(0o600)
            TOKEN.unlink(missing_ok=True)
            return {"ok": True}
        if path == "/api/youtube/connect":
            if __import__("tenantmode").is_tenant():
                raise ValueError("Use Sign in with Google on this page: the desktop sign-in would open a browser on the server, not on your device.")
            if not SECRET.exists():
                raise ValueError("save client_secret.json first")
            if YT_STATE["connecting"]:
                raise ValueError("already waiting for Google sign-in")
            threading.Thread(target=yt_connect, daemon=True).start()
            return {"ok": True}
        if path.startswith("/api/niche/"):
            import niche
            import tenantmode

            if not tenantmode.is_tenant():
                raise ValueError("only in a user studio")
            if path == "/api/niche/choose":
                chosen = niche.preset(str(b.get("id", "")))
                if not chosen:
                    raise ValueError("unknown niche")
                _niche_start(lambda: chosen)
                return {"ok": True}
            if path == "/api/niche/custom":
                desc = str(b.get("description", ""))
                if not sys.modules["llm"].api_key():  # `llm` is imported inside other branches of this function, so the module is reached by name
                    raise ValueError("Add your OpenRouter key in Settings first: the niche check uses your own key.")
                fit = niche.fit_check(desc)
                NICHE_JOB["fit"] = fit
                if not fit["fit"]:
                    return {"ok": True, **fit}
                _niche_start(lambda: niche.build_custom(desc, fit))
                return {"ok": True, **fit}
            if path == "/api/niche/confirm":
                return {"ok": True, "brief": niche.confirm()}
        if path == "/api/youtube/web-start":
            import ytweb

            uri = ytweb.redirect_uri()
            if not uri:
                raise ValueError("This studio has no public address set, so Google cannot send you back to it.")
            return {"url": ytweb.start(uri)}
        if path == "/api/youtube/disconnect":
            TOKEN.unlink(missing_ok=True)
            if __import__("tenantmode").is_tenant():
                __import__("ytweb").release()  # the channel can then be connected to the studio that really owns it
            return {"ok": True}
        raise ValueError("unknown endpoint")



if __name__ == "__main__":
    import tenantmode

    if tenantmode.is_tenant():
        tenantmode.apply_defaults()
        webauth.LIMITER.global_max = 30  # guessing from many addresses at once is stopped too (a sign-in that works gives its slot back; a signed-in session is not affected)
        webauth.CLAIM_LIMITER.global_max = 30
    print(f"Dashboard: http://studio.localhost:{PORT}   (also http://127.0.0.1:{PORT})")
    addrs = listen_addresses(webauth.enabled())
    if os.getenv("STUDIO_BIND", "").strip() and len(addrs) == 1 and addrs[0] == "127.0.0.1":
        print("STUDIO_BIND ignored: set a password first with python set_password.py")
    for extra in addrs[1:]:
        threading.Thread(target=ThreadingHTTPServer((extra, PORT), H).serve_forever, daemon=True).start()
        print(f"Also listening on {extra}:{PORT} behind the login")
    ThreadingHTTPServer((addrs[0], PORT), H).serve_forever()
