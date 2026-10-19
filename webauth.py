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
COOKIE = "studio_session"
SESSION_DAYS = 14
SESSIONS_FILE = DATA / "sessions.json"
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
    def __init__(self):
        self.fails: dict[str, list[float]] = {}
        self.lock = threading.Lock()

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
            if len(recent) >= MAX_FAILS:
                self.fails[ip] = recent
                return False
            recent.append(now)
            self.fails[ip] = recent
            return True

    def fail(self, ip: str, now: float | None = None) -> None:
        with self.lock:
            self.fails.setdefault(ip, []).append(now or time.time())

    def clear(self, ip: str) -> None:
        with self.lock:
            self.fails.pop(ip, None)


LIMITER = Limiter()


def login_page(error: str = "") -> bytes:
    msg = f'<p class="err" role="alert">{error}</p>' if error else ""
    return (config.ROOT / "login.html").read_text().replace("<!--ERROR-->", msg).encode()
