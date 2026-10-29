"""A small Chrome DevTools driver for tests that must click in a real browser (standard library only; skipped where Chrome is not installed).

Real mouse events are used for clicks, so a handler that re-renders the thing that was clicked behaves as it does for a person."""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from time import sleep as _sleep  # bound now: the shared test setup replaces time.sleep for every test

CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


class Browser:
    def __init__(self, width=1440, height=900, mobile=False):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.dir = tempfile.mkdtemp(prefix="chrome-test-")
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", f"--remote-debugging-port={self.port}",
                                      f"--user-data-dir={self.dir}", f"--window-size={width},{height}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws = None
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json"))
                ws = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                _sleep(0.25)
        if ws is None:
            self.close()
            raise RuntimeError("Chrome did not start")
        self.sock = socket.create_connection(("127.0.0.1", self.port))
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {ws.split(str(self.port), 1)[1]} HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.n = 0
        self.size(width, height, mobile)

    # -- websocket plumbing
    def _read(self, k):
        while len(self.buf) < k:
            self.buf += self.sock.recv(1 << 20)
        out, self.buf = self.buf[:k], self.buf[k:]
        return out

    def _frame(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read(8))[0]
            msg += self._read(ln)
            if b1 & 0x80:
                return msg

    def send(self, method, **params):
        self.n += 1
        data = json.dumps({"id": self.n, "method": method, "params": params}).encode()
        mask = os.urandom(4)
        ln = len(data)
        hdr = bytes([0x81]) + (bytes([0x80 | ln]) if ln < 126 else bytes([0x80 | 126]) + struct.pack(">H", ln) if ln < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", ln))
        self.sock.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        while True:
            m = json.loads(self._frame())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    # -- what a test uses
    def size(self, width, height, mobile=False):
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=mobile)

    # The page's HTML has a loading skeleton inside #main, so "#main has children" is true before the app script has run; a click then did nothing. Ready means the app is
    # running and has replaced the skeleton.
    READY = "typeof toggleNotes === 'function' && document.getElementById('main') && document.getElementById('main').children.length > 0 && !document.querySelector('#main .skel')"

    def open(self, url, wait_for=READY, timeout=15):
        self.send("Page.navigate", url=url)
        self.until(wait_for, timeout)
        self.js("window.__errors=[];addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)))")

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", "script error"))
        return r.get("result", {}).get("value")

    def until(self, cond, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.js(cond):
                    return True
            except RuntimeError:
                pass
            _sleep(0.1)
        raise TimeoutError(f"never true: {cond}")

    def center(self, selector_js):
        """[x, y] of the middle of the element found by a JS expression, scrolled into view."""
        return self.js(f"(()=>{{const e={selector_js};if(!e)return null;e.scrollIntoView({{block:'center',inline:'center'}});const r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}})()")

    def click(self, selector_js):
        """A real left click (mouse down and up at the element's centre). selector_js is a JS expression that returns the element."""
        pos = self.center(selector_js)
        if not pos:
            raise LookupError(f"no element for {selector_js}")
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=pos[0], y=pos[1], button="left" if t != "mouseMoved" else "none", clickCount=1)
        _sleep(0.15)

    def key(self, name, code=None, vk=0):
        for t in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=t, key=name, code=code or name, windowsVirtualKeyCode=vk)

    def errors(self):
        return self.js("JSON.stringify(window.__errors||[])")

    def shot(self, path):
        open(path, "wb").write(base64.b64decode(self.send("Page.captureScreenshot", format="png")["data"]))

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass
        shutil.rmtree(self.dir, ignore_errors=True)
