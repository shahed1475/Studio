# YouTube Automation Master Report

**Last Updated:** 19 Nov 2026
**System Status:** OPERATIONAL (Free Mode Active)
**Test Suite:** 2619 PASSED

---

## System Overview

The YouTube automation studio (`/home/fahad/studio`) is a 24/7 autonomous production system for history/legend videos, enhanced with an Advanced Competitor Intelligence and Video Analysis System.

## Core Modules Preserved

- Research Agent, script generator, voice, visuals, render, review, and upload modules
- Existing patterns from `channelwatch`, `discover`, and `trendwatch` reused for API communication

---

## Development Status

### Completed in This Session (19 Nov 2026)

| Component | Status | Evidence |
|---|---|---|
| Dashboard Autopilot crash fix | **DONE** | `channelwatch.latest()` now reads only weekly digests |
| `/competitor` page fix | **DONE** | Route now returns `generate_insight_report()` |
| Competitor approval gate | **DONE** | 2 new tests in `test_dashboard_routes.py` |
| Agent bus double-finish fix | **DONE** | Guard added to `_move_saved` |
| Upload guard KeyError fix | **DONE** | Handles missing `tags` key |
| **Pipeline test: The Beale Ciphers Short** | **COMPLETE** | `run.py make "The Beale Ciphers"` finished in 3.5 min |
| **Video QA** | **PASS** | All studiochecks pass, ffprobe verified |

### Test Results

```
$ .venv/bin/python -m pytest -q
=========================== short test summary ============================
2619 passed, 21 skipped, 4 warnings in 176.03s ==============================
EXIT=0
```

**New Tests Added:**
- `test_latest_reads_the_weekly_digest_and_never_the_craft_advice`
- `test_competitor_proposal_cannot_be_queued_before_its_approved`
- `test_an_ordinary_news_proposal_still_queues_with_one_click`
- `test_a_record_without_tags_reaches_the_send_instead_of_crashing`
- `test_a_closed_bus_task_keeps_its_outcome_when_a_late_retry_moves_it_again`

---

## Advanced Competitor Intelligence Module (`competitor.py`)

| Aspect | Status |
|---|---|
| Purpose | Tracks competitor channels, analyzes metadata |
| Compliance | Metadata-only analysis enforced |
| Integration | Feeds topic proposals into research pipeline |
| Approval Gate | Requires `competitor_research_approved` before queue |

**Verification:** Live `/api/competitor` returns 200, 29,745 bytes, 22 channels, 5 proposals.

---

## Free Mode Status

```
llm.free_only() → True
free_review → True  
free_art → True
neuron usage: 2,219.3 (of 10,000 daily cap)
OpenRouter balance: -0.0468 (below threshold, free mode compensating)
```

**Video Cost:** The Beale Short produced for $0.60 (Cloudflare free art only).

---

## Multi-Account Infrastructure

The multi-tenant code exists but is **NOT DEPLOYED**:

| Component | Status |
|---|---|
| `data/tenants.json` | Does not exist |
| `STUDIO_MODE=tenant` detection | Returns False |
| Tenant containers | Not created |
| Proxy routing | Not active |

**Verdict:** Single-channel studio operating in free mode. Multi-account design documented in `reports/MULTI_ACCOUNT_ARCHITECTURE.md`.

---

## Video Pipeline Test: The Beale Ciphers Short

| Phase | Duration | Status |
|---|---|---|
| Topic selection | instant | **PASS** |
| Research | ~5s | **PASS** |
| Script generation | ~10s | **PASS** |
| Voice + captions | ~12s | **PASS** |
| Archive image search | ~30s | **PASS** |
| Camera motion | ~60s | **PASS** |
| Rendering | ~45s | **PASS** |
| Quality checks | ~10s | **PASS** |

**Final Output:**
- `video.mp4` - 57.5s, 1080x1920, 30fps, 15.02 MB
- `captions.srt` - 15 cues
- `words.json` - speech transcript

**studiochecks output:** All 14 checks PASS.

---

## ⚠️ REVIEW BLOCK: Owner Decision Required

**Video:** `the-beale-ciphers-a-treasure-that-vanished-with-it`
**Status:** `needs review`, `approved: false`

**Reviewer Output:**

```
FAIL block invented_facts: risk 8/10
  - 'treasure worth millions in today's money' presented as certain, but article says disputed/hoax
  - 'one cracked using the Declaration of Independence' implies certainty, but article questions authenticity
  - 'James B. Ward published the ciphers in 1885' stated definitively, but article suggests Ward may have created hoax
```

```
FAIL block title_matches: title may mislead
  Title 'A Century-Old Treasure Mystery' implies treasure's existence as historical fact,
  but narration only mentions researchers called it a hoax.
```

**CLAUDE.md Rule #B:** *"Nothing with an open invented-facts warning is approved, scheduled, or uploaded."*

**Owner Must Decide:**
1. **Accept current version:** Title/description updated, but narration still has invented facts. **Cannot be approved under current rules.**
2. **Archive:** Remove from queue, select different topic
3. **Rebuild:** Re-render with script that properly frames the story as *disputed/hoax mythology* from line 1, not present as historical fact

---

## Risk Assessment

| Area | Level | Evidence | Action |
|---|---|---|---|
| Disk space | **WATCH** | 96% full, 39GB free | Clean outputs or expand storage |
| OpenRouter balance | **ACT** | $-0.0468 | Top up when ready |
| Facts verification | ok | Claim ledger active | None |
| Rights/licensing | ok | Credits in description | None |
| Multi-account | ok | Tenant code not deployed | None |
| Beale Ciphers review | **NEEDS_OWNER_DECISION** | Invented facts: 8/10 risk, title_matches fail | **OWNER MUST DECIDE** whether to reframe, archive, or rebuild |

