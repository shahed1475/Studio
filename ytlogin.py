"""The YouTube login: when it was created, whether it still works, and when it runs out.

While the Google OAuth consent screen is in "Testing" (external users), Google ends every login 7 days after consent
(developers.google.com/identity/protocols/oauth2, read 20 Oct 2026). The pages read do not say whether "In production" removes that, so the
mode is a fact the owner reports (`python run.py youtube-login production` after publishing the app and reconnecting) and the daily
refresh check shows what really happens. Docs: docs/GOOGLE_PRODUCTION.md.
"""
import datetime as dt
import json

import agentlog
import config

STATE = config.ROOT / "data" / "youtube_login.json"
TESTING_DAYS = 7
TS = "%Y-%m-%dT%H:%M:%SZ"
STEPS = ("Reconnect YouTube: on your PC start the dashboard (./start.sh), open YouTube, press Connect, then copy token.json to the server "
         "(scp token.json deploy@<server>:studio/). To stop this every 7 days, open Google Cloud Console, Audience, press Publish app, then reconnect once "
         "and run: python run.py youtube-login production. Details: docs/GOOGLE_PRODUCTION.md.")


def _load() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, indent=2))
    except OSError:
        pass  # advisory record of the last check: a lost save means the alert may repeat next hour, never a crashed health check


def stamp(at: dt.datetime, mode: str | None = None, estimate: bool = False) -> None:
    """Record when the login was created (a new consent), and optionally which mode the Google project is in."""
    d = _load()
    d.update(consented_at=at.strftime(TS), estimate=estimate, mode=mode or d.get("mode", "testing"))
    _save(d)


def status(now: dt.datetime) -> dict:
    d = _load()
    out = {"consented_at": d.get("consented_at"), "mode": d.get("mode", "testing"), "estimate": bool(d.get("estimate")), "last_check": d.get("last_check"),
           "last_ok": d.get("last_ok"), "days_left": None}
    if not out["consented_at"]:
        return {**out, "level": "watch", "detail": "no consent date recorded: reconnect YouTube once so it is stamped"}
    age = (now - dt.datetime.strptime(out["consented_at"], TS).replace(tzinfo=dt.timezone.utc)).total_seconds() / 86400
    if out["mode"] == "production":
        return {**out, "level": "ok", "detail": f"in production mode, login is {age:.1f} days old"}
    out["days_left"] = TESTING_DAYS - age
    left = out["days_left"]
    level = "act" if left <= 1 else "watch" if left <= 2 else "ok"
    return {**out, "level": level, "detail": f"testing mode: logins end {TESTING_DAYS} days after consent, {left:.1f} days left" + (" (consent date estimated)" if out["estimate"] else "")}


def _real_refresh() -> None:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    import upload

    creds = upload.load_creds()
    creds.refresh(Request())
    upload.save_token(creds)


OFFLINE_NAMES = {"TransportError", "ConnectionError", "ServerNotFoundError", "NameResolutionError", "NewConnectionError", "MaxRetryError", "ConnectTimeout",
                 "ReadTimeout", "Timeout", "TimeoutError", "timeout", "gaierror", "ConnectionRefusedError", "ConnectionResetError", "ConnectionAbortedError"}


def offline(e: BaseException | None) -> bool:
    """True when Google was not reached at all (no DNS, no route, refused, timed out) or said to try again later (a retryable answer): the network,
    not the login. The offline drill of 23 Nov 2026 showed 'Temporary failure in name resolution' reported as a failed login with the reconnect steps."""
    for _ in range(6):
        if e is None:
            return False
        if type(e).__name__ in OFFLINE_NAMES or isinstance(e, (TimeoutError, ConnectionError)) or getattr(e, "retryable", False) is True:
            return True
        e = e.__cause__ or e.__context__
    return False


def check(now: dt.datetime, refresh=None) -> dict:
    """Ask Google for a fresh access token. A login that no longer works is reported at once (once a day), not when an upload fails. When Google
    cannot be reached the login was not tested: that is recorded as offline, the owner is asked for nothing, and the day's alert is not used up."""
    try:
        (refresh or _real_refresh)()
        result = {"ok": True, "error": ""}
    except FileNotFoundError:
        result = {"ok": False, "error": "not connected"}
    except Exception as e:
        if "invalid_grant" in str(e):
            result = {"ok": False, "error": "expired"}
        elif offline(e):
            result = {"ok": False, "offline": True, "error": f"offline: {type(e).__name__}: {e}"[:200]}
        else:
            result = {"ok": False, "error": "expired" if type(e).__name__ == "RefreshError" else f"{type(e).__name__}: {e}"[:200]}
    d = _load()
    d["last_check"] = {"at": now.strftime(TS), **result}
    if result["ok"]:
        d["last_ok"] = now.strftime(TS)
    if not result["ok"] and not result.get("offline") and d.get("last_alert") != now.strftime("%Y-%m-%d"):
        d["last_alert"] = now.strftime("%Y-%m-%d")
        title, why = (("The YouTube login expired", "Google ended the login. ") if result["error"] == "expired"
                      else ("YouTube is not connected", "") if result["error"] == "not connected" else ("The YouTube login check failed", result["error"] + ". "))
        agentlog.event("error", title, why + STEPS, notify=True, now=now)
    _save(d)
    return result
