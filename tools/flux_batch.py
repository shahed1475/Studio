"""Draw pictures with FLUX.1 schnell (stable-diffusion.cpp, free, local) for a video made in a Claude Code session (1 Nov 2026).
Usage: PYTHONPATH=. python tools/flux_batch.py jobs.json   (a list of {"id", "prompt", "width", "height", "seed"}). Sequential (one 4 GB card), skips a job whose picture exists,
writes cache/cc/f-<hash>.png and prints "DONE <id> <path> <seconds>". Files in ~/tools/sdcpp/flux (Apache-2.0 weights per the Hugging Face cards, SHA-256 checked on download).
Measured on the GTX 1050 Ti: 212 s for 768x448 at 4 steps."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import config

HOME = Path(os.environ.get("SDCPP") or Path.home() / "tools" / "sdcpp")
FILES = {"diffusion": "flux/flux1-schnell-Q2_K.gguf", "vae": "models/ae.safetensors", "clip_l": "flux/clip_l.safetensors", "t5xxl": "flux/t5-v1_1-xxl-encoder-Q4_K_M.gguf"}
STEPS = 4


def path_for(job: dict) -> Path:
    key = json.dumps([job["prompt"], job["width"], job["height"], job.get("seed", 1), FILES["diffusion"], STEPS], sort_keys=True)
    d = Path(config.CACHE) / "cc"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"f-{hashlib.sha256(key.encode()).hexdigest()[:16]}.png"


def draw(job: dict) -> Path:
    out = path_for(job)
    if out.exists():
        return out
    cmd = [str(HOME / "sd-cli"), "--diffusion-model", str(HOME / FILES["diffusion"]), "--vae", str(HOME / FILES["vae"]), "--clip_l", str(HOME / FILES["clip_l"]),
           "--t5xxl", str(HOME / FILES["t5xxl"]), "-p", job["prompt"], "--cfg-scale", "1.0", "--sampling-method", "euler", "--steps", str(STEPS), "--offload-to-cpu", "--diffusion-fa",
           "-W", str(job["width"]), "-H", str(job["height"]), "--seed", str(job.get("seed", 1)), "-o", str(out) + ".part.png"]
    p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "LD_LIBRARY_PATH": str(HOME)}, timeout=3600)
    part = Path(str(out) + ".part.png")
    if p.returncode != 0 or not part.exists():
        part.unlink(missing_ok=True)
        raise RuntimeError("sd-cli failed: " + (p.stdout + p.stderr)[-600:])
    part.rename(out)
    return out


if __name__ == "__main__":
    for job in json.loads(Path(sys.argv[1]).read_text()):
        t = time.time()
        try:
            print("DONE", job["id"], draw(job), round(time.time() - t), "s", flush=True)
        except Exception as e:
            print("FAIL", job["id"], e, flush=True)
