# Execution checkpoint

Task: the owner's "Studio Suite complete production audit" prompt (20 Nov 2026). Production folder: `/home/fahad/studio`. The workshop on the Desktop is off-limits.

| Phase | State | Report |
|---|---|---|
| 0 Baseline | done | PRODUCTION_BASELINE.md |
| 1 Reconciliation | done | CODEBASE_RECONCILIATION.md |
| 2 Skipped tests | done (21 to 10 skipped; 10 BLOCKED on the workshop-only Flannan spec) | SKIPPED_TESTS_AUDIT.md |
| 3 Pipeline audit | done: doc length 20 to 26 from rules.json; GIF-as-jpg render fix | PIPELINE_AUDIT.md |
| 4 Free models | done: 3 paid leaks gated, parse_json, test/eval pollution of data files fixed and data restored | FREE_MODEL_OPTIMIZATION.md |
| 5 A2A | done: a2a.py (cards, contract tasks, stage hand-overs in _produce_doc) | A2A_ARCHITECTURE_AUDIT.md, A2A_INTEGRATION_TESTS.md |
| 6 Doctor | done: disk request, provider status | DOCTOR_AGENT_AUDIT.md |
| 7 Tasks / duration | done: Autopilot > Rules length control, saved through rulesfile, worker reads 20-26 | TASK_AUTOPILOT_AUDIT.md |
| 8 Dashboard | done: restarted, every page clicked (POSTs refused), length persisted across restart | DASHBOARD_FULL_AUDIT.md |
| 9 End-to-end video | fixture film done (found and fixed local-pictures crash); real 20-26 min film BLOCKED (1 free model, owner switch, pending Pyramids script) | END_TO_END_VIDEO_TEST.md |
| 10 Regression | done: 2670 passed, 0 failed, 11 skipped; agenteval 63/63 | FINAL_REGRESSION_REPORT.md |

## Files changed so far (all uncommitted)
- `tests/test_ccbuild.py`: skip scoped to the 10 spec tests, plus 15 fixture tests.
- `.gitignore`: `studio_mcp/venv/`.
- New, git-ignored: `studio_mcp/venv/` (mcp 2.3.0) and `assets/cc0/hdri`, `assets/cc0/tex` (Poly Haven CC0).
- Earlier on 20 Nov: `run.py`, `animate.py`, `tests/test_animation.py`, `tests/test_render_concat.py`, the Competitor removal.
- Backups: `backups/removed-competitor-20nov/*.bak`.

## Do not repeat
- Baseline commands. The CC0 download (the files are present).
- Creating the MCP venv (it exists).

## Status at the end of 20 Nov
All phases done or classified. Remaining: owner decisions in the master report. On resume: do not re-download the CC0 files, do not rebuild studio_mcp/venv, do not rerun the fixture film.
