# 04 — Hook and skill discovery

Status: COMPLETE. No hook script was executed, and no skill was loaded.

## Studio-local hooks

- `.claude/hooks/studio_guard.py` (16 KB, PreToolUse guard for Bash: refuses destructive `rm` and similar, and deploys without a dry run). From reading its source: it imports only json, posixpath, re, shlex and sys. It runs **no git, no subprocess and no agent**, and writes nothing.
- **It is not registered.** There is no `.claude/settings.json` or `settings.local.json` in Studio, and the user settings contain no `hooks` key. It is exercised only by `tests/test_studio_guard.py`. Live command gating comes from account plugin hooks (as CLAUDE.md says), not from this file. Severity: low, informational. Registering it would be a change to startup infrastructure and the owner's decision.
- No Studio hook runs git before validating the directory, assumes a repository, changes directory, starts agents or writes files.

## Global (non-Studio) startup hooks seen in this session

Plugin SessionStart hooks injected text into this session. These were seen only as context and not inspected (the mission forbids inspecting unrelated plugins). Relevant to the audit:
- One tells the model it "MUST" invoke an architecture skill that runs reviewer agents. That conflicts with the no-subagent rule; the mission file tells the audit session to ignore it.
- One asks for an account to be created with an external service via `curl`. It was not acted on (an outward-facing action the user did not ask for).
- Review Council is installed as agent types; it was neither invoked nor inspected.

## Studio skills (the `.claude/skills/` directory, 51 entries)

ai-film-studio, architecture-redesign, documentary-voice-acting, expressive-voice-director, free-api-provider-routing, gpu-model-compatibility, grilling, grill-me, human-like-tts-production, intelligent-compute-routing, kaggle-gpu-worker, media-studio-expansion, model-checkpoint-recovery, model-inventory-manager, model-license-and-data-policy, model-resource-monitor, model-routing-testing, remote-model-execution, review-judge-compact, script-writer, studio-agent-doctor, studio-agent-eval, studio-agent-trainer, studio-channel-guardian, studio-deploy, studio-packaging, studio-qa-video, studio-script-review, studio-seo, studio-trace-triage, studio-video-finish, voice-emotion-evaluator, voice-recovery-and-checkpoint, voice-skill-creator, watch, youtube-copyright-check, youtube-fact-check, youtube-publisher, youtube-quality-gate, youtube-research, youtube-scriptwriter, youtube-shorts-automation, youtube-video-editor, yt-channel-optimizer, yt-community-post-writer, yt-content-planner, yt-description-writer, yt-hook-scripter, yt-repurposer, yt-thumbnail-brief, yt-title-optimizer.

Note: twelve skill folders (the compute and model-routing family, grilling and grill-me) are untracked in git (see `git status`). Whether each one was added through `extend.py` (as CLAUDE.md requires for third-party skills) is UNVERIFIED and is part of the audit's scope.

Loading mechanism: project skills are discovered from `<cwd>/.claude/skills` at start and loaded on demand with the Skill tool.

## Availability of the skills suggested in mission Part 12 (from this session's skill list)

| Skill | Available |
|---|---|
| engineering:architecture, engineering:system-design, engineering:tech-debt | yes (plugin) |
| studio-agent-doctor, studio-agent-eval, studio-trace-triage, studio-video-finish, studio-deploy, youtube-quality-gate | yes (Studio) |
| backend-design:idempotency-and-side-effects, :error-handling-as-design, :auth-and-authorization, :security-discipline | yes (plugin) |
