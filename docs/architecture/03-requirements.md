# Requirements (Phase 3 complete, awaiting Checkpoint 2, 25 Oct 2026)

## Owner answers so far
| # | Question | Answer (25 Oct) |
|---|---|---|
| Q1 | Priority for the next 3 months | Real audience first |
| Q2 | Monthly budget | Only the USD already in OpenRouter (credit $8.43 on 25 Oct); no other money stated |
| Q3 | Videos a week | 5 (applied on the server: `max_videos_per_week` = 5) |
| Q5 | Daily money cap | $1.50 (applied on the server: `daily_budget_usd` = 1.5) |
| Q6 | Where the daily off-server copy goes | A private GitHub repo (records only; the owner creates the repo; not built yet) |
| Q7 | Approvals | Keep as is: auto-approve after the reviewer, 2-hour veto; every new channel type needs the owner's approval of each video |
| Q8 | Scale in 12 months | Several channels and platforms (the direction) |
| Q9 | Out of scope now | AI film (Step C), other platforms, clones and avatars, the user studio `test` |
| Q10 | Kit steps | Foundation only (Step B), then stop; Step C waits for credit and an audience |
| Q4 | Acceptable record loss | At most 1 day (an automatic daily off-server copy; place not chosen yet) |

## Requirements
- R1: The studio never spends more than the OpenRouter credit. Testable: the money guard stops new work under `MIN_CREDIT_TO_MAKE` ($1.50).
- R2: Daily spend stays at or under $1.50 (`daily_budget_usd`). Testable: `controls status` money block.
- R3: At most 5 videos a week are made. Testable: `max_videos_per_week` = 5 and the planner leaves later slots empty.
- R4: A daily copy of the saved records exists off the server (private GitHub repo, no secrets, no videos), not older than 24 hours. Testable: a check on its age on the Risks card. Needs the owner to create the repo.
- R5: Growth work (packaging, series links, a weekly read of Studio reach) comes before any new channel.
- R6: Nothing is published, deleted or changed on YouTube without the owner (CLAUDE.md E). Autopilot keeps auto-approve and the 2-hour veto for the stories channel.
- R7: Every record save goes through one safe writer (Foundation). Testable: no module writes `meta.json` directly; a test fails if one does.
- R8: Tests run in the cloud on every push (Foundation). Testable: a GitHub Actions run is green.
- R9: Spend is tracked per studio, with its own cap (Foundation).
- R10: A human gate exists as a channel setting (Foundation), used by every new channel type.
- R11: Out of scope until the owner says otherwise: Step C (AI film), non-YouTube platforms, clones and avatars, the studio `test`.

Conflict noted, not hidden: Q8 says "several channels and platforms" and Q9 puts other platforms out of scope. I read it as direction versus now: build the foundation so channels can come later, and post to YouTube only.

## Not asked (defaults, change if wrong)
Performance: a video in about 25 minutes is fine. Reliability: a day of downtime is acceptable; losing records is not (R4). Team: the owner plus Claude sessions. Hosting: the current VPS; no new paid hosting.

## Risk found while writing this
At today's spend ($2.5 to $2.9 a day) the credit of $8.43 lasts about 3 days. R1 means the studio stops by itself near $1.50.
