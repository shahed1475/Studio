"""The hub's container files and deploy script (deploy/Dockerfile.hub, hub-compose.yml, hub.sh). Nothing here starts a container or touches a server."""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "deploy"
SH = D / "hub.sh"
SECRET = "supersecretvalue-do-not-print"


def sh(*args, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HUB_") and k != "DRY"}
    e.update(env or {})
    return subprocess.run(["bash", str(SH), *args], capture_output=True, text=True, env=e, cwd=ROOT)


@pytest.fixture()
def home(tmp_path):
    (tmp_path / "secrets").mkdir()
    f = tmp_path / "secrets" / "hub.env"
    f.write_text(f"HUB_KEYSTORE_KEY={SECRET}\nHUB_PUBLIC_URL=https://hub.example.org\nHUB_ALLOWED_EMAILS=friend@example.com\n")
    os.chmod(f, 0o600)
    clean = tmp_path / "privacy.html"
    clean.write_text("<html>Contact: owner@example.org</html>")
    return {"HUB_HOME": str(tmp_path), "HUB_PRIVACY_FILE": str(clean)}


# ---- the image ----
def test_the_image_copies_exactly_the_studio_modules_the_hub_imports():
    code = ("import os, sys; import hub.server, hub.configure, hub.keystore, hub.llm, niche, wikipedia; import google.oauth2.id_token, google.auth.transport.requests; "
            "r = os.getcwd(); print(' '.join(sorted(os.path.basename(m.__file__) for m in sys.modules.values() if getattr(m, '__file__', None) and os.path.dirname(m.__file__) == r)))")
    needed = set(subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, cwd=ROOT, check=True).stdout.split())
    docker = (D / "Dockerfile.hub").read_text()
    copied = {w for line in docker.splitlines() if line.startswith("COPY ") for w in line.split()[1:-1] if w.endswith(".py")}
    assert needed and needed == copied, (needed ^ copied)


def test_the_image_is_small_and_has_no_secrets_or_studio_code():
    docker = (D / "Dockerfile.hub").read_text()
    assert "COPY . " not in docker and "ADD " not in docker and "apt-get" not in docker and "USER 1000" in docker and 'CMD ["python", "-m", "hub.server"]' in docker
    assert not any(w in docker for w in (".env", "token", "client_secret", "dashboard.py", "worker.py"))
    req = (D / "hub-requirements.txt").read_text().lower()
    assert all(p in req for p in ("requests", "cryptography", "google-auth")) and not any(p in req for p in ("pytest", "numpy", "onnxruntime", "pillow", "edge-tts"))


def test_the_studios_own_requirements_are_not_changed_by_the_hub():
    assert "cryptography" not in (ROOT / "requirements.txt").read_text()  # a change there rebuilds the owner's containers at the next deploy (deploy/deploy.sh)


# ---- the container ----
def test_compose_is_locked_down():
    c = (D / "hub-compose.yml").read_text()
    for must in ("read_only: true", "cap_drop: [ALL]", "no-new-privileges:true", "mem_limit:", "cpus:", "pids_limit:", '"127.0.0.1:'):
        assert must in c, must
    assert "network_mode" not in c and ".:/app" not in c and "HUB_INSECURE_DEV" not in c and "privileged" not in c


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_compose_file_is_valid_and_rendered_settings_are_locked_down(tmp_path):
    env_file = tmp_path / "hub.env"
    env_file.write_text("HUB_KEYSTORE_KEY=x\n")
    r = subprocess.run(["docker", "compose", "-f", str(D / "hub-compose.yml"), "config", "--format", "json"], capture_output=True, text=True,
                       env={**os.environ, "HUB_ENV_FILE": str(env_file), "HUB_DATA_DIR": str(tmp_path), "HUB_UID": "1000", "HUB_GID": "1000"})
    assert r.returncode == 0, r.stderr[-300:]
    svc = json.loads(r.stdout)["services"]["hub"]
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"] and svc["ports"][0]["host_ip"] == "127.0.0.1" and "network_mode" not in svc
    assert [v["target"] for v in svc["volumes"]] == ["/app/data/hub"] and svc["user"] == "1000:1000"


