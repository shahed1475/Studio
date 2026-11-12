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
    f.write_text(f"HUB_KEYSTORE_KEY={SECRET}\nHUB_PUBLIC_URL=https://hub.example.org\nHUB_ALLOWED_EMAILS=friend@example.com\nHUB_CONTACT=Ann Example, ann@example.org\n")
    os.chmod(f, 0o600)
    return {"HUB_HOME": str(tmp_path)}


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
                       env={**os.environ, "HUB_ENV_FILE": str(env_file), "HUB_DATA_DIR": str(tmp_path), "HUB_MAIL_DIR": str(tmp_path), "HUB_UID": "1000", "HUB_GID": "1000"})
    assert r.returncode == 0, r.stderr[-300:]
    svc = json.loads(r.stdout)["services"]["hub"]
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"] and svc["ports"][0]["host_ip"] == "127.0.0.1" and "network_mode" not in svc
    assert [v["target"] for v in svc["volumes"]] == ["/app/data/hub", "/hubmail"] and svc["user"] == "1000:1000"
    assert [v.get("read_only") for v in svc["volumes"]] == [None, True]  # the studio's Gmail bridge is mounted read-only


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


def test_public_launch_needs_an_https_url(home):
    assert sh("check", "--public", env=home).returncode == 0
    f = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    f.write_text(f.read_text().replace("https://", "http://"))
    assert sh("check", "--public", env=home).returncode != 0


def test_public_launch_needs_a_contact_for_the_privacy_page_and_fails_closed(home):
    f = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    f.write_text("\n".join(l for l in f.read_text().splitlines() if not l.startswith("HUB_CONTACT")) + "\n")
    os.chmod(f, 0o600)
    r = sh("check", "--public", env=home)
    assert r.returncode != 0 and "HUB_CONTACT" in r.stderr and "configure --contact" in r.stderr
    assert sh("check", env=home).returncode == 0  # a private trial does not need it
    assert "OWNER-TO-FILL" in (ROOT / "hub" / "web" / "privacy.html").read_text()  # the shipped page is a draft; the server fills the contact in from HUB_CONTACT


# ---- putting the hub into the studio's web proxy file ----
STUDIO_CADDY = 'srv2029460.hstgr.cloud {\n  @t_test header_regexp tc Cookie (^|;\\s*)studio_tenant=test(;|$)\n  handle @t_test {\n    reverse_proxy 127.0.0.1:18922\n  }\n}\n'


def merged(src, host="hub.example.org"):
    r = sh("caddy-merge", str(src), env={"HUB_HOST": host})
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_merge_keeps_the_studios_routes_byte_for_byte_and_adds_one_marked_hub_block(tmp_path):
    f = tmp_path / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    out = merged(f)
    assert out.startswith(STUDIO_CADDY.rstrip("\n")) and out.count("# >>> creator-hub") == 1 and out.count("# <<< creator-hub") == 1
    assert "hub.example.org {" in out and "reverse_proxy 127.0.0.1:8931" in out
    assert f.read_text() == STUDIO_CADDY  # merge only prints: it never writes


def test_merge_twice_gives_the_same_file_and_a_new_host_replaces_the_old_one(tmp_path):
    f = tmp_path / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    once = merged(f)
    f.write_text(once)
    assert merged(f) == once  # idempotent: no growing blank lines, no second block
    f.write_text(once)
    moved = merged(f, "other.example.org")
    assert "other.example.org {" in moved and "hub.example.org" not in moved and moved.count("# >>> creator-hub") == 1 and moved.startswith(STUDIO_CADDY.rstrip("\n"))


def test_merge_refuses_a_bad_host_and_a_missing_file(tmp_path):
    f = tmp_path / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    r = sh("caddy-merge", str(f), env={"HUB_HOST": "evil.com {\n respond 200"})
    assert r.returncode != 0 and r.stdout == ""
    assert sh("caddy-merge", str(tmp_path / "nope"), env={"HUB_HOST": "hub.example.org"}).returncode != 0


def test_apply_checks_first_validates_with_real_caddy_edits_in_place_and_reloads_gracefully(home, tmp_path):
    (tmp_path / "tenants" / "caddy").mkdir(parents=True)
    f = tmp_path / "tenants" / "caddy" / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    r = sh("caddy-apply", "--public", env={**home, "HUB_HOST": "hub.example.org", "TENANTS_DIR": str(tmp_path / "tenants"), "DRY": "1"})
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "caddy validate" in out and "caddy reload" in out and "studio-proxy" in out
    assert out.index("caddy validate") < out.index("caddy reload")  # validated before the proxy is asked to reload
    assert f.read_text() == STUDIO_CADDY and not list(f.parent.glob(".hub-candidate*"))  # a dry run changes nothing and leaves nothing


