"""The Cloudflare edge in front of the hub (13 Nov 2026): a Worker serves the website and forwards /api to this origin.
Two checks, both off until the owner sets their secret (settings file, never in chat or git):
- HUB_EDGE_SECRET: every request except /healthz must carry it in `X-Edge-Secret` (compared in constant time), so nobody can reach the origin around the Worker and skip its bot check.
  Only then is `X-Client-IP` (the visitor's address the Worker saw) believed, for the per-address limits.
- HUB_TURNSTILE_SECRET (+ HUB_TURNSTILE_SITEKEY for the page): the sign-in email request needs a Turnstile token that Cloudflare confirms (siteverify). A failure of the check itself refuses the request."""
import hmac
import ipaddress
import json
import os
import urllib.parse
import urllib.request

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def edge_secret() -> str:
    return os.getenv("HUB_EDGE_SECRET", "").strip()


def edge_ok(headers, path: str) -> bool:
    s = edge_secret()
    if not s or path == "/healthz":
        return True
    return hmac.compare_digest(str(headers.get("X-Edge-Secret", "")).encode(), s.encode())


def client_ip(headers) -> str | None:
    """The visitor's address as the Worker saw it, only when the request proved it came from the Worker; else None (the socket's address is used)."""
    if not edge_secret() or not edge_ok(headers, "/"):
        return None
    try:
        return str(ipaddress.ip_address(str(headers.get("X-Client-IP", "")).strip()))
    except ValueError:
        return None


def forwarded_host(headers) -> str | None:
    """The address the visitor's browser used (the Worker's), only when the request proved it came from the Worker; the same-site check compares the page's origin with it."""
    if not edge_secret() or not edge_ok(headers, "/"):
        return None
    return str(headers.get("X-Forwarded-Host", "")).strip()[:253] or None


def turnstile_enabled() -> bool:
    return bool(os.getenv("HUB_TURNSTILE_SECRET", "").strip())


def site_key() -> str:
    return os.getenv("HUB_TURNSTILE_SITEKEY", "").strip() if turnstile_enabled() else ""


def _post(url: str, form: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def turnstile_ok(token, ip: str, post=None) -> bool:
    """True when Turnstile is off, or Cloudflare confirms the token. Any error means no."""
    if not turnstile_enabled():
        return True
    if not isinstance(token, str) or not 10 <= len(token) <= 2048:
        return False
    try:
        out = (post or _post)(VERIFY_URL, {"secret": os.environ["HUB_TURNSTILE_SECRET"].strip(), "response": token, "remoteip": ip})
        return out.get("success") is True
    except Exception:
        return False
