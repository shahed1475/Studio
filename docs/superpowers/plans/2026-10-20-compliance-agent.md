# YouTube compliance agent and thumbnail-hook repair: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native, this session). Steps use checkbox syntax.

**Goal:** (1) A thumbnail hook must match what the narration says, and Autopilot detects and fixes a mismatch itself (Delphi first). (2) A per-video compliance agent checks the YouTube rules this channel can break, from a sourced rule catalog, with automatic remedies, and reports in the Risks card.

**Architecture:** `compliance.py` holds the rule catalog (each rule: id, official source URL, date verified, the policy page it depends on, severity) and deterministic checkers. The reviewer runs them with every review (so Autopilot runs them at review, fix and polish time). The AI review also judges the thumbnail text in its one existing call. The fixer gets three remedies (new hook, metadata sanitise, reword copied lines). Existing `newswatch.policy_watch` supplies "a page a rule depends on changed": the Risks card then asks for a re-check of those rules.

**Tech Stack:** Python, pytest. Existing `reviewer`, `fixer`, `thumbnail`, `safety`, `risk`, `newswatch`.

## Research (accessed 20 Oct 2026; Wikipedia-style secondary summaries are NOT used here)
| Rule | Source | Status |
|---|---|---|
| Title max 100 chars, no `<` `>`; description max 5000 bytes, no `<` `>`; tags 500 chars total, commas and the quotes around a multi-word tag count | developers.google.com/youtube/v3/docs/videos (snippet properties) | VERIFIED (read on the page) |
| Misleading titles, thumbnails, descriptions that do not deliver what they promise; high-volume near-identical automated content; scraped/re-uploaded material without commentary | support.google.com/youtube/answer/2801973 | VERIFIED |
| Monetization: templated/repetitive videos, slideshows or reading text you did not write, mass-produced generic AI content are not allowed; AI as a tool, distinct storylines and shared intro/outro are fine | support.google.com/youtube/answer/1311392 | VERIFIED |
| Disclose realistic altered or synthetic content; animation and clearly unrealistic content, and AI help with scripts or thumbnails, need no disclosure; API field `status.containsSyntheticMedia` exists | support.google.com/youtube/answer/14328491, videos resource page | VERIFIED. Our upload already sets it true; the art is storybook style (guarded by a test) |
| Audience (made for kids) must be set per video when the channel has no default; a wrong setting can be overridden and locked | support.google.com/youtube/answer/9527654 | VERIFIED. Upload sets `selfDeclaredMadeForKids: false`; the agent warns on kid-directed wording |
| Videos from unverified API projects locked to private | search results say yes (quoting the reference); the official `videos` page read today says they are NOT restricted | **CONFLICTING**: no rule claims either way; `safety.check` already catches "still private after its slot" and now names this possibility |
| Phone verification needed for custom thumbnails and videos over 15 minutes | third-party guides only | **UNVERIFIED** (not in the catalog as a rule; the upload already survives a thumbnail failure, now recorded and reported) |

## Evidence from our own videos
Copied wording against the source article (8-word runs): 0 to 4.1% across all 8 videos, so warn at 6% and block at 15%. Delphi's thumbnail says "PROPHECY OR PERFORMANCE?" but the polished narration no longer raises that question. The thumbnail is not judged anywhere today.

## Global Constraints
- Never invent a rule: every catalog rule carries its source URL and `verified` date; conflicting or unverified items are labelled, not enforced.
- Never touch a video you approved or one on YouTube (existing fixer rules); rules that block ask the fixer, then the owner.
- One-way cost control: no new model call per rule; thumbnail judgement rides the existing review call.
- Tests first; full suite must pass before every commit; deploy only after the money cap resets (00:12 UTC).

## Tasks
### Task 1: `compliance.py` rules and review wiring
**Files:** Create `compliance.py`, `tests/test_compliance.py`; Modify `reviewer.py` (`rule_checks`), `newswatch.py` (`POLICY_PAGES`).
**Interfaces:** `RULES: list[dict]`; `metadata_check(meta) -> dict` (`metadata_valid`, block); `sanitize(meta) -> list[str]` (changes made); `originality(meta, source) -> dict` (`originality`, warn at 6%, block at 15%); `copied_lines(meta, source) -> list[int]`; `kids_signals(meta) -> dict` (`kids_signals`, warn); `hook_supported(hook, text) -> bool`; `checks(meta, source) -> list[dict]`.
- [ ] Tests: title 101 chars, `<` in title or description, description over 5000 bytes, tags over 500 counting commas and quotes, each fail; a normal video passes; `sanitize` fixes each; copied 8-grams computed on a constructed copy; kids words warn and "130 Children" does not; guard test that `aiart.STYLE` says illustration and not photo.
- [ ] Implement; `rule_checks` appends `compliance.checks(meta, source)`; run suite; commit.

### Task 2: the AI review judges the thumbnail text
**Files:** Modify `reviewer.py` (`llm_review`); Test `tests/test_reviewer.py`.
- [ ] Test: with `thumb_hook` set and the model answering `misleading_thumbnail: true, thumbnail_reason: "..."`, a `thumbnail_matches` check fails with severity block and the reason; absent hook or false answer gives ok; the prompt contains the hook text.
- [ ] Implement in the existing prompt and parser; commit.

### Task 3: remedies in the fixer, better hooks
**Files:** Modify `thumbnail.py` (`hook_for(meta, avoid=())`), `fixer.py`; Tests `tests/test_fixer.py`, `tests/test_thumbnail*.py`.
- [ ] `hook_for` is given a narration summary, avoids earlier hooks, rejects a hook the narration does not support (`compliance.hook_supported`), falls back to title words.
- [ ] Fixer: `thumbnail_matches` -> new hook + `thumbnail.make`; `metadata_valid` -> `compliance.sanitize`; `originality` -> `rewrite_lines` on `copied_lines` with a "reword completely" problem, re-render. Tests for each, run suite, commit.

### Task 4: platform watch
**Files:** Modify `safety.py` (message), `upload.py` (record `thumbnail_error` and tell the owner), `risk.py` (row "YouTube rules"); Tests `tests/test_safety.py`, `tests/test_risk.py`.
- [ ] Still-private-after-slot message names the API-project possibility and links the official page; risk row lists rules checked and goes `watch` when a policy page a rule depends on changed after the rule's `verified` date.

### Task 5: contract, deploy, live proof
- [ ] `docs/COMPLIANCE.md` (rule table above, how to add a rule), `docs/AUTOPILOT.md` pointer. Suite, push, deploy 00:12 UTC job picks it up.
- [ ] Delphi: new hook from the narration via `hook_for`, thumbnails remade, re-review; report the AI review's `thumbnail_matches` result as it is.

## Limits
- The thumbnail judgement is a model reading text, not the image pixels; the hook text is what we control.
- Copy detection catches near-verbatim runs, not paraphrased copying.
- Policies change; the catalog is dated and the Risks card says when a source page changed.