---

## Owner Action Required

1. **CRITICAL - Beale Ciphers Video:**
   - Video cannot be approved with current invented-facts warnings
   - Options:
     - **Option A:** Approve if narration properly reframed as disputed legend (requires script rewrite + re-render)
     - **Option B:** Archive the video (`python run.py archive the-beale-ciphers-a-treasure-that-vanished-with-it`)
     - **Option C:** Rebuild with proper hoax framing

2. **Address disk space:** 39GB free (96% utilization) is a blocking constraint

3. **Review 25-min policy change:** Current `MAX_DOC_LINES=58` produces ~9 minute documentaries. Achieving 25 minutes requires:
   - Increase `MAX_DOC_LINES` to ~3200 words
   - Increase `aiart.MAX_PER_VIDEO["doc"]` from 16 to ~110 pictures
   - Raise Cloudflare neuron cap

4. **Review negative balance:** When convenient, top up OpenRouter account

---

## Reports Generated

| Report | Path |
|---|---|
| Dashboard Interaction Test | `reports/DASHBOARD_INTERACTION_TEST.md` |
| Video Pipeline Test | `reports/VIDEO_PIPELINE_TEST.md` |
| Video QA | `reports/VIDEO_QA.md` |
| Full System Audit | `reports/FULL_AUDIT.md` |
| A2A Audit | `reports/A2A_AUDIT.md` |
| Doctor Evaluation | `reports/DOCTOR_EVALUATION.md` |
| Multi-Account Architecture | `reports/MULTI_ACCOUNT_ARCHITECTURE.md` |

---

## Session Summary

**Completed:**
- All dashboard crashes fixed
- Competitor queue gate implemented and tested  
- Upload guard KeyError fixed
- The Beale Ciphers Short built end-to-end (no paid costs)
- All QA checks passed (ffprobe, captions, audio, video)
- Test suite: 2619 PASSED

**Resolved Issues:**
- Autopilot page crash: `channelwatch.latest()` now reads only weekly digests
- Competitor page `/competitor`: Added `generate_insight_report()` route
- Approval gate: `competitor_research_approved` required before queue
- `agentbus.py`: Double-finish guard prevents duplicate completions
- `upload.py`: KeyError for missing tags handled with default empty list

**Pending Owner Decision (CRITICAL):**
- The Beale Ciphers Short: Review failed with invented facts (8/10) and title mismatch
- **Rule constraint:** Videos with open invented-facts warnings cannot be approved
- Owner must decide: reframe, archive, or rebuild

**Disk Space:** 39GB free (WATCH) - cleanup required or storage expansion

**No Secrets Changed:**
- `data/auth.json` - untouched
- Login credentials - untouched
- All `.env` files, keys, tokens - untouched
---

## 2026-11-20: production audit, Free Mode, A2A and repair (Claude Code session)

Details and evidence: `reports/` (one report per phase); progress in `reports/STUDIO_EXECUTION_CHECKPOINT.md`. Nothing committed, pushed or deployed. Dashboard restarted twice while idle; worker never restarted.

**Baseline:**
- Both containers mount `/home/fahad/studio` and are healthy.
- 268 GB free, swap 7 of 8 GB used, 0 OOM kills in 7 days.
- Free Mode on, paid models off, Autopilot off.

**Code versions:** live is `8e060dc` plus uncommitted edits. GitHub is the same commit. The workshop is a third version (not touched).

**Fixed (each with tests; mutation checks where it guards behaviour):**
1. **Free Mode reached paid models.** The thumbnail score, the narration listen before an approval and the video analysis were gated only by the dollar cap. Now `llm.paid_allowed()` refuses before any request.
2. **Documentaries were fixed at 8 to 10 minutes.** Now the writer follows `rules.json` (20 to 26: 84 to 100 lines, about 2,940 words), there is an Autopilot > Rules control, the review reads 32,000 characters, and Shorts are unchanged.
3. **A GIF saved as `.jpg` killed a finished render** (19 Nov, Pyramids film). Now `render.still_for_ffmpeg`.
4. **Local-picture documentaries crashed after rendering** (`finder` unset, also in HEAD).
5. **`llm.parse_json` rejected fenced replies with a lone brace.**
6. **Tests and the daily agent evaluation wrote invented models and usage into real data** (race losers finishing after the redirect). Now `llm.settle`, eval isolation, a session safety net; the data was restored from backups.
7. **19 of 21 skips removed or justified.** 9 tests needlessly skipped now run; the CC0 skies were re-downloaded (Poly Haven); the MCP server's own venv was made.
8. **A2A:** `a2a.py` on the agent bus: Agent Cards for 27 agents, contract-checked tasks (schema, deadline, retries, acknowledgement, cancellation, no duplicate completion, hand-over map) and checked stage hand-overs in the documentary producer (script, voice, visuals, render, before registration).
9. **Doctor:** disk-space request (never deletes) and a provider status in `doctor.json`.

**Tests:** 2,670 passed, 0 failed, 11 skipped (10 blocked on the workshop-only Flannan spec, 1 MCP by design and passing in its venv). agenteval 63 of 63. Real dashboard clicked page by page in Chrome with POSTs refused: 0 script errors, 0 px sideways on a phone.

