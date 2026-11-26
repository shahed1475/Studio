"""Scene manifest: which picture each scene of a film shows, why it was chosen, and how that changed since the last render (25 Nov 2026).

Why it exists: footage.scene_images returned the per-scene file list and the record kept only counts ("109 different on-topic images"), so nobody could see that
the Seven Sleepers v2 film filled its first 46 scenes from the subject's reserve pool in search order (Seven Sleepers art, then Ephesus coins, then Amman cave photos,
then Qur'an pages, Syriac and Gregory of Tours items) whatever each line said. The manifest makes every picture traceable to its line and flags the risky ways it came.

Every scene gets a stable id from its narration text (not its position), so reordering lines keeps ids; a re-render compares with the previous manifest and reports
  - changed: the same narration now shows a different picture (the reserve hands its pictures out in line order, so inserting lines moves them silently),
  - stale: a scene whose narration changed but whose picture did not (a picture chosen for the old line).
How a picture was chosen ("how"): forced_named, forced_drawn, line_search, art_first, reserve, drawn, reuse, missing (footage.scene_images, trace=),
then real_footage, blender, animated when a later step replaced the scene. "reserve" = a picture about the subject in general, not about the line; "reuse" = no new
picture could be found or drawn, so an earlier one is shown again (a failed drawing is never silent). Nothing here changes which picture a film gets."""
import hashlib
import json
import os
from pathlib import Path

import config

FILE = "scenes.json"
RISKY = ("reserve", "reuse", "missing")


def scene_ids(lines: list[dict]) -> list[str]:
    """One id per line from its narration text; a text that occurs twice gets #2, #3 (positions never enter the id)."""
    seen: dict[str, int] = {}
    out = []
    for l in lines:
        h = hashlib.sha1(str(l.get("text", "")).strip().encode()).hexdigest()[:10]
        seen[h] = seen.get(h, 0) + 1
        out.append(h if seen[h] == 1 else f"{h}#{seen[h]}")
    return out


def _rel(p) -> str | None:
    if p is None:
        return None
    p = Path(p)
    try:
        return str(p.resolve().relative_to(config.ROOT.resolve()))
    except ValueError:
        return str(p)


def _sha(p) -> str | None:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def build(lines: list[dict], stages: list[tuple[str, list]], trace: list[dict] | None = None) -> list[dict]:
    """stages: [("selected", clips), ("real_footage", clips), ("blender", clips), ("animated", clips)] in the order they ran; the last list is what the film shows.
    A scene changed by a later stage takes that stage's name as its "how" and keeps the picture it replaced (whose credit may still be in the credits)."""
    ids = scene_ids(lines)
    first = stages[0][1]
    out = []
    for i, l in enumerate(lines):
        how = (trace[i].get("how") if trace and i < len(trace) else None) or ("missing" if first[i] is None else "unknown")
        replaced = None
        for (_, before), (name, after) in zip(stages, stages[1:]):
            if after[i] != before[i]:
                how, replaced = name, replaced or before[i]
        final = stages[-1][1][i]
        out.append({"id": ids[i], "index": i, "text_sha1": ids[i].split("#")[0], "text": str(l.get("text", ""))[:160], "visual": l.get("visual"),
                    "how": how, "query": (trace[i].get("query") if trace and i < len(trace) else None), "file": _rel(final), "sha256": _sha(final) if final else None,
                    **({"replaced": _rel(replaced)} if replaced is not None else {})})
    return out


def runs(entries: list[dict], kinds=("reserve",), at_least: int = 3) -> list[list[int]]:
    """Consecutive scenes whose picture came the risky way: the Seven Sleepers v2 film had one run of 46."""
    out, cur = [], []
    for e in entries:
        if e["how"] in kinds:
            cur.append(e["index"])
        else:
            if len(cur) >= at_least:
                out.append(cur)
            cur = []
    if len(cur) >= at_least:
        out.append(cur)
    return out


