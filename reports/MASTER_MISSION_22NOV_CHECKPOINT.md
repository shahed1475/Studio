# Master mission (owner's brief of 22 Nov 2026): checkpoint

Resume from the first unticked line. Workshop (`~/Desktop/Youtube-automation`) is off-limits: start Claude Code in `~/studio`.

## Phase 1: discovery (done 22 Nov 2026)
- Git: `main`, clean after `eae8bac` (pushed). Remote branches: main, ci/cloud-tests, feature/footage-tool, feature/hub. No stash.
- Running: studio-dashboard and studio-worker healthy; no `run.py`, Blender or ffmpeg job running at discovery time.
- PC: 6 cores, 23 GB RAM (18 used), 241 GB free disk; GTX 1050 Ti not visible to the containers.
- Switches: Autopilot `enabled` true, `auto_approve` true, `make_videos` true, `pause_scheduling` true (nothing goes to YouTube), `review_window_hours` 2 (CLAUDE.md says 24). Paid models off, free models and free review on, free art on (Cloudflare 3,074 of 9,000 neurons used today).
- Agents: 27 in `agents.py`. Skills: 34 in `~/studio/.claude/skills`. No `AGENTS.md`.
- Notifications: 109 `agentlog.event` call sites, 34 with `notify=True`. Feed: 187 events in 7 days. Top repeats: "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing" x25, "Daily research started/finished" x13, "The saved title now matches YouTube" x9, "Autopilot changed its weekly pace" x9, "Daily briefing" x6.
- Dashboard: black-and-white v4 design is enforced by `tests/test_live_ui.py` (`_greys`); the brief asks for colour: owner decision needed.

