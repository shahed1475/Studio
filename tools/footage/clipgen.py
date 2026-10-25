"""One paid AI clip through OpenRouter's video API, with every I/O step checked and an asset-ledger row written next to the clip.
Runs inside a studio worker container (`python3 - < clipgen.py`) so the studio's own saved key is used; the key is never printed."""
import hashlib
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

CONFIG = Path("config/footage.json")
REQUIRED = ("base_url", "model", "duration_s", "resolution", "aspect_ratio", "generate_audio", "min_balance", "max_duration_s",
            "max_clip_bytes", "price_per_second_usd", "max_clip_cost_usd", "cost_scope", "poll_seconds", "max_polls", "http_timeout_s", "download_timeout_s")
FAILED_STATUSES = ("failed", "cancelled", "expired")
JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


class ClipError(Exception):
    pass


class JobNotCharged(ClipError):
    """The provider ended the job without delivering (failed, cancelled, expired): the studio books no cost for it."""


def load_config(path=CONFIG) -> dict:
    try:
        cfg = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ClipError(f"cannot read {path}: {e}")
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ClipError(f"{path} lacks: {', '.join(missing)}")
    if cfg["duration_s"] > cfg["max_duration_s"]:
        raise ClipError(f"duration {cfg['duration_s']} s is over the cap of {cfg['max_duration_s']} s")
    if estimated_cost(cfg) > cfg["max_clip_cost_usd"]:
        raise ClipError(f"estimated cost ${estimated_cost(cfg):.2f} is over the per-clip cap of ${cfg['max_clip_cost_usd']:.2f}")
    return cfg


def estimated_cost(cfg: dict) -> float:
    """List price per second times the length: this is what the studio books and checks against its daily cap."""
    return round(cfg["price_per_second_usd"] * cfg["duration_s"], 4)


def check_daily_cap(cfg: dict) -> None:
    """Same money guard as every other paid call: today's spend plus this clip must stay inside the daily budget."""
    import llm

    cap, spent, est = llm.load_config()["daily_budget_usd"], llm.spent_today(), estimated_cost(cfg)
    if spent + est > cap:
        raise ClipError(f"daily cap: ${spent:.2f} spent today + ${est:.2f} for this clip is over the ${cap:.2f} cap; nothing was bought")


def book_cost(cfg: dict) -> float:
    """Record the clip's cost in the day's total (the daily guard) and under cost_scope in data/video_costs.json."""
    import llm

    usd = estimated_cost(cfg)
    with llm.cost_scope(cfg["cost_scope"]):
        llm.record(llm._now(), "footage", cfg["model"], 0, 0, usd)
    return usd


def balance(cfg: dict, headers: dict, http=requests) -> float:
    try:
        r = http.get(f"{cfg['base_url']}/credits", headers=headers, timeout=cfg["http_timeout_s"])
    except requests.RequestException as e:
        raise ClipError(f"balance check failed: {e}")
    if r.status_code >= 300:
        raise ClipError(f"balance check failed: HTTP {r.status_code} {_snip(r.text)}")
    try:
        d = r.json()["data"]
        return round(d["total_credits"] - d["total_usage"], 4)
    except (ValueError, KeyError, TypeError):
        raise ClipError(f"balance reply not understood (HTTP {r.status_code}): {_snip(r.text)}")


def _get(http, url, headers, timeout):
    try:
        return http.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise ClipError(f"request failed: {e}")


def _snip(text, n=160) -> str:
    """Server text for an error message: printable characters only, short."""
    return "".join(ch if ch.isprintable() else " " for ch in str(text))[:n]


