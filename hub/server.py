"""The hub's web server (standard library only): the website, sign-in, and the A2A endpoints. `python -m hub.server` listens on 127.0.0.1:8931 (HUB_HOST, HUB_PORT).

Security choices (backend-design auth and security skills): the session cookie is HttpOnly, SameSite=Lax and Secure (HUB_INSECURE_DEV=1 drops Secure for local http only); a request
that rides on the cookie must carry `X-Hub: 1` (a cross-site page cannot add it without a preflight, and this server answers no preflight) and, if it has an Origin, that Origin must
be this host; a Bearer token (the same session token) needs neither because it is never sent by the browser on its own. No CORS headers at all. JSON bodies only, 64 KB at most.
Every A2A call is tied to the signed-in account from the session, never to an id in the request. 60 A2A calls a minute per account. Errors say nothing about internals.
The client's address is the socket's, or the last X-Forwarded-For hop only when HUB_TRUST_PROXY=1 (Caddy in front)."""
import json
import mimetypes
import os
import re
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import a2a, agents as agent_team, auth

WEB = Path(__file__).parent / "web"
COOKIE, CSRF_COOKIE = "hub_session", "hub_csrf"
MAX_BODY = 64 * 1024
CALLS_PER_MINUTE = 60
CSP = ("default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; frame-src https://accounts.google.com/gsi/; "
       "connect-src 'self' https://accounts.google.com/gsi/; style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; img-src 'self' data:; "
       "font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class Hub(BaseHTTPRequestHandler):
    server_version = "CreatorHub"
    sys_version = ""
    agents = agent_team.AGENTS
    llm_for = staticmethod(lambda account_id: None)  # per-account model keys arrive with the research store; until then model agents ask for a key
    mailer = None

    def log_message(self, fmt, *args):  # no request lines in the log: URLs and cookies can carry secrets
        pass

    # ---- helpers ----
    def _ip(self) -> str:
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
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return {}
        return {k: m.value for k, m in c.items()}

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
        return not origin or urlsplit(origin).netloc == self.headers.get("Host", "")

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
        if path == "/healthz":
            return self._json(200, {"ok": True})
        if path == "/api/config":
            csrf = secrets.token_urlsafe(24)
            return self._json(200, {"google_enabled": auth.google_configured(), "google_client_id": os.getenv("HUB_GOOGLE_CLIENT_ID", "").strip(), "csrf": csrf},
                              {"Set-Cookie": [f"{CSRF_COOKIE}={csrf}; Path=/; Max-Age=3600; SameSite=Lax" + ("" if os.getenv("HUB_INSECURE_DEV") == "1" else "; Secure")]})
        if path == "/api/me":
            acc, _ = self._auth()
            return self._json(200, {"ok": True, "account": acc}) if acc else self._json(401, {"ok": False, "error": "signed_out"})
        if path in ("/a2a", "/a2a/"):
            base = self._base_url()
            return self._json(200, {"agents": [{"id": a.id, "name": a.name, "card": f"{base}/a2a/{a.id}/.well-known/agent-card.json"} for a in self.agents.values()]})
        m = re.fullmatch(r"/a2a/([a-z]+)/\.well-known/agent-card\.json", path)
        if m:
            agent = self.agents.get(m.group(1))
            return self._json(200, a2a.agent_card(agent, self._base_url())) if agent else self._json(404, {"ok": False, "error": "not_found"})
        return self._static(path)

    def _static(self, path: str) -> None:
        rel = "index.html" if path == "/" else path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._json(404, {"ok": False, "error": "not_found"})
        body = f.read_bytes()
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        self._headers(200, ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""), len(body))
        self.wfile.write(body)

    def do_OPTIONS(self):  # no CORS: a cross-site page's preflight gets no permission headers
        self._headers(204, "text/plain", 0)

    # ---- POST ----
    def do_POST(self):
        path = urlsplit(self.path).path
        acc, how = self._auth()
        if ((how == "cookie" and acc) or path.startswith("/api/")) and not self._same_site():
            return self._json(403, {"ok": False, "error": "forbidden"})
        data = self._body()
        if data is None:
            return
        ip = self._ip()
        if path == "/api/auth/request":
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


def main() -> None:
    srv = make_server(os.getenv("HUB_HOST", "127.0.0.1"), int(os.getenv("HUB_PORT", "8931")))
    print(f"Creator Hub on http://{srv.server_address[0]}:{srv.server_address[1]}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