## Plan: one sub-plan per subsystem (each testable on its own)
1. [x] Notification cleanup (22 Nov): code, tests, agenteval case + 5 mutations, NOTIFICATION_AUDIT.md, CLAUDE.md section; review window 24 h. Full suite 2,922 passed + 1 expected failure fixed (test_dashboard_agent, menu count rule), 11 skipped; dashboard restarted, healthz 200; committed and pushed on main.
2. [~] Dashboard redesign. Step 1 done 22 Nov: v5 navy + one accent colour system (studio.css v5 block, small windows, manifest, ?v=6), WCAG test replaces the grey test, 25 Chrome screenshots, DASHBOARD_DESIGN_AUDIT.md. Open: page-by-page layout polish, motion.
3. [x] Agent and skill audit (22 Nov): 27 agents healthy, 76/76 checks, 34 skills; run.py help now lists all 67 commands (+test); vendored yt-* lib/url_parser.py gap reported. AGENT_SKILL_AUDIT.md
4. [x] Trend research (22 Nov): Google Trends RSS (no fit), Wikipedia pageviews (Maximilian I of Mexico 7.1x), YouTube API scan, demand check; TRENDS_RESEARCH_2026-11-22.md; raw data in data/research/trends-2026-11-22. Topic for sub-plan 5 waits for the owner.
5. [x] Documentary "Maximilian I of Mexico" MADE 23 Nov 04:53 UTC: output/doc-the-prince-of-miramare-the-tragic-reign-of-ma (1920x1080, 30 fps, 1222.7 s, audio, 258 MB; review verdict pass; NOT approved; thumbnail hook text reads "QUERTARO" (should be Querétaro), owner to check). Earlier notes: script written (96 lines, data/pending_draft.json). Fact-check needs TWO different judges; on 22 Nov only gemini:gemini-3.5-flash-lite answered (gemini-2.5-flash 404, gemini-3.8-flash 503 high demand at Google, OpenRouter and FreeLLMAPI judges failing). An hourly retry loop (8 tries from 12:46 UTC) runs in studio-worker, log logs/maximilian-doc.log ("=== retry loop ended"). Manual resume: re-pin (topicqueue.pin) then `python run.py autopilot make doc`.
6. [~] YouTube scheduling audit done 22 Nov (YOUTUBE_SCHEDULING_AUDIT.md; verify_upload fixed for videos that went public on schedule). Open: approval and a private upload of the new documentary (owner).
7. [x] Recovery tests (worker kill, network loss, restart). Started 23 Nov 06:55 UTC. Render/power-cut recovery was already proven 20-21 Nov (drills 1-3, LOAD_SHEDDING_AND_RENDER_RECOVERY.md, POWER_LOSS_AND_RECOVERY.md); this step covers what they did not.
   - [x] 7a drill 4 PASSED 07:05 UTC: kill -9 of the worker's pid 1 at 2 checked scenes, Docker restarted it in <1 s (restarts 1->2), seg02.part.mp4 (48 B) never used, scan + doctor saw it, resume 2 kept / 6 rendered / 0 re-rendered, 32.0 s decodes in full. Worker then ran jobs at their normal times (no burst).
   - [x] 7b offline drill 07:07 UTC (copy in ~/studio-drills/netdrill-20261123, out/ has the logs): 7 jobs, no crash, no record/model/queue change; OpenRouter key UNKNOWN (right); growthdata exit 1 (clean). FOUND: health said "The YouTube login check failed ... Reconnect YouTube" and Risks went to act (network, not login), and that alert used up the day's slot (a real expiry later that day stayed silent). Doctor's dashboard/own-provider/blender items are drill artefacts.
   - [x] 7c boot readiness checked: docker enabled+active, both containers unless-stopped, linger yes, freellmapi.service + freellmapi-netwatch.service enabled and running since the 21 Nov 23:12 UTC boot (old open item resolved). Dashboard restart 07:30 UTC: healthz 200 in 1 s, sessions.json unchanged. Planned worker restart 07:30: healthy in 62 s, job times unchanged; first save by the new code 07:36 (renamed, .prev kept).
   - [x] 7d fixes done, tests/test_recovery_restart.py 13 passed, agenteval case + 3 mutations, neighbours 338 passed: checkpoint.write_text_atomic (own temp name, permissions kept); worker_state.json, autopilot.json, llm.json, agent.json, token.json (5 writers, upload.save_token) renamed into place; ytlogin.offline (no alert, last_ok kept, Risks follows age, watch after 26 h); safety "could not reach YouTube" once a day; Google retryable RefreshError not called expired. Full suite run 3: 2956 passed, 0 failed, 11 skipped (run 1 found a Tailscale address in ULTIMATE_MISSION_CHECKPOINT.md, fixed; run 2 an order-dependent test of mine, fixed).
   - [x] 7e report reports/RECOVERY_TESTS_2026-11-23.md, committed and pushed (see git log).
8. [ ] Reports, master report section, commit and push

## Owner decisions (22 Nov 2026)
- Dashboard: navy surfaces with one accent colour (replaces the v4 black-and-white rule).
- Approval: keep auto-approve, veto window 24 hours (done: `review_window_hours` 24, backup `autopilot.json.bak-before-window24-22nov`).
- Order: quick wins first; each sub-plan ends tested, committed and checkpointed.

## Session notes
- Start Claude Code in `~/studio`: a session started in the workshop gets the workshop's older skills (it lacks review-judge-compact, script-writer, voice-skill-creator); load studio skills by reading `~/studio/.claude/skills/<name>/SKILL.md`.
- Real-Chrome tests cannot start Chrome inside the Bash sandbox; run them with the sandbox off.

## 16:50 UTC update
- Sub-plan 2 layout pass done (v6): see reports/DASHBOARD_DESIGN_AUDIT.md "Layout pass". Full suite 2943 passed, 11 skipped.
- 16:07 UTC: the PC ran out of memory (desktop apps); the kernel killed the documentary retry loop and Docker restarted both studio containers. No render was running; the saved draft and lock were fine. Loop restarted 16:42 UTC for tries 4-8 (first at about 16:58, then hourly), same log logs/maximilian-doc.log.
