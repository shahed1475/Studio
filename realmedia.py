"""Real pictures for a film or a Short, from every free library the owner approved (10 Nov 2026): real first, a drawn picture only where nothing real fits.

`Finder` is called by `footage.scene_images` after the Wikimedia Commons public-domain search. For a query it asks the libraries (openmedia.py), keeps only items whose licence the studio accepts
(licences.py), keeps only items that name the film's subject or that the picture judge approves, prefers public domain and CC0 over items that need a credit, caps the credit-needing items per video
(each must be written into the description), downloads only what it will use, and records for every picture its address, licence, credit, date and hash (`assets`, saved in the video's record).
Never used: NASA logos, anything below a usable size, Pexels (not on the owner's list), anything a library marks with a licence the studio refuses. A library that fails is skipped and noted."""
import datetime as dt
import hashlib
import io
import ipaddress
import re
import socket
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image

import config
import licences
import openmedia

NARROW = ("commons", "openverse")  # the per-scene searches: quick and specific
WIDE = ("commons", "smithsonian", "met", "aic", "cleveland", "openverse", "nasa", "pixabay")  # the subject itself: a reserve of pictures from every approved library
MIN_WIDTH, PER_SOURCE, TIMEOUT = 600, 6, 60
NASA_NOT = re.compile(r"\b(logo|insignia|emblem|patch|seal|meatball|worm)\b", re.I)
UA = {"User-Agent": "StoryStudio/1.0 (history documentary channel; picture lookup; github.com/shahed1475/Studio)"}
MAX_BYTES, MAX_PIXELS, MAX_HOPS, TOTAL_SECONDS = 25_000_000, 60_000_000, 3, 60  # one picture: 25 MB, 60 million pixels, three redirects, a minute


def default_resolve(host: str) -> list[str]:
    return [a[4][0] for a in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]


def _public_https(url: str, resolve) -> bool:
    """True only for an https address whose name resolves ONLY to public addresses (no loopback, private, link-local, reserved or carrier-grade ones)."""
    try:
        p = urlsplit(url)
        if p.scheme != "https" or not p.hostname:
            return False
        ips = resolve(p.hostname)
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (OSError, ValueError):
        return False


