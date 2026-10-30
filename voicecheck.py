"""The studio listens to its own narration (30 Oct 2026: nobody had ever listened to the new voice, and a voice can fail where every file check passes).

An audio model writes down what it hears in the finished video, WITHOUT being shown the script (shown the script it would simply echo it). Our code then compares that transcript
with the script, part by part: a line that was cut, skipped, repeated or swapped shows as a run of missing or extra words. A single odd word (a name spelled differently by the
listener) is a lead for the owner, never proof of a bad voice, and numbers are not compared (the script writes digits, the voice speaks them). It is a warning only, costs a fraction of
a cent a minute, and never sends anything but our own finished videos. It does not judge tone, pace or sound quality: only a person can."""
import base64
import datetime as dt
import difflib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

import config

ENABLED = True       # the test suite turns this off so no test ever calls a model
MIN_RUN = 4          # this many words missing or extra in a row is a gap worth naming
FAIL_RUN = 6         # a gap this long, or a match under MIN_MATCH, makes the check fail (it still only warns)
MIN_MATCH = 0.90
PART_SECONDS = 150.0
MAX_BYTES = 6_000_000
NUMBER_WORDS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty "
                   "seventy eighty ninety hundred thousand million billion".split())


def words(text: str) -> list[str]:
    """Lower-case words without punctuation, hyphens as spaces, digits and spoken numbers left out (the two cannot be compared)."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower().replace("-", " ")  # László -> laszlo, Hŏ -> ho: the listener writes plain letters
    t = re.sub(r"(?<=\d),(?=\d)", "", t.replace("’", "'"))
    return [w for w in re.findall(r"[a-z0-9']+", t) if not any(c.isdigit() for c in w) and w not in NUMBER_WORDS]


def compare(script: str, heard: str) -> dict:
    s, h = words(script), words(heard)
    sm = difflib.SequenceMatcher(None, s, h, autojunk=False)
    gaps, leads = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ns, nh = i2 - i1, j2 - j1
        if tag == "delete" and ns >= MIN_RUN:
            gaps.append({"kind": "missing", "words": ns, "script": " ".join(s[i1:i2][:14]), "heard": ""})
        elif tag == "insert" and nh >= MIN_RUN:
            gaps.append({"kind": "extra", "words": nh, "script": "", "heard": " ".join(h[j1:j2][:14])})
        elif tag == "replace" and max(ns, nh) >= MIN_RUN:
            gaps.append({"kind": "different", "words": max(ns, nh), "script": " ".join(s[i1:i2][:14]), "heard": " ".join(h[j1:j2][:14])})
        elif tag == "replace":
            pairs = list(zip(s[i1:i2], h[j1:j2])) if ns == nh else [(" ".join(s[i1:i2]), " ".join(h[j1:j2]))]
            leads += [list(p) for p in pairs if p not in leads and max(len(p[0]), len(p[1])) > 3]  # 'a' for 'the' is the listener's choice of article, not a lead
    total = len(s) + len(h)
    match = (2 * sum(b.size for b in sm.get_matching_blocks()) / total) if total else 1.0
    return {"match": round(match, 4), "words": len(s), "gaps": gaps, "heard_as": leads[:20]}


def ok(result: dict) -> bool:
    return result.get("match", 0) >= MIN_MATCH and not any(g["words"] >= FAIL_RUN for g in result.get("gaps", []))


def parts(starts: list[float], total: float, target: float = PART_SECONDS) -> list[tuple[int, int, float, float]]:
    """(first line, last line, start second, end second) of each part: the audio is cut at the start of a line, so every line is in exactly one part."""
    out, first = [], 0
    for i in range(1, len(starts)):
        if starts[i] - starts[first] >= target:
            out.append((first, i - 1, starts[first], starts[i]))
            first = i
    out.append((first, len(starts) - 1, starts[first], total))
    return out


def line_starts(word_rows: list[dict], n_lines: int) -> list[float]:
    """When each narration line begins, from the word times saved with the video (the first line begins at 0)."""
    starts = [0.0]
    for i in range(1, n_lines):
        t = [w["s"] for w in word_rows if w.get("i") == i and isinstance(w.get("s"), (int, float))]
        starts.append(min(t) if t else starts[-1])
    return starts


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _extract(video: Path, t0: float, t1: float) -> bytes | None:
    """One part of the audio as a small mono mp3, or None when ffmpeg cannot make it."""
    try:
        out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", "-f", "mp3", "-"],
                             capture_output=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 and out.stdout else None


PROMPT = ("Write down exactly the words you hear in this audio, in order, as plain text. Do not correct, shorten, summarise or add anything, and do not describe the audio. "
          'Spell names and places the way they sound. Reply JSON only: {"text": "..."}')


def listen(folder: Path, post=None, extract=None, now: dt.datetime | None = None) -> dict:
    """Transcribe the finished video's audio part by part and compare it with the script. Returns {model, at, ok, match, words, gaps, heard_as, parts, coverage, cost} (also saved as
    voice_check.json in the folder) or {"error": reason}. Only our own videos in the output folder are sent, and nothing is bought over the daily cap."""
    import filelock
    import llm
    import modelcfg
    import subtitles
    import videoinspect

    now = now or _now()
    try:
        folder = Path(folder).resolve()
        if folder.parent != Path(config.OUT).resolve() or not (folder / "video.mp4").is_file():
            return {"error": "only our own videos in the output folder are listened to"}
        cfg = llm.load_config()
        if llm.spent_today(now) >= cfg["daily_budget_usd"]:
            return {"error": f"the daily spending cap (${cfg['daily_budget_usd']:.2f}) is used up"}
        model = modelcfg.get("audio_listen")
        if "audio" not in videoinspect.model_modalities().get(model, []):
            return {"error": f"{model} cannot be confirmed to accept audio input"}
        meta = json.loads((folder / "meta.json").read_text())
        lines = [str(l.get("text", "")) for l in meta.get("lines", [])]
        word_rows = subtitles.load_words(folder / "words.json")
        if not lines or not word_rows:
            return {"error": "the video has no script lines or word times to compare with"}
        total = videoinspect._video_seconds(folder / "video.mp4")
        if not total:
            return {"error": "the length of the video could not be read"}
        plan = parts(line_starts(word_rows, len(lines)), total)
        script_all, heard_all, listened, failed, cost = [], [], 0.0, [], 0.0
        for k, (a, b, t0, t1) in enumerate(plan, 1):
            audio = (extract or _extract)(folder / "video.mp4", t0, t1)
            if not audio or len(audio) > MAX_BYTES:
                failed.append(k)
                continue
            body = (post or llm._post)({"model": model, "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT}, {"type": "input_audio", "input_audio": {"data": base64.b64encode(audio).decode(), "format": "mp3"}}]}],
                "max_tokens": 3000, "temperature": 0, "usage": {"include": True}}, llm.key_for(model))
            llm._account(now, "review", model, body)
            cost += float((body.get("usage") or {}).get("cost") or 0)
            if body["choices"][0].get("finish_reason") == "length":
                failed.append(k)
                continue
            got = llm.parse_json(body["choices"][0]["message"]["content"])
            heard = got.get("text") if isinstance(got, dict) else None
            if not isinstance(heard, str) or not heard.strip():
                failed.append(k)
                continue
            script_all.append(" ".join(lines[a:b + 1]))
            heard_all.append(heard)
            listened += t1 - t0
        if not heard_all:
            return {"error": "no part of the audio could be transcribed", "failed_parts": failed}
        per_part = [compare(s, h) for s, h in zip(script_all, heard_all)]
        merged = compare(" ".join(script_all), " ".join(heard_all))
        merged["gaps"] = [g for p in per_part for g in p["gaps"]]  # gaps found inside one part, so a boundary never makes one
        merged["match"] = round(sum(p["match"] * p["words"] for p in per_part) / max(sum(p["words"] for p in per_part), 1), 4)
        merged["heard_as"] = [x for p in per_part for x in p["heard_as"]][:20]
        result = {**merged, "ok": ok(merged), "model": model, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "parts": len(plan), "failed_parts": failed, "cost": round(cost, 5),
                  "coverage": (f"Listened to {listened / 60:.1f} of {total / 60:.1f} minutes of the finished audio in {len(plan)} parts with {model}, without being shown the script, and compared "
                               "the words with the script. Numbers are not compared and names are often spelled differently by the listener, so single words are leads, not proof. "
                               "It cannot judge tone, pace or sound quality: only a person can.")}
        try:
            filelock.write_atomic(folder / "voice_check.json", json.dumps(result, indent=1))
        except OSError:
            result["saved"] = False
        return result
    except Exception as e:  # a listening check that cannot run is reported, never allowed to stop a video
        return {"error": f"{type(e).__name__}: {str(e)[:160]}"}


def summary(result: dict) -> dict:
    """What is kept in the video's record: the verdict and what to look at, not the whole report (that is voice_check.json in the folder)."""
    keep = {k: result[k] for k in ("ok", "match", "words", "model", "at", "parts", "cost") if k in result}
    keep["gaps"], keep["heard_as"] = result.get("gaps", [])[:6], result.get("heard_as", [])[:12]
    return keep


def rows(folder: Path, post=None) -> list[dict]:
    """Rows for the quality gate. Every row is a warning: a model's listening is a lead, not proof."""
    r = listen(folder, post=post)
    if "error" in r:
        return [{"name": "voice_listen", "ok": False, "severity": "warn", "detail": "could not run: " + str(r["error"])[:200]}]
    said = f"{r['match'] * 100:.1f}% of the script's words were heard"
    if r["gaps"]:
        said += "; " + "; ".join(f"{g['kind']} {g['words']} words ({(g['script'] or g['heard'])[:60]})" for g in r["gaps"][:3])
    leads = "; ".join(f"{a} heard as {b}" for a, b in r["heard_as"][:8]) or "none"
    return [{"name": "transcript_matches_script", "ok": bool(r["ok"]), "severity": "warn", "detail": said},
            {"name": "names_heard_differently", "ok": True, "severity": "warn", "detail": f"leads for a person, not proof of a bad voice: {leads}"},
            {"name": "listening_coverage", "ok": True, "severity": "warn", "detail": r["coverage"]}]
