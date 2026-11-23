# Production mission (owner's brief of 23 Nov 2026): one documentary + one Short, pipeline upgrade

Resume from the first unticked line. Workshop off-limits. Topic report: reports/TOPIC_SELECTION_2026-11-23.md.

## Phase 1: readiness (08:00-08:20 UTC) [x]
- Git `main` at 76fac75, clean apart from two other sessions' research reports. Containers healthy (restarted 07:30 for the recovery work); worker idle; no retry loop; no pending_doc / pending_draft / pending_short.
- The brief's "previous documentary failed": out of date. Maximilian I of Mexico was MADE 23 Nov 04:53 UTC (1222.7 s, review pass, judges gemini:gemini-3.5-flash-lite + extra:glm-4.7-flash). Weakness found by the owner: no opening question (fixed in Phase 3).
- Judges probed with one real structured request each (08:20): gemini:gemini-3.5-flash-lite 1.0 s, extra:glm-4.7-flash 10.4 s, extra:qwen-3.8-27b 19.1 s, all valid JSON, three families (google, zhipu, qwen). OpenRouter key: dead (401, owner decision since 22 Nov), so OpenRouter is not used; FreeLLMAPI key is in its own field.
- Resources: RAM 23 GB, about 4 GB available, swap 7/7 GB full (pressure); disk 241 GB free; 6 cores; GTX 1050 Ti 1.3 of 4 GB used by the desktop (not passed to the containers). Studio memory gate 3 GB.
- Training: no training process on this PC (ps; no trainer_state.json in 48 h). Nothing to protect or interrupt.
- Free pictures: Cloudflare 7,242 of 10,000 neurons used today (the Maximilian film); a film needs about 6,000, so the picture stage may wait for the 00:00 UTC reset (built-in checkpoint).

## Phase 2: topic [x] The Mary Celeste (reports/TOPIC_SELECTION_2026-11-23.md)

## Phase 3: script pipeline fix [x]
- Cause of the Maximilian "no question" warning: the outline was told to open on the central question, the chapter writer (who writes the lines) never was. `scriptgen.HOOK_RULE` (chapter 1), `REHOOK_RULE` (every chapter), `scriptgen.hook_fix` (one opening question line before the fact-check when none). tests/test_doc_hook.py 7 passed (all 7 failed before).

## Phase 5: production
- First start 08:55:37 UTC stopped by me at 08:58 (script stage, nothing saved or spent): `run.py` imports `render` at start, so the running job would have rendered with the old colour settings.
- [~] Documentary RESTARTED 09:04:01 UTC with the new renderer: `docker exec -d studio-worker ... python run.py autopilot make doc` (pinned "The Mary Celeste"), log logs/mary-celeste-doc.log. Sources: Mary Celeste, Arthur Conan Doyle. Resume after a cut: re-pin if pinned_topics.json is empty, then the same command (saved draft / pending_doc resume by themselves).

## Phase 6: colour and finish (done before the restart) [x]
- Measured on the Maximilian film: no colour tags; BT.601 matrix where players assume BT.709 (red 200,60,40 played as 212,72,36); 1.45 Mb/s video; AAC 44.1 kHz 224 kb/s; the old "grade" eq=brightness=-0.05:saturation=0.85 crushed up to 21% of a picture to black and raised saturation 0.34->0.50; faststart was fine.
- Fixed: `render.BT709` in every `_venc` (options + h264_metadata VUI flags; options alone reached only the matrix), `render.GRADE` (S-curve with highlight roll-off, lifted blacks, small cool/warm split, saturation 0.9, soft vignette; 0% clipped, 0% crushed, about 10% darker on 3 real pictures) for stills, real footage and parallax clips, final passes CRF 18 (was 21/19), `render.AUDIO` AAC 320 kb/s 48 kHz. tests/test_render_grade.py 3 passed on host (openh264) and worker (libx264); render-related suites in the worker 132 passed (test_animation updated for the new grade). DaVinci Resolve: not installed, not used.
- [ ] Short (after the documentary: one render at a time): pin "The Mary Celeste" short, `python run.py autopilot make short`.
## Phases 6-15: [ ] QC both files, grade/colour metadata, captions, audits, browser QA, report, suite, commit.

