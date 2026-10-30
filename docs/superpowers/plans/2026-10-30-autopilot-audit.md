# Autopilot audit and fixes, 30 Oct 2026

Owner's order (30 Oct, afternoon): raise the daily cap to $5, make the unverified things verified by the studio itself, find where Autopilot fails or shows imperfect output, fix those. Autopilot stays OFF (the switch is the owner's). Evidence below is from the server's real records, logs and YouTube, read on 30 Oct 13:30 to 14:30Z.

Done first: `llm.json` `daily_budget_usd` 3.5 to 5.0 (backup `llm.json.bak-before-cap5-30oct`).

## Findings (root causes, with evidence)
| # | Finding | Evidence | Fix |
|---|---|---|---|
| F1 | The daily behaviour evaluation writes FAKE edits into the real action log (`agenteval.sandbox` isolates 4 files, `conftest.py` isolates more for pytest only) | `data/agent/actions.json`: 9 of 11 rows are `guardian V2 "t" -> "Mami Wata..."`, one added by a run at 13:40:49Z | isolate every shared file for the whole run; test that a run writes nothing outside; remove the 9 fake rows (backup first) |
| F2 | 12 of 27 records have no `format`; governor, planner, Autopilot and `unstick` call them documentaries, reviewer, fixer, controls and upload call them Shorts | records of 8 Shorts on YouTube lack the key; `seven-sleepers-mystery` (a Short, review 9/10 invented facts) | `records.format_of` used where the default was "doc"; backfill the 12 records; test |
| F3 | The doctor drafts a new skill every 6 hours for the same family, with a new model-chosen name each time | 5 drafts for the "Risks" status digest between 28 and 30 Oct (`studio-risk-triage`, `-cash-runway-check`, `-money-and-upload-risk-check`, `-budget-and-upload-risk-check`, `-budget-and-upload-guard`) | one draft per family, remembered; a status digest is not a problem family |
| F4 | Tasks never close when their cause is gone | `agent evaluation failed` open since 26 Oct (seen 15x) while 46 of 46 checks pass; `risks`, `eyes needs your` | triage closes a family task that no longer occurs |
| F5 | Nobody listens to the narration | the owner's question; the film's voice was never checked | `voicecheck.py`: transcribe the final audio with an audio model, compare with the script; warning only; in the pre-launch step; run on the film now |
| F6 | The picture review looks at 10 frames whatever the length | gate output of the film | sample grows with length (about one frame per 25 s, at most 24) |
| F7 | A documentary may open by stating a legend as fact ("simply vanished") | the film's line 0; Shorts already have `clipper.OVERCLAIM` | writer rule and reviewer warning for documentaries |
| F8 | AI disclosure cannot be read back from YouTube | YouTube's docs list `status.containsSyntheticMedia` as writable in insert and update and say nothing about reading; no video returns it | the upload check says so in plain words instead of staying silent |
| F9 | Second sources were never exercised in production | 0 of 10 documentaries has `sources_extra` | dry-run it on a real topic and report the result |
| F10 | The one failing video was never repaired | `seven-sleepers-mystery`, content task seen 12x | repair it end to end with the fixed code |

Not a defect, recorded: La Llorona's schedule loss has no cause in our code (only `recheck.take_back` and `reschedule` send a status update, and `take_back` logs every success; none logged for it). The re-check "could not finish" event of 26 Oct is a network reset.

## Status
(updated as each is done)
