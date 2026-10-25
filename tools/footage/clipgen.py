"""One paid AI clip through a video API, with every I/O step checked, the cost booked before the job is sent, and an asset-ledger row next to the clip.
Runs inside a studio worker container (`python3 - < clipgen.py`) so the studio's own saved key is used; the key is never printed or logged.
Everything it makes goes into one run folder (footagestore.py) that the dashboard's "Footage clips" page reads."""
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

import assetledger  # imported up front: a missing module must show before anything is bought, not after the job is sent
import filelock

CONFIG = Path("config/footage.json")
ROLE = "footage"
LICENCE = "ai-generated"
JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
NUMBERS = ("duration_s", "max_duration_s", "max_clip_bytes", "price_per_second_usd", "max_clip_cost_usd", "poll_seconds", "max_polls", "http_timeout_s",
           "download_timeout_s", "tool_timeout_s", "cost_warn_factor", "duration_tolerance_s", "aspect_tolerance")
NUMBERS_ZERO_OK = ("min_balance", "retries", "backoff_s")
TEXTS = ("base_url", "model", "resolution", "aspect_ratio", "cost_scope", "price_source")
LISTS = ("success_statuses", "failed_statuses", "allowed_containers")


class ClipError(Exception):
    pass


class Refused(ClipError):
    """The studio's own rules said no before anything was bought (daily cap, low balance, per-clip cap)."""


class JobNotCharged(ClipError):
    """The provider ended the job without delivering: the studio releases the cost it had reserved."""


def _snip(text, n=160) -> str:
    """Server text for a message or log line: printable characters only (no newline can forge a line), short."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:n]


def _say(text: str) -> None:
    """Progress line for the caller. A dropped ssh connection must not end the wait for a job that is already paid for."""
    try:
        print(text, flush=True)
    except OSError:
        pass


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- config ----
def load_config(path=CONFIG) -> dict:
    try:
        cfg = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ClipError(f"cannot read {path}: {e}")
    if not isinstance(cfg, dict):
        raise ClipError(f"{path} is not a settings object")
    missing = [k for k in NUMBERS + NUMBERS_ZERO_OK + TEXTS + LISTS + ("generate_audio",) if k not in cfg]
    if missing:
        raise ClipError(f"{path} lacks: {', '.join(missing)}")
    for k in NUMBERS + NUMBERS_ZERO_OK:
        v = cfg[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or (k in NUMBERS and v == 0):
            raise ClipError(f"{path}: {k} must be a positive number" + (" (or 0)" if k in NUMBERS_ZERO_OK else ""))
    for k in TEXTS:
        if not isinstance(cfg[k], str) or not cfg[k].strip():
            raise ClipError(f"{path}: {k} must be a non-empty text")
    for k in LISTS:
        if not isinstance(cfg[k], list) or not all(isinstance(x, str) and x for x in cfg[k]):
            raise ClipError(f"{path}: {k} must be a list of texts")
    if not isinstance(cfg["generate_audio"], bool):
        raise ClipError(f"{path}: generate_audio must be true or false")
    if cfg["price_source"] not in ("live", "config"):
        raise ClipError(f"{path}: price_source must be live or config")
    if urlparse(cfg["base_url"]).scheme != "https":
        raise ClipError(f"{path}: base_url must be https")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", cfg["cost_scope"]):
        raise ClipError(f"{path}: cost_scope must be a plain word")
    if cfg["duration_s"] > cfg["max_duration_s"]:
        raise ClipError(f"duration {cfg['duration_s']} s is over the cap of {cfg['max_duration_s']} s")
    if estimated_cost(cfg) > cfg["max_clip_cost_usd"]:
        raise ClipError(f"estimated cost ${estimated_cost(cfg):.2f} is over the per-clip cap of ${cfg['max_clip_cost_usd']:.2f}")
    return cfg


# ---- money: reserve before the job is sent, release if it was never charged ----
def estimated_cost(cfg: dict) -> float:
    """List price per second times the length: what the studio books and checks against its daily cap."""
    return round(cfg["price_per_second_usd"] * cfg["duration_s"], 4)


def live_price(cfg: dict, headers: dict, http=requests, sleep=time.sleep) -> float:
    """The provider's own price per second for this model, from its price list. Fails closed: no readable price, nothing is bought."""
    r = _get(cfg, http, f"{cfg['base_url']}/videos/models", headers, cfg["http_timeout_s"], sleep)
    if r.status_code >= 300:
        raise Refused(f"the price list is unavailable (HTTP {r.status_code}); nothing was bought")
    try:
        models = r.json()["data"]
        entry = next(m for m in models if isinstance(m, dict) and m.get("id") == cfg["model"])
        skus = entry["pricing_skus"]
    except (ValueError, KeyError, TypeError, StopIteration):
        raise Refused(f"{cfg['model']} has no readable price in the provider's list; nothing was bought")
    if not isinstance(skus, dict):
        raise Refused(f"{cfg['model']} has no readable price in the provider's list; nothing was bought")
    for key in (f"per-video-second-{cfg['resolution']}", "per-video-second"):  # a price for this resolution first, then the base price
        try:
            price = float(skus[key])
        except (KeyError, TypeError, ValueError):
            continue
        if price > 0 and price != float("inf"):
            return price
    raise Refused(f"{cfg['model']} has no usable price for {cfg['resolution']} in the provider's list; nothing was bought")


