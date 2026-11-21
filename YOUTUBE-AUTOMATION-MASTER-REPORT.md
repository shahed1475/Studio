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
