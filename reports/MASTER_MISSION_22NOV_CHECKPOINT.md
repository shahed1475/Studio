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
5. [~] Documentary "Maximilian I of Mexico" (owner chose it 22 Nov): pinned (topicqueue.pin doc), started 08:57 UTC in studio-worker with `python run.py autopilot make doc` (never approves), log logs/maximilian-doc.log. If it stopped: read the log; pictures over the daily Cloudflare cap resume after 00:00 UTC with the same command (data/pending_doc.json); then review, render checks (studiochecks video), frames.
6. [~] YouTube scheduling audit done 22 Nov (YOUTUBE_SCHEDULING_AUDIT.md; verify_upload fixed for videos that went public on schedule). Open: approval and a private upload of the new documentary (owner).
7. [ ] Recovery tests (worker kill, network loss, restart)
8. [ ] Reports, master report section, commit and push

## Owner decisions (22 Nov 2026)
- Dashboard: navy surfaces with one accent colour (replaces the v4 black-and-white rule).
- Approval: keep auto-approve, veto window 24 hours (done: `review_window_hours` 24, backup `autopilot.json.bak-before-window24-22nov`).
- Order: quick wins first; each sub-plan ends tested, committed and checkpointed.

## Session notes
- Start Claude Code in `~/studio`: a session started in the workshop gets the workshop's older skills (it lacks review-judge-compact, script-writer, voice-skill-creator); load studio skills by reading `~/studio/.claude/skills/<name>/SKILL.md`.
- Real-Chrome tests cannot start Chrome inside the Bash sandbox; run them with the sandbox off.
