# Notification audit (22 Nov 2026)

Sub-plan 1 of the owner's master mission (checkpoint: `reports/MASTER_MISSION_22NOV_CHECKPOINT.md`). The plan was approved by the owner on 22 Nov 2026; one refinement is marked below.

## The problem, with evidence
- The bell counted every unread event and every one popped up as a toast. It showed 24 to 25.
- In the week 15 to 22 Nov the feed logged 199 events. The most frequent were all routine reports: "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing" 25 times (nothing changed), "The saved title now matches YouTube" 9, "Autopilot changed its weekly pace: 2 documentaries, 6 Shorts" 7 (the same pace each time), "Daily research started" 7, "Daily research finished" 7, "Daily briefing" 7.

## What changed
| Change | Where | Evidence |
|---|---|---|
| An unchanged routine report (kind `info` or `found`, same title and same detail) within 24 hours is not logged again | `agentlog._repeat_of`, `ROUTINE`, `REPEAT_WINDOW` | The doctor's line 25 times a week; 35 of the week's 199 events were such repeats |
| An event the code marks important (`notify=True`) carries `"alert": true` | `agentlog.record` | Refinement beyond the approved plan: 14 important call sites are not errors ("Possible algorithm change", "Credit is low", "Re-check: a public video has a problem", "Narration check found missing words"). Counting errors alone would have hidden them |
| The badge counts unread warnings and alerts plus decisions waiting for the owner | `notifyview.needs_attention`, `counts.attention` | Replayed week: 199 counted before, 21 errors (plus alerts) now |
| Only warnings and alerts pop up as toasts, and so as desktop alerts (they ride on the toast) | `dashboard.html` `pollNotes` | Every report was a toast |
| The menu's Growth count uses the same rule | `dashboard.py` state, `agentlog.unread(attention_only=True)` | It counted every unread event, like the old bell |
| "Daily research started" is no longer posted | `agent.py` | "Daily research finished" follows minutes later; the doctor reports a research job that fails or stops |
| Veto window 24 hours (was 2) | `autopilot.json` `review_window_hours` (not in git; backup `autopilot.json.bak-before-window24-22nov`) | Owner's decision of 22 Nov; CLAUDE.md said 24. Auto-approve stays on; `pause_scheduling` stays true, so nothing goes to YouTube |

## What did not change
- Every error, every important (`notify=True`) event, every decision (videos to decide on, rule changes, policy hold, edits to public videos, failed jobs, risks at "act") is counted and shown.
- Routine reports are still logged (only an exact repeat within a day is skipped) and listed with their unread mark; the history, "Mark all read" and the desktop-alert switch work as before.
- Telegram (`alerts.py`: errors and `notify=True` events, deduped, capped) is untouched.
- The doctor's line is logged again as soon as its result changes (a changed detail is a new event), and again after 24 hours.

## Left as is, with reasons
- "Autopilot changed its weekly pace": each real change is still logged; repeats of the same pace within a day are not.
- "The saved title now matches YouTube": each one names a different video, so each is a real event. Routine: listed, not counted.
- "Daily briefing": once a day, routine.

## Limits
- Feed lines written before 22 Nov carry no alert mark, so only their errors count in the badge.
- A repeat must match exactly. A message that embeds a changing number (the money line) is logged each time the number changes. That is intended.
- The repeat check reads the last 400 lines of the feed (the feed held 256 lines on 22 Nov).
- Phase 1 reported 109 call sites from a text search. The table below comes from parsing the code (tests and backups excluded) and is the figure to use.

## Tests (run 22 Nov 2026)
- Targeted: `tests/test_agentlog.py`, `tests/test_notifyview.py`, `tests/test_agents_training.py`, `tests/test_dashboard_api.py` and others: 99 passed. Real Chrome: `tests/test_ui_behaviour.py` and `tests/test_live_ui.py`: 33 passed, including the new test where a routine report raises no toast while an error and an alert do, and the routine report is listed as unread.
- Behaviour check `case_an_unchanged_routine_report_is_logged_once_and_the_bell_counts_only_problems_alerts_and_decisions` passes, and fails under each of five mutations: repeats logged again, an action treated as routine, the badge counting every report, alerts not counted, notify leaving no mark.

