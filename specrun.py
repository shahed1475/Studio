"""Builds videos from specs that Claude wrote (13 Nov 2026): the free pipeline, no model money.
A spec folder holds doc.json (a 16:9 documentary) or short.json (a 9:16 Short), pictures.json (picture prompts) and src/*.txt (the saved source pages the passages are quoted from).
Specs come from two places: the owner's GitHub repo (specs/inbox/<name>/ on `main`, read over https, public repo, nothing is written back) and the server's own
data/specs/inbox/<name>/ (the owner pastes a file there). Each new or changed spec is checked by the existing free builders (a passage must be in its saved page, a claim needs a passage),
its missing pictures are drawn on the owner's free Cloudflare account (the day's allowance is shared with freeart), and the held draft is built by ccdoc.build / ccbuild.build with EVERY model call
blocked (`no_model`): the voice is edge-tts, the thumbnails are Pillow. The result is a held, unapproved draft; the owner releases it (CLAUDE.md E). A spec is data, never instructions.
Usage: python run.py specrun [tick | status | check DIR]."""
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import config

REPO = "shahed1475/Studio"
ROOT = config.ROOT / "data" / "specs"
STATE = config.ROOT / "data" / "specrun.json"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")
FILE = re.compile(r"^(doc|short|pictures[a-z0-9_-]*)\.json$|^src/[A-Za-z0-9_.-]{1,80}\.txt$")
MAX_BYTES = 400_000
CREDIT = "AI-generated illustrations (FLUX.2 klein 4B, Apache-2.0, drawn on Cloudflare Workers AI); not photographs of the real place or of real people. Voice: synthetic."
SIZES = {"doc": (1024, 576), "short": (704, 1248)}  # FLUX.2 klein sizes: 4 tiles (104 Neurons) a film picture, 6 (156) a Short picture


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


@contextlib.contextmanager
def no_model():
    """Free mode: any call to a language or picture model raises. A spec build must cost nothing."""
    import llm

    def blocked(*a, **k):
        raise RuntimeError("a model call was blocked: a spec build is free")

    saved = (llm._post, llm.chat, llm.api_key)
    llm._post, llm.chat, llm.api_key = blocked, blocked, (lambda: "")
    try:
        yield
    finally:
        llm._post, llm.chat, llm.api_key = saved