def test_apply_refuses_when_the_hub_is_not_ready_to_be_public(home, tmp_path):
    (tmp_path / "tenants" / "caddy").mkdir(parents=True)
    f = tmp_path / "tenants" / "caddy" / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    envf = Path(home["HUB_HOME"]) / "secrets" / "hub.env"
    envf.write_text(envf.read_text() + "HUB_INSECURE_DEV=1\n")
    r = sh("caddy-apply", "--public", env={**home, "HUB_HOST": "hub.example.org", "TENANTS_DIR": str(tmp_path / "tenants"), "DRY": "1"})
    assert r.returncode != 0 and "HUB_INSECURE_DEV" in r.stderr and f.read_text() == STUDIO_CADDY


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


def test_restart_recreates_the_container_so_changed_settings_are_read(home):
    r = sh("restart", env={**home, "DRY": "1"})
    assert r.returncode == 0 and "--force-recreate" in r.stdout and SECRET not in r.stdout


def test_configure_runs_the_prompt_in_a_locked_down_throwaway_container(home):
    r = sh("configure", env={**home, "DRY": "1"})
    assert r.returncode == 0 and "hub.configure" in r.stdout and "--read-only" in r.stdout and "--cap-drop ALL" in r.stdout and "/secrets/hub.env" in r.stdout and SECRET not in r.stdout


@pytest.fixture()
def fake_docker(tmp_path):
    """A stand-in `docker` that records its calls and can be told to refuse: so the real apply flow runs end to end without touching any proxy."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    log = tmp_path / "docker.log"
    script = bindir / "docker"
    script.write_text('#!/usr/bin/env bash\necho "$1 $*" >> "$FAKE_DOCKER_LOG"\n'
                      'case "$1" in\n  run) [[ "${FAKE_VALIDATE:-ok}" == ok ]] && { echo "Valid configuration"; exit 0; } || { echo "bad config" >&2; exit 1; } ;;\n'
                      '  exec) [[ "${FAKE_RELOAD:-ok}" == ok ]] && exit 0 || { echo "reload refused" >&2; exit 1; } ;;\nesac\nexit 0\n')
    os.chmod(script, 0o755)
    return {"PATH": f"{bindir}:{os.environ['PATH']}", "FAKE_DOCKER_LOG": str(log)}, log


def proxy_setup(tmp_path):
    (tmp_path / "tenants" / "caddy").mkdir(parents=True)
    f = tmp_path / "tenants" / "caddy" / "Caddyfile"
    f.write_text(STUDIO_CADDY)
    return f


def test_apply_end_to_end_edits_in_place_keeps_a_backup_and_cleans_up(home, tmp_path, fake_docker):
    env, log = fake_docker
    f = proxy_setup(tmp_path)
    inode = f.stat().st_ino
    r = sh("caddy-apply", "--public", env={**home, **env, "HUB_HOST": "hub.example.org", "TENANTS_DIR": str(tmp_path / "tenants")})
    assert r.returncode == 0, r.stderr
    assert f.read_text().startswith(STUDIO_CADDY.rstrip("\n")) and "hub.example.org {" in f.read_text()
    assert f.stat().st_ino == inode  # written IN PLACE: the proxy container bind-mounts this one file, a rename would leave it reading the old content
    assert (f.parent / "Caddyfile.bak-before-hub").read_text() == STUDIO_CADDY
    calls = log.read_text().splitlines()
    assert [c.split()[0] for c in calls] == ["run", "exec"] and "caddy validate" in calls[0] and "studio-proxy caddy reload" in calls[1]
    assert not [p for p in f.parent.iterdir() if p.name.startswith(".hub-")]


def test_a_refused_reload_puts_the_old_proxy_file_back(home, tmp_path, fake_docker):
    env, log = fake_docker
    f = proxy_setup(tmp_path)
    inode = f.stat().st_ino
    r = sh("caddy-apply", "--public", env={**home, **env, "FAKE_RELOAD": "refuse", "HUB_HOST": "hub.example.org", "TENANTS_DIR": str(tmp_path / "tenants")})
    assert r.returncode != 0 and "old file is back" in r.stderr
    assert f.read_text() == STUDIO_CADDY and f.stat().st_ino == inode and not [p for p in f.parent.iterdir() if p.name.startswith(".hub-")]


def test_a_failed_validation_changes_nothing_and_never_reloads(home, tmp_path, fake_docker):
    env, log = fake_docker
    f = proxy_setup(tmp_path)
    r = sh("caddy-apply", "--public", env={**home, **env, "FAKE_VALIDATE": "fail", "HUB_HOST": "hub.example.org", "TENANTS_DIR": str(tmp_path / "tenants")})
    assert r.returncode != 0 and "did not validate" in r.stderr and f.read_text() == STUDIO_CADDY
    assert [c.split()[0] for c in log.read_text().splitlines()] == ["run"] and not (f.parent / "Caddyfile.bak-before-hub").exists()


def test_the_script_is_executable_python_free_bash_and_parses():
    assert os.access(SH, os.X_OK)
    assert subprocess.run(["bash", "-n", str(SH)], capture_output=True).returncode == 0
