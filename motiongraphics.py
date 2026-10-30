"""2D animated graphics for a documentary, drawn as extra events of the burned-in ASS subtitles (so the renderer needs no change):

- a chapter title card at the top left when a chapter starts (a bar that wipes down, the chapter's own title, a fade), never for the first chapter, which is the hook;
- a date badge at the top right when a narration line names a year (a small pop and a fade);
- the hook: the first question of the first two narration lines, large at the top for the first three seconds (30 Oct 2026, owner's order: curiosity from the first second).

Everything shown is text that is already in the script or the chapter list: a year is shown only when it is written in the line, and nothing is worked out or added. Graphics
never cover the first seconds, never sit on top of each other, and keep a gap between badges so a documentary does not turn into a slide show."""
import re

HOOK_CLEAR = 4.0     # seconds at the start with no graphics: the opening belongs to the hook
CARD_DELAY = 0.25    # a card starts this long after its chapter's first line begins
CARD_SECONDS = 3.6
BADGE_AFTER = 0.4
BADGE_SECONDS = 3.2
BADGE_GAP = 6.0      # least seconds between two badge starts
ACCENT = "&H0028C8FF"  # the thumbnail accent (255, 200, 40) in ASS order

HOOK_START, HOOK_SECONDS, HOOK_WORDS = 0.25, 3.2, 14

ERA = re.compile(r"\b(\d{1,4})\s?(BCE|BC|AD|CE)\b")
YEAR = re.compile(r"(?<![\d,.])(1[0-9]{3}|20[0-9]{2})(?!\d|,\d|s\b)")


def year_label(text: str) -> str | None:
    """The first year the line writes ("525 BC", "530 BCE", "1933"), exactly as written; None when it names none. Numbers such as 50,000 or "the 1970s" are not years."""
    m = ERA.search(text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m = YEAR.search(text)
    return m.group(1) if m else None


def hook_text(data: dict) -> str | None:
    """The first question sentence in the first two narration lines, in capitals, or None when there is none or it is longer than HOOK_WORDS (a cut question is not the question)."""
    for line in [l.get("text", "") for l in (data.get("lines") or [])[:2]]:
        for sentence in re.split(r"(?<=[.?!])\s+", str(line).strip()):
            if sentence.endswith("?"):
                words = _plain(sentence).split()
                return " ".join(words).upper() if 0 < len(words) <= HOOK_WORDS else None
    return None


def _hook_lines(text: str, per_line: int = 22) -> str:
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > per_line:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "\\N".join(out + ([cur] if cur else []))


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _plain(s: str) -> str:
    """Text that cannot open an override block or a line break in the subtitle format."""
    return re.sub(r"[{}\\]", "", str(s)).strip()


def styles(size: tuple[int, int]) -> list[str]:
    w, h = size
    return [f"Style: Card,DejaVu Sans,{round(h * 0.054)},&H00FFFFFF,&H00000000,&H64000000,1,1,3,2,7,0,0,0",
            f"Style: Badge,DejaVu Sans,{round(h * 0.06)},{ACCENT},&H99000000,&H99000000,1,3,12,0,9,0,0,0",
            f"Style: Hook,DejaVu Sans,{round(h * 0.085)},&H00FFFFFF,&H00000000,&HAA000000,1,1,4,3,8,0,0,0"]


def graphics_events(data: dict, durations: list[float], size: tuple[int, int] = (1920, 1080)) -> list[str]:
    """The Dialogue lines for this video's cards and badges. `durations` are the seconds each narration line takes (the render's own scene lengths)."""
    w, h = size
    starts, t = [], 0.0
    for d in durations:
        starts.append(t)
        t += d
    mx, my = round(w * 0.045), round(h * 0.065)
    bw, bh = max(6, round(w * 0.0042)), round(h * 0.115)
    cards, busy = [], []
    for n, ch in enumerate(data.get("chapters") or [], 1):
        i = ch.get("start_line", 0)
        if i <= 0 or i >= len(starts) or not _plain(ch.get("title", "")):
            continue
        a = starts[i] + CARD_DELAY
        b = a + CARD_SECONDS
        busy.append((a, b))
        tx = mx + bw + round(w * 0.012)
        title = _plain(ch["title"])
        cards.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Card,{{\\an7\\pos({mx},{my})\\p1\\bord0\\shad0\\1c{ACCENT}&\\fad(0,450)\\clip({mx},{my},{mx + bw},{my})"
                     f"\\t(0,450,\\clip({mx},{my},{mx + bw},{my + bh}))}}m 0 0 l {bw} 0 {bw} {bh} 0 {bh}{{\\p0}}")
        cards.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Card,{{\\an7\\move({tx - 28},{my},{tx},{my},0,450)\\fad(350,450)}}"
                     f"{{\\fs{round(h * 0.03)}\\b1\\c{ACCENT}&\\bord2}}CHAPTER {n}{{\\r}}\\N{title}")
    badges, last = [], -BADGE_GAP
    texts = [l.get("text", "") for l in data.get("lines", [])]
    for i, text in enumerate(texts[: len(starts)]):
        label = year_label(text)
        if not label or i == 0:
            continue
        a = starts[i] + BADGE_AFTER
        b = min(starts[i] + durations[i] - 0.2, a + BADGE_SECONDS)
        if a < HOOK_CLEAR or b - a < 1.0 or a - last < BADGE_GAP or any(a < cb and b > ca for ca, cb in busy):
            continue
        last = a
        badges.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Badge,{{\\an9\\pos({w - mx},{my})\\fad(250,350)\\fscx85\\fscy85\\t(0,250,\\fscx100\\fscy100)}}{_plain(label)}")
    return hook_events(data, size) + cards + badges


def hook_events(data: dict, size: tuple[int, int] = (1920, 1080)) -> list[str]:
    """The hook line alone: every film gets it (switch `hook_text: false` in the record turns it off), whether or not it asks for the other graphics."""
    w, h = size
    hook = None if data.get("hook_text") is False else hook_text(data)
    return [f"Dialogue: 2,{_ts(HOOK_START)},{_ts(HOOK_START + HOOK_SECONDS)},Hook,{{\\an8\\pos({w // 2},{round(h * 0.16)})\\fad(200,450)\\b1}}{_hook_lines(hook)}"] if hook else []


def add_to_ass(path, events: list[str], size: tuple[int, int] = (1920, 1080)) -> None:
    """Put the card and badge styles into a subtitle file and its graphics events at the end, replacing any this module wrote before (so a re-render does not stack them)."""
    from pathlib import Path

    f = Path(path)
    kept = [ln for ln in f.read_text().split("\n") if not (ln.startswith("Style: Card,") or ln.startswith("Style: Badge,") or ln.startswith("Style: Hook,") or (ln.startswith("Dialogue:") and (",Card," in ln or ",Badge," in ln or ",Hook," in ln)))]
    text = "\n".join(kept)
    i = text.find("[Events]")
    if i < 0:
        raise ValueError("no [Events] section in the subtitle file")
    text = text[:i].rstrip("\n") + "\n" + "\n".join(styles(size)) + "\n\n" + text[i:].rstrip("\n") + "\n" + "\n".join(events) + ("\n" if events else "")
    f.write_text(text)
