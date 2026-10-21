"""Dashboard login: one owner, email and password, a signed cookie. Stdlib only.

Nothing here needs a password at build time: run `python set_password.py` once on the machine that serves the dashboard.
While data/auth.json does not exist the dashboard stays open, and it then listens on loopback only.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

import config

DATA = config.ROOT / "data"
AUTH_FILE = DATA / "auth.json"
SECRET_FILE = DATA / "auth_secret"
COOKIE = os.getenv("STUDIO_COOKIE", "studio_session")  # a user studio sets its own, so signing in to one studio never replaces the session of another on the same address
SESSION_DAYS = 14
SESSIONS_FILE = DATA / "sessions.json"
INVITES_FILE = DATA / "invites.json"
_SLOCK = threading.Lock()
MAX_FAILS, WINDOW = 5, 600  # five wrong attempts per ten minutes from one address


def enabled() -> bool:
    return AUTH_FILE.exists()


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def set_password(email: str, password: str) -> None:
    email = email.strip().lower()
    if "@" not in email or len(password) < 10:
        raise ValueError("use a real email and a password of at least 10 characters")
    DATA.mkdir(exist_ok=True)
    salt = secrets.token_bytes(16)
    AUTH_FILE.write_text(json.dumps({"email": email, "salt": salt.hex(), "hash": _hash(password, salt)}))
    os.chmod(AUTH_FILE, 0o600)
    SECRET_FILE.write_bytes(secrets.token_bytes(32))  # a new password signs everybody out
    SESSIONS_FILE.unlink(missing_ok=True)
    os.chmod(SECRET_FILE, 0o600)


def _invites() -> dict:
    try:
        return json.loads(INVITES_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_invite(hours: float = 24, now: float | None = None) -> str:
    """A link token for a user's first sign-in: valid for `hours`, once. Only its hash is kept, so the file cannot be used to claim the studio."""
    now = now or time.time()
    token = secrets.token_urlsafe(24)
    live = {k: v for k, v in _invites().items() if v > now}
    live[_digest(token)] = now + hours * 3600
    DATA.mkdir(exist_ok=True)
    INVITES_FILE.write_text(json.dumps(live))
    os.chmod(INVITES_FILE, 0o600)
    return token


def invite_valid(token: str, now: float | None = None) -> bool:
    return bool(token) and _invites().get(_digest(token), 0) > (now or time.time())


def claim(token: str, email: str, password: str, now: float | None = None) -> None:
    """First sign-in: the invite lets the user choose their own email and password, once, and only while the studio has no login yet."""
    if enabled():
        raise ValueError("this studio already has a login")
    if not invite_valid(token, now):
        raise ValueError("this invite link is not valid any more")
    set_password(email, password)  # raises ValueError for a weak password and then the invite stays usable
    INVITES_FILE.unlink(missing_ok=True)


def owner_email() -> str:
    return json.loads(AUTH_FILE.read_text())["email"] if enabled() else ""


def verify(email: str, password: str) -> bool:
    if not enabled():
        return False
    a = json.loads(AUTH_FILE.read_text())
    ok_hash = hmac.compare_digest(_hash(password, bytes.fromhex(a["salt"])), a["hash"])  # always hash: same time for a wrong email
    return hmac.compare_digest(email.strip().lower().encode(), a["email"].encode()) and ok_hash


def _key() -> bytes:
    return SECRET_FILE.read_bytes()


def _sessions() -> dict:
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save_sessions(d: dict) -> None:
    tmp = SESSIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    os.chmod(tmp, 0o600)
    tmp.replace(SESSIONS_FILE)


def _sign(sid: str) -> str:
    return hmac.new(_key(), sid.encode(), "sha256").hexdigest()


def make_token(email: str, now: float | None = None) -> str:
    """A new server-side session; the cookie holds only its random id and a signature."""
    now = now or time.time()
    sid = secrets.token_urlsafe(24)
    with _SLOCK:
        live = {k: v for k, v in _sessions().items() if v["exp"] > now}
        live[sid] = {"email": email, "exp": now + SESSION_DAYS * 86400}
        _save_sessions(live)
    return f"{sid}.{_sign(sid)}"


