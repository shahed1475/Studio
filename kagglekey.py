"""The owner's Kaggle API token (22 Nov 2026, the owner's request): saved from Settings, kept hidden, tested with one read-only call.

Kaggle's Terms of Use (kaggle.com/terms, read 22 Nov 2026) allow only "your own internal, personal, non-commercial use". The channel is monetised, so
nothing in the studio runs video work on Kaggle: this module only stores the token for the owner's personal `kaggle` command line (the wrapper
~/.local/bin/kaggle reads it from settings.json) and checks that Kaggle accepts it. Not in a user studio.
The token goes only in an Authorization header to https://www.kaggle.com (never in a URL, a log, an error text or a page), with a timeout and no redirects.
"""
import re
import time

import requests

FIELD = "kaggle_api_token"
TEST_URL = "https://www.kaggle.com/api/v1/competitions/list"  # read-only; answers 401 without a valid token (checked 22 Nov 2026)
TOKEN = re.compile(r"^KGAT_[A-Za-z0-9_-]{16,200}$")  # Kaggle's API tokens start with KGAT_ (the token page, 22 Nov 2026)


def _tenant() -> bool:
    try:
        import tenantmode

        return tenantmode.is_tenant()
    except Exception:
        return False


def check_format(value: str) -> str:
    """The token, trimmed, or ValueError with a plain reason. The value itself is never put in the message."""
    v = str(value or "").strip()
    if _tenant():
        raise ValueError("not available in a user studio")
    if not TOKEN.match(v):
        raise ValueError("that is not a Kaggle API token: it should start with KGAT_ (kaggle.com > Settings > API Tokens)")
    return v


def saved(settings: dict) -> bool:
    return bool(settings.get(FIELD)) and not _tenant()


def scrub(text, token: str) -> str:
    t = str(text)
    return t.replace(token, "***") if token else t


def test(token: str, get=requests.get) -> dict:
    """{"ok", "detail", "seconds"}: one read-only request with the token in a header. Never returns or logs the token."""
    if not token:
        return {"ok": False, "detail": "No Kaggle token is saved yet."}
    t0 = time.monotonic()
    try:
        r = get(TEST_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15, allow_redirects=False)
    except requests.RequestException as e:
        return {"ok": False, "detail": scrub(f"Kaggle could not be reached ({type(e).__name__}).", token)}
    secs = round(time.monotonic() - t0, 1)
    code = getattr(r, "status_code", 0)
    if code == 200:
        try:
            n = len(r.json())
        except ValueError:
            n = None
        return {"ok": True, "seconds": secs, "detail": f"Kaggle accepted the token ({secs} s)" + (f": it read {n} competitions, nothing was changed." if n is not None else ".")}
    if code in (401, 403):
        return {"ok": False, "seconds": secs, "detail": "Kaggle refused the token (wrong, expired or deleted). Make a new one at kaggle.com > Settings > API Tokens."}
    if code == 429:
        return {"ok": False, "seconds": secs, "detail": "Kaggle is limiting requests right now (HTTP 429). Try again in a few minutes."}
    return {"ok": False, "seconds": secs, "detail": f"Kaggle answered HTTP {code}; the token was not confirmed."}
