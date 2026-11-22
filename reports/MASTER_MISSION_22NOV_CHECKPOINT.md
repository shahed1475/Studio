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
2. [ ] Dashboard redesign (design system, then pages, browser-verified; DASHBOARD_DESIGN_AUDIT.md): navy surfaces + one accent (owner's choice); the v4 grey-token test must be changed with the reason
3. [ ] Agent and skill audit (27 agents, 34 skills: run each, record evidence; AGENT_SKILL_AUDIT.md)
4. [ ] Google Trends research package (browser, real data only)
5. [ ] 20-25 min documentary: script, judge cascade review incl. a rejection and correction, render, full MP4 validation (multi-day: free models and the daily picture allowance)
6. [ ] Approval and YouTube scheduling check (private only, no public release)
7. [ ] Recovery tests (worker kill, network loss, restart)
8. [ ] Reports, master report section, commit and push

## Owner decisions (22 Nov 2026)
- Dashboard: navy surfaces with one accent colour (replaces the v4 black-and-white rule).
- Approval: keep auto-approve, veto window 24 hours (done: `review_window_hours` 24, backup `autopilot.json.bak-before-window24-22nov`).
- Order: quick wins first; each sub-plan ends tested, committed and checkpointed.

## Session notes
- Start Claude Code in `~/studio`: a session started in the workshop gets the workshop's older skills (it lacks review-judge-compact, script-writer, voice-skill-creator); load studio skills by reading `~/studio/.claude/skills/<name>/SKILL.md`.
- Real-Chrome tests cannot start Chrome inside the Bash sandbox; run them with the sandbox off.