## Every place that posts a notification

84 `agentlog.event` calls in 27 files (tests and backups excluded). Classes:

- Routine report: 33
- Warning: 21
- Alert: 14
- Routine action: 12
- Depends on `'error' if summary['act'] else 'info'`: 1
- Alert when `notify`: 1
- Alert when `level != 'ok'`: 1
- Depends on `'applied' if apply_now else 'found'`: 1

| File:line | Kind | Class | Title (code) |
|---|---|---|---|
| `agent.py:149` | info | Routine report | `'Daily briefing'` |
| `agent.py:110` | applied | Routine action | `f"Added {len(new)} story idea{('s' if len(new) != 1 else '')} to the queue"` |
| `agent.py:249` | info | Routine report | `'Daily research finished'` |
| `agent.py:176` | error | Warning | `f'Problem while I was working: {step}'` |
| `agent.py:247` | strategy | Alert | `f"{len(added)} new growth idea{('s' if len(added) != 1 else '')}"` |
| `agent.py:262` | 'error' if summary['act'] else 'info' | Depends on `'error' if summary['act'] else 'info'` | `f"Risks: {len(summary['act'])} need action, {len(summary['watch'])} to watch"` |
| `agent.py:238` | applied | Alert | `f"I applied: {s['text']}"` |
| `agenteval.py:2072` | info | Routine report | `title` |
| `agenteval.py:2071` | info | Routine report | `title` |
| `agenteval.py:2074` | applied | Routine action | `'Repaired a title'` |
| `autopilot.py:699` | error | Warning | `f"Stopped spending on: {meta.get('title', slug)}"` |
| `autopilot.py:181` | info | Routine report | `title` |
| `autopilot.py:557` | found | Routine report | `f"Held a duplicate: {meta.get('title', slug)[:60]}"` |
| `autopilot.py:732` | applied | Routine action | `f"Autopilot made a new {('documentary' if fmt == 'doc' else 'Short')} (supervised): {folde…` |
| `autopilot.py:423` | found | Alert | `f'Narration check found missing words: {title}'` |
| `autopilot.py:507` | error | Warning | `f"Pictures may not fit: {mine.get('title', slug)}"` |
| `autopilot.py:529` | error | Warning | `f'Final check found a problem: {title}'` |
| `autopilot.py:531` | error | Warning | `f'Pulled back for repair: {title}'` |
| `dailyreport.py:109` | info | Routine report | `f"Daily report {day}: {len(report['uploaded'])} uploaded, {len(report['made'])} made, {len…` |
| `discover.py:125` | found | Routine report | `f"New competitor: {c['title']}"` |
| `discover.py:179` | found | Routine report | `f"Added to your reference channels: {_plain(c['title'])}"` |
| `discover.py:219` | info | Routine report | `f"{len(poor)} reference channel{('s' if len(poor) != 1 else '')} may not fit your niche"` |
| `discover.py:195` | info | Routine report | `f"Removed from your reference channels: {b['channel']}"` |
| `doctor.py:439` | found | Routine report | `f"Doctor: {len(sick)} agent(s) unhealthy, {len(result['needs'])} setup item(s) missing"` |
| `drift.py:95` | found | Alert | `'Possible algorithm change'` |
| `escalate.py:78` | found | Alert when `notify` | `f'{agent} needs you: {seo.plain(problem)[:70]}'` |
| `fixer.py:433` | applied | Routine action | `f"Polished: {meta.get('title', slug)}"` |
| `fixer.py:486` | info | Routine report | `f"Set aside to be remade: {meta.get('title', slug)}"` |
| `fixer.py:436` | error | Warning | `f"Held, facts warning remains: {meta.get('title', slug)}"` |
| `fixer.py:621` | info | Routine report | `f"Set aside and remade: {meta.get('title', slug)}"` |
| `fixer.py:642` | error | Warning | `f"Needs your eyes: {meta.get('title', slug)}"` |
| `fixer.py:644` | applied | Routine action | `f"Fixed: {meta.get('title', slug)}"` |
| `fixer.py:455` | info | Routine report | `f"Extra repair try: {meta.get('title', slug)}"` |
| `governor.py:112` | info | Routine report | `f"Autopilot changed its weekly pace: {c['doc']} documentaries, {c['short']} Shorts"` |
| `guardian.py:234` | found | Routine report | `f'Guardian could not finish checking {m.parent.name[:40]}'` |
| `guardian.py:207` | applied | Routine action | `f'Guardian repaired the metadata of {title}'` |
| `guardian.py:217` | applied | Routine action | `f'Guardian rewrote the thumbnail text of {title}'` |
| `guardian.py:224` | applied | Alert | `f'Guardian sent {title} back to Autopilot for repair'` |
| `guardian.py:213` | found | Routine report | `f'Guardian could not change the thumbnail of {title}'` |
| `newswatch.py:200` | found | Alert | `f"YouTube changed its page: {c['page']}"` |
| `newswatch.py:207` | error | Warning | `'Policy classification failed'` |
| `policyclass.py:121` | found | Alert | `f"Policy change ({k['severity']}): {c.get('page')}"` |
| `recheck.py:286` | found | Alert | `f'Re-check: a public video has a problem ({title})'` |
| `recheck.py:241` | found | Routine report | `f"Re-check: {title} has a metadata problem ({', '.join(bad)})"` |
| `recheck.py:301` | found | Alert | `f'Re-check: a scheduled video has a problem ({title})'` |
| `recheck.py:321` | applied | Routine action | `f'Restored the schedule and approval of an uploaded video ({slug[:40]})'` |
| `recheck.py:83` | info | Routine report | `'The saved title now matches YouTube'` |
| `recheck.py:109` | applied | Alert | `f"A video on hold was still scheduled on YouTube: made private ({meta.get('title', '')[:50…` |
| `recheck.py:112` | found | Routine report | `f"Could not check the hold on {meta.get('title', m.parent.name)[:50]}"` |
| `recheck.py:244` | found | Routine report | `f"Re-check: {title} still has a metadata problem ({', '.join(bad)})"` |
| `recheck.py:297` | applied | Alert | `f'Re-check: took a scheduled video back to private ({title})'` |
| `recheck.py:328` | found | Routine report | `'Could not compare saved titles with YouTube'` |
| `recheck.py:278` | applied | Routine action | `f'Re-check: repaired the metadata of an uploaded video ({title})'` |
| `recheck.py:292` | found | Alert | `f'Re-check: could NOT take a failing scheduled video back to private ({title})'` |
| `recheck.py:351` | found | Routine report | `f"Re-check could not finish for {meta.get('title', folder.name)[:50]}"` |
| `recheck.py:270` | found | Alert | `f'Re-check: a public video needs a metadata change ({title})'` |
| `recheck.py:268` | found | Routine report | `f'Re-check: could not prepare a change for a public video ({title})'` |
| `reconcile.py:78` | error | Warning | `f"A video is not on YouTube any more: {meta.get('title', folder.name)[:60]}"` |
| `reviewer.py:673` | error | Warning | `f'The AI review keeps failing: {alert[0]}'` |
| `risk.py:234` | info | Alert when `level != 'ok'` | `f'Money: ${left:.2f} left, ${llm.spent_today(now):.2f} spent today'` |
| `risk.py:206` | applied | Alert | `'Credit is low: ' + '; '.join(changed)` |
| `run.py:537` | info | Routine report | `f"Set aside a saved script: {str(saved['data'].get('title', ''))[:60]}"` |
| `run.py:830` | info | Routine report | `f"Waiting for tomorrow's free pictures: {str(data.get('title', ''))[:60]}"` |
| `run.py:666` | info | Routine report | `f"Resuming an interrupted film: {str(data.get('title', ''))[:60]}"` |
| `run.py:1528` | error | Warning | `f"A command failed: run.py {' '.join(cmd)}"` |
| `run.py:1066` | error | Warning | `'Agent evaluation failed'` |
| `safety.py:94` | error | Warning | `'Autopilot paused: a published video has a problem' if paused else 'A published video has …` |
| `safety.py:145` | error | Warning | `'Autopilot paused: a published video has a problem' if paused else 'A published video has …` |
| `safety.py:126` | error | Warning | `msg[0]` |
| `scriptreview.py:290` | found | Routine report | `f"Script held before voice and pictures: {str(data.get('title', slug))[:60]}"` |
| `specrun.py:239` | info | Routine report | `f'Spec built: {base.name}'` |
| `specrun.py:243` | error | Warning | `f"Spec {res['status']}: {base.name}"` |
| `tenantmode.py:113` | error | Warning | `'Storage is full: no new videos'` |
| `tenantmode.py:120` | applied | Routine action | `'Storage is back under the limit: new videos start again'` |
| `titletest.py:195` | 'applied' if apply_now else 'found' | Depends on `'applied' if apply_now else 'found'` | `f"Title test: {('changed' if apply_now else 'suggest changing')} the title of a weak video…` |
| `titletest.py:173` | found | Routine report | `f"Title test: {meta['title'][:50]} is watched only {pct:.0f}% through"` |
| `titletest.py:149` | applied | Routine action | `f"Title test: the new title did worse ({tt['original'][:40]}...)"` |
| `topicrank.py:179` | info | Routine report | `f'Dropped a topic: {topic[:70]}'` |
| `topicrank.py:217` | applied | Routine action | `f'Screened the topic queue: {len(removed)} removed'` |
| `topicrank.py:174` | info | Routine report | `f'Chose a topic: {topic[:70]}'` |
| `upload.py:194` | error | Warning | `f"Thumbnail was not set: {meta.get('title', folder.name)}"` |
| `upload.py:205` | error | Warning | `f"Cover was not set: {meta.get('title', folder.name)}"` |
| `worker.py:175` | error | Warning | `'The server disk is almost full'` |
| `ytlogin.py:85` | error | Warning | `title` |

