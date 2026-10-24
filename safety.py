"""Safety net: did a published video really go live and stay live, and are the secrets on this machine protected.

`check` asks YouTube about videos whose publish time has passed. A problem (still private, rejected, claimed, blocked in
countries, removed) pauses Autopilot and tells the owner, so one bad video never turns into ten.
"""
import datetime as dt
import fnmatch
import json
import os
import subprocess
from pathlib import Path

import agentlog
import autopilot
import config
import records

TS = "%Y-%m-%dT%H:%M:%SZ"
GRACE = dt.timedelta(minutes=15)      # YouTube needs a moment to flip a scheduled video to public
WATCH_FOR = dt.timedelta(days=3)      # claims and takedowns show up in the first days
RECHECK = dt.timedelta(hours=6)
SECRETS = [".env", "token*.json", "client_secret*.json", "settings.json", "llm.json"]
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"  # read-only: views, watch time, impressions and click rate of the owner's own channel
ALLOWED_SCOPES = {"https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly", ANALYTICS_SCOPE}
WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"  # lets the title test change a title; the owner's choice (titletest mode "apply"), never a user studio's
REASONS = {"copyright": "a copyright claim", "claim": "a content claim", "duplicate": "it was seen as a duplicate",
           "termsOfUse": "a terms of use problem", "inappropriate": "it was judged inappropriate", "length": "its length",
           "trademark": "a trademark claim", "uploaderAccountClosed": "the account is closed", "uploaderAccountSuspended": "the account is suspended"}


def _service():
    import trendwatch

    return trendwatch._service()


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def judge(video: dict | None, published: bool) -> list[str]:
    """Plain-English problems for one videos.list item (None when YouTube returned nothing for the id)."""
    if video is None:
        return ["the video was removed from YouTube or is not visible to us"]
    st, out = video.get("status", {}), []
    if st.get("uploadStatus") in ("rejected", "failed", "deleted"):
        why = st.get("rejectionReason") or st.get("failureReason") or ""
        out.append(f"YouTube {st['uploadStatus']} the upload" + (f" because of {REASONS.get(why, why)}" if why else ""))
    if published and st.get("privacyStatus") == "private":
        out.append("it is still private after its publish time (check YouTube Studio: a block, a Studio setting or an account limit; it may also be that uploads from this API project "
                   "stay private until the project is audited: sources disagree, see developers.google.com/youtube/v3/docs/videos)")
    blocked = (video.get("contentDetails", {}).get("regionRestriction") or {}).get("blocked")
    if blocked:
        out.append(f"it is blocked in {len(blocked)} countr{'y' if len(blocked) == 1 else 'ies'}, often because of a claim")
    return out


def _due(now: dt.datetime) -> list[tuple[Path, dict]]:
    due = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
            when = _parse(meta.get("publish_at") or meta.get("uploaded_at") or "")
        except ValueError:
            continue
        if not meta.get("video_id") or meta.get("hold") or when > now - GRACE or when < now - WATCH_FOR:  # a held upload is kept private (or gone) on purpose: it is not "published with a problem"
            continue
        try:
            if now - _parse(meta["health"]["checked_at"]) < RECHECK:
                continue
        except (KeyError, ValueError):
            pass
        due.append((m, meta))
    return due


def check(now: dt.datetime | None = None, yt=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    due = _due(now)
    if not due:
        return {"checked": 0, "problems": [], "paused": False}
    if yt is None:
        try:
            yt = _service()
        except Exception as e:
            if type(e).__name__ == "RefreshError" or "invalid_grant" in str(e):
                msg = ("The YouTube login expired", "Reconnect YouTube in the dashboard. If this repeats every 7 days, set the Google OAuth consent "
                       "screen to \"In production\" (Google Cloud Console, Audience, Publish app).")
            else:
                msg = ("Could not reach YouTube to check published videos", f"{type(e).__name__}: {e}")
            agentlog.event("error", msg[0], msg[1], notify=True, now=now)
            return {"checked": 0, "problems": [], "paused": False, "error": msg[0]}
    found = {}
    ids = [m[1]["video_id"] for m in due]
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="status,contentDetails", id=",".join(ids[k:k + 50])).execute().get("items", []):
            found[v["id"]] = v
    problems = []
    for path, meta in due:
        published = _parse(meta.get("publish_at") or meta["uploaded_at"]) <= now - GRACE
        issues = judge(found.get(meta["video_id"]), published)
        records.merge(path.parent, {"health": {"ok": not issues, "checked_at": now.strftime(TS), "problems": issues}})
        problems += [f"{path.parent.name}: {i}" for i in issues]
    paused = False
    if problems:
        cfg = autopilot.load_config()
        if cfg.get("enabled"):
            autopilot.save_config({**cfg, "enabled": False})
            paused = True
        agentlog.event("error", "Autopilot paused: a published video has a problem" if paused else "A published video has a problem",
                       "; ".join(problems[:3]) + (" Fix it in YouTube Studio, then turn Autopilot on again." if paused else ""), notify=True, now=now)
    return {"checked": len(due), "problems": problems, "paused": paused}


def _secret_files(root: Path) -> list[Path]:
    seen = []
    for pat in SECRETS:
        seen += [p for p in root.glob(pat) if p.is_file() and p not in seen]
    return seen


def fix_permissions(root: Path | None = None) -> list[str]:
    fixed = []
    for p in _secret_files(root or config.ROOT):
        if p.stat().st_mode & 0o077:
            os.chmod(p, 0o600)
            fixed.append(p.name)
    return fixed


def _c(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def local_audit(root: Path | None = None, use_git: bool = True) -> list[dict]:
    root = root or config.ROOT
    files = _secret_files(root)
    loose = [p.name for p in files if p.stat().st_mode & 0o077]
    out = [_c("file_modes", not loose, f"readable by other users: {', '.join(loose)}" if loose else f"{len(files)} secret files are private to you")]
    token = root / "token.json"
    data = {}
    if token.exists():
        try:
            data = json.loads(token.read_text())
        except ValueError:
            data = {}
    allowed = set(ALLOWED_SCOPES)
    try:
        if json.loads((root / "data" / "titletest.json").read_text()).get("mode") == "apply":
            allowed.add(WRITE_SCOPE)
    except (OSError, ValueError):
        pass
    extra = sorted(set(data.get("scopes") or []) - allowed)
    out.append(_c("token_scopes", not extra, f"the login has more power than needed: {', '.join(extra)}" if extra else "only upload and read access"))
    out.append(_c("refresh_token", not token.exists() or bool(data.get("refresh_token")),
                  "login can renew itself" if data.get("refresh_token") else ("no login saved yet" if not token.exists() else "no refresh token: reconnect YouTube")))
    if use_git and (root / ".git").exists():
        try:
            tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, timeout=20).stdout.split()
            leaked = [t for t in tracked if any(fnmatch.fnmatch(Path(t).name, p) for p in SECRETS) and not t.endswith(".example")]
            out.append(_c("git_tracked", not leaked, f"committed to git: {', '.join(leaked)}" if leaked else "no secret file is committed"))
            unignored = [p.name for p in files if subprocess.run(["git", "check-ignore", "-q", p.name], cwd=root, timeout=20).returncode != 0]
            out.append(_c("git_ignored", not unignored, f"not in .gitignore: {', '.join(unignored)}" if unignored else "every secret file is in .gitignore"))
        except (OSError, subprocess.SubprocessError):
            pass
    return out
