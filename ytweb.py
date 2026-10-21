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
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    pending = {k: v for k, v in _load().items() if v["exp"] > now}
    pending[state] = {"verifier": flow.code_verifier, "exp": now + WAIT}
    PENDING.parent.mkdir(exist_ok=True)
    PENDING.write_text(json.dumps(pending))
    PENDING.chmod(0o600)
    return url


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
    TOKEN.write_text(flow.credentials.to_json())
    TOKEN.chmod(0o600)
    _after_login()
