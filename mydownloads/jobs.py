"""The download queue: one video at a time, each step written to disk so a power cut loses nothing.

A video already in the folder is skipped. A video the engine says is not the owner's is refused. Three failures in a row stop the job (the internet is
probably down) and keep the rest for a Continue. Stop puts the current video back in the queue.
"""
import copy
import datetime as dt
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import engine as engines
from . import intent, store

MIN_FREE = 1 << 30  # refuse to start with less than 1 GB free
POLITE_SECONDS = 2.0  # a short rest between two downloads
FAIL_LIMIT = 3


class Busy(Exception):
    """A job is already running."""


def _free(path) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free


def _clean(title) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(title or "")).strip()[:200]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Runner:
    def __init__(self, eng, threaded=True, sleep=time.sleep, free_bytes=_free):
        self.engine, self.threaded, self.sleep, self.free_bytes = eng, threaded, sleep, free_bytes
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self.job = store.load_job()
        if self.job and self.job.get("state") == "running":  # the computer stopped while it was downloading
            for it in self.job.get("items", []):
                if it.get("status") == "downloading":
                    it.update(status="queued", percent=0, speed=None, eta=None)
            self.job.update(state="interrupted", message="The last download was interrupted. Press Continue to finish the rest.")
            store.save_job(self.job)

    # -- what the page shows
    def snapshot(self):
        with self._lock:
            if not self.job:
                return None
            s = copy.deepcopy(self.job)
        s["resumable"] = s.get("state") in ("stopped", "interrupted") and any(i.get("status") == "queued" for i in s.get("items", []))
        return s

    # -- starting, stopping, continuing
    def start(self, items):
        if not isinstance(items, list) or not items:
            raise ValueError("Nothing was chosen to download.")
        if len(items) > intent.MAX_BATCH:
            raise ValueError(f"One job takes at most {intent.MAX_BATCH} videos.")
        seen, clean = set(), []
        for it in items:
            vid = it.get("id") if isinstance(it, dict) else None
            if not isinstance(vid, str) or not store.VIDEO_ID.match(vid):
                raise ValueError("One of the videos has an id I cannot read.")
            if vid not in seen:
                seen.add(vid)
                clean.append({"id": vid, "title": _clean(it.get("title")) or vid, "kind": "short" if it.get("kind") == "short" else "long", "status": "queued", "percent": 0,
                              "speed": None, "eta": None, "file": "", "bytes": 0, "error": "", "stage": ""})
        folder = store.folder()
        if self.free_bytes(folder) < MIN_FREE:
            raise ValueError("There is less than 1 GB of disk space free, so I did not start. Free some space first.")
        with self._lock:
            if self.job and self.job.get("state") == "running":
                raise Busy("A download is already running.")
            self.job = {"id": "j" + uuid.uuid4().hex[:10], "state": "running", "started": _now(), "folder": str(folder), "message": "", "items": clean}
            store.save_job(self.job)
            self._stop.clear()
        self._launch()
        return self.snapshot()

    def resume(self):
        with self._lock:
            if not self.job or self.job.get("state") not in ("stopped", "interrupted") or not any(i["status"] == "queued" for i in self.job["items"]):
                raise ValueError("There is nothing to continue.")
            self.job.update(state="running", message="")
            store.save_job(self.job)
            self._stop.clear()
        self._launch()
        return self.snapshot()

    def stop(self):
        self._stop.set()

    def _launch(self):
        if self.threaded:
            threading.Thread(target=self._thread_main, daemon=True, name="mydownloads-job").start()

    def _thread_main(self):
        try:
            self.run()
        except Exception as e:  # never leave a job shown as running forever
            with self._lock:
                self.job.update(state="stopped", message=f"The job stopped because of an error: {engines.friendly(e)}")
                store.save_job(self.job)

    # -- the work
    def _set(self, it, save=True, **fields):
        with self._lock:
            it.update(fields)
            if save:
                store.save_job(self.job)

    def _progress(self, it, p):
        self._set(it, save=False, percent=round(float(p.get("percent") or 0), 1), speed=p.get("speed"), eta=p.get("eta"), bytes=p.get("bytes") or 0, stage=p.get("stage") or "")

    def _log(self, it):
        store.audit({"id": it["id"], "title": it["title"], "status": it["status"], "file": it.get("file", ""), "error": it.get("error", "")})

    def run(self):
        folder, fails, halted, pause = Path(self.job["folder"]), 0, False, False
        for it in self.job["items"]:
            if it["status"] != "queued":
                continue
            if self._stop.is_set():
                break
            if pause:
                self.sleep(POLITE_SECONDS)
            pause = False
            self._set(it, status="downloading", percent=0, error="", stage="starting")
            have = store.saved_path(it["id"])
            if have:
                self._set(it, status="skipped", percent=100, file=str(have), stage="")
                self._log(it)
                continue
            try:
                path = self.engine.download(it["id"], folder, lambda p, it=it: self._progress(it, p), self._stop)
                self._set(it, status="done", percent=100, file=str(path), bytes=Path(path).stat().st_size, speed=None, eta=None, stage="")
                fails, pause = 0, True
            except engines.Cancelled:
                self._set(it, status="queued", percent=0, speed=None, eta=None, stage="")
                break
            except engines.NotMine as e:
                self._set(it, status="refused", error=str(e), stage="")
            except Exception as e:
                self._set(it, status="failed", error=engines.friendly(e), stage="")
                fails += 1
                pause = True
                if fails >= FAIL_LIMIT:
                    halted = True
            self._log(it)
            if halted:
                break
        with self._lock:
            left = any(i["status"] == "queued" for i in self.job["items"])
            if left:
                msg = "Three videos in a row failed, so I stopped. Read the message on each, then press Continue." if halted else "Stopped. Press Continue to finish the rest."
                self.job.update(state="stopped", message=msg)
            else:
                n = {k: sum(1 for i in self.job["items"] if i["status"] == k) for k in ("done", "skipped", "refused", "failed")}
                self.job.update(state="done", message=", ".join(f"{v} {k}" for k, v in n.items() if v) or "Nothing to do.")
            store.save_job(self.job)
