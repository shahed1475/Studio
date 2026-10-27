"""Training data for a small model, built from this studio's own finished videos and checked before anything is trained or pushed.

What it is for: a small model that could one day do the cheap, repeatable jobs (a script from a source text, the packaging of a script) so the paid models are
needed less. What it is not: a model that "knows how the system works" (playbooks and code do that better and cannot hallucinate it) and nothing a small model
may do alone: the fact-checker and reviewer stay strong models.
Rules written into the code:
- only passed, approved, not-held videos with a clean claim ledger, never someone else's video;
- provenance: an example whose writer was a Claude model is excluded (Anthropic's commercial terms forbid using its services to train competing models unless it
  approves), and so is one whose writer was not recorded; the owner can name models whose output may be used (`allow`);
- Wikipedia text is CC BY-SA 4.0 (attribution and share-alike): every example carries its source titles and licence, and the set stays private;
- a script example always carries its source text, so the model learns to write from sources, never from memory;
- no network, no model, no cost: it reads files and writes `data/trainset/<date>/`. Pushing to Hugging Face and training are separate, owner-approved steps."""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import config

ANTHROPIC = re.compile(r"anthropic|claude", re.I)
LICENSE = "Source text: Wikipedia, CC BY-SA 4.0 (attribution and share-alike). Keep the set private; any model trained on it carries that obligation."
MIN_TO_TRAIN = {"script": 300, "packaging": 300}  # examples per task before a LoRA run is worth its cost (practitioner guidance: a few hundred clean ones for style)
SECRETS = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key\s*[:=]\s*\S{8,})", re.I)
PII = re.compile(r"([\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d\s().-]{9,}\d)")
JUNK = re.compile(r"(https?://|www\.|\*\*|^#+\s|\[[^\]]+\]\([^)]+\))", re.M)
INSTRUCTIONS = ("Write the narration for a calm history and legend video, one sentence per line, from the source text only. Name what is known, what is legend and "
                "what is disputed. Invent nothing, quote nothing the source lacks.")
SOURCE_CAP = 12_000


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower())


def _words(text: str) -> list[str]:
    return _norm(text).split()


def provenance(meta: dict, allow: tuple = ()) -> tuple[bool, str]:
    model = str(meta.get("script_model") or "")
    if not model:
        return False, "the writer model was not recorded for this video"
    if model in allow:
        return True, ""
    if ANTHROPIC.search(model):
        return False, f"written by {model}: Anthropic's terms forbid training competing models on its outputs unless it approves"
    return True, ""


def claims_ok(folder: Path) -> tuple[bool, str]:
    try:
        rows = json.loads((folder / "claims.json").read_text())
    except (OSError, ValueError):
        return False, "no claim ledger"
    if not isinstance(rows, list) or not rows:
        return False, "empty claim ledger"
    status = [str(r.get("verification_status", "")).upper() for r in rows if isinstance(r, dict)]
    if "CONFLICTING" in status:
        return False, "a claim is marked conflicting"
    if status.count("UNVERIFIED") > 0.2 * len(status):
        return False, "more than a fifth of the claims are unverified"
    return True, ""


def source_cached(meta: dict) -> str:
    """The source article text from the disk cache only (never the network); empty when it is not there."""
    import reviewer

    out = []
    for title in reviewer.source_titles(meta):
        f = config.CACHE / "wiki" / (re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:60] + ".txt")
        if f.exists():
            out.append(f.read_text())
    return "\n\n".join(out)


def eligible(folder: Path, meta: dict, allow: tuple = ()) -> tuple[bool, str]:
    if not meta.get("approved") or meta.get("hold"):
        return False, "not approved, or on hold"
    if (meta.get("review") or {}).get("verdict") != "pass" or meta.get("facts_open"):
        return False, "the review did not pass, or a facts warning is open"
    if len(meta.get("lines") or []) < 9:
        return False, "no script"
    for ok, why in (provenance(meta, allow), claims_ok(folder)):
        if not ok:
            return False, why
    return True, ""


def examples(folder: Path, meta: dict, source=source_cached) -> list[dict]:
    """The training examples one finished video gives: its script from its source text, and its packaging from its script."""
    narration = "\n".join(str(l.get("text", "")).strip() for l in meta["lines"] if str(l.get("text", "")).strip())
    src = source(meta)[:SOURCE_CAP]
    base = {"slug": folder.name, "format": meta.get("format", "short"), "script_model": meta.get("script_model"), "license": LICENSE,
            "source_titles": __import__("reviewer").source_titles(meta), "claims": _claim_counts(folder)}
    out = [{"id": _hash(folder.name + "script"), "task": "script", "input": {"instructions": INSTRUCTIONS, "format": base["format"], "topic": meta.get("topic", ""), "source": src},
            "output": narration, "meta": base}]
    pack = {"title": meta.get("title", ""), "description_lead": str(meta.get("description", "")).split("\n\n")[0][:300], "tags": meta.get("tags", []), "thumb_hook": meta.get("thumb_hook", "")}
    out.append({"id": _hash(folder.name + "packaging"), "task": "packaging", "input": {"format": base["format"], "topic": meta.get("topic", ""), "script": narration[:1500]},
                "output": json.dumps(pack, ensure_ascii=False), "meta": base})
    return out


