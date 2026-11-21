# Mission checkpoint, 20 Nov 2026 (supervised Autopilot production)

Updated 16:15 UTC. Nothing committed, pushed, uploaded, approved or scheduled.

## State
- Short `the-true-story-of-tenali-rama`: made and reviewed; the re-review with the new overclaim check says needs_human (line 10 "prove" where the source says "suggest"). Repair waits for 00:00 UTC (its new line needs one new free picture).
- Documentary `doc-did-seven-sleepers-hide-in-a-cave-and-awaken-`: script 81 lines, 2,839 words (about 22 minutes), 12 chapters; voice made; Blender globe of Ephesus rendered (10.8 s); 70 of 81 pictures drawn; stopped at the picture checkpoint (data/pending_doc.json, `waiting_for_pictures` 11 of 81, tries 0).
- Allowances: Cloudflare 8,909 of 9,000 Neurons; OpenRouter free requests nearly used. Both reset at 00:00 UTC.

## Resume (after 00:00 UTC, when nothing renders)
1. `docker --context default exec -w /app studio-worker python run.py repair the-true-story-of-tenali-rama`
2. `docker --context default exec -d -w /app studio-worker sh -c 'python -u run.py autopilot make doc > logs/mission-doc-21nov.log 2>&1'`
3. Verify both files, the dashboard list, the suite and agenteval; finish the reports and the master report section.
A session-only scheduled task does this at 00:12 UTC 21 Nov while this Claude session stays open.

## Tests
Full suite 2,738 passed, 0 failed, 11 skipped (explained). agenteval 67/67 (3 new cases, each with mutation checks).
