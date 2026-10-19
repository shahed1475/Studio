import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILLS = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    assert m, f"{path} has no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if _ and not line.startswith((" ", "\t", "-")):
            out[k.strip()] = v.strip().strip('"')
    return out


def test_there_are_skills():
    names = {p.parent.name for p in SKILLS}
    assert {"youtube-fact-check", "studio-qa-video", "studio-packaging", "studio-deploy", "watch", "youtube-shorts-automation", "youtube-research", "youtube-scriptwriter", "youtube-copyright-check", "youtube-video-editor", "youtube-quality-gate", "youtube-publisher"} <= names


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_follows_the_agent_skills_format(path):
    fm = frontmatter(path)
    assert fm["name"] == path.parent.name and re.fullmatch(r"[a-z0-9-]{1,64}", fm["name"])
    assert 20 <= len(fm["description"]) <= 1024 and "<" not in fm["description"] and ">" not in fm["description"]
    assert len(path.read_text().splitlines()) <= 500  # keep the body short; details go in separate files


@pytest.mark.parametrize("path", [p for p in SKILLS if p.parent.name.startswith(("studio-", "youtube-")) and p.parent.name != "youtube-shorts-automation"], ids=lambda p: p.parent.name)
def test_studio_skills_only_name_code_that_exists(path):
    for name in set(re.findall(r"`([a-z_]+\.py)`", path.read_text())):
        assert (ROOT / name).exists(), f"{path.parent.name} mentions {name}, which does not exist"
    for func in re.findall(r"`((?:seo|fixer|webcheck|thumbnail|wikipedia)\.[a-z_]+)(?:\(|`)", path.read_text()):
        module, attr = func.split(".")
        assert hasattr(__import__(module), attr), f"{path.parent.name} mentions {func}, which does not exist"


def test_the_vendored_watch_skill_has_no_marketplace_hook_and_records_its_source():
    d = ROOT / ".claude" / "skills" / "watch"
    assert "bradautomates" in (d / "VENDORED.md").read_text() and "0be1933" in (d / "VENDORED.md").read_text()
    assert not (d / "hooks").exists() and not (d / "scripts" / "build-skill.sh").exists()


SCRIPTS = sorted((ROOT / ".claude" / "skills").glob("youtube-*/scripts/*.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_skill_scripts_are_executable_and_every_command_in_the_skill_names_a_real_script(script):
    import os
    assert os.access(script, os.X_OK) and script.read_text().startswith("#!/usr/bin/env python3")
    skill = (script.parent.parent / "SKILL.md").read_text()
    assert f"scripts/{script.name}" in skill, f"{script.parent.parent.name} never mentions scripts/{script.name}"


def test_skill_scripts_run_and_report_a_missing_video_with_exit_code_2(tmp_path):
    import subprocess
    import sys
    for s in SCRIPTS:
        if s.name == "inspect.py":
            continue
        r = subprocess.run([sys.executable, str(s), "no-such-video-slug"], capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 2, f"{s.name}: exit {r.returncode}: {r.stderr[-200:]}{r.stdout[-200:]}"