# ---- GitHub (public repo, read only) ----
def _get(url: str) -> bytes:
    assert url.startswith(("https://api.github.com/", "https://raw.githubusercontent.com/")), url
    req = urllib.request.Request(url, headers={"User-Agent": "story-studio-specrun", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(MAX_BYTES + 1)


def fetch_github(get=None, repo: str = REPO) -> list[str]:
    """Copy every spec folder of `main` that is not copied yet into data/specs/gh/. Only the names and files the pattern allows; returns the folder names fetched."""
    get = get or _get
    api = f"https://api.github.com/repos/{repo}/contents/specs/inbox"
    got = []
    try:
        listing = json.loads(get(api + "?ref=main"))
    except Exception:  # no folder yet, offline or rate limited: nothing to do this time
        return got
    for d in listing if isinstance(listing, list) else []:
        name = d.get("name", "")
        if d.get("type") != "dir" or not NAME.match(name):
            continue
        files = []
        try:
            for e in json.loads(get(f"{api}/{name}?ref=main")):
                if e.get("type") == "file" and FILE.match(e["name"]):
                    files.append(e["name"])
                elif e.get("type") == "dir" and e.get("name") == "src":
                    files += ["src/" + x["name"] for x in json.loads(get(f"{api}/{name}/src?ref=main")) if x.get("type") == "file" and FILE.match("src/" + x["name"])]
            dest = ROOT / "gh" / name
            for f in files[:60]:
                data = get(f"https://raw.githubusercontent.com/{repo}/main/specs/inbox/{name}/{f}")
                if len(data) > MAX_BYTES:
                    continue
                (dest / f).parent.mkdir(parents=True, exist_ok=True)
                (dest / f).write_bytes(data)
            got.append(name)
        except Exception:
            continue
    return got


# ---- one spec ----
def spec_dirs() -> list[Path]:
    out = []
    for sub in ("inbox", "gh"):
        d = ROOT / sub
        out += [p for p in sorted(d.iterdir()) if p.is_dir() and NAME.match(p.name)] if d.exists() else []
    return out


def kind_of(base: Path) -> str | None:
    return "doc" if (base / "doc.json").exists() else "short" if (base / "short.json").exists() else None


def signature(base: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in base.rglob("*") if p.is_file() and p.name != "pictures_zz_norm.json"):  # the normalised copy is ours, not the author's
        h.update(f.relative_to(base).as_posix().encode() + f.read_bytes())
    return h.hexdigest()[:16]


def prepare(base: Path, kind: str) -> dict:
    """The spec with each source file resolved inside its own folder (a path that leaves the folder is dropped, so validation refuses it), and picture jobs without a provider
    drawn on Cloudflare at the size for this kind."""
    spec = json.loads((base / f"{kind}.json").read_text())
    root = base.resolve()
    for s in spec.get("sources") or []:
        f = (base / "src" / Path(str(s.get("file", ""))).name).resolve()
        s["file"] = str(f) if f.is_file() and root in f.parents else ""
    jobs = {}
    for f in sorted(base.glob("pictures*.json")):
        if f.name == "pictures_zz_norm.json":
            continue
        for j in json.loads(f.read_text()):
            if not j.get("provider"):
                jobs[j["id"]] = {**j, "provider": "cloudflare", "model": "klein", "width": SIZES[kind][0], "height": SIZES[kind][1]}
    if jobs:
        (base / "pictures_zz_norm.json").write_text(json.dumps(list(jobs.values())))
        spec["ai_credit"] = CREDIT  # the pictures are drawn here, whatever the spec's author wrote about how they were made
        if kind == "short":
            spec["credits"] = [CREDIT]
    return spec


def check(base: Path) -> tuple[str | None, dict | None, list[str], list[str]]:
    kind = kind_of(base)
    if not kind:
        return None, None, ["no doc.json or short.json"], []
    try:
        spec = prepare(base, kind)
    except (OSError, ValueError) as e:
        return kind, None, [f"the spec files cannot be read: {e}"], []
    if kind == "doc":
        import ccdoc

        errors, warns = ccdoc.validate(spec, base)
    else:
        import ccbuild

        errors, warns = ccbuild.validate(spec, base)
    return kind, spec, errors, warns


def draw_missing(base: Path, spec: dict, kind: str) -> dict:
    """Draw the pictures the spec names that are not on disk yet (Cloudflare only: the server has no GPU). {'missing': n, 'drawn': n, 'cap': bool, 'failed': n, 'undrawable': [ids]}"""
    import ccdoc
    import tools.cloudflare_batch as cb

    jobs = ccdoc.load_jobs(base)
    need, out = [], {"missing": 0, "drawn": 0, "cap": False, "failed": 0, "undrawable": []}
    for l in spec["lines"]:
        pid = l.get("picture")
        if pid in jobs and not ccdoc.resolve(pid, base, jobs).exists():
            if jobs[pid].get("provider") == "cloudflare":
                need.append(jobs[pid])
            else:
                out["undrawable"].append(pid)
    out["missing"] = len({j["id"] for j in need})
    for r in cb.run(list({j["id"]: j for j in need}.values())):
        out["drawn"] += r["status"] == "DONE"
        out["cap"] |= r["status"] == "CAP"
        out["failed"] += r["status"] == "FAIL"
    return out


def process(base: Path) -> dict:
    """{'status': built | rejected | waiting | failed, ...} for one spec folder."""
    kind, spec, errors, warns = check(base)
    if errors:
        return {"status": "rejected", "reasons": errors[:8], "warnings": warns[:5]}
    drawn = draw_missing(base, spec, kind)
    if drawn["undrawable"]:
        return {"status": "rejected", "reasons": [f"picture '{p}' is not drawn and cannot be drawn on the server: give it a prompt in pictures.json" for p in drawn["undrawable"][:5]]}
    if drawn["cap"] or drawn["failed"]:
        return {"status": "waiting", "reasons": [f"{drawn['drawn']} drawn, {drawn['failed']} failed, free allowance {'used up for today' if drawn['cap'] else 'ok'}: the rest is tried again next time"]}
    try:
        with no_model():
            if kind == "doc":
                import ccdoc

                folder = ccdoc.build(spec, base)
            else:
                import ccbuild

                folder = ccbuild.build(spec, base)
    except (Exception, SystemExit) as e:
        return {"status": "failed", "reasons": [f"{type(e).__name__}: {str(e)[:300]}"]}
    return {"status": "built", "folder": Path(folder).name, "warnings": warns[:5]}


def tick(get=None, github: bool = True) -> dict:
    """One pass: fetch new specs, build at most one, say what happened. Safe to run every few minutes."""
    import agentlog
    import risk

    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {"skipped": "another specrun is running"}
        if risk.running_jobs():
            return {"skipped": "a render is running"}
        fetched = fetch_github(get) if github else []
        st, result = load_state(), {"fetched": fetched, "built": [], "rejected": [], "waiting": [], "failed": []}
        for base in spec_dirs():
            sig = signature(base)
            old = st.get(base.name, {})
            if old.get("sig") == sig and old.get("status") in ("built", "rejected", "failed"):
                continue
            res = process(base)
            st[base.name] = {"sig": sig, "at": _now(), **res}
            result[res["status"]].append(base.name)
            if res["status"] == "built":
                agentlog.event("info", f"Spec built: {base.name}", f"A held draft is ready in {res['folder']}: watch it, then release it. Made for free, no model calls.")
                save_state(st)
                break  # one build a tick: the next waits for the next pass
            if res["status"] in ("rejected", "failed") and old.get("sig") != sig:
                agentlog.event("error", f"Spec {res['status']}: {base.name}", "; ".join(res.get("reasons", []))[:400])
        save_state(st)
        return result


def status() -> dict:
    st = load_state()
    return {"specs": {k: {x: v.get(x) for x in ("status", "at", "folder", "reasons")} for k, v in st.items()}, "inbox": [p.name for p in spec_dirs()]}
