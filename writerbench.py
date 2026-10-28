"""Writer bench: can a free open model write a Short script that passes our free rules?

The same Short prompt production uses (`scriptgen.short_prompt`) is sent to each candidate model for a few of our own source articles, and every answer is
scored by free, deterministic rules only: valid JSON, line and word counts that fit the Short length target, no chapter labels, no repeated lines, a hook that
does not overclaim, no copied source wording, and no number or year the source does not contain. No Claude call is made: this bench produces no training
data and no verdicts from a model (Anthropic's terms bar using its output to train models; docs/superpowers/plans/2026-10-28-audit-and-self-training.md).
Only models whose OpenRouter price is zero are called, and the free daily allowance production needs is left untouched. Results go to data/writerbench/.
What it cannot tell: whether the facts are right beyond numbers and years (that needs the fact-checker), or whether the story is good."""
import datetime as dt
import json
import re
import time

import clipper
import compliance
import config
import freemodels
import llm
import packaging
import reviewer
import scriptgen

DIR = config.ROOT / "data" / "writerbench"
KEEP_FREE_REQUESTS = 60  # of the day's free requests, left for production
SOURCE_CHARS = 9000
HARD = ("json", "grounded_numbers", "no_admission")  # a script failing one of these is unusable, whatever else it does well