## The real feed, 15 Nov 07:00 to 22 Nov 07:00 UTC, replayed through the new rules

- Events logged: 199. Under the new rules: 160 (35 unchanged repeats not logged, 4 "Daily research started" no longer posted).
- Events that counted in the bell when unread: 199 (every one). Under the new rules: 21 errors (plus alerts: the alert mark did not exist before today, so old notify events cannot be told apart in the old feed).
- Unchanged repeats that would not have been logged:

  - 20 x "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing"
  - 6 x "Autopilot changed its weekly pace: 2 documentaries, 6 Shorts"
  - 3 x "Daily research started"
  - 3 x "Competitor research proposals submitted"
  - 1 x "Autopilot changed its weekly pace: 3 documentaries, 6 Shorts"
  - 1 x "Risks: 0 need action, 5 to watch"
  - 1 x "Money: $-0.06 left, $0.00 spent today"

- Most frequent titles in the week (all kinds):

  - 25 x "Doctor: 0 agent(s) unhealthy, 1 setup item(s) missing" (found)
  - 9 x "The saved title now matches YouTube" (info)
  - 7 x "Autopilot changed its weekly pace: 2 documentaries, 6 Shorts" (info)
  - 7 x "Daily research started" (info)
  - 7 x "Daily research finished" (info)
  - 7 x "Daily briefing" (info)
  - 5 x "Competitor research proposals submitted" (info)
  - 4 x "Risks: 0 need action, 5 to watch" (info)
  - 3 x "2 new growth ideas" (strategy)
  - 2 x "Autopilot changed its weekly pace: 3 documentaries, 6 Shorts" (info)
