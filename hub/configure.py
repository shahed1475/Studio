"""`python -m hub.configure`: the terminal prompt where you paste the Gmail app password and the Google client id.

What you type goes straight into the private secrets file (hub/secretstore.py: mode 600, outside the repository, written atomically). The password is read with
hidden input and nothing typed is ever printed back, logged or sent anywhere except to Gmail when you ask for the test email. Nothing is written until every answer is
in; Ctrl-C or a closed terminal leaves the old file as it was. Exit codes: 0 saved (or --status shown), 1 nothing saved, 2 an answer was refused, 3 saved but the test email failed."""
import argparse
import getpass
import importlib.util
import re
import smtplib
import ssl
import stat
import sys
from pathlib import Path

from . import mailer as mailers, secretstore

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CLIENT_ID = re.compile(r"^\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$")
APP_PASSWORD = re.compile(r"^[A-Za-z0-9]{16}$")
TRIES = 3
INTRO = """Nightloom hub: private settings
Your Gmail address, a Gmail app password and your Google sign-in client id are stored in
  {path}
readable by you only. The password is typed hidden and is never shown again. Press Enter to skip a question
(or, where it says "already set", to keep what is stored). Nothing is saved until the last question is answered."""
NEXT_STEPS = """Next:
  1. Restart the hub:  python -m hub.server
  2. For Google sign-in open the site at http://localhost:8931 (not 127.0.0.1): Google's page for the client id says to list
     http://localhost and http://localhost:<port> as Authorized JavaScript origins."""


class Refused(Exception):
    """An answer that cannot be used. The text is safe to print."""


def _kept(flag: bool) -> str:
    return " (already set, Enter keeps it)" if flag else " (Enter to skip)"


def _ask_checked(ask, out, prompt, normalise, why) -> str:
    for _ in range(TRIES):
        raw = ask(prompt).strip()
        if not raw:
            return ""
        value = normalise(raw)
        if value is not None:
            return value
        out(why)
    raise Refused(f"No usable answer after {TRIES} tries. Nothing was saved.")


def _ask_password(ask, ask_secret, out, have: bool) -> str:
    raw = ask_secret("Gmail app password (16 characters, typing is hidden)" + _kept(have) + ": ")
    value = re.sub(r"\s+", "", raw)  # Google shows it in four groups with spaces
    if not value:
        return ""
    if not APP_PASSWORD.match(value):
        out("That does not look like a Google app password (16 letters or digits, shown by Google in four groups).")
        out("Your normal Gmail password will not work here and should not be stored in a file.")
        if ask("Type yes to store it anyway: ").strip().lower() != "yes":
            raise Refused("Not stored. Nothing was saved.")
    return value


def _edge(path: Path, ask, ask_secret, out) -> int:
    """The Cloudflare settings. The edge secret must be the same text as the Worker's EDGE_SECRET (set there with `secret put`); the Turnstile site key is public, its secret is not."""
    changes = {}
    edge = re.sub(r"\s+", "", ask_secret("Edge secret (the same text you gave the Worker, 32 or more characters, hidden); empty to keep: "))
    if edge:
        if len(edge) < 32:
            raise Refused("The edge secret must be at least 32 characters (make one with: openssl rand -hex 32). Nothing was saved.")
        changes["HUB_EDGE_SECRET"] = edge
    key = re.sub(r"\s+", "", ask("Turnstile site key (public, starts with 0x); empty to keep: "))
    if key:
        if not re.match(r"^[0-9A-Za-z_-]{6,80}$", key):
            raise Refused("That does not look like a Turnstile site key. Nothing was saved.")
        changes["HUB_TURNSTILE_SITEKEY"] = key
    tsecret = re.sub(r"\s+", "", ask_secret("Turnstile secret key (hidden); empty to keep: "))
    if tsecret:
        if not re.match(r"^[0-9A-Za-z_-]{16,120}$", tsecret):
            raise Refused("That does not look like a Turnstile secret. Nothing was saved.")
        changes["HUB_TURNSTILE_SECRET"] = tsecret
    if not changes:
        out("Nothing to change. Nothing was saved.")
        return 1
    out(f"Saved to {secretstore.save(changes, path)} (readable only by you). Restart the hub to use it: ~/hub/deploy/hub.sh restart")
    return 0


def _hint(ex: Exception) -> str:
    if isinstance(ex, smtplib.SMTPAuthenticationError):
        return "Gmail refused the login. Check the address and the app password (the account needs 2-Step Verification to have one)."
    if isinstance(ex, ssl.SSLError):
        return "The secure connection to the mail server could not be verified."
    if isinstance(ex, OSError):
        return "Could not reach smtp.gmail.com. Check the internet connection and that port 587 is not blocked."
    return "The error class above is all that is shown, so no secret can reach the screen."


def _send_test_mail(to: str, env: dict) -> None:
    mailers.SMTPMailer(env.get("HUB_SMTP_HOST", ""), mailers._port(env.get("HUB_SMTP_PORT", "")), env.get("HUB_SMTP_USER", ""),
                       env.get("HUB_SMTP_PASSWORD", ""), env.get("HUB_MAIL_FROM") or env.get("HUB_SMTP_USER", "")).send(
        to, "Nightloom hub: test message", "This is a test from the Nightloom hub setup. Mail works; there is nothing else to do with this message.")


