"""Google sign-in on the web, for user studios.

The owner's studio signs in with a desktop flow that opens a browser on the server itself. A user opens their studio from their own device, so they
need a normal web flow: the studio sends them to Google, Google sends them back to `https://<studio address>/oauth/callback` with a code, and the code
becomes the same token file the rest of the studio already uses. This needs a "Web application" OAuth client (web_client_secret.json) with that callback
address added; the owner makes it once. Plan: docs/superpowers/plans/2026-10-21-user-side-5-tenants.md.
"""
import json
import os
import time
from pathlib import Path

import config

SECRET = config.ROOT / "web_client_secret.json"
TOKEN = config.ROOT / "token.json"
PENDING = config.ROOT / "data" / "oauth_pending.json"
WAIT = 600  # seconds a sign-in may take from the click to Google's answer
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def available() -> bool:
    return SECRET.exists()


def redirect_uri() -> str | None:
    """Where Google sends the user back: this studio's own public name, from STUDIO_HOSTS (the first name without a port)."""
    for h in os.getenv("STUDIO_HOSTS", "").split(","):
        h = h.strip()
        if h and ":" not in h:
            return f"https://{h}/oauth/callback"
    return None


def _flow(redirect: str):
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_secrets_file(str(SECRET), scopes=SCOPES, redirect_uri=redirect)


def _load() -> dict:
    try:
        return json.loads(PENDING.read_text())
    except (OSError, ValueError):
        return {}


def start(redirect: str, now: float | None = None) -> str:
    """The address to send the user to. Asks for a refresh token (offline access with a fresh consent) so the studio stays signed in."""
    if not available():
        raise ValueError("Google sign-in is not set up on this server yet: ask the owner.")
    now = now or time.time()
    flow = _flow(redirect)
    url, state = flow.authorization_url(access_type="offline", prompt="select_account consent")  # always ask which account: a browser signed in as someone else must never connect their channel unseen
    pending = {k: v for k, v in _load().items() if v["exp"] > now}
    pending[state] = {"verifier": flow.code_verifier, "exp": now + WAIT}
    PENDING.parent.mkdir(exist_ok=True)
    PENDING.write_text(json.dumps(pending))
    PENDING.chmod(0o600)
    return url


def _channel_id(creds) -> str:
    from googleapiclient.discovery import build

    items = build("youtube", "v3", credentials=creds, cache_discovery=False).channels().list(part="id", mine=True).execute().get("items", [])
    if not items:
        raise ValueError("That Google account has no YouTube channel. Choose the account that owns your channel.")
    return items[0]["id"]


def _registry():
    import filelock

    gate = os.getenv("STUDIO_RENDER_GATE", "").strip()
    if not gate:
        return None, None
    path = Path(gate) / "channels.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path, filelock


def _claim(channel_id: str) -> None:
    """One channel belongs to one studio, and never to the studio's owner: the owner's own channel ids are listed in STUDIO_OWNER_CHANNELS, and the claims of
    every user studio are kept in one file in the folder they share."""
    owners = {c.strip() for c in os.getenv("STUDIO_OWNER_CHANNELS", "").split(",") if c.strip()}
    if channel_id in owners:
        raise ValueError("That is the studio owner's channel. Sign in with the Google account that owns YOUR channel.")
    path, filelock = _registry()
    me = os.getenv("STUDIO_NAME", "")
    if path is None:
        return
    with filelock.locked(path):
        try:
            claims = json.loads(path.read_text())
        except (OSError, ValueError):
            claims = {}
        if claims.get(channel_id) not in (None, me):
            raise ValueError("That channel is already connected to another studio.")
        claims[channel_id] = me
        filelock.write_atomic(path, json.dumps(claims))


def release() -> None:
    """Disconnecting gives this studio's channel back, so it can be connected to a studio that really owns it."""
    path, filelock = _registry()
    me = os.getenv("STUDIO_NAME", "")
    if path is None or not path.exists():
        return
    with filelock.locked(path):
        try:
            claims = json.loads(path.read_text())
        except (OSError, ValueError):
            return
        filelock.write_atomic(path, json.dumps({k: v for k, v in claims.items() if v != me}))


def _after_login() -> None:
    import datetime as dt

    import ytlogin

    ytlogin.stamp(dt.datetime.now(dt.timezone.utc), mode="production")


def finish(code: str, state: str, redirect: str, now: float | None = None) -> None:
    """Google's answer: the state must be one this studio issued in the last ten minutes, and works once. The token file is written owner-only."""
    now = now or time.time()
    pending = _load()
    entry = pending.pop(state, None)
    if PENDING.exists():
        PENDING.write_text(json.dumps(pending))  # the state is spent whatever happens next
    if not entry or entry["exp"] < now:
        raise ValueError("This sign-in link expired or unknown. Start again from the YouTube page.")
    flow = _flow(redirect)
    flow.code_verifier = entry["verifier"]
    flow.fetch_token(code=code)
    _claim(_channel_id(flow.credentials))  # refused here: nothing is written, the login is thrown away
    TOKEN.write_text(flow.credentials.to_json())
    TOKEN.chmod(0o600)
    _after_login()