def _with_live_price(cfg: dict, headers: dict, http, sleep, run) -> dict:
    """The settings with the provider's live price in them (when price_source is live), checked against the per-clip cap."""
    if cfg["price_source"] != "live":
        return cfg
    price = live_price(cfg, headers, http, sleep)
    out = {**cfg, "price_per_second_usd": price}
    run.log(f"live price ${price:.4f} a second (the settings said ${cfg['price_per_second_usd']:.4f})")
    if estimated_cost(out) > out["max_clip_cost_usd"]:
        raise Refused(f"at the live price this clip costs ${estimated_cost(out):.2f}, over the per-clip cap of ${out['max_clip_cost_usd']:.2f}; nothing was bought")
    return out


def _studio_money():
    import llm

    try:
        return llm, llm.load_config()["daily_budget_usd"]
    except (OSError, ValueError, KeyError) as e:
        raise ClipError(f"cannot read the studio's spending settings: {e}")


def check_daily_cap(cfg: dict) -> None:
    """The early, cheap refusal: today's spend plus this clip must stay inside the daily budget."""
    llm, cap = _studio_money()
    try:
        spent, est = llm.spent_today(), estimated_cost(cfg)
    except (OSError, ValueError) as e:
        raise ClipError(f"cannot read today's spend: {e}")
    if spent + est > cap:
        raise Refused(f"daily cap: ${spent:.2f} spent today + ${est:.2f} for this clip is over the ${cap:.2f} cap; nothing was bought")


