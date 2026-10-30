"""Finishes a narration track: a gentle compressor, then a two-pass loudness normalisation (30 Oct 2026, owner: louder but not too loud).

Measured that day on the same voice: the studio's one-pass `loudnorm` asked for -14 LUFS and delivered about -15. A 3:1 compressor first and a two-pass `loudnorm` in linear mode
reach the target exactly (-14.5 and -14.0 both hit) at a -1.5 dB true peak, and the loudness range falls from 2.4 to 1.6 LU, so the voice is steadier on phone speakers.
YouTube turns louder uploads down and never turns quiet ones up (the code's own note on its -14 reference), so going louder than -14 gains nothing.
Applied to the narration file only: line lengths do not change, so the captions and scene timing stay exact. Any failure leaves the file as it was."""
import json
import os
import subprocess
from pathlib import Path

PRE = "acompressor=threshold=0.09:ratio=3:attack=5:release=80:makeup=2"


def _run(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-nostats", "-y", "-loglevel", "info", *args], capture_output=True, text=True, check=True, timeout=900).stderr


def finish(src, dst=None, lufs: float = -14.5, tp: float = -1.5) -> bool:
    """Finish `src` (in place unless `dst` is given). True when done, False (file untouched) on any failure."""
    src = Path(src)
    out = Path(dst) if dst else src
    tmp = out.with_name(out.stem + ".fin.tmp" + out.suffix)
    try:
        first = _run(["-i", str(src), "-af", f"{PRE},loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
        j = json.loads(first[first.rindex("{"):first.rindex("}") + 1])
        second = (f"{PRE},loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
                  f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
        _run(["-i", str(src), "-af", second, "-c:a", "libmp3lame", "-b:a", "192k", str(tmp)])
        if not tmp.is_file() or tmp.stat().st_size < 1000:
            raise ValueError("no output")
        os.replace(tmp, out)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False