def _json(resp) -> dict:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def generate(cfg: dict, key: str, prompt: str, out_dir, http=requests, sleep=time.sleep, today: str | None = None) -> dict:
    import assetledger

    if not key:
        raise ClipError("no OpenRouter key in the studio")
    if not prompt:
        raise ClipError("empty prompt")
    auth, base = {"Authorization": f"Bearer {key}"}, cfg["base_url"]
    check_daily_cap(cfg)
    before = balance(cfg, auth, http)
    if before < cfg["min_balance"]:
        raise ClipError(f"balance {before} is under {cfg['min_balance']}, stopping")
    body = {"model": cfg["model"], "prompt": prompt, "duration": cfg["duration_s"], "resolution": cfg["resolution"],
            "aspect_ratio": cfg["aspect_ratio"], "generate_audio": cfg["generate_audio"]}
    try:
        reply = http.post(f"{base}/videos", headers=auth, json=body, timeout=cfg["http_timeout_s"])
    except requests.RequestException as e:
        raise ClipError(f"submit failed: {e}")
    if reply.status_code >= 300:
        raise ClipError(f"submit failed HTTP {reply.status_code}: {_snip(reply.text)}")
    job = _json(reply).get("id")
    if not isinstance(job, str) or not JOB_ID.fullmatch(job):
        raise ClipError(f"no usable job id in the reply: {_snip(reply.text)}")
    print(f"job: {job} (paid from here on)", flush=True)
    try:
        result = _finish(cfg, auth, http, sleep, job, before, prompt, Path(out_dir), today)
    except (ClipError, OSError, ValueError, AttributeError, TypeError) as e:
        booked = 0.0 if isinstance(e, JobNotCharged) else book_cost(cfg)  # a job that may have run is charged until the provider says otherwise
        raise ClipError(f"job {job}: {e}; booked ${booked:.2f}; balance now {_safe_balance(cfg, auth, http)}") from e
    result["booked_usd"] = book_cost(cfg)
    return result


def _finish(cfg, auth, http, sleep, job, before, prompt, out, today) -> dict:
    import assetledger

    base = cfg["base_url"]
    for i in range(1, cfg["max_polls"] + 1):
        poll = _get(http, f"{base}/videos/{job}", auth, cfg["http_timeout_s"])
        status = _json(poll).get("status") if poll.status_code < 300 else None
        status = status or f"http-{poll.status_code}"
        print(f"poll {i}: {status}", flush=True)
        if status == "completed":
            break
        if status in FAILED_STATUSES:
            raise JobNotCharged(f"ended: {status}")
        sleep(cfg["poll_seconds"])
    else:
        raise ClipError(f"not done after {cfg['max_polls']} polls; it may still finish and be charged")
    got = _get(http, f"{base}/videos/{job}/content", auth, cfg["download_timeout_s"])
    if got.status_code >= 300:
        raise ClipError(f"download failed HTTP {got.status_code} (it was charged)")
    if got.content[4:8] != b"ftyp":
        raise ClipError(f"downloaded file is not an MP4: {got.content[:80]!r}")
    if len(got.content) > cfg["max_clip_bytes"]:
        raise ClipError(f"clip is {len(got.content)} bytes, over the cap of {cfg['max_clip_bytes']}")
    out.mkdir(parents=True, exist_ok=True)
    dest, part = (out / f"{job}.mp4").resolve(), (out / f"{job}.mp4.part").resolve()
    try:
        part.write_bytes(got.content)
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)
    row = assetledger.row(dest, f"{base}/videos/{job}", "ai-generated", today or date.today().isoformat(), author=cfg["model"])
    row.update({"ai_label": True, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "job": job})
    bad = assetledger.problems([row], [dest.name], {dest.name: row["sha256"]})
    if bad:
        raise ClipError(f"the ledger row is not accepted ({'; '.join(bad)}); the paid clip is kept at {dest}")
    ledger = dest.with_suffix(".ledger.json")
    try:
        ledger.write_text(json.dumps(row, indent=1))
    except OSError as e:
        raise ClipError(f"cannot save the ledger row ({e}); the paid clip is kept at {dest} and must not be used without one")
    after = _safe_balance(cfg, auth, http)
    return {"clip": str(dest), "ledger": str(ledger), "job": job, "bytes": len(got.content), "cost": round(before - after, 4) if isinstance(after, float) else None, "balance_after": after}


def _safe_balance(cfg, auth, http):
    """The balance as a float, or a string saying why it is unknown (an error message must still be written)."""
    try:
        return balance(cfg, auth, http)
    except ClipError as e:
        return f"unknown ({e})"


def main(argv=None) -> int:
    try:
        import llm

        cfg = load_config(os.environ.get("FOOTAGE_CONFIG", CONFIG))
        out_dir = os.environ.get("FOOTAGE_OUT_DIR", "cache/footage")
        res = generate(cfg, llm.api_key(), (argv or sys.argv[1:] or [cfg.get("test_prompt", "")])[0], out_dir)
    except ClipError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    print("RESULT " + json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
