# Final regression (2026-11-20, live code in /home/fahad/studio)

| Suite | Command | Result |
|---|---|---|
| Full test suite | `.venv/bin/python -m pytest -q` (outside the sandbox: Chrome, ffmpeg, Blender) | **2,670 passed, 0 failed, 11 skipped** (141 s) |
| MCP server tests | `.venv/bin/python` with `studio_mcp/venv` packages appended | **10 passed** |
| Agent behaviour checks | `agenteval.run(write=False)` | **63 passed, 0 failed** (61 earlier today, plus 2 new cases) |
| Real-data guard | SHA-256 of `data/free_models.json` and `data/rules_state.json` before and after the suite and the evaluation | unchanged |

At the start of the day the suite read 2,596 passed, 2 failed (animation) and 21 skipped.

## Skipped tests, one by one
- `tests/test_ccbuild.py` lines 22, 27, 34, 41, 48, 55, 62, 69, 76 and 93 (10 tests): **BLOCKED**. They need the real Flannan Isles spec (`docs/studio/flannan/short.json`), which exists only in the workshop folder and was never committed. The same validator rules are covered by 15 fixture tests.
- `tests/test_studio_mcp.py:89`: skipped in `.venv` **by design**. The `mcp` library lives in the MCP server's own venv, where the test passes (10 of 10 above).

## New or changed tests today (none weakened)
| Area | Tests |
|---|---|
| Free Mode | `test_free_mode_no_paid_checks.py` (4, plus 3 mutation checks), agenteval free-mode case plus its mutation test |
| A2A | `test_a2a.py` (12), agenteval A2A case plus 2 mutations |
| Data hygiene | `test_race_settle.py` (protection plus the reproducing mutation), conftest session safety net |
| Documentary length | `test_doc_structure.py` (rewritten to the owner's setting; the old 8 to 10 still gives the old numbers), `test_doc_length_setting.py` (9), `test_variety`, `test_risk`, agenteval length case |
| Render | `test_render_concat.py` (GIF named .jpg, with real ffmpeg, plus mutation), `test_local_pictures.py` (finished and registered, plus mutation) |
| JSON reading | `test_llm.py` (7 new cases) |
| Doctor | `test_doctor_capacity.py` (3) |
| Fixtures for the Blender route | `test_ccbuild.py` (9 tests no longer skipped, 15 new) |
| Fakes updated to behave like the real stages | `test_motion_wiring`, `test_local_pictures`, `test_rerender_safety`: the fake voice now writes its narration file and the fake motion writes its clips, as the real ones do. The new hand-over checks require that. |

## Not run
- No real 20 to 26 minute documentary (BLOCKED; see `END_TO_END_VIDEO_TEST.md`).