**Blocked:**
- The real 20 to 26 minute Autopilot film:
  - only 1 free model answered (Gemini and Gemma rate-limited upstream);
  - it needs the owner's Autopilot switch;
  - Autopilot would first render the waiting sourceless Pyramids script.
- 10 Flannan tests need an approved transfer from the workshop.

**Owner decisions:**
- The waiting Pyramids script.
- Turning Autopilot on with `pause_scheduling`.
- The `story-studio-rw` MCP config still points to the deleted VPS (command in `reports/SKIPPED_TESTS_AUDIT.md`).
- Installing faster-whisper.
- The off-server backup.
- Merging the workshop version.
- The commit.

## 21 Nov 2026: self-recovering Autopilot, supervised production
Nothing committed, pushed, approved, scheduled or uploaded. Autopilot stayed off; productions ran through its own make and repair commands.
- **Recovery**: a real power cut (20 Nov 18:53 UTC, idle) left all 839 state files intact. Fixed: pid reuse hiding a cut, duplicate video after a late cut, long-film final pass now in resumable 2-minute parts (drill 3 in the worker: cut mid-part, kept 10/10 scenes and part 1, exact 9,000-frame result). On the real film, try 3 kept 81/81 scenes and 9/9 parts.
- **Productions**: Seven Sleepers documentary finished (19.1 min, decodes fully, -14.0 LUFS, Blender globe of Ephesus, 12 chapters) but **failed review** on 3 unsupported details and misses the 20-minute minimum. Tenali Rama Short repaired to **pass**. New Short "Raijin and Fujin" **held** (unsupported "oldest temple gate" claim).
- **Permanent fixes found in production**: final parts and pixel-format changes, the description crash in every Autopilot film, the word rate (19.1-minute film passed the 20-minute minimum), the fixer editing the wrong line, narrated "The payoff:" labels, closings that cut names and dropped "subscribe". Plus the router judge that could be the writer. Each has a regression test and mutation checks (PERMANENT_FAILURE_FIXES.md).
- **Tests**: full suite 2,774 passed, 1 failed, 11 skipped (the 10 Flannan-spec tests and the mcp test, as before). The one failure was a dashboard test expecting the old word count; it was updated to the measured rate and its file passes (9/9). The full suite was not rerun after that last one-line change.
- **Owner decisions**: Seven Sleepers (`run.py repair`), Raijin and Fujin (`repair --extra` or set aside), `auto_approve`/`pause_scheduling` before switching Autopilot on, committing the uncommitted work, the dashboard UI check (needs your login).

## 22 Nov 2026 (evening): recovery, Doctor truthfulness, model key, memory gate (Claude Code session)
Checkpoint with evidence: reports/ULTIMATE_MISSION_CHECKPOINT.md.

**Root cause of a day of failed fact-checks.** `settings.json` held the FreeLLMAPI key in the OpenRouter field (identical values; a saved key wins over `.env`), so every OpenRouter model answered 401; the `.env` key is dead too (OpenRouter: 401 "User not found"). The studio counted each 401 against each model, benched them for six hours, retried hourly, and the Doctor kept reporting 12/12 free models and "all agents healthy".

**Fixed (each with tests; agent changes with an agenteval case and mutation checks):**
- `llm.py`: a 401 from OpenRouter marks the provider refused for 30 minutes per key fingerprint (`openrouter_refused`), skips every OpenRouter model meanwhile, leaves model health alone, and raises one owner alert a day; a failed fact-check names each judge asked and how it failed (`attempts_since`).
- `dashboard.py`: the OpenRouter field accepts only `sk-or-` keys and no key is saved under two services (`_check_key_field`).
- `doctor.py`: every agent row carries `health` (HEALTHY, STALE, FAILED, NOT_TESTED), `checked_at`, `source`, `last_success`, `failure_reason`; a real free key check (`GET /api/v1/key`: HEALTHY, FAILED, UNKNOWN, NOT_CONFIGURED) and a `model key refused` setup request; a model counts as available only when its newest success is newer than its newest failure. `risk.py`: a doctor report older than 13 hours is shown as STALE.
- `freemodels.py`: a 502/503/504 from the owner's proxy pauses that model five minutes instead of benching it six hours.
- `run.py`: a documentary whose every script attempt failed stops (a thin script refused in attempt 1 was voiced and rendered when the later attempts failed).
- `checkpoint.memory_short` + `autopilot`: no new video and no re-render starts with under 3 GB of memory available; a running render is never stopped.
- Launcher: one Desktop launcher and one menu entry open `http://127.0.0.1:8913` (was the Tailscale address); duplicates and the dead VPS client launchers moved to `~/.local/share/story-studio-launchers-retired-2026-11-22/`.

