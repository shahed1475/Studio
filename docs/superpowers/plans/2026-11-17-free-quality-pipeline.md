# Free-quality pipeline: free models that work like paid ones, and every real-media key used

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native, in one session) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Autopilot makes documentaries and Shorts of near-paid quality at $0 by making the free models reliable (measured ranking, hedged calls, staged writing, a review panel) and by actually using the Pixabay, Smithsonian and other real-media libraries the owner has set up.

**Architecture:** Keep every existing control (claim ledger, quote finder, reviewer, gate, review window). Add reliability *around* the free models instead of trusting one answer: measure each free model per role, race the two best, write in small stages with deterministic checks between them, judge with a panel plus code that does not need a model. Add a `mixed` look that lets real archive photos and clips in beside drawn scenes, so the keys in Settings are used.

**Tech Stack:** Python 3.13, OpenRouter free models (`llm.py`, `freemodels.py`), Cloudflare Workers AI free pictures (`freeart.py`), `realmedia.py` / `openmedia.py` / `footage_real.py`, pytest.

**Spec:** the owner's order of 17 Nov 2026 in chat ("make free models do what paid models do for scripts and reviews, use Pixabay and the other keys, create the best videos for free"); evidence below. Existing rules: `CLAUDE.md` sections "Free-only mode", "Real photos and credited licences", "Money and repair rules".

