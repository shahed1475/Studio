"""Sign-in for the hub: an emailed one-time code, or Google. Sessions are server-side rows; the cookie holds a random token, the table holds only its hash.

Limits are our own choices, not a standard (OWASP gives none): code 8 digits, 10 minutes, 5 tries, 3 sends an hour per address, 10 per address of origin; a session
idles out after 7 days and ends after 30. Decisions are written to the audit table without the code, the token or the address (a short hash of the address instead).
Google: the ID token's signature, audience and expiry are checked by Google's library, the issuer and the double-submit CSRF value here; the account key is Google's `sub`;
an address is trusted only when Google is authoritative for it (@gmail.com, or a verified Workspace domain), so an unknown address from another provider never links to,
or takes over, an existing account."""
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid

import config

from . import db, mailer as mailers

SECRET_FILE = config.ROOT / "data" / "hub" / "secret"
CODE_TTL, MAX_TRIES = 600, 5
SEND_PER_EMAIL, SEND_PER_IP, VERIFY_PER_IP, WINDOW = 3, 10, 30, 3600
SEND_PER_IP_DAY = 20  # one source may start at most 20 sign-in emails a day, whatever the hourly window allows
PURGE_AFTER = 86400  # rate_hits rows live this long: the longest window any limiter uses (the model caller counts a day). A purge by a shorter window erased other limiters' counts.
SESSION_IDLE, SESSION_ABSOLUTE = 7 * 86400, 30 * 86400
SENT = {"ok": True, "message": "Check your email for an 8-digit code. It works for 10 minutes."}
INVALID = {"ok": False, "error": "invalid_or_expired"}
GOOGLE_REFUSED = {"ok": False, "error": "google_refused"}
EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


def _secret() -> bytes:
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_bytes(secrets.token_bytes(32))
        os.chmod(SECRET_FILE, 0o600)
    return SECRET_FILE.read_bytes()


def _code_hash(email: str, code: str) -> str:
    return hmac.new(_secret(), f"{email}|{code}".encode(), hashlib.sha256).hexdigest()


