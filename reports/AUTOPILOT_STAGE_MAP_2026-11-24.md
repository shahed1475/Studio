# Autopilot documentary pipeline: stage map, failure handling and gaps (24 Nov 2026)

Method: a read-only subagent traced the code from `worker.py` (tick every 1,800 s) through `autopilot.tick` -> `plan_actions` -> `do_make` -> `run._cmd_doc` ->
`_produce_doc` -> `finish_video`, then QA, approval and publishing (file:line evidence in the session; spot-checked by hand: `run.cmd_redo` takes no lock,
`reset_for_rerender` dropped the review). It ran no tests and touched no data. "Tests" = files in tests/ that exercise the stage; all of them ran in the full
suite of 23 Nov 23:04 UTC (3,022 passed, 11 skipped, 0 failed). Live run evidence: the Seven Sleepers re-render (reports/SEVEN_SLEEPERS_RENDER_2026-11-24.md).

| # | Stage | Code | Agent | State / checkpoint | On failure | Tests |
|---|---|---|---|---|---|---|
| 1 | Topic | plan_actions, planner.needs, run._best_topic, topicrank.pop_best | creator | pinned > saved draft > ranked queue | premise check, duplicate check and ranking errors let the topic through | test_topicrank, test_autopilot, test_planner, test_duplicates |
| 2 | Research | wikipedia.facts_multi, _second_sources (off) | creator | sources, anchors in the record | Wikipedia down -> no sources -> ungrounded script (the reviewer flags it later) | test_grounding, test_secondsources |
| 3 | Script | scriptgen.doc_script, 4 attempts | creator | data/pending_draft.json (3 uses), data/pending_doc.json | a chapter failing 3 times is skipped silently; local writer fallback | test_doc_attempts, test_doc_structure, test_draft_checkpoint, test_run_resume |
| 4 | Fact-check | scriptgen.checked / verify_and_revise / unsupported | creator (judge prompt) | `script_factcheck` (new, 24 Nov) | no two-family answer -> BLOCKED, waits 120 + 300 s, then the draft is kept and the try not counted; only for grounded scripts | test_fact_check_patience, test_factcheck_record, test_llm, test_grounding |
| 5 | Script review | run._script_gate -> scriptreview.gate (rules only) | creator | data/agent/scriptreview.json | a hold re-asks the writer | test_scriptreview, test_script_retry_note |
| 6 | Title / thumbnail | finish_video: seo.make, honest_first, thumbnail.make | creator | title, tags, thumbnail | title check error = pass; thumbnail falls back to frames | test_seo_research, test_packaging, test_thumbnail_art |
| 7 | Voice direction | sentence pause, voice_tail (photo look); no per-line direction for films | creator | voice_used | none | test_voice_tail, test_editprofile |
| 8 | Voice | tts.narrate (120 s per line, retries) | creator | per-line cache, mark_stage voice, a2a hand-over | a hung stream is cut and retried; other errors raise and the next run resumes from the cache | test_tts_timeout, test_voice_wiring |
| 9 | Images | footage.scene_images, realmedia.Finder, aiart/freeart, Blender | creator | picture caches; footage/credits/assets | stops on a scene with no picture or < 6 unique; waits for tomorrow when the free allowance is spent (forced art, and since 24 Nov also a film under 55% variety) | test_footage, test_picture_wait, test_realmedia, test_freeart, test_blenderscenes |
| 10 | Scene plan | one picture per line, _forced_art, blenderscenes.plan | creator | - | - | test_blenderscenes, test_real_photos |
| 11 | Timeline | durations, chapter times, subtitles.build_cues | creator | words.json, captions; a2a visuals hand-over refuses a scene with no file | | test_a2a, test_subtitles |
| 12 | Editing | _parallax, motiongraphics, _animate, subscribe.add_to | creator | parallax, graphics, subscribe_shown | each falls back to the plain version | test_parallax, test_motiongraphics, test_subscribe_pop |
| 13 | Music / sound | musicbed.bed, sfx.add_to | creator | music, sfx_shown | none or plain on failure | test_musicbed, test_sfx |
| 14 | Render | render._render_ungated (parts, full decode, BT.709) | creator | work/segments.json, .part files, mark_stage assembled | low disk / bad scene raises, finished scenes kept | test_render_recovery, test_render_concat, test_final_parts |
| 15 | QA | reviewer.review (rules, two-family AI review, pictures, listen) | reviewer | review, review_history, review_attempt | AI review error = "unreviewed", never a pass; vision check that cannot run does not block | test_reviewer, test_judges, test_prelaunch, test_review_trail |
| 16 | Approval | autopilot._approve (auto-approve + 24 h veto window) | reviewer / publisher | approved, approved_by | held while an invented-facts warning is open | test_autopilot, test_fixer |
| 17 | Publishing | pause_scheduling, policy hold, duplicates, governor, private upload with publishAt, upload lock + find_interrupted + verify_upload | publisher | publish_at, video_id, upload_started, upload_check | duplicate check / governor errors pass; verify mismatch only printed | test_pause_scheduling, test_upload_guard, test_upload_hardening, test_governor |

## Fixed in this session (tested)
- Fact-check judges of one family counted as two (stage 4): see the Phase B section of the checkpoint.
- A film under the variety floor rendered with repeated pictures when the free pictures ran out (stage 9, Mary Celeste); named-but-unrelated library pictures skipped the judge.
- A re-render dropped the stored review without keeping it in review_history (stage 14/15, `run.reset_for_rerender`).

## Open (not fixed; owner or a later session)
1. `run.py redo` / `remake` / `cmd_redo` take no Autopilot lock by themselves (only a tick, `repair` and `reschedule` do); a hand-run redo can race a tick. The Seven Sleepers redo was run inside `autopilot.exclusive()`.
2. Free drawing paused by a 429/5xx (not the daily quota) is not "spent", so the variety wait does not trigger; scenes then reuse pictures.
3. Fail-open checks: picture title judge, premise screen, duplicate checks, governor, `title_ok` treat an error as a pass.
4. A chapter the writer fails three times is dropped without a note; a pending script past MAX_RESUMES is replaced without a notice.
5. Autopilot's tick output is not written to logs/, so the dashboard's live stage cannot see an Autopilot-run build (inferred from worker.py, not tested).
6. Not tested at all: a failure between render and records.save; a re-render that fails after the fixer saved its edits.
