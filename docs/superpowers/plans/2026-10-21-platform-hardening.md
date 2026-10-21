# Platform hardening: facts, money, Growth and Autopilot, honest reporting

> Native execution, test first. Findings F1 to F13 are in docs/AUDIT_2026-10-21.md.

**Goal:** stop paying to render scripts that invent facts, make Growth and Autopilot share one picture, and make every number the owner sees true.

## Research (21 Oct 2026)
- Chain-of-Verification (Dhuliawala et al., ICLR 2024 workshop): draft, plan verification questions, answer them independently of the draft, then revise; the "factored" variants reduce repeating the draft's own mistakes. Applied as: the judge sees only the sources and the lines, never the writer's reasoning (`scriptgen.unsupported`).
- Attribution before claim (practitioner guides, anecdotal evidence): a claim without a supporting passage is removed. Applied as: a line the writer cannot support from the sources is dropped (`scriptgen.verify_and_revise`).
- Neither removes hallucination: they lower it. The review after the render stays as the second gate. Limit stated to the owner.
- YouTube's own pages (read 20 Oct) already say a title or thumbnail must deliver what it promises; third-party "click-through" advice that contradicts that is refused (`strategy.CLICKBAIT`).

## Steps (all test first; suite 655 tests at the last run)
1. **Script gate that cannot fail open** (F1, F2). `scriptgen.unsupported`, `verify_and_revise` (check, rewrite from sources, check again, drop what stays flagged, refuse a script the sources mostly do not support, refuse one that could not be checked). Used by `doc_script` in place of `support_filter`. DONE.
2. **Facts gate in Autopilot** (owner's rule: nothing with an open invented-facts warning is approved, scheduled, prechecked or uploaded). `autopilot` `facts_open`, held notice after a polish that does not clear it. DONE, deployed.
3. **Third repair try for picture-only problems** (`fixer.attempt_limit`, `fix_limit`). DONE.
4. **Topic hygiene** (F5). `topicrank.premise_check` (one cheap Claude call before a topic is made: invented premise, sensitive subject, already made), `audit_queue` and `python run.py audit-queue` (removed topics kept in `data/removed_topics.json`). DONE in code; the one-off audit of the live queue is run after deploy.
5. **Growth** (F6, F7, F4). Advisor runs on the writer model, receives Autopilot's production feedback (`strategy.production_feedback`), advice that repeats earlier advice is refused, at most 3 open proposals per kind, clickbait title advice refused, `python run.py tidy-strategies` for the pile that exists. DONE in code; tidy run after deploy.
6. **Autopilot follows Growth visibly** (F-section 1). Every topic choice is written to Activity with its reason (`Chose a topic: ...`); Activity page now shows what Autopilot and the agents did. DONE.
7. **Honest reporting** (F3, F8, F10, F11). Settings cost estimate from measured tokens plus AI pictures; fixer event wording; Risks facts row and Next documentary row; planner no longer calls a warned video ready; stale labels; stray `}`. DONE.
8. **No more races** (F9). `python run.py repair <slug> [--extra]` holds the Autopilot lock. DONE.
9. **Not done, by decision** (F12): wider YouTube permission (it would also allow deleting videos).
10. **Owner-only**: top up OpenRouter; Publish app + reconnect before 25 Oct (docs/GOOGLE_PRODUCTION.md).

## Review Focus (what the tests could not cover)
- The judge is a model: a flagged line may be true, an unflagged one may be wrong. Mitigation: the full review after the render.
- Dropping lines can leave a script thin; `doc_script` already refuses under 400 words or 5 chapters and `cmd_doc` retries 4 times.
- `premise_check` lets a topic through when the model cannot answer; the script gate and review still apply.
