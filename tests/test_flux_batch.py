"""tools/flux_batch.py (1 Nov 2026): FLUX.1 schnell pictures drawn free on the owner's PC; the cache key names the model so it never collides with a Z-Image picture."""
import subprocess
from pathlib import Path

import pytest

import config
import tools.flux_batch as fb
import tools.zimage_batch as zb

JOB = {"id": "s01", "prompt": "a stadium", "width": 768, "height": 448, "seed": 101}


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")


def test_the_cache_path_is_stable_and_never_the_same_as_a_z_image_picture():
    assert fb.path_for(JOB) == fb.path_for(dict(JOB)) and fb.path_for(JOB).name.startswith("f-")
    assert fb.path_for(JOB) != fb.path_for({**JOB, "seed": 102}) and fb.path_for(JOB) != zb.path_for(JOB)


def test_a_picture_that_exists_is_not_drawn_again(monkeypatch):
    out = fb.path_for(JOB)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"x")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    assert fb.draw(JOB) == out


def test_the_command_uses_the_flux_files_four_steps_and_the_low_memory_flags(monkeypatch):
    seen = {}

    def run(cmd, **k):
        seen["cmd"] = cmd
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    out = fb.draw(JOB)
    c = seen["cmd"]
    assert out.exists() and not Path(str(out) + ".part.png").exists()
    assert c[c.index("--steps") + 1] == "4" and "--offload-to-cpu" in c and "--diffusion-fa" in c
    assert any(x.endswith("flux1-schnell-Q2_K.gguf") for x in c) and any(x.endswith("clip_l.safetensors") for x in c) and any("t5-v1_1-xxl" in x for x in c)
    assert c[c.index("-W") + 1] == "768" and c[c.index("-H") + 1] == "448"


def test_a_failed_run_raises_and_leaves_no_half_picture(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "boom"))
    with pytest.raises(RuntimeError, match="boom"):
        fb.draw(JOB)
    assert not fb.path_for(JOB).exists()
