"""A 24 s vertical UGC-style ad for the CATS coin, made in a Claude Code session (2 Nov 2026). Local only: nothing here uploads or goes to Autopilot.

Honest limits: the presenter is AI-generated and labelled so on screen; the script makes NO claim about the coin (no price, no returns, no features, no partners: none was
supplied or verified) and ends with a risk line; the logo is an original placeholder drawn by code, not the coin's real logo; the "motion" is a handheld-style camera move on still
pictures (no real lip-sync, no moving people). Usage: PYTHONPATH=. python tools/ugc_cats.py   (the four pictures u1 u2 u4 u5 must exist: docs/studio/cats/pictures_local.json)."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config
import tts

ROOT = Path(config.ROOT)
OUT = ROOT / "output_ugc" / "cats-ugc-24s"
FONT = "/usr/share/fonts/julietaula-montserrat-fonts/Montserrat-Bold.otf"
W, H, FPS, TOTAL, FADE = 1080, 1920, 30, 24.0, 0.15
GOLD = (212, 175, 55)
LINES = ["Same old coins. Same old noise.", "Then a name that makes you look twice.", "Meet CATS.", "Look it up. Read the details. Judge for yourself.",
         "Do your own research, always.", "CATS. Curious? Start with a look. This is not financial advice, and crypto can lose you money."]
SCENES = [("u1", "pan"), ("u2", "push"), ("logo", "push"), ("u4", "pan"), ("u5", "push"), ("u2", "pull")]


def picture(pid: str) -> Path:
    import tools.zimage_batch as zb

    job = next(j for j in json.loads((ROOT / "docs/studio/cats/pictures_local.json").read_text()) if j["id"] == pid)
    p = zb.path_for(job)
    if not p.exists():
        raise SystemExit(f"picture {pid} is not drawn yet: {p.name}")
    return p


def make_logo(work: Path) -> tuple[Path, Path]:
    """An original gold cat-head mark and wordmark (a placeholder: the owner has no logo for the coin). A transparent PNG and a full card."""
    S = 900
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(215, 330), (235, 90), (410, 250)], fill=GOLD)
    d.polygon([(685, 330), (665, 90), (490, 250)], fill=GOLD)
    d.polygon([(250, 300), (258, 160), (365, 255)], fill=(30, 24, 8))
    d.polygon([(650, 300), (642, 160), (535, 255)], fill=(30, 24, 8))
    d.ellipse([170, 200, 730, 640], fill=GOLD)
    for sx in (1, -1):
        cx = 450 + sx * 118
        d.polygon([(cx - 62 * sx, 405), (cx, 372), (cx + 62 * sx, 420), (cx, 440)], fill=(18, 16, 10))
        d.ellipse([cx - 9, 384, cx + 9, 428], fill=GOLD)
    d.polygon([(425, 480), (475, 480), (450, 512)], fill=(18, 16, 10))
    for k, dy in enumerate((-18, 4, 26)):
        d.line([(300, 520 + dy), (150, 505 + dy * 2)], fill=(18, 16, 10), width=5)
        d.line([(600, 520 + dy), (750, 505 + dy * 2)], fill=(18, 16, 10), width=5)
    f = ImageFont.truetype(FONT, 150)
    word, gap = "CATS", 34
    wd = sum(d.textlength(c, font=f) for c in word) + gap * 3
    x = (S - wd) / 2
    for c in word:
        d.text((x, 690), c, font=f, fill=GOLD)
        x += d.textlength(c, font=f) + gap
    mark = work / "logo.png"
    img.save(mark)
    card = Image.new("RGB", (W, H))
    cd = ImageDraw.Draw(card)
    for y in range(H):  # a deep navy to black gradient
        t = y / H
        cd.line([(0, y), (W, y)], fill=(int(14 * (1 - t)), int(20 * (1 - t)), int(40 * (1 - t) + 4)))
    big = img.resize((900, 900))
    card.paste(big, (90, 480), big)
    cp = work / "logo_card.png"
    card.save(cp)
    return mark, cp


def zoom(kind: str, n: int) -> str:
    shake = "+7*sin(on/9)"
    if kind == "push":
        return f"zoompan=z='1.0+0.16*on/{n}':x='iw/2-(iw/zoom/2){shake}':y='ih/2-(ih/zoom/2)+6*sin(on/7+1)':d={n}:s={W}x{H}:fps={FPS}"
    if kind == "pull":
        return f"zoompan=z='1.17-0.14*on/{n}':x='iw/2-(iw/zoom/2){shake}':y='ih/2-(ih/zoom/2)+6*sin(on/7+1)':d={n}:s={W}x{H}:fps={FPS}"
    return f"zoompan=z='1.14':x='(iw-iw/zoom)*(0.22+0.56*on/{n}){shake}':y='ih/2-(ih/zoom/2)+6*sin(on/7+1)':d={n}:s={W}x{H}:fps={FPS}"


def run(cmd: list, cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed: " + r.stderr[-700:])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"
    work.mkdir(exist_ok=True)
    mark, card = make_logo(work)
    config.VOICE = "en-US-AvaMultilingualNeural"  # a female voice (config lists it as an option); the owner's film voice stays Andrew
    for rate in ("+0%", "+5%", "+10%", "+15%"):
        config.VOICE_RATE = rate
        narration, ass, durs = tts.narrate(LINES, work, pause=0.3, tail=0.25)
        if sum(durs[:-1]) + 4.2 <= TOTAL:  # the last scene needs about 4 s of end card
            break
    durs = durs[:-1] + [TOTAL - sum(durs[:-1])]
    print("voice rate", rate, "scene seconds", [round(x, 2) for x in durs])
    clips = []
    for i, ((pid, kind), dur) in enumerate(zip(SCENES, durs)):
        n = round((dur + (FADE if i < len(SCENES) - 1 else 0)) * FPS)
        src = card if pid == "logo" else picture(pid)
        out = work / f"s{i}.mp4"
        base = f"scale=1620:2880:flags=lanczos,setsar=1,{zoom(kind, n)}"
        if i == len(SCENES) - 1:  # the end card: the logo fades in over the presenter, with the risk line
            (work / "risk.txt").write_text("Not financial advice.\nCrypto is risky: you can lose money.")
            fg = (f"[0:v]{base}[b];[1:v]scale=520:-1,format=rgba,fade=in:st=0.9:d=0.6:alpha=1[l];[b][l]overlay=(W-w)/2:250[v];"
                  f"[v]drawtext=fontfile={FONT}:textfile=risk.txt:fontsize=40:fontcolor=white@0.95:x=(w-text_w)/2:y=860:line_spacing=14:box=1:boxcolor=black@0.38:boxborderw=22[o]")
            run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(src), "-loop", "1", "-i", str(mark), "-filter_complex", fg, "-map", "[o]", "-t", f"{n / FPS:.3f}", "-r", str(FPS), "-pix_fmt", "yuv420p", str(out)], work)
        else:
            run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(src), "-vf", base, "-t", f"{n / FPS:.3f}", "-r", str(FPS), "-pix_fmt", "yuv420p", str(out)], work)
        clips.append(out)
    # hard dips between shots: a short cross-fade, timed so each shot is fully visible at its own start
    inputs, chain, acc, start = [], "", "[0:v]", 0.0
    for c in clips:
        inputs += ["-i", str(c)]
    for k in range(1, len(clips)):
        start += durs[k - 1]
        chain += f"{acc}[{k}:v]xfade=transition=fade:duration={FADE}:offset={start - FADE:.3f}[x{k}];"
        acc = f"[x{k}]"
    grade = ("eq=contrast=1.07:saturation=0.94:brightness=-0.012,colorbalance=rs=-0.05:bs=0.06:rh=0.06:bh=-0.05,curves=all='0/0 0.25/0.22 0.75/0.80 1/1',"
             "vignette=angle=PI/5,noise=alls=6:allf=t+u,unsharp=3:3:0.4")
    (work / "label.txt").write_text("AI-generated presenter")
    top = f"drawtext=fontfile={FONT}:textfile=label.txt:fontsize=28:fontcolor=white@0.80:x=(w-text_w)/2:y=70"
    chain += f"{acc}{grade},ass=captions.ass,{top}[vout]"
    pad = ("aevalsrc=0.05*sin(2*PI*110*t)+0.035*sin(2*PI*164.81*t)+0.03*sin(2*PI*220*t):s=44100:d=24,"
           "lowpass=f=900,tremolo=f=0.15:d=0.4,afade=t=in:d=2,afade=t=out:st=21:d=3,volume=0.55")
    audio = f"[{len(clips)}:a]apad=whole_dur=24,volume=1.0[n];[{len(clips) + 1}:a]anull[m];[n][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    final = OUT / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-i", str(narration), "-f", "lavfi", "-i", pad, "-filter_complex", chain + ";" + audio,
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(TOTAL), str(final)], work)
    print("DONE", final)


if __name__ == "__main__":
    sys.exit(main())