class Finder:
    def __init__(self, topic: str, anchors: list[str], judge=None, credit_cap: int = 12, search=openmedia.search, get=requests.get, folder: Path | None = None, resolve=None):
        self.topic, self.anchors, self.judge, self.credit_cap = topic, list(anchors or []), judge, credit_cap
        self.search, self.get, self.resolve = search, get, resolve or default_resolve
        self.folder = Path(folder) if folder else config.CACHE / "real"
        self.assets: list[dict] = []
        self.problems: list[str] = []
        self.credit_count = 0
        self._credits: list[str] = []
        self._bad: set[str] = set()

    # ---- what the scene code calls ----
    def __call__(self, query: str, anchors: list[str] | None = None, limit: int = 1, skip=(), wide: bool = False) -> list[tuple[Path, str]]:
        anchors = list(anchors or self.anchors)
        cands: list[dict] = []
        for rank, src in enumerate(WIDE if wide else NARROW):
            try:
                items = self.search(src, query, "image", PER_SOURCE, self.get)
            except Exception as ex:  # a library that is down, rate-limited or has no key must not stop the film
                self.problems.append(f"{src}: {str(ex)[:120]}")
                continue
            for it in items:
                if it.get("accepted") and it.get("url") and not (src == "nasa" and NASA_NOT.search(str(it.get("title")))):
                    cands.append({**it, "_rank": rank})
        cands = list({c["url"]: c for c in cands}.values())
        direct = [c for c in cands if self._names_subject(c, anchors)]
        rest = [c for c in cands if c not in direct]
        if self.judge and rest:
            labels = {f"{c['title']} | {c['source']}": c for c in rest}
            kept = set(self.judge(list(labels)))
            direct += [c for l, c in labels.items() if l in kept]
        direct.sort(key=lambda c: (licences.PREFERENCE.get(licences.kind(c["licence"]), 9), c["_rank"]))
        out: list[tuple[Path, str]] = []
        for c in direct:
            if len(out) >= limit:
                break
            credit_needed = licences.needs_credit(c["licence"])
            if credit_needed and self.credit_count >= self.credit_cap and c["url"] not in self._known_urls():
                continue
            path = self._download(c)
            if path is None or path in skip or path in [p for p, _ in out]:
                continue
            credit = self._credit(c)
            if credit not in self._credits:
                self._credits.append(credit)
                self.credit_count += credit_needed
                self.assets.append({"file": path.name, "title": c["title"], "source": c["source"], "page": c["page"], "url": c["url"], "licence": c["licence"], "credit": credit,
                                    "fetched": dt.date.today().isoformat(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            out.append((path, credit))
        return out

    def credits(self) -> list[str]:
        return list(self._credits)

    # ---- inside ----
    def _known_urls(self) -> set[str]:
        return {a["url"] for a in self.assets}

    def _names_subject(self, c: dict, anchors: list[str]) -> bool:
        text = f"{c['title']}".lower()
        words = anchors or [w for w in re.findall(r"[a-z]{5,}", self.topic.lower())]
        return any(a.lower() in text for a in words)

    def _credit(self, c: dict) -> str:
        """One credit line: title (cut at a word), the author when the library names one, the licence, the library and the picture's page. Refusal words and the word "copyright" are removed
        from the title and author: a title like "Non-commercial vehicles" or an author line "based on copyright claims" must not make the gate refuse a licence-clean item."""
        def clean(text, limit):
            t = " ".join(licences.REFUSED.sub("", re.sub(r"(?i)copyright\w*", "", openmedia._plain(text, 400))).split())
            return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0].rstrip(",;:- ") + "..."

        base = f"{clean(c['title'], 70)} by {clean(c['author'], 50)}" if c.get("author") else clean(c.get("credit") or c["title"], 110)
        label = openmedia.SOURCES.get(c["source"], (c["source"],))[0]
        if label.lower() not in base.lower():
            base += f", {label}"
        if c["licence"].lower() not in base.lower():
            base += f" ({c['licence']})"
        return f"{base}, {c['page']}"

    def _bytes(self, url: str) -> bytes:
        """The file at a library's address, fetched only from public https addresses (every redirect hop is checked first, none is followed by requests itself), streamed, and cut off at a
        size and time limit. A library entry is third-party data and the worker shares the host's network: no internal address may be reached through it (security review, 10 Nov 2026).
        Limit: a name could resolve differently at connect time than at this check (DNS rebinding); the size and time limits and the image check below bound what that could cost."""
        deadline = time.monotonic() + TOTAL_SECONDS
        for _ in range(MAX_HOPS + 1):
            if not _public_https(url, self.resolve):
                raise ValueError("not a public https address")
            r = self.get(url, headers=UA, timeout=TIMEOUT, stream=True, allow_redirects=False)
            if r.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, r.headers.get("Location") or "")
                continue
            if r.status_code != 200:
                raise ValueError(f"HTTP {r.status_code}")
            buf = bytearray()
            for chunk in r.iter_content(65536):
                buf += chunk
                if len(buf) > MAX_BYTES or time.monotonic() > deadline:
                    raise ValueError("download too large or too slow")
            return bytes(buf)
        raise ValueError("too many redirects")

    def _download(self, c: dict) -> Path | None:
        url = c["url"]
        if url in self._bad:
            return None
        dest = self.folder / (hashlib.md5(url.encode()).hexdigest()[:12] + ".jpg")
        if dest.exists():
            return dest
        try:
            data = self._bytes(url)
            with Image.open(io.BytesIO(data)) as im:
                if im.width * im.height > MAX_PIXELS:  # judged from the header, before any pixel is decoded
                    raise ValueError(f"too many pixels ({im.width} x {im.height})")
                im.load()
                if im.width < MIN_WIDTH:
                    raise ValueError(f"too small ({im.width} px wide)")
                self.folder.mkdir(parents=True, exist_ok=True)
                im.convert("RGB").save(dest, "JPEG", quality=92)
        except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError) as ex:
            self._bad.add(url)
            self.problems.append(f"{c['source']}: {str(ex)[:100]}")
            return None
        return dest