**Verified live (worker, before 17:24 UTC):** two independent judges answered the real strict review path: `extra:nemotron-3-ultra-550b` (FreeLLMAPI, served by `nvidia/nemotron-3-ultra-550b-a55b`) and `gemini:gemini-3.5-flash-lite` (owner's Gemini key).

**Audit findings not yet fixed (owner decisions or later work):** no working OpenRouter key (owner: new key or stay free); the studio has a training-set builder but no training pipeline, no Hugging Face link and 8 eligible examples (300 needed per task); "A2A" is an in-process shape with no network protocol and no live callers; tasks to autopilot and trainer have no reader; topic popped before a script exists (draft orphaned on an outage); documentary length is a warning only; full list in the checkpoint.

## 24 Nov 2026 (15:07 UTC onward): power-outage recovery (Claude Code session)
Checkpoint with evidence: reports/POWER_OUTAGE_RECOVERY_2026-11-24.md. Nothing committed, pushed, deployed, uploaded, scheduled or approved by this session.
- **Outage**: power lost 14:45-14:52 UTC. No Claude work was interrupted (the previous session finished at 04:37 UTC, full suite green); only routine worker ticks, re-run since. Containers healthy, dashboard /healthz 200.
- **State found that differs from the last report**: the Mary Celeste UGC Short was built at 04:20 UTC (held, unapproved; 60.4 s, 13/13 studio checks, 12 distinct pictures seen, one three-masted ship for a two-masted brigantine). The Seven Sleepers film was approved at 06:15 UTC by auto-approve after a real two-family AI review (google + zhipu), with its known picture defects still in the MP4; `pause_scheduling` keeps it off the schedule.
- **Fixed**: (1) `autopilot.read_pictures` recorded a picture review that could not run (429) as `ok: true`; now `ok: false, ran: false` with the reason, never blocking (test, agenteval case, 2 mutation checks). (2) `sfx.apply`, the last audio pass, resampled every film to 44.1 kHz; it now keeps 48 kHz (test + mutation check against the old code).
- **Blocked**: Seven Sleepers re-render (Cloudflare account spent until 00:00 UTC 25 Nov; ~28 drawings ≈ 2,900-4,400 Neurons needed); voice (no recordings or permission file); Kaggle (non-commercial terms).
- **Owner decisions**: Seven Sleepers approval while defects remain; drawing limit and length for its re-render; commit and push.

## 24 Nov 2026 (15:45-16:30 UTC): Seven Sleepers completion mission, Kaggle research (Claude Code session)
Report and checkpoint: reports/SEVEN_SLEEPERS_COMPLETION_MISSION_2026-11-24.md. Nothing committed, pushed, uploaded, scheduled or published.
- **Seven Sleepers approval withdrawn** (approved false, hold true, old approval kept in `approval_history` with the old MP4's sha256); Autopilot's planner run dry plans nothing for it, even with pause_scheduling off.
- **Kaggle** (read today on Kaggle's own pages): Terms 22 Jun 2025 "internal, personal, non-commercial use"; AUP bars "activity unrelated to ML data science" and "server farming"; T4 x2 (16 GB each), P100 retired 15 Sep 2026, 12 h sessions, ~30 h a week. Not used for production; permission request drafted, NOT sent (reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md). Compute options: reports/COMPLIANT_GPU_COMPUTE_OPTIONS_2026-11-24.md; models: reports/DOWNLOADED_MODEL_INVENTORY_2026-11-24.md.
- **Script v2** (data/rescript/ss_script2.py): 109 lines, 16 chapters, ~3,580 words (~21.5 min est.), 16 new lines from five more Wikipedia articles; lines 52/54/67 get new visual notes. Two-family fact-check run 4 passed (0 of 109 flagged, lines_sha 912837e164f4); runs 1-2 flags fixed or refuted by exact passages; run 3 BLOCKED (one family only).
- **Code**: per-film `art_limit` (run._art_limit, ceiling 64) with tests, agenteval case and mutation checks.
- **Render scheduled** for 00:02 UTC 25 Nov (user timer ss-redo2-render; Cloudflare's free day resets 00:00 UTC); held for the owner after it.
- **Mary Celeste Short**: opening picture redrawn with Z-Image Turbo on the owner's GPU (Apache-2.0 verified by SHA-256), stern pseudo-lettering painted out, rebuilt: 60.43 s, 48 kHz, 13/13 checks, held.

## 24 Nov 2026 (17:00-18:00 UTC): Kaggle as a real remote GPU worker (Claude Code session)
Report: reports/KAGGLE_REMOTE_WORKER_2026-11-24.md. Nothing committed or pushed; no competition submission; no credential printed or uploaded; no video touched.
- **Inspected**: Kaggle CLI 2.2.5 logged in (token read by the owner's wrapper, never shown); GPU quota 11.74 of 30 h (refresh 28 Nov); entered competitions titanic, house-prices, spaceship-titanic; their CSVs on disk match Kaggle's files and read cleanly; rules: titanic and house-prices data non-commercial only, spaceship-titanic any purpose.
- **Terms**: competition work (A) and personal non-commercial experiments (B) allowed; commercial channel production (C) BLOCKED until Kaggle's written permission (draft request not sent).
- **Built**: `kaggleworker.py` (public-twin proof by SHA-256, private T4 notebook, push with a time cap, poll, retrieval into new folders, manifest verification, recovery), gate change in `computerouter.py` (a private-flagged file only via a verified twin), `computejobs.job_id` now includes the data class (defect: a production request could inherit a public-test job), `run.py compute kaggle-*`, config: worker on for the `benchmark` task only.
- **Real run (PASS)**: job 8ba727ef5f45c77c on 2 x Tesla T4 (15.64 GB each, 32.87 GB RAM): the owner's Qwen3-4B-Instruct-2507 Q4_K_M, fetched from its maker and proven identical (SHA-256 3605803b...), loaded by transformers 5.20.2 in 101 s (8.12 GB peak), 3 answers at 10.9-15.6 tokens/s, retrieved and verified against the notebook's manifest. Two defects it exposed were fixed with tests (stage logging, QUEUED read as RUNNING).
- **Real expiry test**: job 136f1b32068c72a8 (150 s cap) has been QUEUED by Kaggle (no GPU) since 17:14 UTC; recovery is proven with fakes only so far.

## 25 Nov 2026 (03:40-04:40 UTC): Seven Sleepers inspected and held, plugin hook, gpu-router branch, two routes into the forbidden folder (Claude Code session)
Nothing approved, uploaded, scheduled, published, committed, merged or deployed. No production process was stopped or restarted.

- **Seven Sleepers v2 rendered and inspected (held).** The 00:02 UTC job finished at 01:47:22 UTC in the real worker; nothing else was running. MP4: 1,295.4 s (21.6 min), 1920x1080 at 30 fps, AAC 48 kHz, sha256 d885501e...; studiochecks 12/12; no black or frozen stretch; all 108 cuts on line boundaries; the voice sits 40 ms after the captions with no drift; every line present. Fixed: old 54 and old 67 (Damascus), the last-third replay, 48 kHz, length. Still wrong:
  - archive pictures on about 23 wrong lines in the first half, including Christian pictures on Qur'an lines and Islamic texts on Christian lines;
  - repeats 17-19 and 42-43;
  - invented Arabic-looking lettering (68, 73, 107), with 68 presented as Qur'an verses;
  - garbled lettering still in the redraw of old 52 (now 60);
  - a drawn presenter beside a real director's name (87);
  - a 0.9 s ending.
  The record stays hold true, approved false, and the old approval and fingerprint are kept. Full list with times: reports/SEVEN_SLEEPERS_COMPLETION_MISSION_2026-11-24.md (25 Nov section). Owner decision: accept or repair.
- **Kaggle expiry test** (job 136f1b32068c72a8, from 24 Nov). It ran on a T4 after its queue. All 5 answers were written and retrieved and verified (q5 "401" is a model error; 17 x 23 = 391). Kaggle reported CANCEL_ACKNOWLEDGED after the work had finished. The worker now marks such a session COMPLETED (a needless recovery session had cost about 2.6 GPU minutes), and recovery refuses when nothing is left (2 tests). Recovery after a cut in the middle of an item is still untested on hardware. Production on Kaggle stays BLOCKED (no written permission). Details: reports/KAGGLE_REMOTE_WORKER_2026-11-24.md section 13.
- **gpu-router plugin (separate from production).** Branch `feature/gpu-router-plugin` on GitHub at 7fa9023 (based on main 92d2572). Not merged, no pull request, not wired into the studio, not deployed. Its 27 tests were re-run today and pass. The review is plugins/gpu-router/REVIEW_2026-11-25.md on that branch: 0.1.0's Kaggle status reader failed on real CLI 2.x output; no accelerator was sent; quota was local only; there was no non-commercial gate; Modal (paid) was on by default. All were fixed in 0.1.1 on the branch. The repo is public, so the branch is publicly visible (it holds no keys).
- **Claude Code message "SessionStart:compact hook failed".** The source is the claude.ai-synced plugin **aws-startup-advisor 2.0.1** (Amazon Web Services). Its hooks/hooks.json runs `cat ${CLAUDE_PLUGIN_ROOT}/scripts/startup-context.txt` on every session start (matcher "*"), but the synced copy has no scripts/startup-context.txt; its scripts/ folder holds only three validator .py files. Recorded in this session's log at 15:07 UTC 24 Nov (startup) and 01:00 UTC 25 Nov (compact). The hook is non-blocking: it only prints the error and has no effect on renders or on the studio. The studio does not use AWS, so the plugin is not needed for this work. Nothing was changed: the plugin folder is synced from the owner's claude.ai account, a local edit would be overwritten, and the owner asked for no blind reinstall or deletion. The owner's fix is to disable aws-startup-advisor in `/plugin` (or at claude.ai/customize), or to ignore the message.
- **Two silent routes into the forbidden folder (/home/fahad/Desktop/Youtube-automation), found during this session:**
  1. **The shell's Python.** Claude Code's shell has `VIRTUAL_ENV` set to that folder's .venv, so a bare `python3` ran that folder's interpreter. It was used for read-only helper scripts (standard library) and for one faster-whisper attempt, which crashed and was dropped.
  2. **The current Docker context.** The current context is `desktop-linux` (Docker Desktop), which runs a **second studio-dashboard and studio-worker pair with /app bind-mounted from that folder** (up since 14:52 UTC 24 Nov, like the real pair on context `default`). Plain `docker exec` reached it. `run.py judges`, a model-mode check and `run.py review` ran there by mistake. The review failed (that copy has no such film) and wrote a 159-byte file, logs/seven-sleepers-review-v2-25nov.log, into that folder. Python may also have written bytecode caches there; this was not checked, because that would mean looking inside.

  Nothing there was deleted or changed on purpose. From now on, only `/home/fahad/studio/.venv/bin/python`, `/usr/bin/python3` and `docker --context default` are used (memory note never-bare-python-forbidden-venv). The 00:02 render itself ran on the real pair (`docker --context default`) and wrote to ~/studio.

  **Owner decisions:**
  - whether the Docker Desktop studio pair should keep running; if its Autopilot is on, it acts on the workshop's own records and login;
  - whether to remove the stray log file;
  - whether to start Claude Code from ~/studio rather than from the workshop folder, which avoids both routes.
- **Tests:** full studio suite 3,108 passed, 11 skipped (5 min 4 s; studio interpreter, PATH limited to the studio venv and system folders); gpu-router plugin 27 passed. Studio review of the film: verdict unreviewed (AI review ModelUnavailable, all rule checks ok, one rehook_gap warning).

## 25 Nov 2026 (04:40-06:30 UTC): Seven Sleepers root cause and repair plan, environment safety, GPU-router review, AWS plugin, second studio (Claude Code session)
Nothing was rendered, drawn, approved, uploaded, scheduled, merged, pushed, deployed, disabled or stopped, and no Neurons were spent. The film stays HELD (approved false).

**Documentary.**
- **Status:** held and not approved. The current film is sha256 `d885501e…`; it and the previous film (`f16337c6…`) are both preserved and re-verified.
- **Root cause:** `footage.scene_images` gives a scene whose own search fails the subject's reserve pictures *in pool order*. It judges relevance against the subject, not the line, and it never saved the per-scene mapping. Scenes 0–45 follow the anchor search order exactly. All 55 drawn scenes show their own line's drawing.
- **Fix:** traceability and detection: `scenemanifest.py` and `scenes.json` (stable ids, how each picture was chosen, sha256, a diff against the last render, links to the final video's fingerprint), plus a reviewer row `scene_sources`. 12 tests, an agenteval case and 3 mutation checks. The selection policy is unchanged; that is the owner's decision.
- **Repair plan:** 13 free moves of already-verified files and at most 42 drawings with no writing (about 4,376 Neurons, 6,981 with retries), through the exact-picture `local_pictures` route with a new ending hold and fade. Details: `reports/SEVEN_SLEEPERS_COMPLETION_MISSION_2026-11-24.md` (25 Nov, second section) and `reports/SEVEN_SLEEPERS_SCENE_MANIFEST_2026-11-25.md`.
- **Two-family picture review:** BLOCKED. It does not exist for images yet, and the text judges were unavailable today.

**Environment safety (verified).**
- **This session as started:**
  - it began in the workshop folder;
  - `VIRTUAL_ENV` and the first PATH entry pointed into it;
  - `PYTHONSTARTUP` named a VS Code workspace file;
  - the current Docker context was `desktop-linux`.
- **What was used from then on:** cwd `~/studio` (git root `~/studio`, branch main), Python `/home/fahad/studio/.venv/bin/python` (prefix `~/studio/.venv`, base `/usr`, 3.14.10), Docker `--context default` → `unix:///var/run/docker.sock`. The studio pair there mounts `/home/fahad/studio` (compose project `studio`). No `DOCKER_HOST` override, and no aliases or functions for python or docker.
- **Safe launch:**

  ```
  bash /home/fahad/studio/tools/claude-studio.sh
  ```

  Use `--check` to see what a session would get without starting one. The script removes the workshop from PATH, clears the Python and Docker overrides, sets `DOCKER_CONTEXT=default`, checks the daemon and the mount, and refuses to start if any variable still points at the workshop. Tested from this session's environment: it passes, and it refuses on a polluted variable.
- **Unresolved:** this session itself still starts each command in the workshop folder (that is where it was launched). Closing it and restarting with the launcher ends that.
- **Process faults (repeated here because the owner asked):**
  - Earlier today a bare `python3` and a plain `docker exec` reached the workshop. A review command left `logs/seven-sleepers-review-v2-25nov.log` (159 bytes) there; it was **not** deleted or inspected.
  - In this session one stray `python3 -c 1` was stopped by the permission check before it ran.
  - `rm -rf` of a cloned `.git` inside the scratch quarantine was also refused; the copy was made without it instead.

**GPU-router plugin (review only).**
- **Report:** `reports/GPU_ROUTER_PLUGIN_REVIEW_2026-11-25.md`.
- **Test evidence:** 27 of 27 tests pass, but they cover arithmetic and parsing only. Coverage was not measured. `vetskill` found 0 high findings.
- **Critical findings:**
  - it uploads the whole job folder with no file allowlist or privacy check;
  - its design puts R2 keys inside Kaggle;
  - outputs are lost when Kaggle ends a session at its time cap after the work is done;
  - "complete" is recorded without verified output.
- **Verdict:** NOT safe to integrate. Port its ideas into the studio's own Kaggle worker if ever wanted.
- **Not done:** NOT installed, integrated, merged, pushed or deployed. Branch `7fa9023` is unchanged.

**AWS plugin warning ("SessionStart:compact hook failed").**
- **Cause:** `aws-startup-advisor@synced` 2.0.1, from the owner's claude.ai account (marketplace `anthropic-plugin-directory`). Its only hook runs `cat ${CLAUDE_PLUGIN_ROOT}/scripts/startup-context.txt` at every session start; the file is missing from the synced bundle, and nothing else in the plugin refers to it. So the file is missing; the path is not wrong.
- **Impact:** a non-blocking error line only. Other session-start hooks ran (the agent-memory hook succeeded in the same start), and renders are unaffected.
- **Use:** the studio does not use the plugin. Nothing in `~/studio` enables or names it (it has no project settings file). The workshop project was not checked, by order.
- **Fix (needs the owner):** from `~/studio`, `claude plugin disable aws-startup-advisor@synced --scope local` (this project only), or `/plugin` → aws-startup-advisor → Disable. Scope `user` would disable it in every project on this PC. Removing it at claude.ai/customize would remove it on every device. It also removes its AWS agents, skills and MCP tools, which the studio does not use. Nothing was changed.

**Second studio (Docker Desktop).** Only things visible from the allowed side were checked: daemon names, status, resource use and process lists. No inspect, logs, exec or files.
- **Authorised studio:**
  - context `default`, `studio-worker` and `studio-dashboard`, up since 14:52 UTC 24 Nov, each running `python worker.py` / `dashboard.py`;
  - its Autopilot (`~/studio/autopilot.json`) has enabled, make_videos and auto_approve on, and pause_scheduling **on**;
  - no job is running now.
- **Docker Desktop (`desktop-linux`):** its own `studio-worker` (`python worker.py`, up 14 h 12 min) and `studio-dashboard` (`python dashboard.py`), plus searxng. CPU about 0%.
- **Inconclusive:** network traffic shows 0 B for *both* pairs. With host networking that number is meaningless, so it proves nothing.
- **Unknown:** whether its Autopilot is switched on. That lives in the workshop's own settings, which may not be read.
- **Ports:** only the authorised dashboard listens on host port 8913.
- **Risk:** a second worker loop runs the workshop's older code. If its Autopilot or scheduled jobs are active with a valid login, it can:
  - upload or re-schedule videos the real studio does not know about (duplicates or conflicting schedules);
  - spend the shared free allowances (Cloudflare Neurons, OpenRouter free requests, YouTube API quota);
  - act without today's safeguards.
- **Recommendation:** **stop** the two Docker Desktop studio containers (`docker --context desktop-linux stop studio-worker studio-dashboard`). This is reversible with `start`, and no data is touched. Then stop Docker Desktop starting them at login. **Owner approval needed**; nothing was stopped.

**Skills.**
- `grill-me` and `grilling` (MIT, mattpocock/skills @ d653911) are installed through `extend.py` (scan 0/0/0, pinned).
- `task-observer` (CC BY 4.0) was refused by the studio's gate on 3 "high" findings that read as descriptive. It is kept, not installed, in `data/quarantine/task-observer-6325c8e/`, its scripts were not run, and it is used by hand (`data/skill-observations/observation-log/`, 4 entries).
- `docs/EXTENSIONS.md` is updated, and `extend.py verify` reports 17 vendored skills match what was reviewed.

**Tests:** full studio suite 3,123 passed, 11 skipped (5 min 8 s, studio interpreter only); new tests/test_scene_manifest.py 12 passed; agenteval case + 3 mutation checks passed; extend.py verify 17 skills match; gpu-router plugin 27 passed (not installed).

## 25 Nov 2026 (07:00-09:30 UTC): Kaggle GPU worker audit and plan; Seven Sleepers repair readiness (Claude Code session, read-only)
Nothing was submitted to Kaggle, cancelled, uploaded, downloaded, drawn, rendered, approved, merged or deployed. No production setting or production code changed. The session environment was re-verified first (`tools/claude-studio.sh --check`: cwd `~/studio`, studio Python, Docker `default` → `/var/run/docker.sock`, 0 forbidden PATH entries); commands use absolute interpreters.

**New reports:**
- `reports/KAGGLE_WORKER_ARCHITECTURE_AND_AUDIT_2026-11-25.md`
- `reports/KAGGLE_POLICY_AND_WORKLOAD_ELIGIBILITY_2026-11-25.md`
- `reports/KAGGLE_MODEL_INVENTORY_2026-11-25.md`
- `reports/KAGGLE_GPU_BENCHMARK_PLAN_2026-11-25.md`
- `reports/KAGGLE_WORKER_SECURITY_REVIEW_2026-11-25.md`
- `reports/SEVEN_SLEEPERS_REPAIR_READINESS_2026-11-25.md`

**Kaggle worker (VERIFIED):**
- **Code:** `kaggleworker.py` plus the gate, state machine and verification exist and work for the `benchmark` task only. 58 mocked tests pass.
- **Real hardware:** 3 sessions on 2 x T4 (Qwen3-4B public twin, fp16, one GPU used, 9.7–15.6 tok/s, load 101–111 s, queue 0 min to 2 h 17 min).
- **Live account:** GPU quota 11.88 of 30 h used, refresh 28 Nov. No session has run since 24 Nov evening, so nothing is running or orphaned.
- **Correction:** the "stuck in QUEUED" claim about job 136f1b32068c72a8 is out of date. It ran, and all 5 answers were verified; recovery after a cut in the middle of an item is still untested on hardware.
- **Gaps:** no live quota check (BLOCKED_QUOTA), no queue timeout, no GPU utilisation, time to first token or absolute times, no local baseline, the llama.cpp CUDA engine failed to build, and the second T4 is unused.
- **Not yet production-ready.**

**Policy (read today on Kaggle's own pages):**
- **Terms:** Version June 22, 2025 (active), "internal, personal, non-commercial use". Production stays BLOCKED.
- **Session limits:** Kaggle's GPU tips say 9-hour sessions while the Notebooks page says 12; plan with 9.
- **spaceship-titanic rules page:** it contradicts itself (summary: non-commercial; section A: any purpose). Treat as unclear, and stop attaching it to benchmarks.

**Models:** the inventory rescan is identical to 24 Nov (83 distinct entries).
- **On Kaggle today (2):** the Qwen3-4B twin (tested) and the Z-Image Turbo twin (engine unverified, benchmark only).
- **Possible with an "Ollama-registry twin" (6):** library models such as `qwen3:8b`. Their blobs are not byte-identical to the Hugging Face GGUFs, but Ollama's public registry serves the same SHA-256 bytes (HEAD-checked).
- **Everything else:** the owner's own fine-tunes and adapters, unknown licences, content-policy models, or too big.

**Speed:** no new benchmark was run. For a 4B model, local is probably faster (an inference, to be measured). Kaggle can only pay off for models that do not fit 4 GB, run as long batches.

**Seven Sleepers:** NOT READY. Today's corrections:
- scene 31's photo is St Mary's Abbey, **York**, so it moves to REPLACE;
- scene 50 shows pseudo-writing, so it moves to REDRAW;
- scene 65's photo is placed in Jordan, so it stays with the owner.

The budget is now about 4,585 / 7,398 Neurons (44 drawings).
- **Safeguard limits:** `scenes.json` warns but does not block auto-approve, does not flag missing files, and gives no row for older films.
- **Picture review:** the two-family review is designed, BLOCKED until built.
- **Fallback rule:** the proposal is draw before using the general pool.
- **Not done:** no drawing and no render.

**GPU-router plugin:** review only.
- **Branch:** `7fa9023` unchanged, identical to the remote, clean.
- **Correction today:** `kernels push` uploads only the metadata and code file (checked in the CLI source). The plugin's `push_manifest` does upload a whole folder as a dataset.

**Decisions waiting for the owner (each one separate):**

| # | Decision | Recommended | Risk if done / if not | Reversible? | Blocked? |
|---|---|---|---|---|---|
| 1a | Stop the two Docker Desktop studio containers | yes | none known for the real studio / a second controller may act on the shared login and quotas | yes (`docker --context desktop-linux start …`) | no |
| 1b | Turn off Docker Desktop's start-at-login | yes, after 1a | other Docker Desktop work stops autostarting | yes (Docker Desktop settings) | no |
| 2 | Disable `aws-startup-advisor@synced` for the studio project only (`claude plugin disable … --scope local` from ~/studio) | yes | AWS tools gone in this project / a harmless error line | yes (`enable`) | no |
| 3 | Approve the scene plan (with today's corrections) and a Neurons budget | after the dashboard check | Neurons spent / the film stays defective | Neurons: no; film: yes (backups) | yes: needs 4, 5, the dashboard figure and a second reader for scene 38 |
| 4 | Two small opt-in code changes (ending hold and fade; library asset records on the exact-picture route) | yes | small code risk, with tests / the repair cannot render | yes | no |
| 5 | Build the two-family picture review | yes | free model requests / no independent picture check | yes | no (judges' availability unverified) |
| 6 | Documentary fallback: draw instead of using the general pool | yes, documentaries only | more Neurons per film / pictures that do not fit the line | yes | no |
| 7 | Scenes 31, 50, 65: REPLACE, REDRAW, owner's call | yes for 31 and 50; owner to decide 65 | — | yes | no |
| 8 | Restart Claude Code with `tools/claude-studio.sh` | when ready | none / commands keep starting in the forbidden folder | yes | no |
| 9 | Stray log in the forbidden folder | **withdrawn: no action, no investigation, no cleanup (owner's rule)** | — | — | blocked by rule |
| 10 | Keep `task-observer` out of the studio and use its method by hand | yes | — | yes | no |
| K1 | Kaggle worker improvements, no quota used: live quota gate, instruments, drop the competition attachment, Ollama-registry twin, local benchmark harness, tests | yes | small code risk | yes | no |
| K2 | Run benchmark tests 0, A and B (about 15 GPU minutes plus 10 local minutes) | yes, after K1 | quota use / no speed evidence | quota: no | needs K1 |
| K3 | Run benchmark tests C to E (about 40 GPU minutes) | after K2 | quota use | quota: no | needs K2 |
| K4 | Keep "benchmark" classed as personal, or send Kaggle the permission request first | owner's call | terms ambiguity | — | no |

## 25 Nov 2026 (later): Kaggle deep research (read-only; no Kaggle job, no quota read or used, no download, no production change)
Reports (all dated 2026-11-25):
- `KAGGLE_DEEP_RESEARCH`
- `KAGGLE_MULTI_GPU_INVESTIGATION`
- `KAGGLE_LLAMA_CPP_CUDA_COMPATIBILITY`
- `KAGGLE_LOCAL_VS_REMOTE_BENCHMARK_PLAN`
- `KAGGLE_QUOTA_AND_RECOVERY_DESIGN`
- `KAGGLE_WORKER_IMPLEMENTATION_PROPOSAL`
- `CLAUDE_SESSION_STARTUP_HOOK_REVIEW`
- the unapplied `KAGGLE_WORKER_PROPOSED_DIFF_2026-11-25.patch` (dry-run clean)

Findings:
- **Second T4 idle:** caused by our own `.to("cuda:0")` (`kaggleworker.py:379`). The reports show 7,833 MiB on GPU 0 against 3 MiB on GPU 1.
- **llama.cpp build:** the 24 Nov failure log was lost to `pip -q` and a 600-character cut. It failed within about 19 s, at configure time. Fix: the pinned official prebuilt `ubuntu-cuda-12.8` binary, which suits both the T4 and the GTX 1050 Ti. CUDA 13 has no Pascal support, and 13.5 PTX cannot run on driver 580.
- **Quota:** readable by a supported API (`kaggle quota`).
- **Ollama twins:** six Ollama models have registry manifests identical to the local ones.
- **Startup hook:** the `SessionStart:compact` error comes from the synced `aws-startup-advisor` 2.0.1, whose `scripts/startup-context.txt` is missing.

Session safety:
- The launcher check refused, because the sandbox injects git `safe.directory` variables naming the forbidden folder.
- A Review Council pre-dispatch hook read the forbidden folder's git state when a reviewer agent was requested; the agent was not dispatched, and no further agents were used.
- Restart from a normal terminal with the launcher.

Nothing approved.
