"""The studio runs on the owner's PC since 17 Nov 2026: deploy.sh must work with STUDIO_VPS=local (no ssh), and the home override must keep the desktop first."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_home_override_gives_the_desktop_priority():
    o = yaml.safe_load((ROOT / "deploy/home-compose.yml").read_text())["services"]
    assert o["worker"]["cpus"] == 3 and o["dashboard"]["cpus"] == 2
    for s in ("worker", "dashboard"):
        assert o[s]["cpu_shares"] == 256 and o[s]["oom_score_adj"] == 500


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


@pytest.mark.skipif(not shutil.which("git"), reason="git missing")
def test_deploy_dry_runs_locally_without_ssh(tmp_path):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "w"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "one")
    _git(work, "push", "-q", "origin", "HEAD:main")
    home = tmp_path / "home"
    home.mkdir()
    _git(tmp_path, "clone", "-q", str(origin), str(home / "studio"))
    _git(work, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "two")
    _git(work, "push", "-q", "origin", "HEAD:main")
    env = {**os.environ, "HOME": str(home), "STUDIO_VPS": "local", "PATH": os.environ["PATH"]}
    r = subprocess.run(["bash", str(ROOT / "deploy/deploy.sh"), "dry"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "DRY RUN" in r.stdout and "Fast-forward: yes" in r.stdout


def test_local_deploy_uses_the_native_docker_engine_not_docker_desktop(tmp_path):
    """Docker Desktop runs containers in a VM that starts only at login and hides host networking: the studio uses Fedora's own engine."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "w"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "one")
    _git(work, "push", "-q", "origin", "HEAD:main")
    home = tmp_path / "home"
    home.mkdir()
    _git(tmp_path, "clone", "-q", str(origin), str(home / "studio"))
    fake = tmp_path / "bin"
    fake.mkdir()
    seen = tmp_path / "ctx"
    (fake / "docker").write_text(f'#!/bin/sh\necho "$DOCKER_CONTEXT" >> {seen}\n')
    (fake / "docker").chmod(0o755)
    env = {**os.environ, "HOME": str(home), "STUDIO_VPS": "local", "PATH": f"{fake}:{os.environ['PATH']}", "DOCKER_CONTEXT": "desktop-linux"}
    subprocess.run(["bash", str(ROOT / "deploy/deploy.sh"), "dry"], env=env, capture_output=True, text=True, timeout=60)
    assert seen.exists() and set(seen.read_text().split()) == {"default"}


def test_deploy_without_a_target_refuses():
    env = {k: v for k, v in os.environ.items() if k != "STUDIO_VPS"}
    r = subprocess.run(["bash", str(ROOT / "deploy/deploy.sh"), "dry"], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode != 0 and "STUDIO_VPS" in r.stderr


def test_local_deploy_without_the_server_folder_fails(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "STUDIO_VPS": "local"}
    r = subprocess.run(["bash", str(ROOT / "deploy/deploy.sh"), "dry"], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode != 0


def test_first_refuses_local():
    r = subprocess.run(["bash", str(ROOT / "deploy/deploy.sh"), "first"], env={**os.environ, "STUDIO_VPS": "local"}, capture_output=True, text=True, timeout=30)
    assert r.returncode != 0 and "local" in (r.stdout + r.stderr)