def diff(old: list[dict], new: list[dict]) -> dict:
    """What a re-render changed, by stable id (text), never by position."""
    before = {e["id"]: e for e in old}
    by_index_old = {e["index"]: e for e in old}
    changed = [e["index"] for e in new if e["id"] in before and before[e["id"]].get("file") != e.get("file")]
    moved = [e["index"] for e in new if e["id"] in before and before[e["id"]]["index"] != e["index"]]
    stale = [e["index"] for e in new if e["id"] not in before and e["index"] in by_index_old and by_index_old[e["index"]].get("file") == e.get("file")
             and e.get("how") not in ("forced_drawn", "drawn", "art_first")]
    return {"changed": changed, "moved": moved, "stale": stale, "new_lines": [e["index"] for e in new if e["id"] not in before],
            "removed_lines": len([i for i in before if i not in {e["id"] for e in new}])}


def summary(entries: list[dict], changes: dict | None = None) -> dict:
    files: dict[str, list[int]] = {}
    for e in entries:
        if e.get("file"):
            files.setdefault(e["file"], []).append(e["index"])
    s = {"file": FILE, "scenes": len(entries), "how": {}, "reserve": [e["index"] for e in entries if e["how"] == "reserve"],
         "reuse": [e["index"] for e in entries if e["how"] in ("reuse", "missing")], "reserve_runs": runs(entries),
         "same_file": {f: ix for f, ix in files.items() if len(ix) > 1}}
    for e in entries:
        s["how"][e["how"]] = s["how"].get(e["how"], 0) + 1
    if changes is not None:
        s["changes_since_last_render"] = changes
    return s


def write(folder: Path, lines: list[dict], stages: list[tuple[str, list]], trace: list[dict] | None = None) -> dict:
    """Writes <folder>/scenes.json atomically (the previous one, if any, is compared first and kept as scenes.prev.json) and returns the summary for the record."""
    folder = Path(folder)
    entries = build(lines, stages, trace)
    path = folder / FILE
    changes = None
    if path.exists():
        try:
            changes = diff(json.loads(path.read_text()).get("scenes", []), entries)
        except (OSError, ValueError):
            changes = {"error": "the previous scenes.json could not be read"}
        (folder / "scenes.prev.json").write_bytes(path.read_bytes())
    s = summary(entries, changes)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"summary": s, "scenes": entries}, indent=1, ensure_ascii=False))
    os.replace(tmp, path)
    s["sha256"] = _sha(path)
    return s


def check(meta: dict) -> tuple[bool, str] | None:
    """The reviewer's reading of the summary in the record: None when the film has no manifest (made before 25 Nov 2026)."""
    s = meta.get("scene_manifest")
    if not s:
        return None
    if s.get("error"):
        return False, f"the scene manifest could not be written ({s['error']}): which picture each scene shows is unknown; look at every scene before approving"
    problems = []
    if s.get("reserve_runs"):
        problems.append("runs of 3+ scenes filled from the subject's general reserve, not chosen for their line: " + "; ".join(f"{r[0]}-{r[-1]}" for r in s["reserve_runs"][:4]))
    elif s.get("reserve"):
        problems.append(f"{len(s['reserve'])} scene(s) from the general reserve: {s['reserve'][:12]}")
    if s.get("reuse"):
        problems.append(f"{len(s['reuse'])} scene(s) show an earlier picture again because no new one could be found or drawn: {s['reuse'][:12]}")
    if s.get("same_file"):
        problems.append(f"{len(s['same_file'])} file(s) shown in more than one scene")
    ch = s.get("changes_since_last_render") or {}
    if ch.get("changed"):
        problems.append(f"{len(ch['changed'])} unchanged line(s) got a different picture than in the last render: {ch['changed'][:12]}")
    if ch.get("stale"):
        problems.append(f"{len(ch['stale'])} revised line(s) still show the old line's picture: {ch['stale'][:12]}")
    if problems:
        return False, "; ".join(problems) + ". Look at these scenes before approving (scenes.json in the video folder lists every picture and how it was chosen)."
    return True, (f"no scene of {s.get('scenes')} came from the general reserve or shows a repeat ({', '.join(f'{k} {v}' for k, v in sorted(s.get('how', {}).items()))}); "
                  "a line_search picture was searched with the line's note but accepted at subject level, so the picture review still looks at the scenes")