## Evidence this plan rests on (measured 17 Nov 2026)
- Keys set in Settings: `openrouter_key`, `pixabay_key`, `smithsonian_key`; `.env` has Cloudflare id and token. No Pexels (not on the owner's licence list). Paid models are off (`llm.json` `enabled` false); credit is -$0.03 (bought $42.13, used $42.16).
- The free quota is **not** the limit: the account has bought more than $10 once, so OpenRouter gives 1,000 free requests a day (`is_free_tier` false); 866 were left at 00:30 UTC.
- The limits are quality and speed: today 25 model calls, 6 failed (4 "did not return JSON", one 429, one unusable review); `freemodels.choose` ranks only by past successes, asks one model at a time, and each call may wait up to 240 s (`llm._post`). A first documentary attempt (Titanic) used about 20 minutes and was thrown away after two fact-check tries.
- The Pixabay and Smithsonian keys are **unused by Autopilot's default look**: `run._real_media_on` returns False for `art_style` "photo", so `realmedia.Finder` is never built; only named Commons photos and up to four clips (`real_footage`) can be real. Recent videos' credits show only Commons and Openverse.

## Global Constraints
- Never relax a reviewer check, the claim ledger, the quote finder, `facts_open`, licence rules (`licences.py`) or the review window. Free models are weaker judges, so a model can only warn or add scrutiny.
- Allowed licences stay: public domain, CC0, CC BY, CC BY-SA, NASA media without logos, Pixabay Content License, labelled AI art. No Pexels. Every real item keeps address, licence, credit and date; credits go in the description (`credits_in_description` gate).
- Spend stays $0: no paid model, no paid picture, no paid clip. The Cloudflare free allowance stays shared (`free_art_cap` 9,000 Neurons a day).
- Every new rule gets an `agenteval` case and a mutation check (CLAUDE.md "Rules for changes"); an agent's playbook is cut at 1,500 characters.
- Tests that touch shared files use the isolation in `tests/conftest.py`. `.venv/bin/python -m pytest -q` passes before every commit.
- No deploy, no push, no switch of `autopilot.json` without the owner's yes in chat. Do not restart the worker while a render runs.

## Review Focus
- A free model that answers fast but wrong (valid JSON, invented facts): the panel and the ledger must still catch it.
- Two raced calls both succeeding: only one answer is used and the extra call must still count against the daily free allowance.
- A real photo that is on-topic by tag but wrong in fact (a different ship, a modern replica): the image judge and the licence check must both pass before it is used.
- A library that returns nothing, a bad key or a rate limit (Pixabay 100 requests a minute): the scene falls back to a drawn picture, never to a gap.
- A key-needing credit line missing from the description: the gate must fail, not publish.

---

### Task 0: A Settings card for the owner's own free LLM provider (DeepSeek, GLM and others)

The owner has a free-LLM key they already use for coding and wants Autopilot to use its better models. The service speaks the OpenAI format (every FreeLLM-style catalog and proxy found on 17 Nov does), so the card is generic: a base address, a key and model names, not one brand. Which service it is, its base address and its model names are the owner's to enter; the code assumes nothing.

**Files:**
- Modify: `dashboard.py` (settings save and test endpoints), `dashboard.html` (Settings card "Extra model provider"), `config.py` (read the saved fields), `llm.py` (`_post` routing, `load_config`), `freemodels.py` (merge the provider's models into the roster)
- Test: `tests/test_extra_provider.py`, `tests/test_llm.py`

**Interfaces:**
- Produces: `settings.json` fields `extra_llm_url` (https address ending in `/v1`), `extra_llm_key` (write-only, saved from Settings, never shown again, never in a log, cache, event or commit), `extra_llm_models` (`{"script": ["..."], "review": ["..."]}`), `extra_llm_on` (switch). `llm.extra_models(role) -> list[str]` returns ids prefixed `extra:` so `_post` knows where to send them. `POST /api/extra-llm/test` sends one tiny prompt and returns `{ok, seconds, model}` without echoing the key. `freemodels.choose` ranks `extra:` models with the same measured reliability as the others (Task 1) and the writer and the reviewer must come from different model families (deepseek writes, glm reviews).
- Safety: only https addresses on public hosts (same address check as `realmedia._public_https`); `http` only to localhost for a self-hosted proxy, behind an explicit checkbox. Only public text is sent (source articles and scripts); never the owner's email, keys, tokens or settings. Cost is recorded as $0 (calls and tokens are still counted); a shared "free key pool" from a stranger is not accepted advice here: the owner's own key only.

- [ ] **Step 1: Write failing tests**: `test_key_is_saved_but_never_returned_by_the_settings_api`, `test_non_https_or_private_address_is_refused_unless_local_box_is_ticked`, `test_extra_models_join_the_roster_and_writer_and_reviewer_differ_in_family`, `test_a_failing_extra_provider_falls_back_to_openrouter_free_models`, `test_the_key_never_appears_in_events_logs_or_the_cache`.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement** the card, the test button, the routing and the roster merge; reuse the existing write-only key pattern used for `pixabay_key`.
- [ ] **Step 4: Run** `tests/test_extra_provider.py tests/test_llm.py tests/test_live_ui.py` and the full suite; add an `agenteval` case "a provider key is never written to a log" with its mutation check; pass.
- [ ] **Step 5: Commit** "Settings: an extra OpenAI-compatible model provider for scripts and reviews".

### Task 1: Measure the free models per role (baseline first)

**Files:**
- Modify: `freemodels.py` (`record`, `choose`), `llm.py` (`_free_chat` passes timing and role)
- Test: `tests/test_freemodels.py`

**Interfaces:**
- Produces: `freemodels.record(model, ok, now, status=None, role=None, seconds=None)` keeps per `(model, role)` counts `ok`, `bad`, `json_bad`, `slow` and a rolling median `seconds`; `freemodels.reliability(model, role) -> float` in 0..1 (0.5 when unknown); `choose(role, now, avoid, n)` ranks by `reliability` then by lower median seconds.

- [ ] **Step 0: Diagnose the "did not return JSON" failures first.** `llm.json` caps output at `max_output_tokens`; a free reasoning model can spend that on thinking and cut its answer off. Log the reply's `finish_reason` for each failed free call (a value of `length` means truncation) and report the counts. If truncation is the main cause, the fix is a larger cap or a non-reasoning model for the script role, not more retries.
- [ ] **Step 1: Write failing tests** `test_choose_prefers_the_model_that_answered_valid_json_fast` (two models, one with 9 ok / 1 bad and 20 s, one with 3 ok / 7 bad), `test_unknown_model_is_neutral_and_still_tried`, `test_a_429_is_busy_not_unreliable`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_freemodels.py -q` and see them fail.
- [ ] **Step 3: Implement** the new fields (keep the old `ok`/`fails` keys so an older file still loads) and the ranking; `llm._free_chat` times each `_post` with `time.monotonic()` and passes `role`.
- [ ] **Step 4: Run the tests** and `tests/test_llm.py`; all pass.
- [ ] **Step 5: Commit** "Free models: rank by measured reliability and speed per role".

### Task 2: Hedged free calls and a shorter wait

**Files:**
- Modify: `llm.py` (`_free_chat`, new `_race`), `llm.json` key `free_timeout_s` (default 120, owner-editable)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: Task 1 `freemodels.choose`.
- Produces: `llm._race(models: list[str], prompt, role, cfg, key, now) -> dict | None`: starts the top two models at once in threads, returns the first answer that parses, ignores the other; both requests are counted (`freemodels.count_request`). Used for roles `script` and `review` only; `cheap` stays single. `_post` uses `cfg["free_timeout_s"]` for free models.

- [ ] **Step 1: Write failing tests** with a fake `_post`: `test_race_returns_the_first_valid_answer_and_counts_both_requests`, `test_race_survives_one_model_failing`, `test_race_returns_none_when_both_fail`, `test_free_timeout_comes_from_config`.
- [ ] **Step 2: Run** and see them fail.
- [ ] **Step 3: Implement** `_race` with `concurrent.futures.ThreadPoolExecutor(max_workers=2)`; do not cancel the loser's HTTP call (just ignore it).
- [ ] **Step 4: Run** `tests/test_llm.py tests/test_agents_training.py`; pass.
- [ ] **Step 5: Commit** "Free models: race the two best for scripts and reviews".

### Task 3: Staged documentary writing with checks between stages

**Files:**
- Modify: `scriptgen.py` (new `doc_staged(topic, sources) -> (lines, chapters)` used by the documentary path when the writer is a free model)
- Test: `tests/test_scriptgen_staged.py`

**Interfaces:**
- Produces: `scriptgen.parse_lines(text: str) -> list[dict]` reads line-delimited `NARRATION || VISUAL NOTE` (no JSON), `scriptgen.doc_staged(...)`: (1) outline call, a short list of nine chapters with one question each; (2) one call per chapter, 5 to 8 lines each, source passages attached; (3) deterministic checks: `MAX_DOC_LINES`, 480 to 600 s of words (`rulesfile` `long_min/max_minutes`), a question in the first two lines (`reviewer` rule `hook_question`), no chapter label in the narration (`script_labels`); (4) only a failing chapter is asked again, once.

- [ ] **Step 1: Write failing tests** with a fake chat: `test_parse_lines_reads_double_bar_format_and_ignores_prose`, `test_a_short_chapter_is_asked_again_and_only_that_chapter`, `test_the_hook_question_is_enforced_before_the_script_is_returned`, `test_total_length_lands_in_the_target_range`.
- [ ] **Step 2: Run** and see them fail.
- [ ] **Step 3: Implement** `parse_lines` and `doc_staged`; keep the one-shot writer as the fallback when the outline call fails twice. Update `playbooks/creator.md` only if its Never section stays inside 1,500 characters.
- [ ] **Step 4: Run** `tests/test_scriptgen*.py tests/test_agents_training.py`; add the `agenteval` case "staged script never ships a chapter label" and its mutation check; pass.
- [ ] **Step 5: Commit** "Documentary scripts written in stages for free models".

### Task 4: A review panel that is not one model's word

**Files:**
- Modify: `llm.py` (`_free_review` takes a third model when the first two disagree), `scriptgen.py` (`verify_and_revise` runs the code check first), `reviewer.py` (unchanged checks, panel note in the text)
- Test: `tests/test_llm.py`, `tests/test_reviewer.py`

**Interfaces:**
- Produces: `scriptgen.unsupported_by_source(lines, sources) -> list[int]`: line numbers whose names, years and numbers are not found in the source text (uses `reviewer.claim_span`); `verify_and_revise` sends only those lines to the model fact-check. `llm._free_review` returns `strictest(a, b)` when the two agree on shape and flags, and a third model's vote decides a disagreement on a flag (strictest of the two that agree, never the optimistic one).

- [ ] **Step 1: Write failing tests**: `test_unsupported_by_source_finds_a_year_the_article_lacks`, `test_review_panel_asks_a_third_model_only_on_disagreement`, `test_two_agreeing_pass_votes_do_not_override_a_flag_from_code`.
- [ ] **Step 2: Run** and see them fail.
- [ ] **Step 3: Implement**; record the panel models in `LAST_REVIEW` so the review text says who judged.
- [ ] **Step 4: Run** `tests/test_reviewer.py tests/test_llm.py tests/test_agents_training.py`; add the `agenteval` case "an invented year is flagged by code even when two models pass it" with its mutation check; pass.
- [ ] **Step 5: Commit** "Fact check: code first, then a free-model panel".

### Task 5: A `mixed` look that uses every real-media key

**Files:**
- Modify: `run.py` (`LOOKS`, `_real_media_on`, `_forced_art`), `footage.py` (scene allocation), `config/` none
- Test: `tests/test_house_style.py`, `tests/test_real_media_look.py`

**Interfaces:**
- Produces: `LOOKS["mixed"] = {"doc": {"parallax": True, "graphics": True, "voice_tail": 0.15, "real_footage": 4}, "short": {"parallax": True}}`; `_real_media_on(data)` is True for `art_style` "mixed". In the mixed look a scene takes a real photo or clip when `realmedia.Finder` returns an accepted item for that scene's own search words and the image judge passes it (same rule as today's non-photo videos); a scene about a person, an event or an abstract idea is drawn. Flat gentle zoom (`parallax.flat_scenes`) applies to any scene that may show people; real archive photos are never bent by depth motion.

- [ ] **Step 1: Write failing tests**: `test_mixed_look_builds_a_finder_and_photo_look_still_does_not`, `test_a_scene_about_a_person_is_drawn_not_taken_from_an_archive`, `test_a_library_with_no_key_or_no_hit_falls_back_to_a_drawn_scene`, `test_credits_for_pixabay_and_smithsonian_reach_the_description`.
- [ ] **Step 2: Run** and see them fail.
- [ ] **Step 3: Implement** the look and the gate; no change to `licences.py`.
- [ ] **Step 4: Run** the full suite; add an `agenteval` case "a real item without a credit line fails the gate" with its mutation check; pass.
- [ ] **Step 5: Commit** "Mixed look: real archive photos and clips beside drawn scenes".

### Task 6: Prove it on real output, then switch it on

**Files:**
- Modify (server only, owner's yes first): `autopilot.json` `house_style.look` to `mixed`
- Create: `docs/studio/FREE_QUALITY_RESULTS_2026-11-17.md`

- [ ] **Step 1: Baseline** from the current run: record calls, failures and minutes for The Mary Celeste (script stage) from `data/llm_usage.json` and `data/free_models.json`.
- [ ] **Step 2: With the owner's yes, deploy** (`deploy/deploy.sh dry-run-first`) and set `look` to `mixed`; back up `autopilot.json` first.
- [ ] **Step 3: Let Autopilot make one documentary and one Short.** Then run `python run.py review <slug>`, `studiochecks.py video`, `videoinspect.py` frames, and the `watch` skill; say what was seen and what was not.
- [ ] **Step 4: Compare** with the paid-era films (Lost Army, Antikythera): calls used, repair tries needed, reviewer verdict, real-versus-drawn scene counts, credits written.
- [ ] **Step 5: Write the results file** with the numbers, the failures and the remaining limits; commit and push only with the owner's yes.

**Done means:** a documentary and a Short pass the reviewer with at most one repair, use at least two real-media libraries beyond Commons, spend $0, and the first free-model script is no longer thrown away.

### Task 7: A2A, so the studio's agents can ask and answer each other (the owner's order of 17 Nov; item H1 of docs/superpowers/plans/2026-11-14-free-autopilot-and-new-films.md)

A2A is the open Agent2Agent protocol: each agent publishes an Agent Card, and peers send it a message and read back a task. The studio already has the parts: 26 agents with playbooks and a hand-over map (`agents.py`), a task inbox (`agentbus.py`: `post`, `claim`, `finish`, `to_owner`), a ladder that picks only whitelisted safe fixes (`escalate.py`), and an unmerged A2A gateway on branch `feature/hub` (`hub/a2a.py`, built for the multi-creator Hub and to be reused only after a security review). This task adds a thin A2A layer on top of those; it does not add a second bus.

**Files:**
- Create: `a2a.py`, `playbooks/a2a.md` (cut at 1,500 characters)
- Modify: `agents.py` (cards come from `AGENTS`), `agentbus.py` (kind `a2a`), `dashboard.py` (optional HTTP door, off by default), `agenteval.py`
- Test: `tests/test_a2a.py`

**Interfaces:**
- Produces: `a2a.card(agent: str) -> dict`: an A2A Agent Card (`name`, `description` from the playbook's Role line, `skills` from the agent's commands, `capabilities` all false, text and JSON input modes). `a2a.send(source, target, text, slug="", context_id=None) -> dict`: posts an `a2a` task through `agentbus.post` and returns `{id, contextId, status: {state}}` (states submitted, working, input-required, completed, failed, canceled). `a2a.get(task_id)` and `a2a.cancel(task_id)`. `a2a.consult(source, question, targets, slug) -> {answers, summary, recommended_fix, needs_owner}`: each target answers once as a free-model call made under its own playbook (`playbook.acting_as`), in the form `{answer, evidence: [..], confidence 0..1}`; one synthesis by the arbiter (`autopilot`); the result can only name a fix already in `escalate`'s whitelist.
- Safety (these are the rules the tests pin): a consult is at most 4 agents, 2 rounds and 8 model calls, and 3 consults per video a day; no agent messages itself or an agent it has no hand-over to unless it is the doctor or autopilot; identical messages are dropped; every text is cleaned and labelled as data (`seo.plain`, `seo.linky`), never an instruction; an answer without evidence counts as an opinion and cannot raise a fix; **nothing here can publish, delete, change a public video, flip an owner switch, release a policy hold or spend money**; only free models are used (`llm.free_only` or the owner's provider); the outside HTTP door (`POST /a2a`, `GET /.well-known/agent-card.json`) is off by default, loopback only, behind a bearer token the owner creates in Settings, and read-only for cards.
- Where it is used first: (1) the fixer asks the script reviewer and the reviewer why a draft fails and which safe fix fits; (2) the doctor and the triage agent consult before they draft a skill or a post-mortem; (3) the growth loop: collector, diagnoser, research and creator pass evidence (a video that held viewers, a dropping traffic share) to a topic suggestion that still needs its own source article and every existing gate; (4) autopilot asks the guardian before it schedules.

- [ ] **Step 1: Write failing tests**: `test_every_agent_has_a_complete_card_and_a_playbook_role`, `test_send_creates_one_agentbus_task_and_get_reads_its_state`, `test_a_duplicate_or_self_message_is_dropped`, `test_a_consult_stops_at_four_agents_two_rounds_and_eight_calls`, `test_a_recommended_fix_outside_the_whitelist_is_ignored`, `test_an_answer_without_evidence_cannot_raise_a_fix`, `test_no_a2a_path_reaches_publish_delete_or_an_owner_switch`, `test_the_http_door_is_off_without_a_token_and_never_listens_beyond_loopback`, `test_text_with_links_or_instructions_is_cleaned`.
- [ ] **Step 2: Run** them and see them fail.
- [ ] **Step 3: Implement** `a2a.py` on `agentbus` and `escalate`; read `feature/hub`'s `hub/a2a.py` first and take only what survives the review.
- [ ] **Step 4: Run** `tests/test_a2a.py tests/test_agents_training.py` and the full suite; add `agenteval` cases "an A2A consult never reaches an owner-only action" and "a consult is capped" with a mutation check each; pass.
- [ ] **Step 5: Commit** "A2A: Agent Cards and consults over the agent bus".

## What stays true after this plan
Free models are weaker judges than Claude. This plan narrows the gap with more calls (about 40 to 60 free requests a film out of 1,000 a day), staged writing and code checks; it does not make a free model equal to a paid one. A one-time top-up would still make scripts faster and more reliable; that is the owner's money decision and nothing here depends on it.
