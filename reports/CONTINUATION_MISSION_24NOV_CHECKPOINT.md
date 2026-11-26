# Continuation mission (owner's paste of 24 Nov 2026 local, 23 Nov 22:36 UTC): checkpoint

Resume from the first unticked line. All times UTC. The Desktop workshop is off-limits and was not read. Previous checkpoint: reports/PRODUCTION_MISSION_23NOV_CHECKPOINT.md
(note: its section headed "24 Nov 2026 ~18:40 UTC" happened on 23 Nov; the PC clock is Bangladesh time, UTC+6).

## Phase A: verified starting state (22:36-22:50 UTC) [x]
- The PC rebooted at about 22:07 UTC (every process ~29 min old at 22:36; worker.log "worker started 22:07:35"). No job was running at the cut: worker idle, no pending_doc / pending_draft / pending_short, no autopilot.lock.
- Git main f20bba1, 4 commits ahead of origin/main (08842e1, 574a347, e0756ea, f20bba1), not pushed. Uncommitted at start: llm.py (an unfinished two-family fix from the previous session, last saved 22:02 UTC, just before the cut) and two untracked research reports of another session.
- That llm.py change broke 3 tests (fakes without `avoid_families`; two fake judges of one "family"): 3 failed, 95 passed.
- Containers healthy, dashboard /healthz 200. Only one Claude CLI process (this session). GPU: an Ollama llama-server of the owner's (1.2 GB), not the studio.
- Autopilot: enabled, make_videos true, auto_approve true, pause_scheduling TRUE (nothing is scheduled or sent).
- Resources: RAM 23 GB, 11 GB available; swap 0 used; disk /home 235 GB free; GPU 2.3 of 4 GB used.
- Cloudflare free pictures: 8,909.1 of the 9,000 cap used on 23 Nov (resets 00:00 UTC). Paid models off (Free Mode), OpenRouter key dead (401).
- Judge probe 22:45 UTC (one planted false line each): gemini:gemini-3.5-flash-lite and gemini:gemini-3.8-flash DOWN (503); extra:glm-4.7-flash (Zhipu) 20 s, extra:qwen-3.8-27b (Qwen) 8 s, both flagged only the false line.
- Seven Sleepers record: approved TRUE, old 81-line fact-list script (fingerprint c408ebcfcd1f), review of 21 Nov 12:32 with no id, not on YouTube. Only pause_scheduling keeps it from a slot.
- Candidate script data/rescript/ss_script.py: SHA-256 98d0c2a9cd974f3c15d737de36c1a7be16624a115c7fb8ad905ce765091c62d8, 93 lines, 14 chapters, 3,033 words (this counter; the previous note said 3,031), max 44 words a line; fingerprint with the film's title 197d78b5ce77. Sources: the 3 cached Wikipedia articles, 25,602 chars, cached 21 Nov 02:33 UTC.

## Phase B: fact-check independence [x code] [ ] Seven Sleepers check
- Found: the script fact-check (scriptgen.unsupported -> llm.chat strict -> llm._free_review) required two different model NAMES only; two NVIDIA Nemotron models counted as two judges. It could ask only Gemini direct, the Settings review list (extra:gemini-3.6-flash, extra:nemotron-3-ultra-550b) and OpenRouter (dead key), never the cascade's GLM/Qwen, so with a family rule it could never pass while Gemini is down. The video review (judges.py) already enforced families. No answer cache exists (llm.cached is provider-side prompt caching only). A missing second judge was already "no review", never a pass.
- Fixed (uncommitted): llm._free_review needs a second judge of another family (answer_family: asked id + what the provider served; a router that does not name its model cannot be judged independent -> BLOCKED); a blocked check raises ModelUnavailable with its reason and never falls back to one local model; the second-judge search never asks or waits for the first family; the fact-check may ask the cascade's own judges on the owner's provider (llm.judge_extra_models from config/judges.json, never a router or a writer); LAST_REVIEW keeps models, served, families, providers, time and each judge's own answer; scriptgen.unsupported keeps them per part (scriptgen.factchecks -> `script_factcheck` in the script record); one router list (judges.is_router = llm.is_router); reviewer playbook Never line.
- Tests: test_llm (8 new/updated), tests/test_factcheck_record.py (3), agenteval case `case_two_judges_of_one_family_are_one_opinion_and_a_missing_second_family_blocks_the_fact_check` + 5 mutation checks; closed-world fakes pinned (tests/test_extra_provider.py _settings, two agenteval cases). Related suites: 303 passed.
- [~] Seven Sleepers two-family fact-check (fixed path, scriptgen.unsupported; judgments only, nothing rewritten by a model). Records: data/rescript/ss_factcheck_24nov*.json.
  - 22:55 my own source check first: 6 lines fixed (5 legend-as-fact, 31 "middle chapter", 33 quote marks, 51 dig dates disputed, 55 "by one account", 84 hedge). Backup ss_script.py.bak-before-24nov-fixes.
  - Run 1 (fp 146914b8cd16, 349 s): google+nvidia on every part; 8 flags: 3 real (62, 81, 85) fixed; 5 refuted by exact passage (34, 64, 65, 84, 86). Backup .bak-before-judge-fixes-24nov.
  - Run 2 (fp 0fd07ca3b386, 268 s): nvidia+google, then nvidia+particle; 7 flags, all fair wording overreach (45, 49, 56, 86, 89, 90, 91) + my own 14: fixed. Backup .bak-before-judge2-fixes-24nov.
  - Run 3 (fp 8725f8e53865) running at 23:08 UTC.

