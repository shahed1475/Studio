# Pipeline audit (2026-11-20)

Flow: Autopilot (`autopilot.plan_actions`) decides, the worker runs `python run.py …` as a new process for each job (`worker.py:109`), and every stage writes its state to files, so a job can be re-run.

| Stage | Entry point | Input → output (persisted) | Provider | Errors and retries | Tests |
|---|---|---|---|---|---|
| Topic | `topicrank.pop_best`, `run._best_topic` | queue and signals → topic. A source article must exist. Duplicate check (`duplicates.py`). | none | A topic is re-queued, then dropped after 2 failures | test_topicrank, test_duplicates |
| Research | `wikipedia.facts_for`; `secondsources` (paid, off in Free Mode) | topic → source text, `sources` in meta | Wikipedia | No source: the script is flagged for a human check | test_grounding, test_secondsources |
| Script | `scriptgen.doc_script` (outline, then one call per chapter), `scriptgen.verify_and_revise`, `run._script_gate` → `scriptreview` | source → `lines`, `chapters`, title, tags | `llm.chat` (free race) | 3 tries per chapter; held script, writer asked again; 3 holds post a doctor task | test_doc_structure, test_scriptreview, test_grounding |
| Voice | `tts.narrate` | lines → `narration`, `durations`, words.json | free TTS | exception, the job fails | test_tts* |
| Visuals | `footage.scene_images` (real media first, then drawings), `_real_footage`, `_animate`, `_parallax` | lines → clips and credits (`meta.assets`) | Commons and other free libraries, Cloudflare free art | Drawing failure: falls back to search, then the pool, then reuse; the scene goes blank only with nothing at all | test_footage*, test_animation, test_freeart |
| Render | `render.render` (gated) | clips, durations, narration → `video.mp4` | ffmpeg (local) | CalledProcessError, the job fails | test_render_concat, test_motion, test_smooth_people… |
| Review | `reviewer`, `gate.py`, `studiochecks`, `ledger` | video and meta → checks, `claims.json` | free judges (two, worse answer counts) | A model failure is `unreviewed`, never a pass | test_reviewer, test_gate* |
| Packaging | `thumbnail.make`, `seo`, `video_packaging_rules`, `compliance.final_description` | → title, description with credits, tags, chapters, thumbnails | free models plus rules | | test_packaging, test_seo* |
| Registration | `records.save(folder, data)` → `output/<slug>/meta.json`; the dashboard lists `output/` | | | | test_dashboard_*, test_records |
| Approval | `autopilot.do_approve` (owner or auto-approve), `facts_open` blocks | | | | test_autopilot |
| Publishing | `do_schedule`, `do_upload` (private with a time; `upload_started` written first; per-video lock) | | YouTube API | A retry finds the earlier copy | test_upload_guard, test_autopilot |

## Defects found and fixed
1. **Documentary length could not meet the owner's 20 to 26 minutes.**
   - Cause: `scriptgen` was fixed at 42 to 58 lines and 1,150 words (8 to 10 minutes), set apart from the reviewer's `rules.json` benchmark.
   - Fix: `scriptgen.doc_budget(lo, hi)` derives lines, words, chapters and line length from `rules.json` `benchmarks.long_min_minutes` / `long_max_minutes`. That is the same pair the reviewer's `doc_length` warning and `craftlearn` read. The pair is now 20 / 26.
   - Result: 84 to 100 lines (one picture each), about 2,940 words, 10 to 13 chapters of 7 to 9 lines, 27 to 39 words a line. Every tested topic shape lands at 23.1 to 23.7 minutes of narration.
   - With 8 / 10, the function returns exactly the old numbers (test).
   - The outline prompt now says "Plan a 20 to 26 minute…".
   - `reviewer.REVIEW_TEXT_CHARS` is raised from 20,000 to 32,000, so the AI review reads the last chapter of a long film.
   - The hard reviewer limit (`limits.doc_duration_s`, 180 to 1,800 seconds) already allowed 26 minutes and is unchanged. Shorts are separate (`shorts_min/max_seconds`, unchanged).
   - Tests: `tests/test_doc_structure.py` (5 rewritten or new), `test_variety`, `test_risk`, and the agenteval documentary case plus its existing mutation (the old 50-line cap is still caught).
2. **A GIF saved as `.jpg` killed a finished render.** `logs/180853-doc.log`, 19 Nov, "The Secret Code of the Pyramids": the voice, 54 scenes and 33 motion clips were done, then ffmpeg read `cache/e5ea9fed7777.jpg` (a GIF, 817×573) with its GIF reader, "Option loop not found", and the job failed. Fix: `render.still_for_ffmpeg` writes any still that is not really a JPEG or PNG as a JPEG once, in the work folder. Test with real ffmpeg (GIF-named-jpg, WebP, real JPEG) plus a mutation check.
3. Free Mode paid calls in the thumbnail score, the narration listen and the video analysis: fixed (see `FREE_MODEL_OPTIMIZATION.md`).

## Observed, not changed (owner's decision)
- That same Pyramids film had **no source article** ("script will be flagged for a human check"). The pipeline allows a sourceless documentary when it is started by hand (`run.py doc <topic>`); Autopilot topics need one. A title like "Deciphering Egypt's Celestial Blueprint" is a pseudo-history risk: keep the rule that it waits for the owner.
- A 20 to 26 minute film needs about 90 pictures. With the photo look every scene is drawn, which is more than one free Cloudflare day (9,000-neuron cap, about 58 to 86 drawings). The rest fall back to real photos or reused pictures, so the film is still made, but with more repeats. Real photos come first in the default look.
- The time for one long render was not measured on this machine yet (see `END_TO_END_VIDEO_TEST.md`).
