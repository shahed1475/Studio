"""Mail and alerts saved from the main dashboard (13 Nov 2026).
Gmail (app password) is for the Creator Hub's sign-in codes: it is kept in settings.json and mirrored to data/hubmail/mail.json, which the hub container reads read-only at every send.
Telegram (bot token + chat id) carries the studio's important events to the owner. Secrets are write-only: no function here returns one and no error text contains one.
The Gmail host is fixed (smtp.gmail.com:587, certificate checked) so the password can only ever be sent to Gmail."""
import datetime as dt
import json
import os
import re
import smtplib
import ssl
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

import config

SETTINGS = config.ROOT / "settings.json"
BRIDGE = config.ROOT / "data" / "hubmail" / "mail.json"
STATE = config.ROOT / "data" / "alerts_state.json"
EMAIL = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@gmail\.com$", re.I)
APP_PASSWORD = re.compile(r"^[a-z]{16}$")
BOT_TOKEN = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,50}$")
DEDUPE_HOURS, DAILY_CAP = 6, 20
API = "https://api.telegram.org"


def _settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {}


def _save(update: dict, remove: tuple = ()) -> None:
    s = _settings()
    s.update(update)
    for k in remove:
        s.pop(k, None)
    SETTINGS.write_text(json.dumps(s, indent=2))
    SETTINGS.chmod(0o600)


def _private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.chmod(0o600)
    tmp.replace(path)


def status() -> dict:
    """What is saved, never the secrets themselves."""
    s = _settings()
    return {"gmail": {"saved": bool(s.get("gmail_app_password")), "address": s.get("gmail_address", "")},
            "telegram": {"saved": bool(s.get("telegram_bot_token")), "chat": bool(s.get("telegram_chat_id")), "bot": s.get("telegram_bot_name", "")}}


def clean(text: str, *secrets: str) -> str:
    out = str(text)
    for sec in secrets + tuple(v for k, v in _settings().items() if k in ("gmail_app_password", "telegram_bot_token") and v):
        if sec:
            out = out.replace(sec, "***")
    return re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***", out)[:200]


# ---- Gmail ----
def save_gmail(address: str, app_password: str) -> None:
    address, pw = str(address).strip().lower(), re.sub(r"[\s\u00a0\u200b-]+", "", str(app_password)).lower()  # Google shows it in four groups; a copy can add spaces, dashes, a non-breaking space or capitals  # Google shows the password in four groups with spaces
    if not EMAIL.match(address):
        raise ValueError("use your full Gmail address (name@gmail.com)")
    if not APP_PASSWORD.match(pw):
        raise ValueError("that is not a Google app password: it is 16 letters (shown in four groups). Your normal Gmail password will not work.")
    _save({"gmail_address": address, "gmail_app_password": pw})
    _private_write(BRIDGE, json.dumps({"address": address, "app_password": pw}))


def remove_gmail() -> None:
    _save({}, ("gmail_address", "gmail_app_password"))
    BRIDGE.unlink(missing_ok=True)


def test_gmail(smtp=None) -> str:
    """Send one test message from the saved address to itself. Returns a short plain result; never the password."""
    s = _settings()
    addr, pw = s.get("gmail_address"), s.get("gmail_app_password")
    if not (addr and pw):
        raise ValueError("save the Gmail address and app password first")
    msg = EmailMessage()
    msg["From"] = msg["To"] = addr
    msg["Subject"] = "Story Studio: test message"
    msg.set_content("This is the test message from your Story Studio dashboard. If you can read it, the Creator Hub can send sign-in codes through this Gmail.")
    try:
        if smtp:
            smtp(addr, pw, msg)
        else:
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as c:
                c.starttls(context=ctx)
                c.login(addr, pw)
                c.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ValueError("Gmail refused the login. Check the address and the app password (the account needs 2-Step Verification to have one).") from None
    except (OSError, smtplib.SMTPException) as e:
        raise ValueError("Could not send through Gmail (" + type(e).__name__ + "). Check the internet connection and try again.") from None
    return f"Sent a test message to {addr}. Check that inbox."


