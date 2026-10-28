"""One fact-check of a bench model's scripts, with Claude as the JUDGE only.

The writer bench (writerbench.py) is free and rule-based. This asks the existing fact-checker (`scriptgen.unsupported`, the same one production uses on every
script, review role, source article as a cached block) which narration lines the source article does not support. The answer is a count in a report: it is never
stored as a label, never joins a training set and never edits a script (Anthropic's terms bar using Claude output to train models; the plan says judging is fine).
It costs a few cents; a spent daily cap means the check does not run, and says so."""
import json

import config
import scriptgen

DIR = config.ROOT / "data" / "writerbench"


def check(bench_file, model: str, sources: dict[str, str], ask=None) -> dict:
    """{"model", "scripts": [{topic, lines, unsupported, ok}], "judged", "lines_ok_pct"} for every usable script of `model` in the bench file.
    `sources` maps a topic to its source text; `ask(lines, source) -> {line: why}` is injectable (default scriptgen.unsupported)."""
    ask = ask or scriptgen.unsupported
    data = json.loads(open(bench_file).read())
    out = []
    for r in data["rows"]:
        if r["model"] != model or not r.get("script") or r["hard_fail"] or r["topic"] not in sources:
            continue
        lines = [l for l in r["script"]["lines"] if isinstance(l, dict) and str(l.get("text", "")).strip()]
        try:
            bad = ask(lines, sources[r["topic"]])
        except Exception as e:  # a fact-checker that cannot answer is not a pass
            out.append({"topic": r["topic"], "lines": len(lines), "error": f"{type(e).__name__}: {str(e)[:120]}"})
            continue
        out.append({"topic": r["topic"], "lines": len(lines), "unsupported": {str(n): why for n, why in bad.items()}, "ok": not bad})
    judged = [s for s in out if "error" not in s]
    total = sum(s["lines"] for s in judged)
    flagged = sum(len(s["unsupported"]) for s in judged)
    rep = {"model": model, "scripts": out, "judged": len(judged), "lines_flagged": flagged,
           "lines_ok_pct": round(100 * (total - flagged) / total, 1) if total else None, "note": "a judge's count for a report; not a label, never training data"}
    return rep
