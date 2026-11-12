"""The hub's web server (standard library only): the website, sign-in, and the A2A endpoints. `python -m hub.server` listens on 127.0.0.1:8931 (HUB_HOST, HUB_PORT).

Security choices (backend-design auth and security skills): the session cookie is HttpOnly, SameSite=Lax and Secure (HUB_INSECURE_DEV=1 drops Secure for local http only); a request
that rides on the cookie must carry `X-Hub: 1` (a cross-site page cannot add it without a preflight, and this server answers no preflight) and, if it has an Origin, that Origin must
be this host; a Bearer token (the same session token) needs neither because it is never sent by the browser on its own. No CORS headers at all. JSON bodies only, 64 KB at most.
Every A2A call is tied to the signed-in account from the session, never to an id in the request. 60 A2A calls a minute per account. Errors say nothing about internals.
The client's address is the socket's, or the last X-Forwarded-For hop only when HUB_TRUST_PROXY=1 (Caddy in front)."""
import html
import json
import mimetypes
import os
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import a2a, agents as agent_team, auth, edge, keystore, llm, profile, research, secretstore

WEB = Path(__file__).parent / "web"
COOKIE, CSRF_COOKIE = "hub_session", "hub_csrf"
MAX_BODY = 64 * 1024
CALLS_PER_MINUTE = 60
CSP = ("default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client https://challenges.cloudflare.com; frame-src https://accounts.google.com/gsi/ https://challenges.cloudflare.com; "
       "connect-src 'self' https://accounts.google.com/gsi/ https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; img-src 'self' data:; "
       "font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def parse_cookies(header: str) -> dict:
    """The Cookie header as {name: value}, one cookie at a time (RFC 6265 style). Python's SimpleCookie gives up at the first cookie it cannot read, and Google's
    sign-in script sets one (g_state, JSON with quote marks), which hid our session cookie behind it. A bad cookie is skipped; the first value of a name wins."""
    out = {}
    for part in (header or "").split(";"):
        name, sep, value = part.partition("=")
        name = name.strip()
        if sep and name and name not in out:
            out[name] = value.strip()
    return out


class Hub(BaseHTTPRequestHandler):
    server_version = "CreatorHub"
    sys_version = ""
    agents = agent_team.AGENTS
    llm_for = staticmethod(llm.make_llm)  # the account's own stored key and model, or None (the agents then ask for a key)
    mailer = None

    def log_message(self, fmt, *args):  # no request lines in the log: URLs and cookies can carry secrets
        pass

    # ---- helpers ----
    def _ip(self) -> str:
        edge_ip = edge.client_ip(self.headers)  # only believed when the request carried the edge secret
        if edge_ip:
            return edge_ip
        if os.getenv("HUB_TRUST_PROXY") == "1":
            xff = self.headers.get("X-Forwarded-For", "")
            if xff:
                return xff.split(",")[-1].strip()[:64]
        return self.client_address[0]

    def _headers(self, code: int, ctype: str, length: int | None, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if "Cache-Control" not in (extra or {}):
            self.send_header("Cache-Control", "no-store")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Frame-Options", "DENY")
        if os.getenv("HUB_INSECURE_DEV") != "1":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for k, v in (extra or {}).items():
            for item in (v if isinstance(v, list) else [v]):
                self.send_header(k, item)
        self.end_headers()

    def _json(self, code: int, obj: dict, extra: dict | None = None) -> None:
        body = json.dumps(obj).encode()
        self._headers(code, "application/json", len(body), extra)
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self._json(413, {"ok": False, "error": "too_large"})
            return None
        raw = self.rfile.read(n) if n else b""
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            self._json(400, {"ok": False, "error": "bad_json"})
            return None
        return data

    def _cookies(self) -> dict:
        return parse_cookies(self.headers.get("Cookie", ""))

    def _auth(self):
        """(account or None, how) where how is 'cookie' or 'bearer'."""
        h = self.headers.get("Authorization", "")
        if h.lower().startswith("bearer "):
            return auth.session_account(h[7:].strip()), "bearer"
        return auth.session_account(self._cookies().get(COOKIE)), "cookie"

    def _same_site(self) -> bool:
        if self.headers.get("X-Hub") != "1":
            return False
        origin = self.headers.get("Origin")
        return not origin or urlsplit(origin).netloc == (edge.forwarded_host(self.headers) or self.headers.get("Host", ""))

    def _session_cookie(self, token: str | None) -> list:
        secure = "" if os.getenv("HUB_INSECURE_DEV") == "1" else "; Secure"
        if token is None:
            return [f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure}"]
        return [f"{COOKIE}={token}; Path=/; Max-Age={auth.SESSION_ABSOLUTE}; HttpOnly; SameSite=Lax{secure}"]

    def _base_url(self) -> str:
        pub = os.getenv("HUB_PUBLIC_URL", "").strip().rstrip("/")
        if pub:
            return pub
        host = self.headers.get("Host", "localhost")
        return f"http://{host}" if re.fullmatch(r"[A-Za-z0-9.\-]+(:\d+)?", host) else "http://localhost"

    # ---- GET ----
    def do_GET(self):
        path = urlsplit(self.path).path
        if not edge.edge_ok(self.headers, path):
            return self._json(403, {"ok": False, "error": "forbidden"})
        if path == "/healthz":
            return self._json(200, {"ok": True})
        if path == "/api/config":
            csrf = secrets.token_urlsafe(24)
            return self._json(200, {"google_enabled": auth.google_configured(), "google_client_id": os.getenv("HUB_GOOGLE_CLIENT_ID", "").strip(), "turnstile_site_key": edge.site_key(), "csrf": csrf},
                              {"Set-Cookie": [f"{CSRF_COOKIE}={csrf}; Path=/; Max-Age=3600; SameSite=Lax" + ("" if os.getenv("HUB_INSECURE_DEV") == "1" else "; Secure")]})
        if path == "/api/me":
            acc, _ = self._auth()
            return self._json(200, {"ok": True, "account": acc}) if acc else self._json(401, {"ok": False, "error": "signed_out"})
        if path == "/api/niches":
            import niche

            return self._json(200, {"niches": [{"id": p["id"], "name": p["name"], "audience": p["audience"]} for p in niche.PRESETS]})
        if path == "/api/profile":
            acc, _ = self._auth()
            return self._json(200, {"ok": True, "profile": profile.get(acc["id"]), "platforms": {k: v["mode"] for k, v in agent_team.PLATFORMS.items()}}) if acc else self._json(401, {"ok": False, "error": "signed_out"})
        if path == "/api/key":
            acc, _ = self._auth()
            return self._json(200, {"ok": True, **keystore.status(acc["id"])}) if acc else self._json(401, {"ok": False, "error": "signed_out"})
        if path in ("/api/research", "/api/export"):
            acc, _ = self._auth()
            if not acc:
                return self._json(401, {"ok": False, "error": "signed_out"})
            if path == "/api/research":
                return self._json(200, {"ok": True, **research.overview(acc["id"])})
            platform = (parse_qs(urlsplit(self.path).query).get("platform") or [""])[0]
            text = research.export_markdown(acc["id"], platform)
            if text is None:
                return self._json(400, {"ok": False, "error": "unknown_platform"})
            body = text.encode()
            self._headers(200, "text/markdown; charset=utf-8", len(body), {"Content-Disposition": f'attachment; filename="plan-{platform.lower()}.md"'})
            return self.wfile.write(body)
        if path in ("/a2a", "/a2a/"):
            base = self._base_url()
            return self._json(200, {"agents": [{"id": a.id, "name": a.name, "card": f"{base}/a2a/{a.id}/.well-known/agent-card.json"} for a in self.agents.values()]})
        m = re.fullmatch(r"/a2a/([a-z]+)/\.well-known/agent-card\.json", path)
        if m:
            agent = self.agents.get(m.group(1))
            return self._json(200, a2a.agent_card(agent, self._base_url())) if agent else self._json(404, {"ok": False, "error": "not_found"})
        return self._static(path)

    def _static(self, path: str) -> None:
        rel = "index.html" if path == "/" else ("favicon.svg" if path == "/favicon.ico" else path.lstrip("/"))
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._json(404, {"ok": False, "error": "not_found"})
        body = f.read_bytes()
        if f.name == "privacy.html":  # the operator's contact line comes from the settings (HUB_CONTACT), as escaped text; until it is set the page shows its draft marker
            contact = " ".join(os.getenv("HUB_CONTACT", "").split())[:200]
            if contact:
                body = body.replace(b"OWNER-TO-FILL", html.escape(contact).encode())
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        static = {} if ctype.startswith("text/html") or os.getenv("HUB_INSECURE_DEV") == "1" else {"Cache-Control": "public, max-age=300"}  # fonts, icons, styles and scripts may be kept five minutes; pages never
        self._headers(200, ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""), len(body), static)
        self.wfile.write(body)

    def do_OPTIONS(self):  # no CORS: a cross-site page's preflight gets no permission headers
        self._headers(204, "text/plain", 0)

    # ---- POST ----
    def do_POST(self):
        path = urlsplit(self.path).path
        if not edge.edge_ok(self.headers, path):
            return self._json(403, {"ok": False, "error": "forbidden"})
        acc, how = self._auth()
        if ((how == "cookie" and acc) or path.startswith("/api/")) and not self._same_site():
            return self._json(403, {"ok": False, "error": "forbidden"})
        data = self._body()
        if data is None:
            return
        ip = self._ip()
        if path == "/api/auth/request":
            if not edge.turnstile_ok(data.get("turnstile"), ip):
                return self._json(400, {"ok": False, "error": "bot_check"})
            r = auth.request_code(data.get("email"), ip, mailer=self.mailer)
            return self._json(429 if r.get("error") == "too_many" else (200 if r["ok"] else 400), r)
        if path == "/api/auth/verify":
            r = auth.verify_code(data.get("email"), data.get("code"), ip)
            if not r["ok"]:
                return self._json(429 if r.get("error") == "too_many" else 401, r)
            return self._json(200, {"ok": True, "account": r["account"]}, {"Set-Cookie": self._session_cookie(r["token"])})
        if path == "/api/auth/google":
            if not auth.google_configured():
                return self._json(503, {"ok": False, "error": "google_not_configured"})
            r = auth.google_login(data.get("credential"), self._cookies().get(CSRF_COOKIE), data.get("csrf"), ip)
            if not r["ok"]:
                return self._json(401, r)
            return self._json(200, {"ok": True, "account": r["account"]}, {"Set-Cookie": self._session_cookie(r["token"])})
        if path == "/api/logout":
            tok = self._cookies().get(COOKIE)
            auth.logout(tok)
            return self._json(200, {"ok": True}, {"Set-Cookie": self._session_cookie(None)})
        if path == "/api/demo/niche":  # public, free, no model: the same rule agent a signed-in creator talks to; nothing is stored
            if not auth.hit(f"demo:{ip}", 20, 60):
                return self._json(429, {"ok": False, "error": "too_many"})
            text = str(data.get("text") or "")[:600]
            res = agent_team.concierge(a2a.Ctx("demo", "concierge", "", "", text, None))
            art = (res.get("artifacts") or [{}])[0].get("data") or {}
            return self._json(200, {"ok": True, "state": res["state"], "text": res["text"], "tier": art.get("tier", ""), "matches": art.get("matches", [])})
        if path == "/api/profile":
            if not acc:
                return self._json(401, {"ok": False, "error": "signed_out"})
            import niche

            try:
                p = profile.save(acc["id"], data.get("niche_id"), data.get("niche_text"), data.get("tier"), data.get("platforms", []), niche.PRESET_IDS, set(agent_team.PLATFORMS))
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            return self._json(200, {"ok": True, "profile": p})
        if path == "/api/account/delete":
            if not acc:
                return self._json(401, {"ok": False, "error": "signed_out"})
            if str(data.get("confirm") or "").strip().lower() != "delete":
                return self._json(400, {"ok": False, "error": "confirm", "message": "Type the word delete to confirm."})
            auth.delete_account(acc["id"])
            return self._json(200, {"ok": True}, {"Set-Cookie": self._session_cookie(None)})
        if path in ("/api/key", "/api/key/remove"):
            if not acc:
                return self._json(401, {"ok": False, "error": "signed_out"})
            if path == "/api/key/remove":
                return self._json(200, {"ok": True, "removed": keystore.remove(acc["id"])})
            if not auth.hit(f"keychange:{acc['id']}", 10, 3600):
                return self._json(429, {"ok": False, "error": "too_many"})
            try:
                key = keystore.clean_key(data.get("key"))
            except ValueError as e:
                return self._json(400, {"ok": False, "error": "bad_key", "message": str(e)})
            try:
                model = keystore.clean_model(data.get("model"))
            except ValueError as e:
                return self._json(400, {"ok": False, "error": "bad_model", "message": str(e)})
            check = llm.check_key(key)  # a free call to OpenRouter; only a refusal rejects the key, trouble reaching OpenRouter stores it as unverified
            if not check["ok"] and check["reason"] == "key_rejected":
                return self._json(400, {"ok": False, "error": "key_rejected", "message": "OpenRouter did not accept this key. Copy it again from your OpenRouter account."})
            keystore.set_key(acc["id"], key, model)
            return self._json(200, {"ok": True, "verified": check["ok"], **keystore.status(acc["id"])})
        m = re.fullmatch(r"/a2a/([a-z]+)", path)
        if m:
            return self._a2a(m.group(1), acc, data)
        return self._json(404, {"ok": False, "error": "not_found"})

    def _a2a(self, agent_id: str, acc, body) -> None:
        if not acc:
            return self._json(401, {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "Sign in required"}}, {"WWW-Authenticate": 'Bearer realm="hub"'})
        if not auth.hit(f"a2a:{acc['id']}", CALLS_PER_MINUTE, 60):
            return self._json(429, {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Too many requests, wait a minute"}})
        out = a2a.handle(self.agents, agent_id, acc["id"], body, self.headers.get("A2A-Version"), self.llm_for(acc["id"]), self._base_url())
        if isinstance(out, dict):
            return self._json(200, out)
        self._headers(200, "text/event-stream", None, {"Connection": "close"})
        try:
            for ev in out:
                self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True


def make_server(host: str = "127.0.0.1", port: int = 8931) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Hub)


def startup_report(environ=None, path=None) -> list[str]:
    """Read the private secrets file into the environment, then say in plain words what is switched on. Names and on/off only, never a value."""
    environ = os.environ if environ is None else environ
    loaded = secretstore.load(path, environ)
    st = secretstore.status(path, environ)
    lines = [f"Secrets file ignored: {loaded['ignored']}"] if loaded["ignored"] else []
    mail_parts = ("HUB_SMTP_HOST", "HUB_SMTP_USER", "HUB_SMTP_PASSWORD")
    missing = [n for n in mail_parts if not st[n]]
    if not missing:
        lines.append("Mail: SMTP is set, sign-in codes are sent by email")
    elif len(missing) == len(mail_parts):
        lines.append("Mail: local outbox only (nothing is sent; codes are written to data/hub/outbox/)")
    else:
        lines.append("Mail: incomplete, missing " + ", ".join(missing) + " (sending codes will fail until it is complete)")
    lines.append("Google sign-in: on" if st["HUB_GOOGLE_CLIENT_ID"] else "Google sign-in: off (no client id set)")
    listed = auth.allow_entries(environ)
    lines.append(f"Sign-up: closed to {len(listed)} listed addresses or domains" if listed else "Sign-up: OPEN to anyone")
    lines.append(f"Sign-in emails: at most {auth.mail_daily_cap(environ)} a day for the whole hub")
    lines.append("Privacy contact: set" if st["HUB_CONTACT"] else "Privacy contact: NOT SET (the privacy page is still a draft)")
    return lines


def main() -> None:
    for line in startup_report():
        print(line)
    srv = make_server(os.getenv("HUB_HOST", "127.0.0.1"), int(os.getenv("HUB_PORT", "8931")))
    print(f"Creator Hub on http://{srv.server_address[0]}:{srv.server_address[1]}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
