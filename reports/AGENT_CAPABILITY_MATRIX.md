# Agent capability and verification matrix (20 Nov 2026)

Sources: `agents.py` registry (27 agents, `agents.problems()` = none), `data/worker_state.json` (last run of each scheduled job), tests that import each module, `agenteval` cases, and what ran live today. Labels: PASS (seen working today on real data), TESTED (unit/behaviour tests pass; not exercised live today), MOCKED (only fakes), NOT TESTED, INFERRED.

| Agent | Module / job | Live today | Tests (files) | Hands to | Status | Evidence / limit |
|---|---|---|---|---|---|---|
| autopilot | autopilot.py / `autopilot` (ticks; Autopilot is OFF) | supervised `make_one` made the Short and runs the documentary | 36 + test_supervised_make | research, creator, fixer, publisher, reviewer | PASS (make + review) | approve/schedule/upload deliberately not run (owner rule); a full tick would approve and schedule Roanoke now |
| research / topic choice | topicrank.py, trendwatch.py / `trendwatch` 06:01 | chose "Tenali Rama" (score 3.648, premise screen passed) and "Seven Sleepers" | 6 + 6 | creator | PASS | topic popped from the queue and logged in the feed |
| creator (writer) | run.py, scriptgen.py | wrote both scripts with free models (gemini-3.5-flash for the Short, minimax-m3.1-flash for the film's chapters) | 30 | scriptreview, seo, reviewer | PASS / documentary in progress | fixed today: patient fact-check, judged in parts, length extension, rewrite length |
| scriptreview | scriptreview.py (gate before voice) | passed the Short's script | 2 | creator, doctor | PASS | |
| fact-check (judges) | scriptgen.verify_and_revise, llm free review | Short: two judges, risk 0; film attempt 1: no judge could answer a 90-line request (fixed) | test_fact_check_patience + agenteval case | | PASS (Short) / see documentary report | free judges missed the "prove" overclaim: new fixed-rule check |
| voice | tts.py (edge-tts, free) | 11 lines for the Short | 18 | | PASS | about 8 s a line |
| visuals | footage.py, realmedia.py, aiart.py, freeart.py | 11 FLUX pictures (1,719 Neurons) for the Short | 18 + 4 + 15 + 5 | | PASS | free allowance 9,000 Neurons a day: checkpoint added for long films |
| Blender (3D) | blenderscenes.py, ccrender.py | Short: nothing planned (no coordinates, no matching place: correct); documentary: pending | 12 + 5 | | TESTED + real headless smoke test | see BLENDER_INTEGRATION_AUDIT.md |
| animation | parallax.py | 11 depth-map clips, 0 failed (Short) | 7 | | PASS | |
| music | musicbed.py | one CC0 nocturne under the Short | 3 | | PASS | |
| render | render.py, subscribe.py, sfx.py | Short: 54.2 s, 1080x1920, 30 fps, AAC, -14.0 LUFS, no black frames, no decode errors | 12 + 7 + 3 | | PASS | |
| seo / packaging | seo.py, video_packaging_rules.py | title, 8 tags, description with the search phrase in front | 10 | reviewer | PASS | |
| reviewer | reviewer.py | Short: 35 checks, verdict pass | 30 | compliance, qa, fixer, publisher | PASS | new rows today: `overclaim` (human), written centuries in the ledger |
| compliance | compliance.py | inside the review (metadata, copying, kids signals) | 7 | | PASS | |
| qa (visual) | videoinspect.py | not run today (paid vision off in Free Mode) | 10 | | TESTED | frames were looked at by the engineer instead |
| fixer | fixer.py / `unstick` 07:48 | not yet on today's videos | 8 | reviewer | TESTED | the Short's overclaim is its first live case (see the Short report) |
| publisher | upload.py | NOT run (owner rule) | 14 | recheck, health | NOT TESTED by design | |
| recheck, titletest, health, report, policywatch, growth, collector, diagnoser, learner | own jobs | ran on schedule today (worker_state) with no error lines in the worker log | 3, 6, 0, 3, 0, 6, 6, 3, 3 | | INFERRED healthy (ran, no errors) | not exercised by this mission |
| guardian | guardian.py / `guardian` 08:22 | ran; never makes anything public | 1 | autopilot | INFERRED | |
| backup | backup.py / `backup` 03:30 | ran | 1 | | INFERRED | off-server copy still missing (owner step) |
| evaluator | agenteval.py / `agent-review` 05:30 | 3 new cases today, each with mutation checks | 6 | triage, doctor | PASS | full run: see the final report |
| doctor | doctor.py / `doctor` 07:46 | knows Blender, music, waiting-film checkpoint and set-aside scripts now | 4 + 2 | scriptreview | TESTED | it recommends and resumes by telling the owner; it never starts a production |
| triage, trainer | tracetriage.py, playbook/lessons | not exercised | 2, 0 | | NOT TESTED today | |
| a2a hand-overs | a2a.py inside `_produce_doc` | script hand-over passed in attempt 1 of the film | 5 | | PASS (script stage) | voice, visuals, render hand-overs: see the documentary report |

Dashboard registration: `dashboard.videos()` (the list the Videos page shows) is read in the dashboard container; the page itself needs the owner's login (`/api/state` answers 401 without it), so no click-through was done.

## 21 Nov 2026 update (supervised production)
| Agent | Live today | Status | Evidence / limit |
|---|---|---|---|
| autopilot (make_one) | made the Seven Sleepers film (3 tries) and the Raijin and Fujin Short; never approved | PASS (make) | AUTOPILOT_DOCUMENTARY_PRODUCTION.md, AUTOPILOT_SHORT_PRODUCTION.md |
| research / topic choice | "Raijin and Fujin, the Storm Gods" from the queue | PASS | log `mission-short-new-21nov.log` |
| creator (writer) | nemotron-3.5-super-vl:free wrote the new Short; it narrated "The payoff:" | PASS with defect fixed | label rule extended |
| fact-check / free judges | two free judges flagged 3 unsupported details in the film; the router-judge hole closed | PASS | FREE_MODEL_ROUTING_AUDIT.md |
| voice | 81 film lines, Short lines; lines kept on resume | PASS | |
| visuals | 62 different pictures for 81 scenes; 10 for the Short; a broken download skipped safely | PASS | |
| Blender | real globe of Ephesus in the film | PASS | frames at 62 s and 67 s |
| render | 81 scenes, 9 checked final parts; failed once on a pixel-format change (fixed), then kept 81/81 and 9/9 | PASS after fix | |
| reviewer | held the film (fail) and the new Short (block); passed the repaired Tenali Short | PASS | |
| fixer | repaired Tenali Rama (after the wrong-line bug was fixed); Raijin: new title, description, ending, label cut | PASS after fix | 2 tries used on Raijin |
| a2a hand-overs | 4 checked stages on the film and on both Shorts | PASS (in-process checks, not inter-process messages) | |
| doctor, guardian, others | not exercised by this mission | INFERRED | |