# ---- Telegram ----
def _call(method: str, token: str, payload: dict | None = None, fetch=None) -> dict:
    url = f"{API}/bot{token}/{method}"
    if fetch:
        return fetch(url, payload)
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None, headers={"Content-Type": "application/json"}, method="POST" if payload else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"ok": False}


def save_telegram(token: str, fetch=None) -> str:
    token = str(token).strip()
    if not BOT_TOKEN.match(token):
        raise ValueError("that is not a Telegram bot token (it looks like 123456789:AA...; get it from @BotFather)")
    try:
        me = _call("getMe", token, fetch=fetch)
    except Exception:
        raise ValueError("Could not reach Telegram. Try again in a minute.") from None
    if not me.get("ok"):
        raise ValueError("Telegram did not accept that token. Copy it again from @BotFather.")
    name = str((me.get("result") or {}).get("username", ""))[:40]
    _save({"telegram_bot_token": token, "telegram_bot_name": name}, ("telegram_chat_id",))
    return name


def find_chat(fetch=None) -> str:
    """After the owner sends the bot any message, learn that chat's id (private chats only) and keep it."""
    token = _settings().get("telegram_bot_token")
    if not token:
        raise ValueError("save the bot token first")
    try:
        up = _call("getUpdates", token, fetch=fetch)
    except Exception:
        raise ValueError("Could not reach Telegram. Try again in a minute.") from None
    chats = [(m.get("chat") or {}) for u in (up.get("result") or []) for m in [u.get("message") or {}] if (m.get("chat") or {}).get("type") == "private"]
    if not chats:
        raise ValueError("No message found. Open your bot in Telegram, press Start, send it any word, then press this button again.")
    _save({"telegram_chat_id": str(chats[-1]["id"])})
    return "Found your chat. Press Send a test message."


def remove_telegram() -> None:
    _save({}, ("telegram_bot_token", "telegram_chat_id", "telegram_bot_name"))


def send_telegram(text: str, fetch=None) -> bool:
    s = _settings()
    token, chat = s.get("telegram_bot_token"), s.get("telegram_chat_id")
    if not (token and chat):
        return False
    try:
        return bool(_call("sendMessage", token, {"chat_id": chat, "text": text[:3500], "disable_web_page_preview": True}, fetch=fetch).get("ok"))
    except Exception:
        return False


def test_telegram(fetch=None) -> str:
    if not _settings().get("telegram_chat_id"):
        raise ValueError("press Find my chat first")
    if not send_telegram("Story Studio: test message. Alerts will arrive here.", fetch=fetch):
        raise ValueError("Telegram did not deliver the message. Check the token and that you pressed Start in the bot.")
    return "Sent. Check Telegram."


# ---- pushing studio events ----
def push(kind: str, title: str, detail: str = "", notify: bool = False, now: dt.datetime | None = None, fetch=None, background: bool = True) -> bool:
    """Send an event to Telegram when it matters (a notify event or an error), at most once per title in 6 hours and 20 a day. Best effort: it never raises."""
    try:
        if not (notify or kind == "error") or not _settings().get("telegram_chat_id"):
            return False
        now = now or dt.datetime.now(dt.timezone.utc)
        try:
            st = json.loads(STATE.read_text())
        except (OSError, ValueError):
            st = {}
        day = now.strftime("%Y-%m-%d")
        if st.get("day") != day:
            st = {"day": day, "n": 0, "seen": st.get("seen", {})}
        seen = {t: ts for t, ts in st.get("seen", {}).items() if (now - dt.datetime.fromisoformat(ts)).total_seconds() < DEDUPE_HOURS * 3600}
        if title in seen or st["n"] >= DAILY_CAP:
            return False
        seen[title] = now.isoformat()
        st.update(n=st["n"] + 1, seen=seen)
        _private_write(STATE, json.dumps(st))
        text = f"{title}\n{detail}".strip()
        if background and not fetch:
            threading.Thread(target=send_telegram, args=(text,), daemon=True).start()
            return True
        return send_telegram(text, fetch=fetch)
    except Exception:
        return False