def cases(n: int = 5) -> list[dict]:
    """Up to n of our own videos that have a source article: {topic, source}. One per topic."""
    out, seen = [], set()
    for m in sorted(config.OUT.glob("*/meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            meta = json.loads(m.read_text())
            source = reviewer.source_text(meta)
        except (OSError, ValueError):
            continue
        topic = (meta.get("topic") or "").strip()
        if topic and source and topic.lower() not in seen and meta.get("grounded"):
            seen.add(topic.lower())
            out.append({"topic": topic, "source": source[:SOURCE_CHARS]})
        if len(out) >= n:
            break
    return out


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d[\d,]*\b", text))


def score(script: dict | None, source: str) -> dict:
    """{"checks": {name: (ok, detail)}, "score": 0..1, "hard_fail": [names]} for one script. Free rules only."""
    checks: dict[str, tuple[bool, str]] = {}
    lines = [l for l in (script or {}).get("lines", []) if isinstance(l, dict) and str(l.get("text", "")).strip()] if isinstance(script, dict) else []
    texts = [str(l["text"]).strip() for l in lines]
    checks["json"] = (bool(lines) and bool(str((script or {}).get("title", "")).strip()), f"{len(lines)} lines")
    lo, hi = scriptgen.short_word_range()
    words = sum(len(t.split()) for t in texts)
    checks["line_count"] = (9 <= len(lines) <= 12, f"{len(lines)} lines (9 to 12)")
    checks["word_budget"] = (lo - 10 <= words <= hi + 5, f"{words} words ({lo} to {hi})")
    checks["visuals"] = (bool(lines) and all(str(l.get("visual", "")).strip() for l in lines), "every line has a picture search")
    checks["title"] = (0 < len(str((script or {}).get("title", ""))) <= 70, "title under 70 characters")
    bad_labels = [t for t in texts if scriptgen.label_of(t)]
    checks["no_labels"] = (not bad_labels, f"{len(bad_labels)} narrated labels")
    checks["no_loop"] = (len({t.lower() for t in texts}) == len(texts), "no repeated line")
    hook = texts[0] if texts else ""
    checks["hook"] = (bool(hook) and len(hook.split()) <= 12 and not clipper.OVERCLAIM.search(hook), f"first line {len(hook.split())} words")
    copied = compliance.copied_lines({"lines": [{"text": t} for t in texts]}, source) if texts else []
    checks["originality"] = (len(copied) <= max(1, len(texts) // 5), f"{len(copied)} lines copy the source")
    unseen = sorted(n for n in _numbers(" ".join(texts)) if len(n.replace(",", "")) >= 3 and n not in _numbers(source))
    checks["grounded_numbers"] = (not unseen, "every number and year is in the source" if not unseen else f"not in the source: {', '.join(unseen[:5])}")
    checks["no_admission"] = (not scriptgen.thin_script(lines), "no 'my sources say little' line")
    repeats = packaging.script_repeats(texts)
    checks["no_retell"] = (not repeats, f"{len(repeats)} retold pairs")
    ok = sum(1 for v in checks.values() if v[0])
    return {"checks": checks, "score": round(ok / len(checks), 3), "hard_fail": [n for n in HARD if not checks[n][0]]}


def ask_free(model: str, prompt: str, key: str, now: dt.datetime) -> tuple[dict | None, str]:
    """One call to one free model. (parsed JSON or None, a short reason when None). Refuses any model that is not free, and stops when the free allowance
    production needs is nearly used."""
    listed = {m["id"] for m in freemodels.refresh(now)}
    if model not in listed:
        return None, "not a free model"
    if freemodels.remaining(now, key, llm.load_config()["free_daily_limit"]) <= KEEP_FREE_REQUESTS:
        return None, "free allowance kept for production"
    for json_mode in (True, False):
        freemodels.count_request(now, "bench")
        try:
            body = llm._post(llm._payload(model, prompt, 2500, json_mode, "script"), key)
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if json_mode and code == 400:
                continue
            return None, f"{type(e).__name__}{f' {code}' if code else ''}"
        try:
            return llm.parse_json(body["choices"][0]["message"]["content"]), ""
        except (ValueError, KeyError, IndexError, TypeError):
            return None, "no JSON in the answer"
    return None, "rejected"


def run(models: list[str], cs: list[dict], ask=None, now: dt.datetime | None = None, pause: float = 3.0, write: bool = True) -> dict:
    """Every model writes a script for every case. `ask(model, prompt) -> (dict | None, reason)` is injectable; the default is ask_free."""
    now = now or llm._now()
    key = llm.api_key()
    ask = ask or (lambda m, p: ask_free(m, p, key, now))
    rows = []
    for model in models:
        for c in cs:
            start = time.time()
            got, why = ask(model, scriptgen.short_prompt(c["topic"], c["source"]))
            res = score(got, c["source"])
            rows.append({"model": model, "topic": c["topic"], "seconds": round(time.time() - start, 1), "reason": why, "score": res["score"] if got else 0.0,
                         "script": got if isinstance(got, dict) else None, "hard_fail": res["hard_fail"] if got else ["no answer"], "failed": [k for k, v in res["checks"].items() if not v[0]] if got else [], "answered": got is not None})
            time.sleep(pause if pause else 0)
    out = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "cases": [c["topic"] for c in cs], "rows": rows, "summary": summarize(rows)}
    if write:
        DIR.mkdir(parents=True, exist_ok=True)
        (DIR / f"{now.strftime('%Y%m%d-%H%M')}.json").write_text(json.dumps(out, indent=1))
    return out


def summarize(rows: list[dict]) -> list[dict]:
    """One line per model, best first: how many scripts were usable (answered and no hard failure) and the mean score."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["model"], []).append(r)
    out = []
    for model, rs in by.items():
        usable = [r for r in rs if r["answered"] and not r["hard_fail"]]
        common: dict[str, int] = {}
        for r in rs:
            for f in r["failed"]:
                common[f] = common.get(f, 0) + 1
        out.append({"model": model, "tries": len(rs), "answered": sum(r["answered"] for r in rs), "usable": len(usable),
                    "mean_score": round(sum(r["score"] for r in rs) / len(rs), 3), "seconds": round(sum(r["seconds"] for r in rs) / len(rs), 1),
                    "often_fails": sorted(common, key=lambda k: -common[k])[:3]})
    return sorted(out, key=lambda s: (-s["usable"], -s["mean_score"]))
