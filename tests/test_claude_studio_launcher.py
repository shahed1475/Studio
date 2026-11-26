"""tools/claude-studio.sh starts Claude Code in ~/studio with a clean environment, and refuses otherwise.

The launcher is hard-wired to /home/fahad/studio (the owner's PC), so these tests run only there. Each run gets an
empty environment plus a fake `docker` and a fake `claude` on PATH: no daemon, no Claude session and no network is
touched. STUDIO_LAUNCHER_UNDER_TEST points the tests at another copy (used for mutation checks against old versions).
"""
import os
import subprocess
from pathlib import Path

import pytest

STUDIO = Path("/home/fahad/studio")
LAUNCHER = Path(os.environ.get("STUDIO_LAUNCHER_UNDER_TEST", STUDIO / "tools" / "claude-studio.sh"))
FORBIDDEN = "/home/fahad/Desktop/Youtube-automation"

pytestmark = pytest.mark.skipif(
    not (LAUNCHER.exists() and (STUDIO / ".venv" / "bin" / "python3").exists()),
    reason="the launcher and the studio venv exist only on the owner's PC",
)

# What the fake docker answers for `inspect studio-worker`.
WORKER = {
    "mounted": "echo /home/fahad/studio",
    "absent": 'echo "Error: No such object: studio-worker" >&2; exit 1',
    "denied": 'echo "permission denied while trying to connect to the docker API at unix:///var/run/docker.sock" >&2; exit 1',
    "elsewhere": "echo /srv/other",
}


def _tool(folder, name, body):
    path = folder / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


def _run(tmp_path, worker="mounted", args=(), extra_env=None):
    fake = tmp_path / "bin"
    fake.mkdir()
    _tool(fake, "docker", (
        'case "$*" in\n'
        '  "context inspect default"*) echo unix:///var/run/docker.sock ;;\n'
        f'  *"inspect studio-worker"*) {WORKER[worker]} ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n"
    ))
    started = tmp_path / "claude-started"
    _tool(fake, "claude", f'pwd -P > "{started}"\n')
    env = {"HOME": str(tmp_path), "PATH": f"{fake}:/usr/bin:/bin"}
    env.update(extra_env or {})
    result = subprocess.run(["bash", str(LAUNCHER), *args], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)
    return result, started


def test_launcher_syntax():
    assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0


def test_check_passes_when_the_worker_mounts_studio(tmp_path):
    result, started = _run(tmp_path, "mounted", ["--check"])
    assert result.returncode == 0, result.stderr
    assert "cwd:            /home/fahad/studio" in result.stdout
    assert "/app <- /home/fahad/studio" in result.stdout
    assert not started.exists()


def test_check_passes_when_the_worker_is_not_running(tmp_path):
    result, _ = _run(tmp_path, "absent", ["--check"])
    assert result.returncode == 0, result.stderr
    assert "/app <- not running" in result.stdout


def test_launch_starts_claude_in_studio(tmp_path):
    result, started = _run(tmp_path, "mounted")
    assert result.returncode == 0, result.stderr
    assert started.read_text().strip() == "/home/fahad/studio"


@pytest.mark.parametrize("args", [(), ("--check",)])
def test_refuses_when_docker_cannot_be_asked(tmp_path, args):
    # Fail closed: an unreachable or forbidden daemon is not "not running".
    result, started = _run(tmp_path, "denied", args)
    assert result.returncode == 1
    assert "cannot ask the default docker daemon" in result.stderr
    assert "permission denied" in result.stderr
    assert not started.exists()


def test_refuses_a_worker_that_mounts_another_folder(tmp_path):
    result, started = _run(tmp_path, "elsewhere")
    assert result.returncode == 1
    assert "/srv/other" in result.stderr
    assert not started.exists()


@pytest.mark.parametrize("args", [(), ("--check",)])
def test_refuses_inside_a_claude_code_session(tmp_path, args):
    result, started = _run(tmp_path, "mounted", args, {"CLAUDECODE": "1"})
    assert result.returncode == 1
    assert "running Claude Code session" in result.stderr
    assert "normal terminal" in result.stderr
    assert not started.exists()


def test_refuses_a_variable_that_points_at_the_forbidden_folder(tmp_path):
    result, started = _run(tmp_path, "mounted", (), {"LEFTOVER_DIR": FORBIDDEN + "/x"})
    assert result.returncode == 1
    assert "LEFTOVER_DIR" in result.stderr
    assert not started.exists()