def check_token(token: str, now: float | None = None) -> str | None:
    """The owner's email when the cookie is genuine, still on the server's list and not expired, else None."""
    try:
        sid, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(sid), sig):
            return None
        sess = _sessions().get(sid)
        if not sess or sess["exp"] < (now or time.time()) or sess["email"] != owner_email():
            return None
        return sess["email"]
    except (ValueError, OSError, KeyError, TypeError):
        return None


def revoke(token: str) -> None:
    """Sign out: the session is deleted on the server, so a copied cookie stops working too."""
    sid = token.rsplit(".", 1)[0]
    with _SLOCK:
        d = _sessions()
        if d.pop(sid, None) is not None:
            _save_sessions(d)


def cookie_from(header: str) -> str:
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return ""


class Limiter:
    def __init__(self, global_max: int = 0):
        self.fails: dict[str, list[float]] = {}
        self.lock = threading.Lock()
        self.global_max = global_max  # 0 = no limit across all visitors; a user studio on the open internet sets one
        self.all: list[float] = []

    def blocked(self, ip: str, now: float | None = None) -> bool:
        now = now or time.time()
        with self.lock:
            recent = [t for t in self.fails.get(ip, []) if now - t < WINDOW]
            self.fails[ip] = recent
            return len(recent) >= MAX_FAILS

    def reserve(self, ip: str, now: float | None = None) -> bool:
        """Take an attempt slot before the password is checked, atomically, so parallel guesses cannot all slip past the limit."""
        now = now or time.time()
        with self.lock:
            recent = [t for t in self.fails.get(ip, []) if now - t < WINDOW]
            self.all = [t for t in self.all if now - t < WINDOW]
            if len(recent) >= MAX_FAILS or (self.global_max and len(self.all) >= self.global_max):
                self.fails[ip] = recent
                return False
            recent.append(now)
            self.all.append(now)
            self.fails[ip] = recent
            return True

    def fail(self, ip: str, now: float | None = None) -> None:
        with self.lock:
            self.fails.setdefault(ip, []).append(now or time.time())

    def clear(self, ip: str) -> None:
        """A right password: this visitor's attempts are forgotten, and so are their slots in the shared count (only wrong guesses use it up)."""
        with self.lock:
            for t in self.fails.pop(ip, []):
                if t in self.all:
                    self.all.remove(t)


LIMITER = Limiter()
CLAIM_LIMITER = Limiter()  # the first-password page is counted apart, so guessing at it cannot lock the login page


def login_page(error: str = "") -> bytes:
    msg = f'<p class="err" role="alert">{error}</p>' if error else ""
    return (config.ROOT / "login.html").read_text().replace("<!--ERROR-->", msg).encode()


def claim_page(token: str, error: str = "") -> bytes:
    """The first-sign-in page of a user studio: the login page's look, with the invite token and a form for the user's own email and password."""
    import html
    import re

    page = login_page(error).decode()
    form = ('<form method="post" action="/claim"><input type="hidden" name="token" value="' + html.escape(token) + '">'
            '<div><label for="e">Your email</label><input id="e" name="email" type="email" autocomplete="username" inputmode="email" required autofocus></div>'
            '<div><label for="p">Choose a password (10 or more characters)</label><input id="p" name="password" type="password" autocomplete="new-password" minlength="10" required></div>'
            '<div><label for="p2">Repeat it</label><input id="p2" name="password2" type="password" autocomplete="new-password" minlength="10" required></div>'
            '<button type="submit">Create my studio login</button></form>')
    page = re.sub(r"<form.*?</form>", lambda m: form, page, count=1, flags=re.S)
    return re.sub(r"<p>Sign in to .*?</p>", "<p>Welcome. Choose the email and password you will use to open your own studio.</p>", page, count=1, flags=re.S).encode()
