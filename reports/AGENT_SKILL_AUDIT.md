# Agent and skill audit (22 Nov 2026)

Sub-plan 3 of the owner's master mission. Skills loaded first: studio-agent-eval, studio-agent-doctor, studio-trace-triage (read from `~/studio/.claude/skills`).
Everything here was run read-only: `agenteval.run(write=False)`, `doctor.scan` (reads the worker log, fixes nothing), `agents.problems()`, `playbook.problems()`, `extend.py verify`, the skill tests, and a reference check of every SKILL.md.

## Agents: all healthy
- Registry: 27 agents, `agents.problems()` empty (every agent has a job or commands and its hand-overs resolve).
- Playbooks: 27 of 27 complete (`playbook.problems` empty for each).
- Doctor scan: all 16 agents with a worker job `ok` (none stale, none failing).
- Behaviour checks: 76 of 76 pass (including the two new cases of 22 Nov: quiet notifications, judge cascade).

## Skills: 34, healthy, two findings
- Format: 63 skill tests pass. Pins: `extend.py verify`: 15 vendored skills match what was reviewed.
- Every file and `run.py` command named in each SKILL.md was checked:
  - Documents named by ai-film-studio, architecture-redesign, media-studio-expansion, voice-skill-creator and youtube-research do not exist yet: they are files those skills tell the reader to CREATE (plans, INSTALL.md, analysis.json). Not a defect.
  - **Finding 1, fixed:** 9 studio skills tell agents to run commands (`run.py agents`, `doctor`, `agent-review`, `guardian`, `judges`, `script-review`, `seo-fix`, `inspect`) that exist but were missing from `run.py`'s help: it listed 32 of the 67 commands it handles. All 67 are now in the help, grouped by job, each described from its own code; `tests/test_run_help.py` fails if a handled command is missing (checked by removing one line: it fails).
  - **Finding 2, reported, not changed:** six vendored skills (yt-community-post-writer, yt-content-planner, yt-description-writer, yt-hook-scripter, yt-thumbnail-brief, yt-title-optimizer) say "parse a URL with `lib/url_parser.py`"; `extend.py` copied each skill folder but not the upstream repo's shared `lib/`. Impact is small (the skills are advisory and a reader can read a YouTube link without it). Fixing means vendoring third-party code through `vetskill.py` and `extend.py`, and editing the skills would break their pinned fingerprints: the owner's decision.

## Agent table (read 22 Nov 2026)
| Agent | Job | Doctor status | Last run (UTC) | Playbook |
|---|---|---|---|---|
| autopilot | autopilot | ok | 2026-11-22T08:38 | complete |
| research | trendwatch | ok | 2026-11-22T06:01 | complete |
| growth | agent | ok | 2026-11-22T06:30 | complete |
| collector | growthdata | ok | 2026-11-22T03:43 | complete |
| diagnoser | diagnose | ok | 2026-11-22T03:43 | complete |
| learner | weekly | ok | 2026-11-16T19:46 | complete |
| news | policywatch | ok | 2026-11-22T06:10 | complete |
| creator | commands only | no worker job |  | complete |
| scriptreview | commands only | no worker job |  | complete |
| clipper | commands only | no worker job |  | complete |
| seo | commands only | no worker job |  | complete |
| qa | commands only | no worker job |  | complete |
| compliance | commands only | no worker job |  | complete |
| reviewer | commands only | no worker job |  | complete |
| fixer | unstick | ok | 2026-11-22T06:50 | complete |
| publisher | commands only | no worker job |  | complete |
| recheck | recheck | ok | 2026-11-22T08:08 | complete |
| titletest | titletest | ok | 2026-11-22T08:00 | complete |
| guardian | guardian | ok | 2026-11-22T08:08 | complete |
| health | health | ok | 2026-11-22T08:08 | complete |
| reporter | report | ok | 2026-11-22T07:00 | complete |
| monetization | commands only | no worker job |  | complete |
| backup | backup | ok | 2026-11-22T03:30 | complete |
| triage | commands only | no worker job |  | complete |
| trainer | commands only | no worker job |  | complete |
| evaluator | agent-review | ok | 2026-11-22T05:30 | complete |
| doctor | doctor | ok | 2026-11-22T03:41 | complete |

## Limits
- A passing behaviour check shows the rules hold on its cases, not that an agent is right on a new problem.
- The doctor judges health from the worker log and each job's cadence; an agent that runs but does poor work is not caught here (the reviewer, quality gate and trace triage cover that).
- No agent was started for this audit (none spends money or touches YouTube from here).
