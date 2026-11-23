# Ultimate mission checkpoint (started 22 Nov 2026, 17:09 UTC)

Resume from here after a cut. Older checkpoint: reports/MASTER_MISSION_22NOV_CHECKPOINT.md.

## Phase A: recovery baseline (17:09-17:24 UTC session window)
- Git: ~/studio on `main`, HEAD `b835692`, clean apart from this file. Workshop folder not used (note: the Skill tool reads project skills from the session's start folder, the workshop; studio skills are read from `~/studio/.claude/skills/` instead).
- Containers: `studio-worker`, `studio-dashboard` healthy, restart policy `unless-stopped`, 3 GB memory limit each, `oom_score_adj` 500, CPU weight 256. Restarted once by Docker at 16:07:12 UTC after the host OOM. System Docker is enabled at boot, so the studio already starts with the PC.
- Worker processes: `python worker.py`, the Maximilian retry loop (sh pid 234, sleeping). No render, no ffmpeg, no make running.
- Retry loop: tries 1-4 of 8 failed (13:53, 15:00, killed by OOM at 16:07, 17:04 UTC). Try 5 at about 18:04 UTC, then hourly to try 8. Draft saved: `data/pending_draft.json` (Maximilian I of Mexico, 96 lines). Locks: `autopilot.lock` is an flock, free when its process ends; nothing stuck.
- **Root cause of every judge failure (found in this session, 17:09-17:24 UTC):** `settings.json` `openrouter_key` holds the FreeLLM proxy key (identical to `extra_llm_key`, 59 chars, not `sk-or-`), saved over the OpenRouter field; a saved key wins over `.env`, so every OpenRouter model answered 401 ("Missing Authentication header"). The `.env` key is also dead: OpenRouter's free `/api/v1/key` says 401 "User not found". So no OpenRouter route works at all. The first 401 appears on 22 Nov; 18-21 Nov had none. Earlier explanation ("Google high demand") was only part of it.
- Working judges (probed in this session): `gemini:gemini-3.5-flash-lite` (owner's Gemini key, direct) and `extra:nemotron-3-ultra-550b` via the FreeLLM proxy (200 in 4.3 s, served by `nvidia/nemotron-3-ultra-550b-a55b`; its 502s earlier were transient). Proxy: 342 models, `owned_by: freellmapi`; gemini-3.6-flash, glm-4.7-flash, qwen-3.8-27b, gpt-oss-120b were rate-limited (429) at the probe.
- Training: no training process on this PC (no GPU job, nothing named train/finetune/lora, no trainer_state.json since 15 Nov). GPU GTX 1050 Ti 4 GB, 1.2 GB used by the desktop. `forge-serve` (Desktop/models/forge) is a separate OpenAI-compatible server, not Studio.
- Resources 17:09 UTC: RAM 23 GB, 16 GB used, 7.2 GB available; zram swap 7.6 of 8 GB used (pressure); disk 241 GB free (75 %). Largest users: Chrome windows (about 0.4-0.75 GB each, many), a QEMU VM 0.65 GB, Plasma, two Claude apps, VS Code. OOM at 16:07: the kernel killed the retry loop's sh, docker-init and a Chrome tab. Studio has only a warning (`checkpoint.memory_note`), no gate before heavy work.
- Launchers: two identical owner launchers on the Desktop (`Story Studio.desktop`, `story-studio.desktop`) plus one in applications, all opening the dashboard's Tailscale address on port 8913 in Chrome app mode; two client launchers pointing to `srv2029460.hstgr.cloud`, the VPS deleted on 17 Nov (dead).

## Defect list (Phase B, growing)
1. OpenRouter key refused (401) is treated as 26 separate model failures: every model is asked, each 401 is counted against the model's own health (false "bad" records), retried hourly, and the owner never gets one plain "the key is refused" message. Needs a provider-wide circuit breaker and an alert.
2. The OpenRouter key save accepts any 10-300 character string: no format check, no check against the other saved keys.
3. "No free judge could answer" never names which models were tried and why (401, 429, 502): the evidence lives only in `llm_usage.json` notes, capped at 50 a day.
4. No memory gate before a heavy job (make, render): only a warning.
5. Launchers: duplicates and a dead client address.


## Phase B audits (four read-only Sonnet agents, this session)
- Doctor: checked only that a key existed; counted a model as available when its cool-down ran out; Risks card never checked the report's age; rows had no source, last success or failure reason; only 16 of 27 agents scanned (no job = not scanned).
- Agents/A2A: 27 agents, all with playbooks; 75/75 eval at 05:30. `a2a.py` has the shape of A2A but no network protocol (no agent card, no JSON-RPC, no listener) and its send/deliver have no live caller; tasks to autopilot and trainer have no reader (t00034 open since 19 Nov); `specbuild` job has no agent; `clip`/`schedule` registered commands do not exist.
- Training/HF: no training pipeline, no HF repo or token, no registry; `trainset.py` dry run = 8 eligible records (4 videos) vs 300 needed per task; risks: writer attribution for two videos, Gemini-output terms unchecked, split by slug not story.
- Video workflow: thin script survived into production (FIXED); topic popped before a script exists (draft orphaned on an outage; the loop re-pins by hand); length not gated (20-25 min is a warning only; a fresh 1,500-word script passes); house look not persisted for docs on resume; no source = no fact-check; no disk/memory gate (memory FIXED); environmental stops count as tries; judge-failure-as-pass in `topicrank.premise_check`, `reviewer.title_ok`; wrong-shaped judge reply read as "nothing unsupported".

## Phase C done (by 17:24 UTC)
OpenRouter refusal breaker + alert + judge names in the error (llm.py, scriptgen.py); key field checks (dashboard.py); doctor health fields, live key check, proven-availability count (doctor.py, freemodels.py last_ok); stale doctor report on Risks (risk.py); proxy 5xx short pause (freemodels.py); thin-script stop (run.py); memory gate (checkpoint.py, autopilot.py); 2 agenteval cases with 6 mutation checks; tests: test_openrouter_refused.py, test_doc_attempts.py, test_doctor_capacity.py (+3), test_freemodels.py (+1), test_autopilot.py (+1). Launcher fixed (outside the repo, backups in ~/.local/share/story-studio-launchers-retired-2026-11-22/).
Live proof (this session, before 17:24 UTC): strict review answered by extra:nemotron-3-ultra-550b (NVIDIA via FreeLLMAPI) and gemini:gemini-3.5-flash-lite.

## Owner decisions open
1. OpenRouter: both saved keys are dead. Save a new `sk-or-` key, or stay free (Gemini key + FreeLLMAPI). The wrong value in settings.json `openrouter_key` (the FreeLLMAPI key) is left in place until the owner says; it is harmless now (skipped after one 401).
2. Training: nothing to train on yet; whether to build a pipeline at all.
3. Rule 11 of the brief (no automatic scheduling) vs the standing auto-approve with a 24 h veto.

## Commit and deploy (17:38-17:41 UTC)
- Full suite 2964 passed, 11 skipped (17:38). An earlier run showed 5 failures caused by my own mutation edits of run.py during the run (source-reading tests) and 3 from the new length gate meeting one-line fake scripts (fixed with a fixture in those two files); none were product defects.
- Commit f58e5ff pushed to main; secret scan of the commit: no saved key present.
- Dashboard container restarted alone (healthy, /login 200 after about 60 s); worker untouched (retry loop alive).
- Doctor run 17:40:35 UTC: openrouter_key FAILED with OpenRouter's own message; needs: model key refused, off-server backup; own_provider 1/5 proven, openrouter_free 0/12 with note; 16 rows HEALTHY with last_success and source. Before today it said 12/12 and 5/5.
- Additional fixes in this commit: length gate before voice (90 % of rules.json minimum), judge reply without a verdict is not a pass, saved draft topic picked first. Not changed by design: topicrank.premise_check and reviewer.title_ok fail open (pre-selection only; the final AI review records "unreviewed", never a pass).

## Next exact action
Watch Maximilian try 5 (about 17:58 UTC, check 3 of 3 of the saved draft). Then: topic requeue on fact-check outage, length gate, judge-failure-as-pass fixes, browser test of every page in the owner's Chrome.