## 10:15 UTC status
- Script: written and fact-checked 09:04-09:25 UTC (89 lines, 3,335 words, 13 chapters, title "The Ghost Ship: The True Story of the Mary Celeste"); opens on a question (the hook fix worked); saved in data/pending_doc.json, tries 0.
- Voice: lines 0-70 made and recorded; the edge-tts stream HUNG on line 71 from 09:49 to 10:10 UTC (no timeout in tts._synth_once). Fixed: `tts.LINE_TIMEOUT` 120 s per attempt with retries (tests/test_tts_timeout.py, 40 voice tests pass). Job stopped and resumed 10:10:47.
- Resume REFUSED by the memory gate (1.8 GB free, needs 3 GB; the owner's QEMU VM ~6 GB, Chrome, VS Code). Not bypassed. `logs/.mary-celeste-wait.sh` (setsid, host) checks every 2 min for 8 h and resumes at 3.3 GB free; it never starts a second job.
- Free pictures: about 2,750 of 10,000 Cloudflare units left today, a film needs about 6,000: the picture stage will finish after the 00:00 UTC reset (built-in wait).
- NEXT: when the film is made -> QC (ffprobe, full decode, colour tags, frames, audio, captions), then the Short (pin "The Mary Celeste" short; `python run.py autopilot make short`), QC, browser check, report reports/PRODUCTION_MISSION_23NOV.md, suite, commit.

## 13:00-14:05 UTC: recovery after the 12:44 UTC power cut (recovery mission session)
- Interrupted: the Mary Celeste film (voice lines 0-70 saved, line 71 half-written as .part; waiting since 10:10 on the 3 GB memory gate). The 10:10 wait script died with the reboot and could never have started the job anyway (`docker top -o args` fails without a pid column). Nothing else was running; no duplicate job; Autopilot only logged memory waits.
- Verified: 143 of 143 saved files (script + 71 voice lines with records) matched their SHA-256 after the resume; the .part was never used; the cut did not use a try.
- Judges probed 13:08 (one planted false line): gemini-3.5-flash-lite 1.0 s, extra:glm-4.7-flash 22 s, extra:qwen-3.8-27b 32 s, all valid JSON, all flagged only the false line.
- Doctor after reboot: 16 job agents healthy, only "off-server backup" missing. agent-review 13:10: 79/79.
- [x] Script defect found and fixed: the free-model script retold whole chapters, named people with no introduction and ended on a stray fact. Causes: `extend_to_length` appended source facts after the closing chapter; `LINE_WORDS_MAX` was never enforced (lines of 59-86 words); the writer's source was the article cut at 17,889 characters for a 20-26 minute film.
  - Job stopped by me at 13:13:05 in the voice stage (no picture spent). Old script kept as data/pending_doc.json.bak-before-rewrite-23nov, old voice in output_old/mary-celeste-first-script-voice-23nov.
  - New script written in this Claude session from the FULL article (37,585 chars, what the reviewer checks): 104 lines, 13 chapters, 3,273 words (about 22 min of narration). scriptreview.rows all ok; two-judge fact-check: run 1 flagged 3 (fixed), run 2 (nemotron-3-ultra) flagged 24 citing a "SOURCES cutoff", recheck on the matching sections passed 23, last 2 verified by exact passage. Recorded in the record as script_rewrite / script_model.
  - Film resumed 13:31:09 UTC.
- [x] Code: `scriptgen.growable` (hook and closing chapters never extended), `scriptgen.split_long_lines` + `sentences` (cut at whole sentences, writer only); tests in tests/test_doc_length_extension.py (13 pass), agenteval case + 4 mutation checks (tests/test_agents_training.py, 102 pass); creator playbook brief still keeps its whole Never section (1,487 chars); youtube-scriptwriter skill brought up to date. UNCOMMITTED.
- [ ] Film: voice -> pictures (free allowance: 1,758 units left today, ~16 pictures; the rest after 00:00 UTC) -> render -> review. Resume after a stop: same command `docker exec -d -w /app studio-worker sh -c 'python run.py autopilot make doc >> logs/mary-celeste-doc.log 2>&1'`.
- [ ] Short (after the film; picture budget), QC both, reports, suite, commit.

## 16:20 UTC: the film is made, not ready
- MADE 15:57 UTC: output/doc-the-ghost-ship-the-true-story-of-the-mary-cel/video.mp4, ffprobe: 1181.5 s (19 min 41.5 s), 1920x1080, 30 fps, h264 yuv420p, bt709 primaries/transfer/matrix, AAC 44.1 kHz stereo (the 48 kHz rule did not reach this file: check render.AUDIO), 406 MB. Blender 7/7. Voice: current channel voice (owner chose 23 Nov: re-voice after hearing new samples).
- Review 16:10 UTC (`run.py review`): UNREVIEWED. block llm_review ModelUnavailable (Gemini 503 at Google; GLM 69 s and Qwen 17 s on a small probe, likely past the 120 s limit on the full review). Warnings: picture_variety 54 different pictures for 104 scenes; doc_length 1182 s (owner range 1200-1560); rehook_gap 159 s; originality 8 %.
- SEO picked the title "Mary Celeste: What Happened to Her Ten Missing Crew?": wrong (the ten were the captain, his wife, their daughter and seven crew). Must be changed before any approval.
- [ ] Why the film rendered with repeated pictures instead of stopping for the 00:00 UTC reset (`_wait_for_pictures`): investigate; then redraw the repeated scenes after the reset.
- [ ] Re-run the review when two judge families answer.
- [ ] Re-voice after the owner's recordings and sample choice; then the Short.
- Not approved, not scheduled, not uploaded (pause_scheduling true).

## 24 Nov 2026 ~18:40 UTC: master mission "fix review/Autopilot, UGC video, QA, release" (owner's paste)
- Repeated reviewer report = Seven Sleepers (`output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-`), stored review of 2026-11-21T12:32:26Z, approved by the reviewer agent, not on YouTube, no publish time.
- ROOT CAUSE (evidence): (1) its four findings are rule checks; a rules-only review run on a reflink copy at 18:19 UTC gave the identical four (same script, same video); (2) the panel showed no date, id or script fingerprint, so a new review looked like the old one; (3) no history, and an unreviewed run deleted the stored review. No dashboard review job ran for this video after 21 Nov (logs/*-review.log).
- [x] Fix: reviewer.py (result `id`, `script_sha` = `script_fingerprint`, `keep_history` -> `review_history` last 20, `review_attempt` for an unreviewed try, invalidate keeps history); dashboard.py `review_trail` (script_sha_now, history summary, attempt); dashboard.html panel line (date, age, id, script, stale / same-script note), attempt line, "Earlier reviews" list; address keeps the open video (`#videos/<slug>`), so a refresh stays on it.
- [x] Tests: tests/test_review_trail.py (4) + 3 mutations caught (scratchpad mut_trail.py); tests/test_review_panel_ui.py (2, real Chrome: B shown, A kept, real reload keeps B, changed script -> "stale", failed try shown); with test_ui_behaviour 28 passed.
- LIVE NOTE: dashboard.html changes are already served (pages are read per request); dashboard.py `review_trail` needs a dashboard restart (not done: release approval).
- [ ] Full suite after the change; Seven Sleepers script fixes (hook, re-hook map, length, lines 12/30) + re-render; Autopilot stage test; UGC draft video; dashboard full QA; voice samples (BLOCKED: recordings); release review; commit; deploy (approval).

## ~19:35 UTC: Seven Sleepers rescript, waiting for independent judges
- Dashboard restarted 18:41:47 UTC (owner's yes; healthz 200 in 2 s, no job running, worker untouched). Full suite after the review fix: 3006 passed, 0 failed, 11 skipped.
- The Seven Sleepers script was a fact list (feast dates x6, durations x6, note fragments read aloud, 4 of 81 lines tell the legend). New script written in this session from its three full source articles (25,670 chars): data/rescript/ss_script.py (copy of the scratch file), 93 lines, 14 chapters, 3,031 words, about 1,227 s at the film's own measured pace (2,839 w -> 1,149 s). scriptreview.rows: all ok. Fact-check: OpenRouter nemotron-3-ultra + nemotron-3.5-lightning (ONE family: not independent) flagged 1 line (closing, reworded).
- Two-family check (glm Zhipu + qwen) BLOCKED: timeouts, 502, 429 quota. GLM and Qwen run on the owner's Cloudflare account through FreeLLMAPI: the same daily Neurons as the free pictures (8,909 of 9,000 used today). Gemini 503 since 16:10.
- FOUND: the script fact-check path (scriptgen.unsupported via _review_chat strict) accepts two judges of the same family; the video review cascade (judges.py) enforces families. Not yet fixed.
- NEXT (after 00:00 UTC reset or Gemini back): two-family check of ss_script.py; then back up the folder to output_old, write the lines into meta.json, `with autopilot.exclusive(): run.cmd_redo(slug)`, pictures fit one day (~93 lines; real photos lower it); then review (fresh id) and inspect the MP4.
