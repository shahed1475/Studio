# Repair step for the "invented facts" warning: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native, in this session). Steps use checkbox syntax.

**Goal:** A video that passed review but carries a moderate invented-facts warning (risk 4 to 6 of 10) gets one bounded repair before it is approved and scheduled: the details the reviewer named are rewritten from the source article, a wrong description is corrected, and the video is reviewed again.

**Architecture:** The reviewer already names the specific details in the `invented_facts` check (`issues`). `fixer.polish` rewrites only those narration lines with the existing `rewrite_lines` (source-only, no new numbers), corrects the description when a problem names it, backs up the old script, re-renders only if narration changed, then asks the reviewer again. Autopilot gets a new action `polish`, at most one per tick, once per video, never on a video the owner approved, never inside the final 30 hours before its slot, never when the daily cap is spent.

**Tech Stack:** Python, pytest (existing `tests/`), existing `fixer`, `reviewer`, `autopilot`.

**Spec:** the owner's request (20 Oct 2026): "add a repair step for the invented facts warning ... everything must work perfectly". Evidence: Pied Piper's description says "13th-century inscription" while the source says a c. 1440-50 manuscript; Delphi says "historians debate whether the Oracle was truly divine or political" which the source never says. Contract is `docs/AUTOPILOT.md` (updated in Task 4).

## Global Constraints
- Facts come only from the source article (CLAUDE.md A); a rewrite may not bring in a number the source lacks (existing `rewrite_lines` rule).
- Never touch a video the owner approved (`approved_by == "you"`) or one already on YouTube (`video_id`) or on hold.
- State lives in `meta.json`; re-runnable; the old script is saved before any edit (`script_before_polish.json` in the video folder).
- One try per video: `meta["polish_done"]` is set on every outcome, so nothing loops.
- A model failure is never a pass and never a fail (existing review rule); the review after polish is the real judge.
- Tests must pass before any commit; never write real `autopilot.json`/`llm.json` in tests.

## Review Focus
- Warning with no issues text (old stored review): fall back to the `invented_facts` detail text.
- No source article: polish records "no source" and changes nothing.
- Rewrite returns no usable edit: nothing is re-rendered, the video keeps its pass, outcome is recorded.
- Polish run twice: the second is a no-op.
- Owner-approved, on-hold and uploaded videos are never selected.
- Daily cap spent: no polish is planned (it would fall to a weaker model).
- Slot less than 30 h away: no polish (no time to re-render and re-check).
- Two candidates: only one action per tick, the soonest slot first.

## File Structure
- `reviewer.py`: `llm_review` attaches `issues` to `invented_facts` and `invented_facts_watch`.
- `fixer.py`: `watch_problems`, `correct_description`, `polish`.
- `autopilot.py`: state flags, `plan_actions` rule, `do_polish`, tick handling.
- `docs/AUTOPILOT.md`: the contract.
- tests: `tests/test_reviewer.py`, `tests/test_fixer.py`, `tests/test_autopilot.py`.

### Task 1: The review keeps the named issues
**Files:** Modify `reviewer.py` (`llm_review`); Test `tests/test_reviewer.py`.
**Produces:** `invented_facts` and `invented_facts_watch` checks carry `"issues": list[str]`.
- [ ] Failing test `test_the_facts_checks_keep_the_issues_the_model_named`: model returns risk 5 and issues `["a","b"]`; both checks have `issues == ["a","b"]`.
- [ ] Run, see it fail. Implement: set `issues` on both checks. Run, pass. Commit.

### Task 2: `fixer.polish`
**Files:** Modify `fixer.py`; Test `tests/test_fixer.py`.
**Interfaces:**
- `watch_problems(checks: list[dict]) -> list[str]`: the `issues` of the failing `invented_facts_watch`'s sibling `invented_facts`, else its detail text after "risk n/10. "; `[]` when there is no failing watch check.
- `correct_description(meta, source, problems, chat=None) -> bool`: rewrites the description's first two sentences from the source; False when the answer is unusable (40 to 400 characters).
- `polish(slug, chat=None, rerender=None, now=None) -> dict`: `{"skipped": reason}` or `{"changed": [...], "rerendered": bool, "verdict": ...}`.
- [ ] Tests (each red first): `test_polish_rewrites_the_named_lines_backs_up_the_script_and_reviews_again` (rerender called once, backup file holds the old lines, `polish_done` set, verdict returned); `test_polish_corrects_a_description_the_issues_name_without_a_re_render`; `test_polish_changes_nothing_and_says_so_when_there_is_no_source_or_no_usable_edit`; `test_polish_runs_once`; `test_polish_never_touches_a_video_you_approved`; `test_watch_problems_falls_back_to_the_detail_text`.
- [ ] Implement `polish` using `rewrite_lines` (raise its problems cap to 2000 characters), `reviewer.invalidate`, then `reviewer.review`; an `unreviewed` result leaves `polish_done` set and the video to be reviewed again by Autopilot. Log an `agentlog` "applied" event naming what changed.
- [ ] Run the file, then the full suite. Commit.

### Task 3: Autopilot plans and runs the polish
**Files:** Modify `autopilot.py`; Test `tests/test_autopilot.py`.
**Interfaces:** `build_state` videos gain `polish_wanted: bool`; state gains `spend_ok: bool`; `do_polish(slug, cfg, now)` calls `fixer.polish` and approves a pass through `_approve`; constant `POLISH_MIN_LEAD = timedelta(hours=30)`.
- [ ] Tests (red first): `test_a_passed_video_with_a_facts_warning_is_polished_before_it_is_approved_or_scheduled`; `test_only_one_polish_per_tick_the_soonest_slot_first`; `test_no_polish_for_owner_approved_held_uploaded_polished_or_close_to_its_slot`; `test_no_polish_when_the_daily_cap_is_spent`; `test_a_polish_that_re_renders_ends_the_tick_round`.
- [ ] Implement: `polish_wanted` = pass, not news, not `approved_by == "you"`, a failing `invented_facts_watch`, `polish_done` absent. `plan_actions`: for such a video with `spend_ok` and (no slot or slot more than `POLISH_MIN_LEAD` away) emit `polish` and skip its approve/schedule; keep only the best candidate. `tick`: treat `polish` like `fix` (worked, stop when re-rendered). Register in `EXECUTORS`.
- [ ] Full suite. Commit.

### Task 4: Contract, deploy, live proof
- [ ] `docs/AUTOPILOT.md`: add "Polish before approval" (what, when, limits, one try).
- [ ] Full suite, pull --rebase, push, `deploy.sh` (no restart while a render runs).
- [ ] Live: let Autopilot run (or call `autopilot.do_polish`) on Pied Piper first (no slot), then Delphi. Report the new review's invented-facts score and warnings as they are, the lines changed, and the money spent.

## Limits (to be reported, not hidden)
- The reviewer is a model: a 4/10 can reappear with different nitpicks after a polish; one try only, then the video stays passed with its warning.
- Rewrites are made from Wikipedia, a secondary source; no web check is added for interpretive embellishments.
- Re-rendering a video costs time and a little money; videos inside the final 30 hours are never touched.