def _tag(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def norm_email(email) -> str | None:
    e = str(email or "").strip().lower()
    return e if len(e) <= 254 and EMAIL.match(e) else None


def _audit(con, event: str, outcome: str, now: float, account_id=None, detail: str = "", ip: str = "") -> None:
    con.execute("insert into audit(at,account_id,event,outcome,detail,ip) values(?,?,?,?,?,?)", (now, account_id, event, outcome, detail[:200], ip[:64]))


def _count(con, key: str, now: float) -> int:
    return con.execute("select count(*) from rate_hits where key=? and at>?", (key, now - WINDOW)).fetchone()[0]


def _record(con, key: str, now: float) -> None:
    con.execute("delete from rate_hits where at<?", (now - PURGE_AFTER,))
    con.execute("insert into rate_hits(key,at) values(?,?)", (key, now))


DEFAULT_MAIL_CAP = 100


def mail_daily_cap(environ=None) -> int:
    """Sign-in emails the whole hub may send in 24 hours (HUB_MAIL_DAILY_CAP, default 100): a mail account has a daily sending limit and a flood must not use it up."""
    raw = str((os.environ if environ is None else environ).get("HUB_MAIL_DAILY_CAP", "")).strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_MAIL_CAP


def allow_entries(environ=None) -> list[str]:
    """HUB_ALLOWED_EMAILS: comma-separated addresses, or @domain for a whole domain. Empty means sign-up is open."""
    raw = str((os.environ if environ is None else environ).get("HUB_ALLOWED_EMAILS", ""))
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def allowed(email: str, environ=None) -> bool:
    entries = allow_entries(environ)
    e = str(email or "").strip().lower()
    return not entries or any(e == x or (x.startswith("@") and e.endswith(x)) for x in entries)  # "@team.example" needs the @ right before the domain: evilteam.example does not match


def request_code(email, ip: str, mailer=None, now: float | None = None) -> dict:
    """Mail a sign-in code. The answer is the same for an address that has an account and one that has not."""
    now = time.time() if now is None else now
    e = norm_email(email)
    if not e:
        return {"ok": False, "error": "bad_email"}
    if not allowed(e):
        return {"ok": False, "error": "not_invited"}  # nothing is stored or counted for an address that is not on the list
    ek, ik = f"send:e:{_tag(e)}", f"send:ip:{ip}"
    code = f"{secrets.randbelow(10 ** 8):08d}"
    with db.tx() as con:
        ipd = f"sendday:ip:{ip}"
        if (_count(con, ek, now) >= SEND_PER_EMAIL or _count(con, ik, now) >= SEND_PER_IP
                or con.execute("select count(*) from rate_hits where key=? and at>?", (ipd, now - 86400)).fetchone()[0] >= SEND_PER_IP_DAY):
            _audit(con, "code_sent", "rate_limited", now, detail=_tag(e), ip=ip)
            return {"ok": False, "error": "too_many"}
        if con.execute("select count(*) from rate_hits where key='send:all' and at>?", (now - 86400,)).fetchone()[0] >= mail_daily_cap():
            _audit(con, "code_sent", "mail_capped", now, detail=_tag(e), ip=ip)
            return {"ok": False, "error": "mail_busy"}  # checked before the older code is retired, so a person already signing in keeps the code they have
        _record(con, ek, now)
        _record(con, ik, now)
        _record(con, "send:all", now)
        _record(con, ipd, now)
        con.execute("update login_codes set used=1 where email=? and used=0", (e,))
        con.execute("insert into login_codes(email,code_hash,expires_at,created_at) values(?,?,?,?)", (e, _code_hash(e, code), now + CODE_TTL, now))
        _audit(con, "code_sent", "ok", now, detail=_tag(e), ip=ip)
    try:
        (mailer or mailers.from_env()).send(e, "Your sign-in code", f"Your sign-in code is {code}\n\nIt works once, for 10 minutes. If you did not ask for it, ignore this message.")
    except Exception as ex:  # the reason goes to the audit table, the person sees only that mail did not go
        with db.tx() as con:
            _audit(con, "code_sent", "mail_failed", now, detail=type(ex).__name__, ip=ip)
        return {"ok": False, "error": "mail_unavailable"}
    return SENT


def _account_for_email(con, e: str, now: float) -> str:
    row = con.execute("select id from accounts where email=?", (e,)).fetchone()
    if row:
        return row["id"]
    aid = uuid.uuid4().hex
    con.execute("insert into accounts(id,email,created_at) values(?,?,?)", (aid, e, now))
    return aid


def _new_session(con, account_id: str, ip: str, now: float) -> str:
    token = secrets.token_urlsafe(32)
    con.execute("insert into sessions(token_hash,account_id,created_at,last_seen,expires_at,ip) values(?,?,?,?,?,?)",
                (_tag_full(token), account_id, now, now, now + SESSION_ABSOLUTE, ip[:64]))
    return token


def _tag_full(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _public(row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def verify_code(email, code, ip: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    e = norm_email(email)
    code = str(code or "").strip()
    with db.tx() as con:
        ik = f"verify:ip:{ip}"
        if _count(con, ik, now) >= VERIFY_PER_IP:
            _audit(con, "login", "rate_limited", now, ip=ip)
            return {"ok": False, "error": "too_many"}
        _record(con, ik, now)
        row = con.execute("select * from login_codes where email=? and used=0 order by id desc limit 1", (e or "",)).fetchone() if e else None
        usable = bool(row) and row["expires_at"] > now and row["attempts"] < MAX_TRIES and re.fullmatch(r"\d{8}", code) is not None
        expected = row["code_hash"] if row else _code_hash("nobody@invalid.example", "00000000")  # the same work whether or not a code exists
        match = hmac.compare_digest(_code_hash(e or "", code), expected)
        if row and usable:
            con.execute("update login_codes set attempts=attempts+1 where id=?", (row["id"],))
        if not (usable and match):
            _audit(con, "login", "login_failed", now, detail=_tag(e or ""), ip=ip)
            return INVALID
        con.execute("update login_codes set used=1 where id=?", (row["id"],))
        aid = _account_for_email(con, e, now)
        token = _new_session(con, aid, ip, now)
        _audit(con, "login", "login_ok", now, account_id=aid, detail="email", ip=ip)
        acc = con.execute("select * from accounts where id=?", (aid,)).fetchone()
        return {"ok": True, "token": token, "account": _public(acc)}


def session_account(token, now: float | None = None) -> dict | None:
    """The account a session token belongs to, or None. Using a session slides its idle limit, never its absolute end."""
    now = time.time() if now is None else now
    if not token or not isinstance(token, str):
        return None
    h = _tag_full(token)
    with db.tx() as con:
        row = con.execute("select s.*, a.email, a.name from sessions s join accounts a on a.id=s.account_id where s.token_hash=?", (h,)).fetchone()
        if not row:
            return None
        if now >= row["expires_at"] or now - row["last_seen"] >= SESSION_IDLE:
            con.execute("delete from sessions where token_hash=?", (h,))
            return None
        con.execute("update sessions set last_seen=? where token_hash=?", (now, h))
        return {"id": row["account_id"], "email": row["email"], "name": row["name"]}


def hit(key: str, limit: int, window: float, now: float | None = None) -> bool:
    """Count one use of `key` in the last `window` seconds; False (and not counted) when `limit` uses are already in it."""
    now = time.time() if now is None else now
    with db.tx() as con:
        if con.execute("select count(*) from rate_hits where key=? and at>?", (key, now - window)).fetchone()[0] >= limit:
            return False
        con.execute("insert into rate_hits(key,at) values(?,?)", (key, now))
        con.execute("delete from rate_hits where at<?", (now - max(window, PURGE_AFTER),))
        return True


def delete_account(account_id: str, now: float | None = None) -> bool:
    """Remove a person: the account and everything that hangs on it (sessions, profile, research, stored key, tasks), their waiting sign-in codes, and the link between them and the
    security log (those rows stay, with no account and no address). The database file is checkpointed so the deleted text is not left in its write-ahead log."""
    now = time.time() if now is None else now
    with db.tx() as con:
        row = con.execute("select email from accounts where id=?", (account_id,)).fetchone()
        if not row:
            return False
        if row["email"]:
            con.execute("delete from login_codes where email=?", (row["email"],))
        con.execute("update audit set account_id=NULL, ip='' where account_id=?", (account_id,))
        con.execute("delete from accounts where id=?", (account_id,))
        _audit(con, "account_deleted", "ok", now)
    con = db.connect()
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()
    return True


def logout(token) -> None:
    if token and isinstance(token, str):
        with db.tx() as con:
            con.execute("delete from sessions where token_hash=?", (_tag_full(token),))


def logout_everywhere(account_id: str) -> int:
    with db.tx() as con:
        return con.execute("delete from sessions where account_id=?", (account_id,)).rowcount


def _google_verify(token: str) -> dict:
    from google.auth.transport import requests as greq
    from google.oauth2 import id_token

    cid = os.getenv("HUB_GOOGLE_CLIENT_ID", "").strip()
    if not cid:
        raise RuntimeError("HUB_GOOGLE_CLIENT_ID is not set")
    return id_token.verify_oauth2_token(token, greq.Request(), cid)


def google_configured() -> bool:
    return bool(os.getenv("HUB_GOOGLE_CLIENT_ID", "").strip())


def google_login(id_token_str, csrf_cookie, csrf_body, ip: str = "", verify=None, now: float | None = None) -> dict:
    now = time.time() if now is None else now

    def refuse(why: str):
        with db.tx() as con:
            _audit(con, "login", "google_refused", now, detail=why, ip=ip)
        return GOOGLE_REFUSED

    if not csrf_cookie or not csrf_body or not hmac.compare_digest(str(csrf_cookie), str(csrf_body)):
        return refuse("csrf")
    try:
        c = (verify or _google_verify)(id_token_str)
    except Exception as ex:
        return refuse(type(ex).__name__)
    sub, email = str(c.get("sub") or ""), norm_email(c.get("email"))
    cid = os.getenv("HUB_GOOGLE_CLIENT_ID", "").strip()
    if (c.get("iss") not in GOOGLE_ISSUERS or not sub or c.get("email_verified") is not True or not email
            or float(c.get("exp") or 0) <= now or (cid and c.get("aud") != cid)):
        return refuse("claims")
    if not allowed(email):
        with db.tx() as con:
            _audit(con, "login", "not_invited", now, detail=_tag(email), ip=ip)
        return {"ok": False, "error": "not_invited"}
    hd = str(c.get("hd") or "").lower()
    authoritative = email.endswith("@gmail.com") or (bool(hd) and email.endswith("@" + hd))
    with db.tx() as con:
        row = con.execute("select * from accounts where google_sub=?", (sub,)).fetchone()
        if not row:
            by_mail = con.execute("select * from accounts where email=?", (email,)).fetchone()
            if by_mail and not authoritative:
                _audit(con, "login", "google_refused", now, detail="no_link", ip=ip)
                return GOOGLE_REFUSED  # an address Google does not vouch for never joins an account that already uses it
            if by_mail:
                con.execute("update accounts set google_sub=? where id=?", (sub, by_mail["id"]))
                row = by_mail
            else:
                aid = uuid.uuid4().hex
                con.execute("insert into accounts(id,email,google_sub,name,created_at) values(?,?,?,?,?)",
                            (aid, email if authoritative else None, sub, str(c.get("name") or "")[:80], now))
                row = con.execute("select * from accounts where id=?", (aid,)).fetchone()
        token = _new_session(con, row["id"], ip, now)
        _audit(con, "login", "login_ok", now, account_id=row["id"], detail="google", ip=ip)
        return {"ok": True, "token": token, "account": _public(row)}
