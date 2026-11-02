# Owner control panel: plan (2 Nov 2026, written with about 3% of the weekly limit left)

Owner's request (2 Nov): (1) a button to choose how videos are made: OpenRouter key (Autopilot spends credit) or the current system (Claude Code, free); (2) render on the VPS and the PC together, fall back to whichever is on, never stop; (3) a task bar and a standing-instructions box in Story Studio; (4) if the Claude subscription runs out, continue tasks through OpenRouter Claude; (5) upload a video to YouTube and social media from a button; (6) research and enhance; use few tokens.

Status (2 Nov): phases 1 and 2 are BUILT (owner said 'build 1 and 2'): `ownerdesk.py`, the Tasks page, the two video-source buttons, tests/test_ownerdesk.py, an agenteval case with two mutation checks. Phases 3 to 5 are not built. Each phase is small, test-first and deployed with `deploy.sh dry-run-first`.

## What already exists (read from the code, 2 Nov)
- `autopilot.json` `make_videos` (tick on Autopilot > Rules: "Make new videos"): off = repair, review, schedule, upload only. This IS the "current system" switch; the OpenRouter key is saved in Settings. Missing: a clear two-choice control and the words "Claude Code makes videos".
- `agentbus.py` (`data/agent/tasks.json`): tasks between agents and to the owner; the dashboard already lists owner tasks.
- `tools/remote_build.py`: builds a film on the VPS in a throwaway container (dry run by default). Measured 1 Nov: the VPS was NOT faster (1719 s vs 1013 s on the PC); the owner's rule: renders stay on the PC, VPS is an extra lane.
- `llm.py`: every studio model call already goes to OpenRouter Claude, with free models as fallback.
- `upload.py`: YouTube upload, private with a scheduled time, duplicate-safe, read back.

## Phases (smallest first)
1. **Video source control (cheap, about 1 hour).** Replace the tick with two buttons: "Autopilot makes videos (uses OpenRouter credit)" / "Claude Code makes videos (free; Autopilot only checks, schedules, uploads)". Same `make_videos` flag, plus a visible credit line. Test: the flag round-trips; a mutation check that "Claude Code" never starts a paid video.
2. **Task bar and instructions (the base for the rest).** Two boxes: Tasks (a line the owner types, saved through `agentbus` as kind `owner_request`) and Standing instructions (text saved in `data/owner_instructions.json`, capped at 1,500 characters like a playbook, never in git). Agents read the instructions as ADVICE below the hard rules; they can never relax rules A to F, the four hard rules, the money limits or the publishing rules. A task is a note a Claude Code session or the doctor picks up; no server-side agent edits code or flips a switch from free text. Needs an `agenteval` case and a mutation check (an instruction that says "publish publicly" must be ignored).
3. **Claude subscription fallback.** The studio already runs on OpenRouter Claude. For Claude Code itself nothing in the studio can switch the CLI's account; the safe version is a task runner limited to an allowlist of studio operations (hold, release, queue a topic, run a check) that uses OpenRouter Claude when no Claude Code session is open. Never code edits, deploys, approvals or publishing.
4. **Render pool (PC + VPS).** A job file per render (`data/render_jobs/`), a heartbeat from each machine, the PC first (it has the GPU and the drawn pictures), the VPS only for steps that need no GPU (voice, motion, encode) and only when the PC is off or busy; a job never starts twice (lock per video, like the upload lock). The PC's pictures live in its own cache, so a VPS render needs them copied first (remote_build already does this). Risk: two machines writing one video folder; results go to `output_remote/<job>` and are moved by one owner only.
5. **Upload button.** YouTube: a button on a video's page that runs the existing safe upload (private, scheduled to the next free slot, read back); making it public stays in YouTube Studio. Other platforms (Instagram, TikTok, Facebook, X): each needs the owner's own login or app approval; the Metricool and Posty connectors in this account need the owner to sign in first. Not researched online yet (UNVERIFIED: each platform's API terms, review requirements and whether AI-content labels are required).

## Limits and decisions for the owner
- Phase 2 text boxes are an input the owner controls; webpages and videos are still untrusted.
- A render pool and social uploads touch money, accounts and publishing: each needs the owner's yes before it goes live.
- The studio's own agents cost OpenRouter credit ($4.28 left, about $4 a day): Phase 1 matters most for saving it.