## Done meanwhile
- Full suite 23:04-23:09 UTC: 3022 passed, 11 skipped, 0 failed (312.75 s).
- D Mary Celeste: report reports/MARY_CELESTE_REPEATED_PICTURES_2026-11-24.md; fixes R1 (run._produce_doc waits for pictures when variety < 55% and the allowance is spent) and R2 (realmedia judges named items too), tests.
- reset_for_rerender keeps the old review in review_history (found by the Autopilot mapping agent); test in tests/test_fixes.py.
- J hook: candy-plugin Stop hook controle-si-code-modifie.sh -> controle-fin-de-tour.py budget 240 s, waits ~200 s for verifier-projet.sh (.venv/bin/pytest -q, the whole suite, 312 s): times out by design.
- G voice: recordings/ empty, no permission file: personal voice BLOCKED.
- F UGC Short spec staged (NOT in the inbox): data/specs/staging/mary-celeste-ugc-short, `run.py specrun check` -> spec ok. Move to data/specs/inbox after Seven Sleepers' pictures.
- H dashboard button audit running on a secret-free reflink copy /home/fahad/studio-audit-copy-24nov (port 8931) -> data/research/dashboard-audit-24nov.
- Render script ready: data/rescript/ss_redo.py (lock, lines hash check, records.merge, run.cmd_redo). Start ~23:45 UTC so pictures come after the 00:00 reset:
  docker exec -d -w /app studio-worker sh -c 'PYTHONPATH=/app python data/rescript/ss_redo.py <lines_sha> >> logs/seven-sleepers-redo.log 2>&1'

## 00:05 UTC
- Independent code review (subagent) found 3 important defects, all fixed with tests: one judge's verdict could pass when the other replied in another shape
  (it really happened in run 1); the picture wait fired without the allowance being the cause and lied for re-renders; a stale "served as" let a router pass.
  Also fixed: float rounding, Shorts record None not [], realmedia duplicate titles, playbook wording. Related suites 299 passed.
- Seven Sleepers fact-check FINAL: run 9, fp e93dc43d643f, lines 1639ba97b2df, nvidia+particle on every part, no flag (report updated).
- [~] Render started 00:05:18 UTC: docker exec ... data/rescript/ss_redo.py 1639ba97b2df, log logs/seven-sleepers-redo.log, holds autopilot.exclusive.
  Resume if cut: same command (voice/picture caches keep the work); backup output_old/doc-did-seven-sleepers-before-rescript-24nov (+ .inventory.sha256).

## Next (in order)
- [ ] C Seven Sleepers render (only if B passes): back up folder to output_old, autopilot.exclusive, redo, inspect MP4
- [ ] D Mary Celeste repeated pictures: cause, report, regression test
- [ ] E Autopilot stage map + controlled failure tests (safe test project)
- [ ] F UGC-style draft (separate local project)
- [ ] G Voice lab: recordings/permission check
- [ ] H Dashboard QA in Chrome
- [ ] J Hook timeout investigation, full suite
- [ ] K Independent review, L push plan (ask owner), M final report

## 02:45 UTC (usage limit reached; resume here)
- Seven Sleepers render DONE 02:13 UTC: 1095 s, 12/12 studiochecks ok, -15.0 LUFS, peak -3.9 dBFS. Problems: scenes 59-92 replay 0-32 (60 unique/93, art cap 16), scene 67 Jerusalem's Damascus Gate, garbled AI text in 52/54, 18 min < 20-26 target, 44.1 kHz. Review 02:22: unreviewed (AI cascade ModelUnavailable), warnings doc_length + rehook_gap 179 s; approved False. Owner decision: raise art cap/variety floor and re-render.
- UGC Short spec in data/specs/inbox/mary-celeste-ugc-short: waiting; Cloudflare's account answered 429 code 4006 (10,000/day used; studio counted 1,667; GLM/Qwen judges on FreeLLMAPI share the account). Builds itself after 00:00 UTC 25 Nov.
- NEW routing (owner: "create a routing system"), uncommitted, 243 related tests pass: freeart records Cloudflare's 4006 as account spent for the UTC day (data/cloudflare_account_spent.json; available() false); specrun says so; judges in config/judges.json `shares_picture_allowance` (GLM, Qwen) are asked last and skipped when the account is spent (llm.picture_sharing_models). TODO: a dedicated test for each, agenteval case + mutation, full suite.
- Left: Phase K video/voice independent reviews, final report, commit (needs owner yes), push plan (ask owner), memory note.

## ~04:30 UTC: model and compute routing mission (owner's paste)
- Report: reports/MODEL_COMPUTE_ROUTING_2026-11-24.md. New (uncommitted): config/compute.json, modelinventory.py, computecompat.py, computejobs.py, computerouter.py, compute.html, run.py compute, dashboard /compute + /api/compute, 10 skills, tests/test_compute_routing.py, agenteval case + 3 mutations.
- Real runs on this PC: GPU qwen2.5:1.5b (all in VRAM, 49 tok/s), CPU (26 tok/s), GPU offload qwen2.5-coder:7b (1.94/4.91 GB VRAM, 10.3 tok/s). VPS: none. Kaggle: BLOCKED_PENDING_TERMS_REVIEW (no GPU used).
- Full suite: 3075 passed, 11 skipped, 1 failed (help line) -> fixed. Independent review running.
- Incidents: Playwright wrote 2 snapshot files into the workshop's .playwright-mcp/ (stopped); an unquoted heredoc ran backticked words (harmless: read-only inventory, a refused `ollama create`, `view`).