def _offer_test(target: Path, ask, out, send_test) -> int:
    env = {}
    secretstore.load(target, env)
    if not all(env.get(n) for n in ("HUB_SMTP_HOST", "HUB_SMTP_USER", "HUB_SMTP_PASSWORD")):
        return 0
    if ask("Send one test email to your own Gmail address now? [y/N]: ").strip().lower() not in ("y", "yes"):
        return 0
    try:
        send_test(env["HUB_SMTP_USER"], env)
    except Exception as ex:  # the class name and a hint only: smtplib's own text can echo server replies
        out(f"The test email did not go ({type(ex).__name__}). {_hint(ex)}")
        return 3
    out("Test email sent. Look in the inbox (and the spam folder) of your Gmail address.")
    return 0


def _run(args, path: Path, ask, ask_secret, out, send_test) -> int:
    have = secretstore.status(path, {})  # the file only, not the environment
    out(INTRO.format(path=path))
    changes = {}
    address = _ask_checked(ask, out, "Gmail address that will send the sign-in codes" + _kept(have["HUB_SMTP_USER"]) + ": ",
                           lambda s: s.lower() if EMAIL.match(s) else None, "That is not an email address. Try again.")
    if address:
        changes.update(HUB_SMTP_HOST="smtp.gmail.com", HUB_SMTP_PORT="587", HUB_SMTP_USER=address, HUB_MAIL_FROM=address)
    if address or have["HUB_SMTP_USER"]:
        password = _ask_password(ask, ask_secret, out, have["HUB_SMTP_PASSWORD"])
        if password:
            changes["HUB_SMTP_PASSWORD"] = password
    client = _ask_checked(ask, out, "Google Web client id (ends in .apps.googleusercontent.com)" + _kept(have["HUB_GOOGLE_CLIENT_ID"]) + ": ",
                          lambda s: s if CLIENT_ID.match(s) else None, "That is not the shape of a Google client id. Try again.")
    if client:
        changes["HUB_GOOGLE_CLIENT_ID"] = client
    if not changes:
        out("Nothing to change. Nothing was saved.")
        return 1
    target = secretstore.save(changes, path)
    out(f"Saved to {target} (readable only by you).")
    code = 0 if args.no_test else _offer_test(target, ask, out, send_test)
    from . import server  # imported here so --status stays light

    for line in server.startup_report({}, target):
        out(line)
    out(NEXT_STEPS)
    return code


def _contact(path: Path, ask, out) -> int:
    """Only the contact line for the public privacy page (your name and an email or web address). Everything else in the file is kept."""
    have = secretstore.status(path, {})["HUB_CONTACT"]
    raw = " ".join(ask("Contact line for the privacy page, shown to the public (your name and an email or web address)" + _kept(have) + ": ").split())
    if not raw:
        out("Nothing to change. Nothing was saved.")
        return 1
    if len(raw) > 200:
        raise Refused("That is longer than 200 characters. Nothing was saved.")
    out(f"Saved to {secretstore.save({'HUB_CONTACT': raw}, path)} (readable only by you). Restart the hub to show it: hub.sh restart")
    return 0


def _status(path: Path, out) -> int:
    ignored = secretstore.load(path, {})["ignored"]
    if ignored:
        out(f"Secrets file {path}: IGNORED, {ignored}")
    elif path.exists():
        out(f"Secrets file {path}: private (mode {stat.S_IMODE(path.stat().st_mode):o})")
    else:
        out(f"Secrets file {path}: not created yet")
    st = secretstore.status(path, {})
    for name in secretstore.ALLOWED:
        out(f"  {name}: {'set' if st[name] else 'not set'}")
    try:
        lib = importlib.util.find_spec("google.oauth2") is not None and importlib.util.find_spec("requests") is not None
    except (ImportError, ValueError):
        lib = False
    out("Google sign-in library (google-auth, requests): " + ("installed" if lib else "MISSING (pip install google-auth requests)"))
    return 0


def main(argv=None, ask=input, ask_secret=getpass.getpass, out=print, send_test=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m hub.configure", description="Store the hub's Gmail app password and Google client id privately.")
    ap.add_argument("--status", action="store_true", help="show which settings are set (never their values) and exit")
    ap.add_argument("--no-test", action="store_true", help="do not offer to send a test email")
    ap.add_argument("--edge", action="store_true", help="only set the Cloudflare settings: the edge secret and the Turnstile keys (typing of the secrets is hidden)")
    ap.add_argument("--contact", action="store_true", help="only set the contact line shown on the public privacy page")
    ap.add_argument("--file", help="use another secrets file (default: ~/.config/nightloom/hub.env or $HUB_SECRETS_FILE)")
    args = ap.parse_args(argv)
    path = Path(args.file).expanduser() if args.file else secretstore.default_path()
    if args.status:
        return _status(path, out)
    try:
        if args.contact:
            return _contact(path, ask, out)
        if args.edge:
            return _edge(path, ask, ask_secret, out)
        return _run(args, path, ask, ask_secret, out, send_test or _send_test_mail)
    except (EOFError, KeyboardInterrupt):
        out("\nStopped. Nothing was saved.")
        return 1
    except Refused as r:
        out(str(r))
        return 2
    except secretstore.SecretError as ex:
        out(f"Not saved: {ex}")
        return 2
    except OSError as ex:  # a folder that cannot be written, a full disk: say so plainly instead of a traceback
        out(f"Not saved: the file could not be written ({type(ex).__name__}: {ex.strerror or 'see the error class'}).")
        return 2


if __name__ == "__main__":
    sys.exit(main())
