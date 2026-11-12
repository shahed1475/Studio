"""tools/remote_build.py (1 Nov 2026): render on the owner's VPS in a throwaway container, in its own folder, never inside the live studio and never with a secret."""
import json
from pathlib import Path

import pytest

import tools.remote_build as rb

SECRETS = (".env", "token.json", "client_secret.json", "settings.json", "llm.json", "agent.json", "autopilot.json", "data", "output", "output_old", "backups", ".git", ".venv")


def test_the_plan_copies_only_an_allowlist_and_no_secret_or_video(tmp_path):
    plan = rb.plan("docs/studio/kappa/short.json", "ccbuild", job="kappa1", pictures=[Path("cache/cc/p-1.jpg")])
    text = " ".join(" ".join(c) for c in plan)
    assert "--include=*.py" in text and "--exclude=*" in text
    assert not any(f"--include={s}" in text for s in SECRETS)
    assert ".env" not in text.replace("--exclude=*", "")


def test_the_job_runs_in_its_own_folder_not_in_the_live_studio():
    plan = rb.plan("docs/studio/kappa/short.json", "ccbuild", job="kappa1")
    text = " ".join(" ".join(c) for c in plan)
    assert "render-jobs/kappa1" in text and "~/studio" not in text.replace("~/studio/data/models:/app/data/models:ro", "")
    assert "docker exec" not in text and "studio-worker" not in text and "restart" not in text


def test_the_container_is_throwaway_limited_and_polite():
    run = [c for c in rb.plan("docs/studio/kappa/short.json", "ccbuild", job="j") if "docker" in " ".join(c)][0]
    line = " ".join(run)
    assert "--rm" in line and "--cpus=2" in line and "--memory=4g" in line and "nice" in line and "studio:local" in line
    assert "ccbuild.py" in line and "docs/studio/kappa/short.json" in line


def test_the_mixed_look_flag_reaches_the_documentary_builder_only():
    doc = " ".join(" ".join(c) for c in rb.plan("docs/studio/ronaldo/doc.json", "ccdoc", job="r", mix=True))
    assert "ccdoc.py docs/studio/ronaldo/doc.json --mix" in doc
    with pytest.raises(ValueError):
        rb.plan("docs/studio/kappa/short.json", "ccbuild", job="j", mix=True)


def test_an_unknown_tool_or_a_job_name_that_could_escape_the_folder_is_refused():
    for bad in ("../x", "a b", "a;rm", ""):
        with pytest.raises(ValueError):
            rb.plan("docs/studio/kappa/short.json", "ccbuild", job=bad)
    with pytest.raises(ValueError):
        rb.plan("docs/studio/kappa/short.json", "rm -rf", job="ok")


def test_the_result_is_copied_into_a_staging_folder_never_straight_into_output_and_nothing_is_deleted():
    """Two machines may build the same film: a copy straight into output/ could merge into the other machine's folder."""
    plan = rb.plan("docs/studio/kappa/short.json", "ccbuild", job="kappa1")
    last = plan[-1]
    assert last[-1] == "output_remote/kappa1/" and "render-jobs/kappa1/output/" in " ".join(last)
    assert not any(c[-1] == "output/" for c in plan) and not any("rm -rf" in " ".join(c) for c in plan)


def test_the_fonts_the_thumbnails_need_are_in_the_copy_list():
    text = " ".join(" ".join(c) for c in rb.plan("docs/studio/kappa/short.json", "ccbuild", job="j"))
    assert "--include=static/***" in text and "--include=fonts/***" not in text


def test_the_container_runs_as_the_servers_own_user_so_the_owner_can_clear_the_job_folder():
    line = " ".join([c for c in rb.plan("docs/studio/kappa/short.json", "ccbuild", job="j") if "docker" in " ".join(c)][0])
    assert "--user $(id -u):$(id -g)" in line
