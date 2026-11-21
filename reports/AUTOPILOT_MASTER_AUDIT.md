# Autopilot master audit (21 Nov 2026)

Scope: the owner's master prompt of 21 Nov (self-recovering Autopilot). All work in `~/studio`, uncommitted. Autopilot stayed `enabled: false` (with `auto_approve` on, a full tick would approve and schedule); productions ran through Autopilot's own make step (`autopilot.make_one`) and the fixer (`run.py repair`), supervised.

## What is true now (evidence in the linked reports)
| Area | State | Evidence |
|---|---|---|
| Recovery | real power cut (20 Nov 18:53 UTC) while idle: 839 state files intact; a pid-reuse hole and a duplicate-video hole closed; the long film's final pass resumes in 2-minute parts | POWER_LOSS_AND_RECOVERY.md |
| Recovery on a real film | try 3 of the Seven Sleepers film kept **81 of 81 scenes and 9 of 9 parts**; the first resume kept only 22 of 81 (cause not proven; diagnostics added) | AUTOPILOT_DOCUMENTARY_PRODUCTION.md |
| Orchestration | Autopilot plans actions from state (planner, executors, lock); stage hand-overs now on films and Shorts with job, task id, contract, file references, checkpoint and models. These are checks inside one process, recorded as data; the agent bus (A2A tasks between agents) is separate and was not exercised by these productions | a2a.py, run.py |
| Free models | measured per role; circuit breaker, Retry-After, waits, race, truncation retry; a router judge served by the writer is now refused | FREE_MODEL_ROUTING_AUDIT.md |
| Blender | real Cycles globe of Ephesus in the film (10.9 s clip), seen on frames | BLENDER_INTEGRATION_AUDIT.md (21 Nov section) |
| Documentary | made, 19.1 min (below 20), decodes fully, review **fail** (3 unsupported details flagged by two free judges): held | AUTOPILOT_DOCUMENTARY_PRODUCTION.md |
| Shorts | Tenali Rama repaired to **pass**; new Raijin and Fujin Short held (title_matches block) | AUTOPILOT_SHORT_PRODUCTION.md |
| Fixes | 13 rows, 5 found in real production today | PERMANENT_FAILURE_FIXES.md |
| Dashboard UI | not clicked through: it needs the owner's login (an assistant must not sign in with the owner's saved password) | - |

## Did Autopilot complete both videos independently?
Partly. Autopilot's own code chose the topics, wrote, checked, voiced, drew, rendered, packaged and reviewed both. It needed the engineer four times for code defects (final parts, description crash, the fixer's wrong-line edit, the narrated label), each fixed permanently with a test. The film is complete but fails its fact review and its length target; one Short passes, one is held.
