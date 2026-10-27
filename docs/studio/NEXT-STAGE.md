# Next stage: footage tool hardening, dashboard wiring, tech channel (mocks), then the paid test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native, in this session; the owner asked for step-by-step work). Steps use checkbox syntax. Every task: test first, full suite (`.venv/bin/python -m pytest -q`, 1038 pass on 25 Oct), commit on `feature/footage-tool`, one line in `docs/studio/PROGRESS.md`.

**Goal:** finish everything that can be built and proven with mocks and free tools, connect it to the dashboard, test it all, and only then run the paid tests the owner approves.

**Architecture:** no new service. The footage tool (`tools/footage/clipgen.py`) gets its money rules corrected from the provider's own documentation; the dashboard (`dashboard.py`, `footage.html`, `nowview.py`) gets one navigation and status layer over data the modules already save; the tech channel gets its real GitHub fetcher behind the existing injected-fetcher seam (`githubfacts.py`).

**Tech Stack:** Python 3.14 stdlib + `requests`, pytest, ffmpeg/ffprobe, Chrome (claude-in-chrome) for the browser checks.

**Spec:** `docs/architecture/03-requirements.md` (R1 to R11), `docs/architecture/05-target-design.md`, `docs/studio/TECH_CHANNEL.md`, `docs/studio/PROGRESS.md` "Next" lines, `CLAUDE.md` sections A to F and "Money and repair rules".

## Global Constraints
- Test studio only for anything paid; the owner studio is changed only by what the owner asked for in chat (done 25 Oct: cap back to $1.50, Hong Gildong repaired, Mami Wata made).
- Daily cap `$1.50` (`daily_budget_usd`), per-video limit `$2.50` documentary / `$0.70` Short, no new video under `$1.50` credit, new studios `$0` paid until credit is added.
- Never print, log or commit a key. Keys reach servers by `scp` or the Settings page only.
- Nothing is published, deleted or made public; uploads are private and scheduled; `human_approval` stays on for every new channel type (R10).
- Never mark a claim `VERIFIED` without a source (CLAUDE.md A); never report a test as run unless it ran.
- Do not merge to `main`, push, or deploy to the owner studio without the owner's yes in chat.

## Review Focus (inputs the spec implies but no task exercises yet)
1. Provider says `failed` but still bills the key (the docs do not say) -> the tool must not refund by assumption (task A3).
2. `usage.cost` missing, zero or a string in the poll reply -> fall back to the balance difference, never book a negative (A1).
3. `/videos/models` unreachable or lists no price for the chosen resolution -> fail closed with a clear reason, no job sent (A2).
4. A dashboard page opened with an empty data folder, a broken record, or a 100-run history -> renders, never a 500 (B1, B3).
5. GitHub rate limit (60 an hour without a token) or a repository with no licence -> the fact is marked unknown, never invented (C1).

---
## Phase A: footage tool, corrected from OpenRouter's documentation (research 25 Oct 2026)
Research facts (source: openrouter.ai docs "Video Generation", which say the API may change): submit `POST /api/v1/videos` (fields `model`, `prompt`, `duration`, `resolution`, `aspect_ratio`, `generate_audio`, `seed`); poll `GET /api/v1/videos/{id}` (statuses `pending`, `in_progress`, `completed`, `failed`; `cancelled` and `expired` appear only in webhooks); completed reply has `unsigned_urls` and `usage.cost`; price list `GET /api/v1/videos/models` (`pricing_skus`, e.g. `per-video-second`: "0.50" for Veo 3.1); billing of failed jobs: not stated. Our `$0.03` a second for `google/veo-3.1-lite` is unverified (one real clip cost `$0.24` for 8 s).

