"""Render a film on the owner's VPS (1 Nov 2026: "you can use my vps for render").
Usage: PYTHONPATH=. python tools/remote_build.py SPEC --tool ccbuild|ccdoc --job NAME [--mix] [--run]
Without --run it only prints the commands (a dry run). With --run it:
  1. copies an ALLOWLIST of the code (root *.py, tools, config, fonts, playbooks, branding) and the spec's own folder to ~/render-jobs/NAME on the VPS: never .env, tokens, settings, data, output or git;
  2. copies the pictures the spec names (made on this PC: the VPS has no GPU) into that folder's cache/cc;
  3. runs the builder in a THROWAWAY container of the studio image (`studio:local`, which has ffmpeg, numpy, onnxruntime, edge-tts), limited to 2 CPUs and 4 GB and run at low priority, so the live
     Autopilot (the worker has 4 CPUs and 3 GB) is not disturbed; the container never touches ~/studio except the depth model, read-only;
  4. copies the finished folder back into output_remote/NAME/ on this PC (never straight into output/: two machines may build the same film; the owner or the assistant moves it). The job folder on the VPS is left for the owner to clear (nothing here deletes anything).
Nothing here restarts, execs into or edits the live containers."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HOST = "deploy@vps-ai"
REMOTE = "~/render-jobs"
TOOLS = ("ccbuild", "ccdoc")
ALLOW = ("--include=*.py", "--include=tools/***", "--include=config/***", "--include=static/***", "--include=playbooks/***", "--include=branding/***", "--exclude=__pycache__", "--exclude=*")


def plan(spec: str, tool: str, job: str, mix: bool = False, pictures: list | None = None) -> list[list[str]]:
    if tool not in TOOLS:
        raise ValueError(f"tool must be one of {TOOLS}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", job or ""):
        raise ValueError("job name: lower-case letters, digits, - and _ only")
    if mix and tool != "ccdoc":
        raise ValueError("--mix belongs to ccdoc")
    folder = str(Path(spec).parent)
    dest = f"{HOST}:{REMOTE}/{job}"
    cmds = [["ssh", HOST, f"mkdir -p {REMOTE}/{job}"],
            ["rsync", "-a", *ALLOW, "./", f"{dest}/"],
            ["rsync", "-a", "--mkpath", "--exclude=preview", f"{folder}/", f"{dest}/{folder}/"]]
    if pictures:
        cmds.append(["rsync", "-a", "--mkpath", *[str(p) for p in pictures], f"{dest}/cache/cc/"])
    run = (f"docker run --rm --user $(id -u):$(id -g) --cpus=2 --memory=4g -v {REMOTE}/{job}:/app -v ~/studio/data/models:/app/data/models:ro -w /app studio:local "
           f"nice -n 10 python {tool}.py {spec}" + (" --mix" if mix else ""))
    cmds.append(["ssh", HOST, run])
    cmds.append(["rsync", "-a", "--mkpath", f"{dest}/output/", f"output_remote/{job}/"])
    return cmds


def pictures_for(spec_path: str, tool: str, mix: bool = False) -> list[Path]:
    """The picture files on this PC that the spec's lines (and the thumbnail) name."""
    p = Path(spec_path).resolve()
    spec = json.loads(p.read_text())
    if tool == "ccdoc":
        import ccdoc

        jobs = ccdoc.load_jobs(p.parent)
        spec = ccdoc.mixed(spec, jobs) if mix else spec
        ids = [l["picture"] for l in spec["lines"]] + ([spec["thumb_picture"] + ("z" if mix and spec["thumb_picture"] + "z" in jobs else "")] if spec.get("thumb_picture") else [])
        paths = [ccdoc.resolve(i, p.parent, jobs) for i in dict.fromkeys(ids)]
    else:
        import ccbuild

        jobs = ccbuild.load_jobs(p.parent)
        paths = [ccbuild.resolve(l["picture"], jobs) for l in spec["lines"]]
    return [Path(x) for x in dict.fromkeys(paths) if Path(x).exists()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--tool", required=True, choices=TOOLS)
    ap.add_argument("--job", required=True)
    ap.add_argument("--mix", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    cmds = plan(a.spec, a.tool, a.job, a.mix, pictures_for(a.spec, a.tool, a.mix))
    for c in cmds:
        print("$", " ".join(c))
        if a.run:
            subprocess.run(c, check=True)
    if not a.run:
        print("(dry run: add --run to execute)")
    sys.exit(0)
