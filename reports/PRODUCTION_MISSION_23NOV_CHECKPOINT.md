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
