# SDD ledger — plan: docs/superpowers/plans/2026-10-19-autopilot.md
Pre-flight: Task 4 consumes Tasks 1-3 (scheduler.next_slot/to_rfc3339, reviewer.review, upload.uploads_today); Task 6 consumes 1,4,5. Names match Produces blocks. Clean.
Ruling: no git repo and no worktree exist in this project — skip worktree and commits, run the full suite instead — cost if wrong: none (nothing to merge).
Ruling: execution is inline (user said "just start"); final review is a self-review because it must use the same Ollama-less sandbox — cost if wrong: weaker review.
Task 1: complete (tests: pytest tests/test_scheduler.py -> 5 pass)
Task 2: complete (tests: pytest -> 22 pass). Ruling: added 'human' severity + deterministic unhedged-claims check because local LLM returned 0/10 risk on a script with a likely invented named person (Martin von Dornburg) — cost if wrong: more videos need a human look.
Task 3: complete (tests: pytest -> 25 pass)
Task 4: complete (tests: pytest -> 38 pass; tick with autopilot disabled does nothing)
Task 5: complete (tests: pytest -> 48 pass; real run found 2 items from 4 feeds)
Task 6: complete (tests: pytest -> 63 pass; Autopilot page loads, 0 console errors)
Task 7: complete (systemd-analyze verify clean, install script syntax ok; timers NOT installed, user must run it)
Final review: fresh opus reviewer, 16 findings. Re-graded by effect.
Final: fixed #1 redo keeps stale review/approval — test_redo_clears_stale_review_and_schedule RED→GREEN, suite 82/82
Final: fixed #2 failed re-review/edits keep old approval — test_failed_rereview_*, test_editing_invalidates_* RED→GREEN
Final: fixed #3 folder overwrite can lose video_id — test_unique_folder_never_reuses RED→GREEN
Final: fixed #4 broken news entry blocks regular videos — test_news_entry_fails_after_two_attempts RED→GREEN
Final: fixed #5 3-strike excludes videos for network/auth errors — test_only_video_specific_failures_count, reset on release/recheck RED→GREEN
Final: fixed #6 tick races dashboard jobs — test_dashboard_busy_reads_live_pid, test_busy_plans_nothing RED→GREEN
Final: fixed #7 SEO drops Sources — test_seo_keeps_sources_block RED→GREEN
Final: also fixed (cheap, real effect): #9 failed video hidden after approve, #10 past publish time, #11 released hold keeps stale slot, #12 javascript: links, #13 slug traversal, #14 "Make it now" wrong item
Final: minor (deferred): #8 approving before the reviewer has run; #15 dashboard poll can make a tick skip; #16 timers stop at logout without loginctl enable-linger; slugs in inline onclick strings (safe because slugs are [a-z0-9-])
Shorts lane: complete (tests: pytest -> 92 pass). Slots from research: Tue/Thu 12:30, Fri 16:00, Sat/Sun 13:00 ET. Shorts paused until a Pexels key exists.
