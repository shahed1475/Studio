# 07 — Startup verification

Status: PARTIAL (26 Nov 2026). What was run and its real result:

| Check | Result |
|---|---|
| `bash -n tools/claude-studio.sh` | pass |
| `tests/test_claude_studio_launcher.py` (10 cases) | 10 passed |
| Mutation check: same tests against the old launcher (`0e0aebd`) | exactly the 4 cases for the two new rules fail, 6 pass |
| Live `--check` from a session started in the forbidden folder | refuses: "this shell belongs to a running Claude Code session ... Exit Claude Code, open a normal terminal and run: bash /home/fahad/studio/tools/claude-studio.sh" |
| `~/.claude/settings.json` after R3 | valid JSON; parsed content equals the backup minus `permissions.additional_directories` |
| Full suite, clean checkout of `76dcbcf`, sandboxed | 2955 passed, 14 failed, 47 errors (the errors: headless Chrome cannot start in the sandbox) |
| Full suite, clean checkout of `76dcbcf`, outside the sandbox | **3012 passed, 4 failed**, 13 skipped |
| The 4 failing tests on GitHub `main` (`92d2572`) and on `f20bba1` | **4 failed on both**: they predate this work |

The 4 pre-existing failures: `test_agents_training.py::test_every_behaviour_check_of_the_agents_passes`,
`test_judges.py::test_every_judge_failing_or_used_up_is_unreviewed_never_pass_and_never_fail`,
`test_judges.py::test_agenteval_cascade_case_passes_and_fails_when_a_rule_is_broken` (a failed judge gives `fail`
where `unreviewed` is expected), `test_live_ui.py::test_the_notification_routes_answer_and_read_marks_the_feed`.

## Services (F11), done 26 Nov with the owner's "fix the services too"

Backups: `~/.config/systemd/user/backup-2026-11-26/`. `yt-dlp` 2026.11.23 installed in Studio's venv
(`docs/MY_DOWNLOADS.md`). `story-newswatch.timer` disabled and stopped (the worker runs newswatch). `studio-mydownloads`
now runs `/home/fahad/studio/.venv/bin/python -m mydownloads` in `/home/fahad/studio`: active, `GET /` on 127.0.0.1:8923
returns 200. `story-autopilot.timer` stays disabled, unit untouched.

## Not verified (the owner's step)

Launching from a normal terminal: `bash /home/fahad/studio/tools/claude-studio.sh --check`, then without `--check`.
Expected: exit 0, `cwd: /home/fahad/studio`, the real `studio-worker` mount `/home/fahad/studio`.

## Push (done 26 Nov, owner: "commit it, test, push")

The 4 failures were fixed by committing the live, uncommitted work that already fixed them, as `0ffb10f` (51 paths:
judge cascade, scene manifest, compute router code, ten routing skills, their tests). The notification test had a stale
assertion (`badge >= 2`, true only with live data) and now checks `attention == 1`; a mutation that counts every event
fails it. Clean checkout of exactly that tree, outside the sandbox: **3129 passed, 0 failed, 13 skipped**. The commit
was compared with the tested tree file by file: 0 content differences.

Pushed: `92d2572..0ffb10f` (7 commits, fast-forward). GitHub `main` = local `0ffb10f`. Dashboard `/healthz` 200 after.
Left uncommitted on purpose: `grill-me` and `grilling` skills (provenance unchecked), `reports/`, this folder.
No redeploy: `~/studio` is the live checkout; nothing new was started or restarted.
