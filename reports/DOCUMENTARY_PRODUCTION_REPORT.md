# Documentary production report (20 Nov 2026)

## Topic and source
- Topic "Seven Sleepers", chosen by Autopilot's topic ranking (`topicrank.pop_best`, weekly programme) at 08:44 UTC from the Studio queue; pinned again before each restart so every run made the same Autopilot-chosen film.
- Sources (run 7 onward, `scriptgen.source_budget`): Wikipedia "Seven Sleepers" (up to 17,889 characters), "Cave of the Seven Sleepers" (5,378), "Seven Sleepers' Day" (3,085), all CC BY-SA 4.0, retold in our own words. Second sources are off in Free Mode.
- Owner's length: 20 to 26 minutes (rules.json, approved 20 Nov); target about 22 to 23.

## Runs (all `python run.py autopilot make doc`, supervised; logs `logs/mission-doc-20nov*.log`)
| Run | UTC | What happened | Root cause | Permanent fix |
|---|---|---|---|---|
| 1 | 08:44-09:23 | the old 54-line Pyramids script was set aside (new rule); a full draft was written; "could not be fact-checked (ModelUnavailable)"; attempt 2 began writing from scratch | judges cut off by their output limit on one 90-line request | fact-check in parts of 30 lines; busy judges wait 120 s and 300 s and the same draft is checked again |
| 2 | 09:25-09:32 | "no cloud model answered the script job" | Gemini and MiniMax daily limits used up; OpenRouter's free reasoning models thought until the cap (measured: 6,000 of 6,000 tokens, effort "low" ignored) | a thinking budget per role (1,024 writing, 3,000 judging, 512 small jobs); a cut-off reply is asked again without thinking |
| 3 | 09:38-10:10 | script passed its check but was 83 lines, 1,973 words (15.4 minutes); stopped before any picture | short lines; the check removed lines; retold lines removed after | length loop after the check (grow, check again) |
| 4 | 10:11-12:12 | about two hours of writing and checking, then "no free judge could answer" three times; the draft (in memory only) was lost | the writers rotated across six free models, all barred from judging; the draft was never saved | the script's own writer writes its next part first; the draft is saved before its check (with its writers) and resumed after a restart |
| 5 | 12:14-12:30 | draft saved by one writer: 119 lines of about 18 words | one picture per line: about 12,400 Neurons for the free allowance's 9,000 | short lines of one chapter joined toward 30 words (at most 44); saved scripts judged by words, not lines |
| 6 | 12:30-13:08 | resumed the draft, checked and grown twice: 48 lines, 1,653 words (12.9 minutes) | the real root cause: 2 articles cut at 7,000 characters (about 2,000 words) for a 2,600 to 3,300 word film; the check rightly struck what the sources do not say | source text follows the owner's length: about 17,900 characters x 3 articles at 20 to 26 minutes |
| 7 | 13:10-13:25 | 3 articles read; draft 110 lines, 1,988 words before its check | traced: each growth aimed at 1.06x the minimum and the check cut it back below every time | growth aims above the target by what the last check removed (up to 1.6x), as many chapters and lines as the gap needs, up to 3 rounds; retold lines removed before the loop |
| 8 | 13:25- | resumed run 7's draft (no rewriting) | | |

Also found and fixed during these runs: a judge request held 600.8 s against a 120 s limit (total deadline on every request); data/free_models.json wiped by concurrent writers (atomic, locked writes).

## Result
(completed below when run 8 finishes)