def _claim_counts(folder: Path) -> dict:
    try:
        rows = json.loads((folder / "claims.json").read_text())
    except (OSError, ValueError):
        return {}
    out: dict = {}
    for r in rows:
        k = str(r.get("verification_status", "?")).upper() if isinstance(r, dict) else "?"
        out[k] = out.get(k, 0) + 1
    return out


def _shingles(text: str, n: int = 5) -> set:
    w = _words(text)
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def check(ex: dict) -> list[str]:
    """Problems with one example (empty = fine): shape, size, secrets, personal data, junk markup, and a script that is mostly copied from its source."""
    bad = []
    if not isinstance(ex, dict) or not {"id", "task", "input", "output", "meta"} <= set(ex) or ex.get("task") not in MIN_TO_TRAIN:
        return ["bad shape"]
    out, inp = str(ex["output"]), json.dumps(ex["input"], ensure_ascii=False)
    if SECRETS.search(out) or SECRETS.search(inp):
        bad.append("contains something that looks like a key or token")
    if PII.search(out):
        bad.append("contains an email address or phone number")
    if ex["task"] == "script":
        n = len(out.split())
        if n < 85:
            bad.append(f"script too short ({n} words)")
        if JUNK.search(out):
            bad.append("script has a link or markup a voice would read aloud")
        src = str(ex["input"].get("source", ""))
        if len(src) < 800:
            bad.append("no source text: the model would learn to write from memory")
        else:
            mine, theirs = _shingles(out, 12), _shingles(src, 12)
            if mine and len(mine & theirs) / len(mine) >= 0.25:
                bad.append("a quarter or more of the script is copied from the source")
    else:
        try:
            p = json.loads(out)
            if not 15 <= len(str(p.get("title", ""))) <= 100 or not p.get("tags"):
                bad.append("packaging title length or tags are off")
        except ValueError:
            bad.append("packaging output is not JSON")
    return bad


def check_set(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, rejected) with a reason on each rejected one: single-example problems, exact duplicates and near duplicates (the later one goes)."""
    kept, rejected, seen_hash, seen_sh = [], [], set(), []
    for ex in items:
        why = check(ex)
        if not why:
            h = _hash(_norm(ex["output"]))
            sh = _shingles(ex["output"])
            if h in seen_hash:
                why = ["exact duplicate"]
            elif sh and any(len(sh & o) / len(sh | o) >= 0.8 for o in seen_sh if o):
                why = ["near duplicate"]
            else:
                seen_hash.add(h)
                seen_sh.append(sh)
        (rejected.append({**ex, "rejected": why}) if why else kept.append(ex))
    return kept, rejected


def split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Train and validation by video (hash of the slug), so one video is never on both sides."""
    train, valid = [], []
    for ex in items:
        (valid if int(_hash(ex["meta"]["slug"]), 16) % 10 == 0 else train).append(ex)
    return train, valid


def build(now: dt.datetime | None = None, out: Path | None = None, allow: tuple = (), source=source_cached) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    out = (out or config.ROOT / "data" / "trainset") / now.strftime("%Y%m%d")
    out.mkdir(parents=True, exist_ok=True)
    skipped, items = {}, []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        ok, why = eligible(m.parent, meta, allow)
        if not ok:
            skipped[m.parent.name] = why
            continue
        items += examples(m.parent, meta, source)
    kept, rejected = check_set(items)
    train, valid = split(kept)
    for name, rows in (("train", train), ("valid", valid), ("rejected", rejected)):
        (out / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    per = {t: sum(1 for r in kept if r["task"] == t) for t in MIN_TO_TRAIN}
    report = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "videos_seen": len(skipped) + len({r["meta"]["slug"] for r in items}), "videos_skipped": skipped, "examples_kept": per,
              "train": len(train), "valid": len(valid), "rejected": len(rejected), "rejected_reasons": sorted({w for r in rejected for w in r["rejected"]}),
              "ready_to_train": {t: per[t] >= MIN_TO_TRAIN[t] for t in MIN_TO_TRAIN}, "needed": MIN_TO_TRAIN, "dir": str(out), "license": LICENSE}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
