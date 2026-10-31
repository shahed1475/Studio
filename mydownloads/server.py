"""The small web server of My Downloads: http://127.0.0.1:8923, on this computer only.

Who may use it: only a page opened from its own address. The `Host` must be 127.0.0.1:<port> or localhost:<port> (a web page on another site that has
tricked the browser into this address is refused), every POST needs the header `X-MyDownloads` (another site cannot send a custom header without a
permission check, and this server never grants one) and, if the browser sends an `Origin`, it must be its own. It never sends CORS headers.
It serves four fixed files and nothing else, and its only side effect outside its own folder is opening the download folder in the file manager.
"""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import ADDRESS, HOST, PORT, intent, jobs, store
from . import engine as engines

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
FONT = ROOT.parent / "static" / "geist.woff2"
MAX_BODY = 64 * 1024
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


class Upstream(Exception):
    """YouTube or the network failed; the message is already in plain words."""


def _xdg_open(path: Path) -> None:
    try:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        raise ValueError(f"I could not open the folder for you. It is here: {path}")


def _public(chans) -> list:
    return [{"id": c["id"], "title": c.get("title", ""), "handle": c.get("handle", "")} for c in chans]


def _ytdlp_version():
    try:
        import yt_dlp.version

        return yt_dlp.version.__version__
    except Exception:
        return None


class App:
    def __init__(self, eng, runner, web_dir=WEB, font=FONT, open_folder=None):
        self.engine, self.runner, self.open_folder = eng, runner, open_folder or _xdg_open
        web_dir = Path(web_dir)
        self.assets = {"/": (web_dir / "index.html", "text/html; charset=utf-8"), "/app.js": (web_dir / "app.js", "application/javascript; charset=utf-8"),
                       "/style.css": (web_dir / "style.css", "text/css; charset=utf-8"), "/geist.woff2": (Path(font), "font/woff2")}
        self.posts = {"/api/plan": self.plan, "/api/download": self.download, "/api/stop": self.stop, "/api/resume": self.resume,
                      "/api/channels": self.add_channel, "/api/channels/remove": self.remove_channel, "/api/open-folder": self.open}

    def state(self) -> dict:
        f = store.folder()
        return {"folder": str(f), "folder_exists": f.is_dir(), "channels": _public(store.channels()), "job": self.runner.snapshot(), "address": ADDRESS,
                "yt_dlp": _ytdlp_version(), "free_gb": round(self.runner.free_bytes(f) / 2**30, 1)}

    def plan(self, body) -> dict:
        text = str(body.get("text") or "").strip()
        if not text:
            raise ValueError("Tell me what to download, for example “my last 5 videos”.")
        if len(text) > 1000:
            raise ValueError("That is too long. Say it in one short sentence.")
        only = body.get("channel") or None
        if only is not None and not (isinstance(only, str) and store.CHANNEL_ID.match(only)):
            raise ValueError("That channel is not valid.")
        it = intent.parse(text)
        try:
            res = self.engine.plan(it, only)
        except Exception as e:
            raise Upstream(engines.friendly(e))
        return {"summary": intent.describe(it), "intent": {"count": it.count, "order": it.order, "kind": it.kind, "keywords": it.keywords, "urls": it.urls},
                "items": res["items"], "notes": res["notes"]}

    def download(self, body) -> dict:
        return self.runner.start(body.get("items"))

    def stop(self, body) -> dict:
        self.runner.stop()
        return {"ok": True}

    def resume(self, body) -> dict:
        return self.runner.resume()

    def add_channel(self, body) -> dict:
        if body.get("confirm") is not True:
            raise ValueError("Tick the box to say this is your own channel.")
        text = str(body.get("text") or "").strip()
        if not text:
            raise ValueError("Paste your channel link or @name.")
        try:
            info = self.engine.resolve_channel(text)
        except ValueError:
            raise
        except Exception as e:
            raise Upstream(engines.friendly(e))
        store.add_channel(info["id"], info["title"], info["handle"], "your statement in My Downloads that this channel is yours")
        return {"channels": _public(store.channels())}

    def remove_channel(self, body) -> dict:
        removed = store.remove_channel(str(body.get("id") or ""))
        return {"removed": removed, "channels": _public(store.channels())}

    def open(self, body) -> dict:
        f = store.folder()
        f.mkdir(parents=True, exist_ok=True)
        self.open_folder(f)  # always the download folder, never a path from the request
        return {"ok": True, "folder": str(f)}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    app: App

    def log_message(self, fmt, *args):  # keep the terminal quiet; errors are in the page
        pass

    # -- plumbing
    def _send(self, status, body: bytes, ctype, extra=()):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in extra:
            self.send_header(k, v)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(status, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def _refuse(self, status, message):
        self.close_connection = True  # a body we did not read must not leak into the next request
        self._json({"error": message}, status)

    def _own(self):
        p = self.server.server_port
        return {f"127.0.0.1:{p}", f"localhost:{p}"}, {f"http://127.0.0.1:{p}", f"http://localhost:{p}"}

    def _guard(self, post=False) -> bool:
        hosts, origins = self._own()
        if self.headers.get("Host", "") not in hosts:
            self._refuse(403, "Wrong address.")
            return False
        if post:
            if self.headers.get("X-MyDownloads") != "1":
                self._refuse(403, "Not allowed.")
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                self._refuse(403, "Not allowed from another site.")
                return False
        return True

    # -- methods
    def do_GET(self):
        if not self._guard():
            return
        path = urlparse(self.path).path
        if path == "/healthz":
            return self._send(200, b"ok", "text/plain; charset=utf-8")
        if path == "/api/state":
            return self._json(self.app.state())
        asset = self.app.assets.get(path)
        if asset:
            try:
                return self._send(200, asset[0].read_bytes(), asset[1])
            except OSError:
                pass
        self._json({"error": "Not found."}, 404)

    def do_OPTIONS(self):
        self._refuse(405, "Not allowed.")

    def do_POST(self):
        if not self._guard(post=True):
            return
        route = self.app.posts.get(urlparse(self.path).path)
        if route is None:
            return self._refuse(404, "Not found.")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._refuse(400, "Bad request.")
        if n > MAX_BODY:
            return self._refuse(413, "That request is too big.")
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._refuse(400, "I could not read that request.")
        try:
            self._json(route(body))
        except jobs.Busy as e:
            self._json({"error": str(e)}, 409)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Upstream as e:
            self._json({"error": str(e)}, 502)
        except Exception as e:
            print("My Downloads: unexpected error:", repr(e), file=sys.stderr, flush=True)
            self._json({"error": "Something went wrong inside the downloader: " + engines.friendly(e)}, 500)


def make_server(app: App, host=HOST, port=PORT) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    return httpd


def main() -> int:
    eng = engines.Engine()
    runner = jobs.Runner(eng)
    try:
        httpd = make_server(App(eng, runner))
    except OSError as e:
        print(f"My Downloads could not start on {ADDRESS}: {e}. It may already be running: open {ADDRESS}", file=sys.stderr)
        return 1
    print(f"My Downloads is running at {ADDRESS}\nVideos are saved in {store.folder()}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
