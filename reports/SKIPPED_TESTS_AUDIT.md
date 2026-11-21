# Skipped tests audit (2026-11-20)

Before: the live suite had **21 skipped** tests. After this phase: **10 skipped**, each one BLOCKED on a file that only exists in the workshop. Every other skip is resolved and its test runs.

| Test(s) | Skip condition (read in the code) | Requirement | Belongs in production? | Outcome |
|---|---|---|---|---|
| 19 in `tests/test_ccbuild.py` | One module-level `pytestmark = skipif(docs/studio/flannan/short.json missing)` | The hand-written Flannan Isles Short spec | The spec is a worked example for the free Claude Code route. It was **never committed** (git history has only the test, commit `81a446e`), and it is not in `output/`, `output_old/` or `data/`. | **Defect:** 9 of the 19 never read the spec (picture fitting, cache paths, claim sources, credit lines) but were skipped with it. The skip now sits only on the 10 tests that read it (`@needs_spec`). 15 new tests check the same validator rules on a spec written for the tests: footage, follow, hook, passage, unverified, conflicting, two sources, too long, http, missing text, empty ledger, too few lines, the yes/no warning, the ledger. Mutation check: removing the https rule fails a test. **10 remain BLOCKED**: they need the real spec, which exists only in the workshop (`docs/studio/flannan/`). Transfer needs the owner's approval. |
| `tests/test_ccrender.py::test_real_render_writes_picture_and_depth` | Blender missing, or `assets/cc0/hdri` empty | Blender (present: `~/tools/blender/blender`) and the CC0 sky files | Yes, for the Blender route that runs on this PC. The files are git-ignored by design (`.gitignore` lines 49 to 51: "re-downloadable; the ledger is kept"). | **Resolved.** The 31 files listed in `assets/cc0/LEDGER.md` (4 HDRIs, 9 textures × 3 maps, 41 MB) were downloaded again from their recorded source, `dl.polyhaven.org`. Poly Haven's licence page was re-read today: "CC0 means absolute freedom". The test passes (real Blender EEVEE render with a depth map). |
| `tests/test_studio_mcp.py::test_the_server_offers_read_tools…` | `pytest.importorskip("mcp")` | The `mcp` library | The MCP server is designed to run in **its own** environment (`studio_mcp/requirements.txt`: `mcp[cli]>=2,<3`; `studio_mcp/run.sh` runs `venv/bin/python server.py`), not in the studio's `.venv`. | **Resolved without touching `.venv` or system Python.** Created `studio_mcp/venv` with `mcp 2.3.0` (Python 3.14.10) and added `studio_mcp/venv/` to `.gitignore`. With that venv's packages appended to the path, all 10 MCP tests pass. In a plain `.venv` run the test still skips by design, because the library lives in the MCP venv. |

## A production defect found on the way
- The `story-studio-rw` MCP server in `~/.claude.json` still runs `ssh -T deploy@vps-ai env STUDIO_MCP_WRITE=1 /home/deploy/studio-mcp/run.sh`. That VPS was deleted on 17 Nov, which is why the server timed out at the start of this session.
- The local gateway works: `DOCKER_CONTEXT=default studio_mcp/venv/bin/python -c "from gateway import Gateway; print(Gateway().studios())"` returns `{'owner': 'studio-worker'}`.
- **Fix (owner's command, it changes Claude Code's own settings):**
  ```
  claude mcp remove story-studio-rw
  claude mcp add story-studio-rw --scope user -e STUDIO_MCP_WRITE=1 -e DOCKER_CONTEXT=default -- /home/fahad/studio/studio_mcp/run.sh
  ```
  Without `STUDIO_MCP_WRITE=1` the server offers read tools only. Plain `docker` on this PC uses the Docker Desktop context, and the studio containers are in `default`, so the variable is set explicitly.

## How to run the MCP tests
```
cd ~/studio && SP=$(ls -d studio_mcp/venv/lib/python3*/site-packages) && .venv/bin/python -c "import sys; sys.path.append('$SP'); import pytest; sys.exit(pytest.main(['-q','tests/test_studio_mcp.py']))"
```
