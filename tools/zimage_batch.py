"""Draw pictures with Z-Image-Turbo (stable-diffusion.cpp, free, local) for a video made in a Claude Code session (1 Nov 2026).
Usage: python tools/zimage_batch.py jobs.json   (a list of {"id", "prompt", "width", "height", "seed"}). Sequential (one 4 GB card), skips a job whose picture exists,
writes cache/cc/z-<hash>.png and prints "DONE <id> <path> <seconds>". Models in ~/tools/sdcpp (Apache-2.0 weights, see docs/superpowers/plans/2026-11-01-claude-code-video-workflow.md)."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import config

HOME = Path(os.environ.get("SDCPP") or Path.home() / "tools" / "sdcpp")
MODELS = {"diffusion": "z_image_turbo-Q3_K.gguf", "llm": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "vae": "ae.safetensors"}
STEPS = 8


def path_for(job: dict) -> Path:
    key = json.dumps([job["prompt"], job["width"], job["height"], job.get("seed", 1), MODELS["diffusion"], STEPS], sort_keys=True)
    d = Path(config.CACHE) / "cc"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"z-{hashlib.sha256(key.encode()).hexdigest()[:16]}.png"


def draw(job: dict) -> Path:
    out = path_for(job)
    if out.exists():
        return out
    cmd = [str(HOME / "sd-cli"), "--diffusion-model", str(HOME / "models" / MODELS["diffusion"]), "--vae", str(HOME / "models" / MODELS["vae"]),
           "--llm", str(HOME / "models" / MODELS["llm"]), "-p", job["prompt"], "--cfg-scale", "1.0", "--offload-to-cpu", "--diffusion-fa",
           "-W", str(job["width"]), "-H", str(job["height"]), "--steps", str(STEPS), "--seed", str(job.get("seed", 1)), "-o", str(out) + ".part.png"]
    p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "LD_LIBRARY_PATH": str(HOME)}, timeout=3600)
    part = Path(str(out) + ".part.png")
    if p.returncode != 0 or not part.exists():
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
