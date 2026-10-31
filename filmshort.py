"""A Short that explains a public-domain film with the film's own pictures (31 Oct 2026, owner's order: film explainer Shorts for a new channel).

Only a film that is in the public domain and that we can fetch from Wikimedia Commons or the Internet Archive: made in 1930 or earlier (the US public domain on 1 Jan 2026 holds
works of 1930 and before; Duke's Public Domain Day list), with the file's own licence page named as evidence. Our script and our synthetic voice go over the picture: the film's
soundtrack, any restoration music and any colour restoration are not used (use the black and white picture file). Each line shows a stretch of the film from a start time the
spec names, fitted into 1080x1920 on a blurred copy of the same picture. Nothing is flipped, recoloured or otherwise altered to avoid a match: this is a rights-checked
source, not a disguised one. A film from YouTube, or newer than 1930, is refused. The result is a held draft; only the owner releases it."""
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import config
import numbershort
import records

LAST_US_PD_YEAR = 1930
HOSTS = ("commons.wikimedia.org", "upload.wikimedia.org", "archive.org")
FORBIDDEN = ("video", "clips", "footage", "source_video", "youtube_url", "download", "face", "person")
MAX_WORDS = 80


def validate(spec: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    for k in spec:
        if k.lower() in FORBIDDEN:
            errors.append(f"'{k}': the film goes in 'film', and only a rights-checked public-domain film")
    film = spec.get("film") or {}
    year = film.get("year")
    if not isinstance(year, int) or year > LAST_US_PD_YEAR:
        errors.append(f"the film must be from {LAST_US_PD_YEAR} or earlier (the US public domain in 2026); got {year!r}")
    page = film.get("source_page") or ""
    host = (urlparse(page).hostname or "").lower()
    if not page.startswith("https://") or not any(host == h or host.endswith("." + h) for h in HOSTS):
        errors.append("film.source_page must be an https page on Wikimedia Commons or the Internet Archive that states the licence")
    if not (film.get("pd_basis") or "").strip():
        errors.append("film.pd_basis: say why the film is public domain, as the file's own page says it")
    if not film.get("file"):
        errors.append("film.file: the local file of the picture (black and white, no restoration music)")
    if not isinstance(film.get("director_death_year"), int):
        warns.append("the director's death year is not recorded: copyright outside the US (often life plus 70 years) was not checked")
    elif 2026 - film["director_death_year"] < 71:
        errors.append("the director died less than 71 years ago: the film may still be in copyright outside the US")
    lines = spec.get("lines") or []
    if not 5 <= len(lines) <= 9:
        errors.append(f"a film Short has 5 to 9 lines, this has {len(lines)}")
    if sum(len((l.get("text") or "").split()) for l in lines) > MAX_WORDS:
        errors.append(f"too many words for one Short (limit {MAX_WORDS})")
    if not spec.get("title") or len(spec["title"]) > numbershort.MAX_TITLE:
        errors.append(f"the title must be 1 to {numbershort.MAX_TITLE} characters")
    for i, l in enumerate(lines):
        if not (l.get("text") or "").strip():
            errors.append(f"line {i}: no text")
        has_start, has_card = isinstance(l.get("start"), (int, float)) and l["start"] >= 0, isinstance(l.get("card"), dict)
        if has_start == has_card:
            errors.append(f"line {i}: give either 'start' (seconds into the film) or 'card', not both and not neither")
        if has_card and (l["card"].get("type") not in numbershort.CARDS or any(not str(l["card"].get(f, "")).strip() for f in numbershort.CARDS.get(l["card"].get("type"), ()))):
            errors.append(f"line {i}: the card is incomplete")
    if not numbershort.sources_ok(spec.get("sources") or []):
        errors.append("at least two sources, each with title, https address, the passage that carries the claim and the date it was read")
    if lines and not (lines[0].get("text") or "").strip().endswith("?"):
        warns.append("the hook is not a question")
    if lines and "subscribe" not in (lines[-1].get("text") or "").lower():
        warns.append("the last line does not invite a subscribe")
    return errors, warns


def probe_seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def film_clip(src: Path, start: float, seconds: float, out: Path, size=(1080, 1920)) -> Path:
    """`seconds` of the film from `start`, the picture at full width on a blurred, darkened copy of itself. If the film ends first, its last frame is held."""
    import render

    w, h = size
    graph = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,eq=brightness=-0.18[bg];"
             f"[b]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={config.FPS},setsar=1,tpad=stop_mode=clone:stop_duration={seconds:.2f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(src), "-filter_complex", graph, "-an", "-t", f"{seconds:.3f}", *render._venc("20", "veryfast"), str(out)], check=True)
    return out


def build(spec: dict, out_root: Path | None = None, replace: bool = False) -> Path:
    import editprofile
    import render
    import subtitles
    import tts

    errors, warns = validate(spec)
    src = Path((spec.get("film") or {}).get("file") or "")
    if not errors and not src.exists():
        errors.append(f"film.file not found: {src}")
    if errors:
        raise ValueError("; ".join(errors))
    length = probe_seconds(src)
    late = [i for i, l in enumerate(spec["lines"]) if "start" in l and l["start"] >= length]
    if late:
        raise ValueError(f"lines {late} start after the film ends ({length:.0f} s)")
    folder = (out_root or config.OUT) / (spec.get("slug") or numbershort.slug_of(spec["title"]))
    if folder.exists():
        try:
            mine = records.read(folder).get("built_by") == "filmshort"
        except (OSError, ValueError, records.RecordError):
            mine = False
        if not (replace and mine):
            raise FileExistsError(f"{folder.name} exists" + (" and was not made by this tool" if replace and not mine else " (pass replace=True to rebuild a folder this tool made)"))
        shutil.rmtree(folder)
    work = folder / "work"
    work.mkdir(parents=True)
    lines = [l["text"] for l in spec["lines"]]
    prof = editprofile.load()
    say = spec.get("say") or {}
    with numbershort.respelled(say):
        narration, ass, durations = tts.narrate(lines, work, editprofile.short_pause(prof), prof["motion"], prof["caption_pos"], style=spec.get("voice_style", "energetic"))
    ass.write_text(numbershort.restore_spelling(ass.read_text(), say))
    clips = []
    for i, l in enumerate(spec["lines"]):
        if "card" in l:
            p = folder / f"card{i}.png"
            numbershort.draw_card(l["card"]).save(p)
            clips.append(p)
        else:
            clips.append(film_clip(src, l["start"], durations[i] + 0.3, folder / "anim" / f"clip{i:02d}.mp4"))  # a clip in a folder called anim plays once, never looped (render.py)
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=editprofile.lufs_for({}, prof), shots=False, crossfade=0.0, grain=False)
    words = subtitles.load_words(work / "words.json")
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.with_punctuation(words, lines))
    film = spec["film"]
    credit = f"Film: {film['title']} ({film['year']}), {film.get('director', '')}, public domain ({film['pd_basis']}); file page: {film['source_page']}"
    meta = {
        "title": spec["title"], "format": "short", "kind": "film", "built_by": "filmshort", "voice_style": spec.get("voice_style", "energetic"), "hold": True,
        "hold_reason": "a film Short built by filmshort.py: the owner watches it and releases it", "lines": [{"text": t, "visual": ""} for t in lines],
        "description": (spec.get("description") or "").rstrip() + "\n\n" + credit + "\nScript and voice: ours (synthetic voice). The film's own soundtrack is not used.\n\nSources:\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in spec["sources"]),
        "tags": spec.get("tags", []), "sources": spec["sources"], "credits": [credit], "film": {k: v for k, v in film.items() if k != "file"}, "film_seconds": round(length, 1),
        "limits": spec.get("limits", []), "warnings": warns, "durations": [round(x, 2) for x in durations],
    }
    records.create(folder, meta)
    return folder


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python filmshort.py SPEC.json [--check] [--replace]")
        return 2
    spec = json.loads(Path(argv[0]).read_text())
    errors, warns = validate(spec)
    for w in warns:
        print("warn:", w)
    for e in errors:
        print("ERROR:", e)
    if errors or "--check" in argv:
        return 1 if errors else 0
    print("built:", build(spec, replace="--replace" in argv))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