### Task A1: book the provider's own `usage.cost`
**Files:** Modify `tools/footage/clipgen.py` (`_await_and_save`, `_generate` after-success block); Test `tests/test_footage_tool.py`.
**Interfaces:** Produces `_usage_cost(poll_json: dict) -> float | None` (a finite number >= 0 from `usage.cost`, else None).
- [ ] Test `test_the_provider_cost_is_booked_instead_of_the_estimate`: poll reply `{"status":"completed","usage":{"cost":0.31}}` -> `res["booked_usd"] == 0.31`, day total and `video_costs.json` 0.31, record `cost_booked == 0.31`, capped at `max_clip_cost_usd`.
- [ ] Test `test_a_missing_or_odd_usage_cost_falls_back_to_the_balance_difference` (None, "x", -1, NaN).
- [ ] Implement `_usage_cost`; the final poll returns the JSON to `_await_and_save`, which returns it in its result dict as `provider_cost`; `_generate` books `provider_cost - est` (positive or negative) through `_book`, else the existing balance rule.
- [ ] Run `pytest tests/test_footage_tool.py -q`; expect all pass. Commit.

### Task A2: live price check before any money is reserved
**Files:** Modify `tools/footage/clipgen.py` (new `live_price(cfg, headers, http, sleep) -> float`, used by `estimated_cost`'s caller in `_generate` before `reserve`); `config/footage.json` (add `price_source`: `"live"`); Test `tests/test_footage_tool.py`.
- [ ] Test `test_the_live_price_replaces_the_config_price`: `/videos/models` lists the model with `pricing_skus {"per-video-second": "0.03"}` -> estimate 0.24; a `"0.50"` price with 8 s -> 4.00 -> `Refused` ("over the per-clip cap"), no POST, nothing booked.
- [ ] Test `test_an_unreadable_price_list_or_no_price_for_the_resolution_fails_closed` (HTTP 500, no model, SKU for another resolution only) -> `Refused`, no POST.
- [ ] Implement: pick `per-video-second-<res>` if present for `1080p`, else `per-video-second`; parse the string with `float`; reject non-finite or <= 0. `price_source: "config"` keeps the old behaviour for tests and offline use.
- [ ] Run tests; commit.

### Task A3: a failed job is refunded only if the balance did not move
**Files:** Modify `tools/footage/clipgen.py` (`_await_and_save` raises `JobNotCharged`; `_generate` and `resume` decide); Test `tests/test_footage_tool.py`.
- [ ] Test `test_failed_and_balance_dropped_keeps_the_money_booked`: poll `failed`, balance before 9.0 after 8.76 -> cost stays booked, error says "the balance fell".
- [ ] Test `test_failed_and_balance_unchanged_is_released` (existing refund tests keep passing); balance unreadable -> stays booked.
- [ ] Implement in `_generate`/`resume`: on `JobNotCharged`, read `balance` again; `_release` only when `after >= before - 0.0001`.
- [ ] Run tests; commit.

---
## Phase B: connect the dashboard (every feature), then test it all
### Task B1: navigation and status cards
**Files:** Modify `dashboard.html` (nav links to `/now`, `/footage`), `footage.html` (links already there), `nowview.py` (add `footage` block: last run status, spend today vs cap), `risk.py` (row "Losing the records" shows the age of the off-server copy, R4); Test `tests/test_nowview.py`, `tests/test_risk.py`, `tests/test_footageview.py`.
- [ ] Tests: `/api/now` has `footage` with `last_status`, `runs_today`; risk row text contains "off-server copy is N hours old" and turns `watch` over 24 h, `act` over 72 h.
- [ ] Implement `serverstate`/`backup_push` age read (file mtime of the pushed marker or the log line `deploy/backup_push.sh` writes); no network call.
- [ ] Run tests; commit.

### Task B2: channels card (read-only)
**Files:** Create `channelsview.py` (`build() -> dict` from `channelconfig.load_all()`: name, kind, daily budget, `human_approval`, `made_for_kids`, posts per week); Modify `dashboard.py` (`/api/channels`), `dashboard.html`; Test `tests/test_channelsview.py`.
- [ ] Test: tech and crisis profiles listed with `$0` budget and the human gate on; a broken profile file is listed as "invalid: reason", not a 500.
- [ ] Implement, route behind the same login; commit.

### Task B3: every dashboard page, tested
**Files:** Create `tests/test_dashboard_routes.py` (a table of every GET route found in `dashboard.py`'s `do_GET`; each must answer 200 or the documented redirect with an empty data folder AND with a populated one; each `/api/*` must return JSON).
- [ ] Write the route inventory test; run; fix any 500.
- [ ] Browser pass (Chrome, local isolated copy as in `docs/studio/LOCAL.md` B with a throwaway data dir): open each page, screenshot, read console errors; at 390 px width no sideways scroll. Record what was and was not looked at in PROGRESS.md.
- [ ] Commit.

---
## Phase C: tech channel pipeline with mocks and free reads
### Task C1: real GitHub fetcher behind the existing seam
**Files:** Modify `githubfacts.py` (`fetch_repo(full_name, http=requests, token=None) -> dict`: stars, licence SPDX id, last release date, README as untrusted text, all dated); Test `tests/test_githubfacts.py`.
- [ ] Tests: 403 rate limit -> facts marked `unknown` with the reason; no licence -> `licence: None` and the "source available" wording rule; README text never reaches a prompt un-fenced; the token is only an `Authorization` header and never logged.
- [ ] Implement; then ONE free live smoke on 3 public repositories (GIMP, Krita, Kdenlive), results written to PROGRESS.md (read-only, unauthenticated, 60 an hour).
- [ ] Commit.

### Task C2: tech script dry run (model mocked)
**Files:** Test `tests/test_tech_dryrun.py` using `prompts/tech_script.md`, `channelconfig` tech profile, `githubfacts` mock, `crisisreview`-style fail-closed review for tech facts.
- [ ] Test: a script that states a star count not in the fetched facts is rejected; a "free alternative" claim for a repository without an open-source licence is rejected.
- [ ] Implement the smallest reviewer glue; commit. No paid call.

(Crisis channel: stays mocks. Its real source fetcher, official-domain list and the terms of those domains need the owner's decision; nothing is built here.)

---
## Phase D: close-out documents (no code)
- [ ] `docs/studio/COSTS.md` (new): every paid API the project calls, where, measured cost so far (Mami Wata $0.906 recorded; first test clip $0.24; footage price source), top savings. Only measured numbers; unmeasured ones say so.
- [ ] `PROGRESS.md`: one entry per finished task; Hong Gildong release decision and Mami Wata review result recorded.
- [ ] Architecture map: the published artifact needs its link from the owner; until then `docs/architecture/05-target-design.md` section 8-9 is updated by hand.
- [ ] Full suite plus the per-agent groups (reviewer, fixer, autopilot, growth, re-check, crisis, footage, upload, money, dashboard) all green; numbers in PROGRESS.md.

---
## Phase E: the paid tests (owner's yes needed for each line; amounts are caps)
1. Owner saves a capped OpenRouter key in the TEST studio's Settings (never pasted in chat). I answer yes/no that it is set.
2. Sync `feature/footage-tool` to the test studio (allowed), restart only its services, open `/footage` there.
3. One real footage clip, smallest settings (about `$0.24`): check the clip with ffprobe and a full decode, the contact sheet, the ledger row, the cost in `data/video_costs.json`, the log lines.
4. Prove the guard: lower the test studio cap below the clip price, run, expect a refusal with no HTTP call to the provider; put the cap back.
5. Prove a bad source: an unreachable base URL in a throwaway config -> `failed` with a reason, no partial files, no cost.
6. Give the dashboard link (or the SSH tunnel command) and confirm it loads real data.
7. Only after 3 to 6 pass: one tech Short with real GitHub facts, a free voice, the studio's reviewer (cap `$0.50`), private, unscheduled, `human_approval` on.

## Self-review (25 Oct)
- Spec coverage: R1/R2 (A1 to A3 and E4), R4 (B1), R7 to R10 already done and untouched, R5 growth work is NOT in this plan (separate owner priority "audience first"; to be planned next), R11 respected (no AI film, no other platforms).
- Not covered on purpose: crisis channel real sources, Remotion merge (needs the owner's yes to merge `spike/remotion`), Hong Gildong release (owner's call).
- Unverified: the OpenRouter facts above come from its public docs, which say they may change; the price of `google/veo-3.1-lite`; billing of failed jobs.
