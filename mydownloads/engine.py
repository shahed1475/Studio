"""Finding the owner's videos on YouTube and saving them (yt-dlp used as a library).

The one rule that matters: a video is downloaded only when its own fresh metadata says its channel is on the owner's list (store.channels).
That check runs when the list is built and again right before each download, so a stale or edited list cannot get another creator's video through.
"""
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import intent as intents
from . import store

try:
    from yt_dlp.utils import DownloadCancelled as _CancelBase
except Exception:  # the tests use a fake and need no yt-dlp
    _CancelBase = Exception

MAX_SCAN = 500  # most entries read from one list
FORMAT = "bv*[vcodec^=avc1]+ba[ext=m4a]/bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"  # H.264 first: AV1 files do not play on many older phones, TVs and players
OUTTMPL = "%(channel)s/%(title).120B [%(id)s].%(ext)s"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
HANDLE = re.compile(r"^@[\w.-]{3,40}$")
NOT_MINE = "is not one of your channels, so I will not download it."


class NotMine(Exception):
    """The video is not on one of the owner's channels."""


class Cancelled(_CancelBase):
    """The owner pressed Stop."""


def friendly(exc) -> str:
    """A download or lookup error in plain words, with what to do next."""
    raw = ANSI.sub("", str(exc)).strip()
    low = raw.lower()
    if "private video" in low:
        return "This video is private or still scheduled, so YouTube only lets you download it from YouTube Studio (Content, the three dots, then Download)."
    if "not a bot" in low or "sign in to confirm" in low:
        return "YouTube wants a sign-in check from this computer. Turn off any VPN, wait a few minutes and try again. If it keeps happening, update the downloader: .venv/bin/pip install -U yt-dlp"
    if any(s in low for s in ("unable to download webpage", "name resolution", "getaddrinfo", "network is unreachable", "connection reset", "timed out", "urlopen error", "connection refused", "remote end closed")):
        return "No internet connection, or it dropped. Run it again: finished videos are kept and a half-finished one carries on."
    if "no space left" in low:
        return "There is no disk space left. Free some space and run it again."
    if "ffmpeg" in low and ("not found" in low or "install" in low):
        return "ffmpeg is missing, so the picture and sound cannot be joined. Install ffmpeg and run it again."
    if "403" in low and "forbidden" in low:
        return "YouTube refused the download (403). This usually means the downloader is out of date: update it with .venv/bin/pip install -U yt-dlp and try again."
    if "video unavailable" in low or "this video is not available" in low:
        return "This video is unavailable on YouTube (removed or blocked)."
    return re.sub(r"^(ERROR:\s*)+", "", raw)[:200] or "The download failed."


def _watch(video_id: str, kind: str = "long") -> str:
    return f"https://www.youtube.com/shorts/{video_id}" if kind == "short" else f"https://www.youtube.com/watch?v={video_id}"


def _classify(url: str):
    """('video', id), ('channel', id or @handle), ('playlist', None) or ('other', None)."""
    u = urlparse(url)
    host, path = (u.netloc or "").lower().split(":")[0], u.path or ""
    q = parse_qs(u.query)
    if host.endswith("youtu.be"):
        vid = path.strip("/").split("/")[0]
        return ("video", vid) if store.VIDEO_ID.match(vid) else ("other", None)
    if not host.endswith("youtube.com"):
        return "other", None
    if path.startswith("/playlist"):
        return "playlist", None
    if path.startswith("/watch") and q.get("v"):
        return ("video", q["v"][0]) if store.VIDEO_ID.match(q["v"][0]) else ("other", None)
    m = re.match(r"^/(?:shorts|live|embed|v)/([\w-]+)", path)
    if m and store.VIDEO_ID.match(m.group(1)):
        return "video", m.group(1)
    m = re.match(r"^/channel/(UC[\w-]{22})", path)
    if m:
        return "channel", m.group(1)
    m = re.match(r"^/(@[\w.-]+)", path)
    if m:
        return "channel", m.group(1).lower()
    return "other", None


