"""User studios: the parts that only apply when this copy of the studio belongs to a user and not to the owner (STUDIO_MODE=tenant).

Safe first-run settings, a storage limit the app keeps itself (the server gives no disk quotas to this account), and a gate so that only a few
renders run at once across every studio on the server. Without STUDIO_MODE nothing here changes how the studio behaves. Plan:
docs/superpowers/plans/2026-10-21-user-side-5-tenants.md.
"""
import contextlib
import datetime as dt
import fcntl
import json
import os
import sys
import time
from pathlib import Path

import config

LIMIT_GB = 10.0  # per user: videos, archived videos, cache and data
WARN_AT, FULL_AT = 0.8, 1.0
COUNTED = ("output", "output_old", "cache", "data", "logs")


def is_tenant() -> bool:
    return os.getenv("STUDIO_MODE", "").strip().lower() == "tenant"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def apply_defaults(root: Path | None = None) -> bool:
    """First run of a user studio: Autopilot off, auto-approve off, paid models and AI drawing off until the user adds their own key, a $1.50 daily cap,
    the research agent only suggesting. Never touches a setting the user changed later (a marker file says it ran). True when it wrote them."""
    root = Path(root or config.ROOT)
    marker = root / "data" / "tenant_ready.json"
    if marker.exists():
        return False
    (root / "data").mkdir(exist_ok=True)
    if not (root / "autopilot.json").exists():
        _write_json(root / "autopilot.json", {"enabled": False, "auto_approve": False})
    if not (root / "llm.json").exists():
        _write_json(root / "llm.json", {"enabled": False, "daily_budget_usd": 1.5, "ai_art": False, "free": True, "local_fallback": False})
    if not (root / "agent.json").exists():
        _write_json(root / "agent.json", {"mode": "handoff"})
    marker.write_text(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}))
    return True


def usage_gb(root: Path | None = None) -> float:
    root = Path(root or config.ROOT)
    total = 0
    for name in COUNTED:
        for p in (root / name).rglob("*") if (root / name).exists() else []:
            try:
                if p.is_file() and not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                continue
    return total / 1e9


def quota_state(root: Path | None = None, limit_gb: float = LIMIT_GB) -> dict:
    used = usage_gb(root)
    pct = round(used / limit_gb * 100) if limit_gb else 100
    state = "full" if used >= limit_gb * FULL_AT else "warn" if used >= limit_gb * WARN_AT else "ok"
    return {"used_gb": round(used, 3), "limit_gb": limit_gb, "pct": pct, "state": state}


def enforce_quota(root: Path | None = None, now: dt.datetime | None = None, limit_gb: float = LIMIT_GB) -> dict:
    """Run hourly. At the limit no new video is started (existing ones are still reviewed and uploaded); one message says why. The pause is lifted by itself
    once the folder is under 90% again, and only a pause this function made is ever lifted."""
    import agentlog

    root = Path(root or config.ROOT)
    now = now or dt.datetime.now(dt.timezone.utc)
    q = quota_state(root, limit_gb)
    state_file = root / "data" / "tenant_state.json"
    try:
        st = json.loads(state_file.read_text())
    except (OSError, ValueError):
        st = {}
    ap_file = root / "autopilot.json"
    try:
        ap = json.loads(ap_file.read_text())
    except (OSError, ValueError):
        ap = {}
    if q["state"] == "full" and not st.get("paused_by_quota"):
        if ap.get("make_videos", True):
            ap["make_videos"] = False
            _write_json(ap_file, ap)
            st["paused_by_quota"] = True
        agentlog.event("error", "Storage is full: no new videos", f"Your studio uses {q['used_gb']:.1f} of {q['limit_gb']:.0f} GB. Delete videos you no longer need "
                       "(uploaded video files are removed after 7 days by themselves) and new videos start again.", notify=True, now=now)
    elif st.get("paused_by_quota") and q["pct"] < 90:
        ap["make_videos"] = True
        _write_json(ap_file, ap)
        st["paused_by_quota"] = False
        agentlog.event("applied", "Storage is back under the limit: new videos start again", f"{q['used_gb']:.1f} of {q['limit_gb']:.0f} GB used.", now=now)
    st["last"] = {**q, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    state_file.parent.mkdir(exist_ok=True)
    _write_json(state_file, st)
    return q


@contextlib.contextmanager
def render_gate(slots: int = 2, poll: float = 1.0):
    """Wait for one of `slots` locks in the folder STUDIO_RENDER_GATE (shared by every studio on the server) while a video renders. No folder set: no wait."""
    gate = os.getenv("STUDIO_RENDER_GATE", "").strip()
    if not gate:
        yield
        return
    Path(gate).mkdir(parents=True, exist_ok=True)
    held = None
    try:
        while held is None:
            for i in range(slots):
                f = open(Path(gate) / f"slot{i}.lock", "a")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    held = f
                    break
                except BlockingIOError:
                    f.close()
            else:
                time.sleep(poll)
        yield
    finally:
        if held is not None:
            held.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "defaults":
        print("written" if apply_defaults() else "already set")
    elif cmd == "quota":
        print(json.dumps(quota_state()))
    else:
        sys.exit("usage: python tenantmode.py defaults | quota")