def _booked_at(run):
    """When the reservation was made (the run's creation time, UTC), so a give-back or a correction lands on the day that was charged, not on a later day."""
    try:
        return datetime.strptime(run.read().get("created_at") or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (OSError, ValueError, AttributeError):
        return None


def _book(cfg: dict, usd: float, at=None) -> None:
    """Add usd (negative to release) to the day total and to data/video_costs.json under cost_scope. `at` is the day to book on (default: now)."""
    llm, _ = _studio_money()
    try:
        with llm.cost_scope(cfg["cost_scope"]):
            llm.record(at or llm._now(), ROLE, cfg["model"], 0, 0, usd)
    except (OSError, ValueError) as e:
        raise ClipError(f"cannot record the cost ${usd:.2f}: {e}")


def _spent(cfg: dict) -> float:
    llm, _ = _studio_money()
    try:
        return llm.spent_today()
    except (OSError, ValueError) as e:
        raise ClipError(f"cannot read today's spend: {e}")


def _release(cfg: dict, run, usd: float | None = None) -> None:
    """Give a reservation back, exactly once. The amount is CLAIMED from the run record in one locked step (so a run and a resume cannot both give it back); `usd`
    is passed only when the record never got the amount. If the give-back fails after the day total was already changed, the claim is kept (restoring it would
    let a later resume give the same money back again)."""
    before = _spent(cfg)  # read first: if this fails, nothing has been claimed yet
    amount = run.take_cost() if usd is None else usd
    if amount <= 0:
        return
    try:
        _book(cfg, -amount, _booked_at(run))
    except ClipError:
        try:
            unchanged = abs(_spent(cfg) - before) < 1e-9
        except ClipError:
            unchanged = False  # cannot tell: leave the record at 0, never risk a second give-back
        if unchanged and usd is None:
            run.restore_cost(amount)
        raise


def reserve(cfg: dict, state: dict | None = None) -> float:
    """Book the estimate FIRST, then check the cap against the total that now includes it. Two runs at once cannot both slip under the cap: at least one
    sees the other's booking and gives its own back."""
    est = estimated_cost(cfg)
    _book(cfg, est)
    if state is not None:
        state["est"] = est  # set at once, so an interrupt right after the booking still knows about it
    llm, cap = _studio_money()
    if llm.spent_today() > cap:
        if state is not None:
            state["est"] = 0  # zeroed first: an interrupt during the give-back can then not give it back a second time
        try:
            _book(cfg, -est)
        except ClipError:
            if state is not None:
                state["est"] = est
            raise
        raise Refused(f"daily cap: this clip (${est:.2f}) would take today's spend over the ${cap:.2f} cap; nothing was bought")
    return est


# ---- network ----
def _get(cfg: dict, http, url: str, headers: dict, timeout: float, sleep, **kw):
    """GET with retries and doubling waits on connection errors, 429 and 5xx. Returns the last response, or raises ClipError when only errors came back."""
    last_err, resp = None, None
    for attempt in range(cfg["retries"] + 1):
        try:
            resp = http.get(url, headers=headers, timeout=timeout, **kw)
            last_err = None
            if resp.status_code != 429 and resp.status_code < 500:
                return resp
        except requests.RequestException as e:
            last_err, resp = e, None
        if attempt < cfg["retries"]:
            sleep(cfg["backoff_s"] * 2 ** attempt)
    if resp is None:
        raise ClipError(f"request failed after {cfg['retries'] + 1} tries: {_snip(last_err)}")
    return resp


def _usage_cost(poll: dict) -> float | None:
    """The provider's own charge for a finished job (`usage.cost`), or None when it is missing, zero or not a sane number."""
    try:
        cost = float(poll["usage"]["cost"])
    except (KeyError, TypeError, ValueError):
        return None
    return round(cost, 4) if 0 < cost < float("inf") else None  # 0 is not believed: a zero (BYOK, a field not yet filled) must not wipe the booking while the balance fell


def _json(resp) -> dict:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def balance(cfg: dict, headers: dict, http=requests, sleep=time.sleep) -> float:
    r = _get(cfg, http, f"{cfg['base_url']}/credits", headers, cfg["http_timeout_s"], sleep)
    if r.status_code >= 300:
        raise ClipError(f"balance check failed: HTTP {r.status_code} {_snip(r.text)}")
    try:
        d = r.json()["data"]
        left = round(d["total_credits"] - d["total_usage"], 4)
        if not math.isfinite(left):
            raise ValueError("balance is not a finite number")
        return left
    except (ValueError, KeyError, TypeError):
        raise ClipError(f"balance reply not understood (HTTP {r.status_code}): {_snip(r.text)}")


def _balance_or_note(cfg, headers, http, sleep):
    try:
        return balance(cfg, headers, http, sleep), ""
    except ClipError as e:
        return None, _snip(e)


# ---- files and checks ----
def _ffmpeg(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, timeout=timeout)


def _decode_check(path: Path, cfg: dict) -> None:
    """A full decode (CLAUDE.md D): a header and a size say nothing about whether the whole clip plays."""
    try:
        r = _ffmpeg(["-i", str(path), "-f", "null", "-"], cfg["tool_timeout_s"])
    except FileNotFoundError:
        raise ClipError("ffmpeg is missing, so the clip cannot be verified")
    except subprocess.TimeoutExpired:
        raise ClipError("the full decode of the clip timed out")
    if r.returncode != 0 or r.stderr.strip():
        raise ClipError(f"the clip does not decode cleanly: {_snip(r.stderr)}")


def _probe_check(path: Path, cfg: dict) -> dict:
    """Duration, size and shape against what was asked for (CLAUDE.md D). A mismatch is not a clip the studio may use."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=cfg["tool_timeout_s"])
        info = json.loads(r.stdout)
        w, h, dur = int(info["streams"][0]["width"]), int(info["streams"][0]["height"]), float(info["format"]["duration"])
    except FileNotFoundError:
        raise ClipError("ffprobe is missing, so the clip's size and length cannot be verified")
    except (subprocess.TimeoutExpired, ValueError, KeyError, IndexError, TypeError):
        raise ClipError("the clip's size and length could not be read")
    problems = []
    if abs(dur - cfg["duration_s"]) > cfg["duration_tolerance_s"]:
        problems.append(f"length {dur:.1f} s, asked for {cfg['duration_s']} s")
    m = re.fullmatch(r"(\d{3,4})p", cfg["resolution"])
    if m and h != int(m.group(1)):
        problems.append(f"height {h}, asked for {cfg['resolution']}")
    a = re.fullmatch(r"(\d+):(\d+)", cfg["aspect_ratio"])
    if a and abs(w / h - int(a.group(1)) / int(a.group(2))) > cfg["aspect_tolerance"] * int(a.group(1)) / int(a.group(2)):
        problems.append(f"shape {w}x{h}, asked for {cfg['aspect_ratio']}")
    if problems:
        raise ClipError("the clip is not what was asked for: " + "; ".join(problems))
    return {"width": w, "height": h, "duration_s": round(dur, 2)}


def _make_picture(path: Path, out: Path, vf: str, cfg: dict, extra=()) -> bool:
    """A contact sheet or a thumbnail. These are for the dashboard only, so a failure is reported by the caller and never stops the run."""
    try:
        r = _ffmpeg(["-i", str(path), "-vf", vf, "-frames:v", "1", *extra, str(out)], cfg["tool_timeout_s"])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0 and out.is_file() and out.stat().st_size > 0


def _read_body(got, cap: int) -> bytes:
    """The body, stopping as soon as it passes the size cap (a streamed reply is never held whole first)."""
    chunks = getattr(got, "iter_content", None)
    if chunks is None:
        return got.content
    buf = bytearray()
    for chunk in chunks(chunk_size=1 << 20):
        buf += chunk
        if len(buf) > cap:
            raise ClipError(f"clip is over the cap of {cap} bytes; download stopped")
    return bytes(buf)


def _download(cfg, http, base, job, auth, sleep) -> bytes:
    """The clip bytes. A body shorter than the server announced is a truncated download: it is fetched again, within the retry limit."""
    last, cap = "no attempt", cfg["max_clip_bytes"]
    for attempt in range(cfg["retries"] + 1):
        got = _get(cfg, http, f"{base}/videos/{job}/content", {**auth, "Accept-Encoding": "identity"}, cfg["download_timeout_s"], sleep, stream=True)
        try:
            if got.status_code >= 300:
                raise ClipError(f"download failed HTTP {got.status_code} (the job was charged)")
            declared = getattr(got, "headers", {}).get("Content-Length")
            declared = int(declared) if declared and declared.isdigit() else None
            if declared is not None and declared > cap:
                raise ClipError(f"clip is announced as {declared} bytes, over the cap of {cap}")
            body = _read_body(got, cap)
        except requests.RequestException as e:
            last = f"download interrupted: {_snip(e)}"
            body = None
        finally:
            if hasattr(got, "close"):
                got.close()
        if body is not None and (declared is None or declared == len(body)):
            return body
        if body is not None:
            last = f"truncated download: {len(body)} of {declared} bytes"
        if attempt < cfg["retries"]:
            sleep(cfg["backoff_s"] * 2 ** attempt)
    raise ClipError(last)


# ---- one run ----
def _await_and_save(cfg, auth, http, sleep, job, prompt_sha256, run, today) -> dict:
    """Wait for the job, download the clip, verify it, write the ledger row and the pictures. Everything lands in run.dir."""
    base = cfg["base_url"]
    last, provider_cost = "", None
    for i in range(1, cfg["max_polls"] + 1):
        poll = _get(cfg, http, f"{base}/videos/{job}", auth, cfg["http_timeout_s"], sleep)
        status = _json(poll).get("status") if poll.status_code < 300 else None
        last = _snip(status) if status else f"http-{poll.status_code}"
        _say(f"poll {i}: {last}")
        if last in cfg["success_statuses"]:
            provider_cost = _usage_cost(_json(poll))
            break
        if last in cfg["failed_statuses"]:
            raise JobNotCharged(f"ended: {last}")
        sleep(cfg["poll_seconds"])
    else:
        raise ClipError(f"not done after {cfg['max_polls']} polls (last status: {last}); it may still finish and be charged; resume it with --resume")
    content = _download(cfg, http, base, job, auth, sleep)
    if content[4:8] != b"ftyp":
        raise ClipError(f"downloaded file is not an MP4: {content[:80]!r}")
    if len(content) > cfg["max_clip_bytes"]:
        raise ClipError(f"clip is {len(content)} bytes, over the cap of {cfg['max_clip_bytes']}")
    dest, part = (run.dir / f"{job}.mp4").resolve(), (run.dir / f"{job}.mp4.part").resolve()
    try:
        part.write_bytes(content)
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)
    run.update(files={"clip": dest.name})
    try:
        _decode_check(dest, cfg)
    except ClipError:
        dest.unlink(missing_ok=True)  # an unplayable file is not kept as if it were a clip
        run.update(files={"clip": None})
        raise
    try:
        run.update(probe=_probe_check(dest, cfg))
    except ClipError as e:
        raise ClipError(f"{e}; the paid clip is kept at {dest} but is not accepted")
    row = assetledger.row(dest, f"{base}/videos/{job}", LICENCE, today or date.today().isoformat(), author=cfg["model"])
    if row["sha256"] != hashlib.sha256(content).hexdigest():
        dest.unlink(missing_ok=True)
        raise ClipError("the saved clip does not match the downloaded bytes (disk error?)")
    row.update({"ai_label": True, "prompt_sha256": prompt_sha256, "job": job,
                "source_note": "the provider's job for this clip; opening it needs the studio's key"})
    bad = assetledger.problems([row], [dest.name], {dest.name: hashlib.sha256(dest.read_bytes()).hexdigest()})
    if bad:
        raise ClipError(f"the ledger row is not accepted ({'; '.join(bad)}); the paid clip is kept at {dest}")
    ledger = dest.with_suffix(".ledger.json")
    try:
        filelock.write_atomic(ledger, json.dumps(row, indent=2))
    except OSError as e:
        ledger.with_name(ledger.name + ".tmp").unlink(missing_ok=True)
        raise ClipError(f"cannot save the ledger row ({e}); the paid clip is kept at {dest} and must not be used without one")
    run.update(files={"ledger": ledger.name})
    for kind, name, vf, extra in (("contact", f"{job}.contact.jpg", "fps=1/2,scale=320:-1,tile=4x2", ()), ("thumb", f"{job}.thumb.jpg", "scale=480:-1", ("-ss", "0.5"))):
        if _make_picture(dest, run.dir / name, vf, cfg, extra):
            run.update(files={kind: name})
        else:
            run.log(f"{kind} picture could not be made (the clip itself is fine)")
    return {"clip": str(dest), "ledger": str(ledger), "job": job, "bytes": len(content), "provider_cost": provider_cost}


def generate(cfg: dict, key: str, prompt: str, run, http=requests, sleep=time.sleep, today: str | None = None) -> dict:
    """One clip. Records its progress in `run` (a footagestore.Run). Raises ClipError; the run record then says why."""
    run.update(status="running", model=cfg["model"], prompt_preview=_snip(prompt, 200), prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), files={"log": "run.log"}, pid=os.getpid(), pid_start=_proc_start(os.getpid()))
    _say(f"run: {run.dir.parent.name} {run.dir.name}")
    run.log(f"start: model {cfg['model']}, {cfg['duration_s']} s, {cfg['resolution']}")
    state: dict = {}  # what had happened when an interrupt arrives: {"est": reserved cost, "posted": the submit was started}
    try:
        result = _generate(cfg, key, prompt, run, http, sleep, today, state)
    except KeyboardInterrupt:
        try:
            msg = _interrupted(cfg, run, state)
        except BaseException:  # a second interrupt, or any failure, while giving the cost back: the record must still say failed
            msg = "interrupted while giving back the reserved cost; the cost may stay booked (check the day total)"
        run.update(status="failed", error=msg, finished_at=_utc())
        run.log(msg)
        raise
    except Refused as e:
        run.update(status="failed", error=str(e), decision="blocked", reason=str(e), finished_at=_utc())
        run.log(f"asset: decision=blocked reason={e}")
        raise
    except ClipError as e:
        run.update(status="failed", error=str(e), finished_at=_utc())
        run.log(f"FAILED: {e}")
        raise
    except Exception as e:  # nothing may leave a record at "running"; the job id (if any) is already on disk for --resume
        msg = f"unexpected {type(e).__name__}: {_snip(e)}" + ("; the paid job can be resumed" if run.read().get("job") else "")
        run.update(status="failed", error=msg, finished_at=_utc())
        run.log(f"FAILED: {msg}")
        raise ClipError(msg) from e
    reason = f"ledger accepted: {LICENCE}, author {cfg['model']}"
    run.update(status="done", decision="used", reason=reason, finished_at=_utc())
    run.log(f"asset {Path(result['clip']).name}: source=provider job {result['job']} licence={LICENCE} decision=used reason={reason}")
    return result


def _interrupted(cfg: dict, run, state: dict) -> str:
    """What to say, and what to do with the money, for an interrupt at this moment."""
    if run.read().get("job"):
        return "interrupted after the job was sent; the cost stays booked; fetch it with --resume"
    if state.get("posted"):
        return "interrupted while the job was being sent; a job may exist, so the cost stays booked"
    if state.get("est"):
        try:
            _release(cfg, run, None if state.get("recorded") else state["est"])
        except ClipError as e:
            return f"interrupted before a job was sent, but giving back the reserved cost failed ({e})"
        return "interrupted before a job was sent; the reserved cost was released"
    return "interrupted before anything was reserved"


def _generate(cfg, key, prompt, run, http, sleep, today, state) -> dict:
    if not key:
        raise Refused("no OpenRouter key in the studio")
    if not prompt or not prompt.strip():
        raise Refused("empty prompt")
    auth, base = {"Authorization": f"Bearer {key}"}, cfg["base_url"]
    check_daily_cap(cfg)
    before = balance(cfg, auth, http, sleep)
    if before < cfg["min_balance"]:
        raise Refused(f"balance {before} is under {cfg['min_balance']}, stopping")
    cfg = _with_live_price(cfg, auth, http, sleep, run)
    check_daily_cap(cfg)  # again, now with the price the provider will charge
    run.update(balance_before=before)
    est = reserve(cfg, state)  # booked before the job is sent: a crash, a timeout or a kill can no longer lose it
    run.update(cost_booked=est)
    state["recorded"] = True
    run.log(f"reserved ${est:.2f} (balance {before})")
    body = {"model": cfg["model"], "prompt": prompt, "duration": cfg["duration_s"], "resolution": cfg["resolution"],
            "aspect_ratio": cfg["aspect_ratio"], "generate_audio": cfg["generate_audio"]}
    state["posted"] = True
    try:
        reply = http.post(f"{base}/videos", headers=auth, json=body, timeout=cfg["http_timeout_s"])  # never retried: a second POST could buy a second clip
    except requests.RequestException as e:
        raise ClipError(f"the submit got no answer ({_snip(e)}); a job may exist, so ${est:.2f} stays booked")
    if 400 <= reply.status_code < 500 and reply.status_code != 408:
        _release(cfg, run)
        state["est"] = 0
        state["posted"] = False  # refused: no job exists
        raise ClipError(f"submit refused HTTP {reply.status_code}: {_snip(reply.text)}; the reserved cost was released")
    if reply.status_code >= 300:
        raise ClipError(f"submit failed HTTP {reply.status_code} ({_snip(reply.text)}); a job may exist, so ${est:.2f} stays booked")
    job = _json(reply).get("id")
    if not isinstance(job, str) or not JOB_ID.fullmatch(job):
        raise ClipError(f"no usable job id in the reply ({_snip(reply.text)}); a job may exist, so ${est:.2f} stays booked")
    run.update(job=job)  # the id is on disk before anything else can fail
    run.log(f"job {job} sent (paid from here on)")
    _say(f"job: {job} (paid from here on)")
    try:
        result = _await_and_save(cfg, auth, http, sleep, job, hashlib.sha256(prompt.encode()).hexdigest(), run, today)
    except JobNotCharged as e:
        after, note = _balance_or_note(cfg, auth, http, sleep)
        if after is None or after < before - 0.0001:  # the provider does not say whether a failed job is billed: believe the balance, not the status
            raise ClipError(f"job {job}: {e}; the balance {'fell to ' + str(after) if after is not None else 'could not be read'} (was {before}), so ${est:.2f} stays booked") from e
        _release(cfg, run)
        raise ClipError(f"job {job}: {e}; the balance did not move, so the reserved cost was released") from e
    except (ClipError, OSError, ValueError, AttributeError, TypeError) as e:
        after, note = _balance_or_note(cfg, auth, http, sleep)
        raise ClipError(f"job {job}: {e}; ${est:.2f} stays booked; balance now {after if after is not None else 'unknown (' + note + ')'}") from e
    after, note = _balance_or_note(cfg, auth, http, sleep)
    measured = round(before - after, 4) if after is not None else None
    run.update(balance_before=before, balance_after=after, balance_cost=measured)
    booked = est
    if result.get("provider_cost") is not None:
        booked = _settle(cfg, run, est, result["provider_cost"])
    elif measured is not None and measured > est * cfg["cost_warn_factor"]:
        extra = round(min(measured, cfg["max_clip_cost_usd"]) - est, 4)
        try:
            _book(cfg, extra)  # no provider figure: the real fall in the balance counts against the cap, even if other spending is in it
            booked = round(est + extra, 4)
            run.update(cost_booked=booked)
            run.log(f"the balance fell by ${measured:.2f}, more than the ${est:.2f} booked: booked ${extra:.2f} more (other spending, or the price in the settings is too low)")
        except ClipError as e:
            run.log(f"the balance fell by ${measured:.2f} but ${est:.2f} was booked, and booking the difference failed: {e}")
    return {**result, "run_id": run.dir.name, "booked_usd": booked, "measured_cost": measured, "balance_after": after, "balance_note": note}


def _settle(cfg: dict, run, booked: float, provider_cost: float | None) -> float:
    """Make the booking equal to what the provider says it charged (`usage.cost`), up to the per-clip cap; returns the amount now booked."""
    if provider_cost is None:
        return booked
    target = round(min(provider_cost, cfg["max_clip_cost_usd"]), 4)
    delta = round(target - booked, 4)
    if abs(delta) < 0.0001:
        run.update(provider_cost=provider_cost)
        return booked
    try:
        _book(cfg, delta, _booked_at(run))
    except ClipError as e:
        run.log(f"the provider says ${provider_cost:.4f} but ${booked:.4f} is booked, and booking the difference failed: {e}")
        return booked
    run.update(cost_booked=target, provider_cost=provider_cost)
    run.log(f"the provider's own charge is ${provider_cost:.4f}: the booking is now ${target:.4f} (was ${booked:.4f})")
    return target


def resume(cfg: dict, key: str, run, http=requests, sleep=time.sleep, force: bool = False) -> dict:
    """Fetch the clip of a job that was already sent and booked (a lost connection, a kill). Books nothing new. `force` skips the "still going" check (for a
    process id that a restarted container has given to something else)."""
    job = run.read().get("job")
    if not isinstance(job, str) or not JOB_ID.fullmatch(job):
        raise ClipError("this run has no job to resume")
    rec = run.read()
    if rec.get("status") == "done":
        raise ClipError("this run already finished; nothing to resume")  # a done run must never be failed or refunded by a later resume
    if rec.get("status") == "running" and not force and _alive(rec.get("pid"), rec.get("pid_start")):
        raise ClipError(f"this run is still going (process {rec.get('pid')}); wait for it, check the run on the dashboard, or use --resume --force if the process is not ours")
    if not key:
        raise Refused("no OpenRouter key in the studio")
    run.update(status="running", error=None, pid=os.getpid(), pid_start=_proc_start(os.getpid()))
    run.log(f"resuming job {job}")
    try:
        result = _await_and_save(cfg, {"Authorization": f"Bearer {key}"}, http, sleep, job, run.read().get("prompt_sha256", ""), run, None)
    except KeyboardInterrupt:
        run.update(status="failed", error="interrupted while resuming; the cost stays booked; fetch it with --resume", finished_at=_utc())
        raise
    except Exception as e:
        msg = str(e) if isinstance(e, ClipError) else f"unexpected {type(e).__name__}: {_snip(e)}"
        if isinstance(e, JobNotCharged):  # the provider ended the job without a clip: give back what was reserved, but only if the balance did not move
            before = rec.get("balance_before")
            after, _note = _balance_or_note(cfg, {"Authorization": f"Bearer {key}"}, http, sleep)
            if not isinstance(before, (int, float)) or after is None or after < before - 0.0001:
                msg += "; the balance fell or could not be compared, so the cost stays booked"
            else:
                try:
                    _release(cfg, run)
                    msg += "; the balance did not move, so the reserved cost was released"
                except ClipError as be:
                    msg += f"; giving back the reserved cost failed ({be})"
        run.update(status="failed", error=msg, finished_at=_utc())
        run.log(f"FAILED: {msg}")
        raise ClipError(msg) from e
    run.update(status="done", decision="used", reason=f"ledger accepted: {LICENCE}, author {cfg['model']}", finished_at=_utc())
    return {**result, "run_id": run.dir.name}


def _proc_start(pid: int) -> str | None:
    """When the process started (field 22 of /proc/<pid>/stat, in clock ticks since boot): with the pid it tells our process from a new one that got the same number."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _alive(pid, start=None) -> bool:
    """Is another process of this container still working on the run? (A pid that is not ours, answers signal 0, and, when we stored its start time, started
    at that time.)"""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    now = _proc_start(pid)
    return not (start and now and start != now)


def _stop(signum, frame):
    raise KeyboardInterrupt


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _stop)
    try:
        import footagestore
        import llm

        cfg = load_config(os.environ.get("FOOTAGE_CONFIG", CONFIG))
        if argv[:1] == ["--resume"]:
            force = "--force" in argv
            rest = [a for a in argv[1:] if a != "--force"]
            run = footagestore.open_run(*rest) if len(rest) == 2 else None
            if run is None:
                raise ClipError("usage: --resume [--force] <scope> <run_id>")
            res = resume(cfg, llm.api_key(), run, force=force)
        else:
            open_jobs = [r["run_id"] for r in footagestore.runs() if r.get("scope") == cfg["cost_scope"] and r.get("status") == "running" and r.get("job")]
            if open_jobs:
                raise Refused(f"run {open_jobs[0]} has a paid job whose outcome is not known; fetch it with --resume {cfg['cost_scope']} {open_jobs[0]} first")
            run = footagestore.create(cfg["cost_scope"], status="running", model=cfg["model"])
            res = generate(cfg, llm.api_key(), argv[0] if argv else cfg.get("test_prompt", ""), run)
        res["scope"] = cfg["cost_scope"]
        res["run_dir"] = str(run.dir)
        res["files"] = {k: str(run.dir / v) for k, v in run.read().get("files", {}).items() if v}
    except (ClipError, OSError, ValueError) as e:
        print(f"FAILED: {_snip(e, 400)}", file=sys.stderr)
        return 1
    print("RESULT " + json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