class Engine:
    def __init__(self, ydl_cls=None, sleep=time.sleep):
        self._cls = ydl_cls
        self.sleep = sleep

    # -- plumbing
    def _y(self, opts):
        cls = self._cls
        if cls is None:
            import yt_dlp

            cls = yt_dlp.YoutubeDL
        return cls(opts)

    @staticmethod
    def _base(**extra):
        return dict({"quiet": True, "no_warnings": True, "noprogress": True, "socket_timeout": 30, "retries": 5}, **extra)

    def _flat(self, url, limit=None):
        opts = self._base(extract_flat="in_playlist", skip_download=True)
        if limit:
            opts["playlistend"] = limit
        with self._y(opts) as y:
            return y.extract_info(url, download=False)

    def video_info(self, video_id: str) -> dict:
        with self._y(self._base(noplaylist=True, skip_download=True)) as y:
            return y.extract_info(_watch(video_id), download=False)

    # -- adding a channel
    def resolve_channel(self, text: str) -> dict:
        t = (text or "").strip()
        if store.CHANNEL_ID.match(t):
            url = f"https://www.youtube.com/channel/{t}/videos"
        elif HANDLE.match(t):
            url = f"https://www.youtube.com/{t}/videos"
        elif re.fullmatch(r"[\w.-]{3,40}", t):
            url = f"https://www.youtube.com/@{t}/videos"
        else:
            kind, ident = _classify(t if t.lower().startswith("http") else "https://" + t)
            if kind in ("video", "playlist"):
                raise ValueError("That is a video link, not a channel. Paste your channel link or @name.")
            if kind == "channel":
                url = f"https://www.youtube.com/channel/{ident}/videos" if ident.startswith("UC") else f"https://www.youtube.com/{ident}/videos"
            else:
                raise ValueError("I could not read that as a channel. Paste your channel link or @name.")
        info = self._flat(url, limit=1)
        cid = info.get("channel_id") or ""
        if not store.CHANNEL_ID.match(cid):
            raise ValueError("I could not find a channel at that address.")
        return {"id": cid, "title": info.get("channel") or info.get("uploader") or "", "handle": info.get("uploader_id") or ""}

    # -- finding videos
    def plan(self, it, only_channel=None) -> dict:
        notes = list(it.notes)
        chans = [c for c in store.channels() if only_channel in (None, c["id"])]
        if not chans:
            return {"items": [], "notes": notes + ["No channel of yours is set up yet. Add your channel first."]}
        if it.urls:
            return self._plan_links(it, chans, notes)
        return self._plan_search(it, chans, notes)

    def _plan_search(self, it, chans, notes):
        lists = []
        for c in chans:
            try:
                lists.append(self._channel_items(c, it, notes))
            except Exception as e:
                notes.append(f"I could not read {c['title'] or c['id']}: {friendly(e)}")
        items = _merge(lists, it.count)
        if len(items) > intents.MAX_BATCH:
            items = items[: intents.MAX_BATCH]
        if not items and not any("could not read" in n for n in notes):
            notes.append("Nothing of yours matches " + (" ".join(f"“{k}”" for k in it.keywords) if it.keywords else "that") + ".")
        return {"items": items, "notes": notes}

    def _channel_items(self, c, it, notes):
        scan = MAX_SCAN if (it.keywords or it.order == "oldest" or it.count is None or it.kind == "long") else it.count
        if it.kind == "short":
            shorts = [e for e in (self._flat(f"https://www.youtube.com/channel/{c['id']}/shorts", scan).get("entries") or []) if _is_video(e)]
            items = [self._item(e, "short", c) for e in shorts]
        else:
            ups = [e for e in (self._flat(f"https://www.youtube.com/playlist?list=UU{c['id'][2:]}", scan).get("entries") or []) if _is_video(e)]
            short_ids = {e["id"] for e in (self._flat(f"https://www.youtube.com/channel/{c['id']}/shorts", scan).get("entries") or []) if _is_video(e)}
            items = [self._item(e, "short" if e["id"] in short_ids else "long", c) for e in ups]
            if it.kind == "long":
                items = [i for i in items if i["kind"] == "long"]
        if it.keywords:
            need = len(it.keywords)
            scored = [(intents.match_score(i["title"], it.keywords), i) for i in items]
            full = [i for s, i in scored if s == need]
            if full or need == 1:
                items = full
            else:
                items = [dict(i, partial=True) for s, i in scored if s >= 1]
                if items:
                    notes.append("No title has every word, so these match only some of them.")
        if it.order == "oldest":
            items.reverse()
        return items[: it.count] if it.count else items

    def _item(self, e, kind, c):
        return {"id": e["id"], "title": e.get("title") or e["id"], "url": _watch(e["id"], kind), "duration": e.get("duration"), "kind": kind,
                "channel_id": c["id"], "channel": c["title"], "saved": store.saved_path(e["id"]) is not None, "owned": True, "refused": "", "error": "", "partial": False}

    def _plan_links(self, it, chans, notes):
        mine = {c["id"] for c in chans}
        items = []
        for url in it.urls:
            kind, ident = _classify(url)
            if kind == "video":
                items.append(self._link_item(ident, url, mine))
            elif kind == "channel":
                c = next((c for c in chans if c["id"] == ident or c["handle"].lower() == ident), None)
                if c is None:
                    notes.append(f"That channel {NOT_MINE.replace(' so I will not download it', ', so I did not download from it')}")
                else:
                    sub = intents.Intent(count=it.count, order=it.order, kind=it.kind, keywords=it.keywords, urls=[], notes=[])
                    try:
                        items += self._channel_items(c, sub, notes)
                    except Exception as e:
                        notes.append(f"I could not read {c['title'] or c['id']}: {friendly(e)}")
            elif kind == "playlist":
                notes.append("Playlist links are not supported. Paste the video links, or say what you want in words.")
            else:
                notes.append("I could not read one of the links as a YouTube video.")
        seen, out = set(), []
        for i in items:
            if i["id"] not in seen:
                seen.add(i["id"])
                out.append(i)
        return {"items": out, "notes": notes}

    def _link_item(self, video_id, url, mine):
        kind = "short" if "/shorts/" in url else "long"
        base = {"id": video_id, "title": video_id, "url": _watch(video_id, kind), "duration": None, "kind": kind, "channel_id": "", "channel": "",
                "saved": store.saved_path(video_id) is not None, "owned": False, "refused": "", "error": "", "partial": False}
        try:
            info = self.video_info(video_id)
        except Exception as e:
            return dict(base, error=friendly(e))
        owned = info.get("channel_id") in mine
        return dict(base, title=info.get("title") or video_id, duration=info.get("duration"), channel_id=info.get("channel_id") or "", channel=info.get("channel") or "",
                    owned=owned, refused="" if owned else f"This video is on “{info.get('channel') or 'another channel'}”, which {NOT_MINE}")

    # -- saving a video
    def download(self, video_id, folder, on_progress, stop) -> Path:
        if not isinstance(video_id, str) or not store.VIDEO_ID.match(video_id):
            raise ValueError("that is not a video id")
        mine = store.channel_ids()
        if not mine:
            raise NotMine("No channel of yours is set up, so nothing can be downloaded.")
        info = self.video_info(video_id)  # fresh from YouTube: the channel is read now, not trusted from the list
        if info.get("channel_id") not in mine:
            raise NotMine(f"This video is on “{info.get('channel') or 'another channel'}”, which {NOT_MINE}")
        folder = Path(folder)

        # YouTube serves the picture and the sound as two downloads, each reporting 0 to 100: one overall figure, weighted by size when YouTube says the sizes, else in equal halves
        wanted = info.get("requested_formats") or [None]
        grand = sum((f or {}).get("filesize") or (f or {}).get("filesize_approx") or 0 for f in wanted)
        streams, finished, last = {}, set(), [0.0]

        def hook(d):
            if stop.is_set():
                raise Cancelled("stopped")
            status, name = d.get("status"), d.get("filename") or ""
            if status not in ("downloading", "finished"):
                return
            done = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if status == "finished":
                finished.add(name)
                total = done = total or done
            streams[name] = (done, total)
            if grand:
                pct = 100.0 * sum(v[0] for v in streams.values()) / max(grand, sum(v[1] for v in streams.values()))
            else:
                share = 1.0 if name in finished else (done / total if total else 0.0)
                pct = 100.0 * (len(finished - {name}) + share) / len(wanted)
            last[0] = max(last[0], min(pct, 99.0))  # never backwards, and never 100 until the file is saved
            joining = status == "finished" and len(finished) >= len(wanted)
            on_progress({"percent": last[0], "speed": None if status == "finished" else d.get("speed"), "eta": None if status == "finished" else d.get("eta"),
                         "bytes": sum(v[0] for v in streams.values()), "stage": "joining" if joining else "downloading"})

        opts = self._base(noplaylist=True, format=FORMAT, merge_output_format="mp4", outtmpl=OUTTMPL, paths={"home": str(folder)}, windowsfilenames=True, continuedl=True,
                          overwrites=False, retries=10, fragment_retries=10, concurrent_fragment_downloads=2, progress_hooks=[hook])
        node = shutil.which("node")
        if node:
            opts["js_runtimes"] = {"node": {"path": node}}
        with self._y(opts) as y:
            result = y.process_ie_result(info, download=True)
        files = (result or {}).get("requested_downloads") or []
        path = Path(files[0]["filepath"]) if files and files[0].get("filepath") else store.saved_path(video_id)
        if not path or not Path(path).is_file() or os.path.getsize(path) == 0:
            raise RuntimeError("YouTube finished but no video file was saved.")
        return Path(path)


def _is_video(e) -> bool:
    return isinstance(e, dict) and isinstance(e.get("id"), str) and bool(store.VIDEO_ID.match(e["id"]))


def _merge(lists, n):
    """One list from several channels: the first of each, then the second of each, and so on."""
    lists = [l for l in lists if l]
    if len(lists) <= 1:
        out = lists[0] if lists else []
        return out[:n] if n else out
    out, i = [], 0
    while any(i < len(l) for l in lists) and (n is None or len(out) < n):
        out += [l[i] for l in lists if i < len(l)]
        i += 1
    return out[:n] if n else out