# ---- hub.sh ----
def test_caddy_block_for_a_good_host_and_refusal_of_a_bad_one():
    ok = sh("caddy-block", env={"HUB_HOST": "hub.example.org"})
    assert ok.returncode == 0 and "hub.example.org {" in ok.stdout and "reverse_proxy 127.0.0.1:8931" in ok.stdout
    for bad in ("", "hub", "evil.com {\n respond 200", "a b.example", "Hub.Example.org;rm", "x.example\nrespond", "-x.example"):
        r = sh("caddy-block", env={"HUB_HOST": bad})
        assert r.returncode != 0 and r.stdout == "", repr(bad)


def test_the_studio_proxy_generator_includes_the_hub_block_only_when_a_host_is_set():
    t = (D / "tenant.sh").read_text()
    assert 'HUB_HOST' in t and "hub.sh" in t and "caddy-block" in t


def test_check_accepts_a_good_private_setup_and_never_prints_a_value(home):
    r = sh("check", env=home)
    assert r.returncode == 0 and SECRET not in r.stdout + r.stderr


def test_check_refuses_an_env_file_others_can_read(home):
    os.chmod(Path(home["HUB_HOME"]) / "secrets" / "hub.env", 0o644)
    r = sh("check", env=home)
    assert r.returncode != 0 and "600" in r.stderr and SECRET not in r.stdout + r.stderr


def test_check_refuses_a_missing_master_key_by_name(home):
    f = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    f.write_text("HUB_PUBLIC_URL=https://hub.example.org\n")
    os.chmod(f, 0o600)
    r = sh("check", env=home)
    assert r.returncode != 0 and "HUB_KEYSTORE_KEY" in r.stderr


def test_check_refuses_when_there_is_no_env_file(tmp_path):
    r = sh("check", env={"HUB_HOME": str(tmp_path)})
    assert r.returncode != 0 and "hub.env" in r.stderr


def test_public_launch_refuses_the_insecure_dev_flag(home):
    f = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    f.write_text(f.read_text() + "HUB_INSECURE_DEV=1\n")
    assert sh("check", "--public", env=home).returncode != 0
    assert sh("check", env=home).returncode == 0  # a private trial on this machine may use it


def test_public_launch_needs_https_url_and_a_finished_privacy_page(home):
    assert sh("check", "--public", env=home).returncode == 0
    bad_url = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    bad_url.write_text(bad_url.read_text().replace("https://", "http://"))
    assert sh("check", "--public", env=home).returncode != 0
    bad_url.write_text(bad_url.read_text().replace("http://", "https://"))
    Path(home["HUB_PRIVACY_FILE"]).write_text("Contact: OWNER-TO-FILL")
    r = sh("check", "--public", env=home)
    assert r.returncode != 0 and "OWNER-TO-FILL" in r.stderr
    assert "OWNER-TO-FILL" in (ROOT / "hub" / "web" / "privacy.html").read_text()  # the shipped page is still a draft until the owner fills it


def test_open_sign_up_is_an_explicit_choice(home):
    f = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    f.write_text("\n".join(l for l in f.read_text().splitlines() if not l.startswith("HUB_ALLOWED_EMAILS")) + "\n")
    os.chmod(f, 0o600)
    r = sh("check", "--public", env=home)
    assert r.returncode != 0 and "--open" in r.stderr
    assert sh("check", "--public", "--open", env=home).returncode == 0


def test_dry_run_prints_the_commands_and_runs_nothing(home):
    r = sh("up", env={**home, "DRY": "1"})
    assert r.returncode == 0 and "DRY:" in r.stdout and "docker" in r.stdout and SECRET not in r.stdout
    assert not (Path(home["HUB_HOME"]) / "data").exists()  # a dry run creates nothing


def test_the_script_is_executable_python_free_bash_and_parses():
    assert os.access(SH, os.X_OK)
    assert subprocess.run(["bash", "-n", str(SH)], capture_output=True).returncode == 0
