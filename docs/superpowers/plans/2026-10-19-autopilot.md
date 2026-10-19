# Autopilot, Reviewer Agent and YouTube Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Topic choice, video creation, review and scheduled upload run by themselves, a reviewer agent gates every upload, and a weekly agent turns YouTube security and policy news into a digest and draft video topics.

**Architecture:** Plain Python modules next to `run.py`. `autopilot.tick()` is a pure-decision function (`plan_actions`) plus an executor; it is run every 30 minutes by a systemd user timer and also from the dashboard. `reviewer.review()` writes a verdict into `meta.json`; only `pass` verdicts are auto-approved and scheduled. The dashboard gets an Autopilot page for settings, the schedule, holds and the news digest.

**Tech Stack:** Python 3.14 stdlib (`zoneinfo`, `xml.etree`, `fcntl`), existing Ollama helper `scriptgen._chat`, ffmpeg/ffprobe, `google-api-python-client` (already installed), pytest, systemd user units.

**Spec:** Conversation of 2026-10-19 (no written spec; user opted out of questions and chose "best defaults, I will review in dashboard"). Defaults below are builder calls.

## Global Constraints

- Policy guardrails stay: AI-narration disclosure on every upload, at most 5 uploads/day hard cap (`config.MAX_UPLOADS_PER_DAY`), uploads are private; public only via `publishAt`.
- Autopilot defaults OFF (`"enabled": false` in `autopilot.json`); nothing runs until the user switches it on in the dashboard.
- Defaults: 1 upload/day, 24 h review window between pass and publish, upload 2 h before `publishAt`, queue refilled when under 3 topics, at most 2 finished videos waiting.
- Publish slots (America/New_York): Fri 18:00, Sun 10:00, Thu 15:00.
- News-sourced videos (`meta["source"] == "news"`) are never auto-approved; verdict is `needs_human` at best.
- Held videos (`meta["hold"] is True`) are never uploaded.
- No em-dashes in any user-visible dashboard text.
- Secrets (`client_secret.json`, `token.json`, `settings.json`) are never logged or shown.
- No git repo exists: the "commit" step is replaced by running the full test suite.

## Review Focus

- Ollama unreachable during `review`: verdict is `fail` with a blocking "review unavailable" check, never an auto-pass.
- YouTube token missing or expired at upload time: tick records the error and continues; nothing is marked uploaded.
- Two ticks overlap (a documentary takes over 30 min to make): second tick exits immediately via the lock.
- Slot crossing the US DST change (1 Nov 2026): `next_slot` returns the correct UTC instant on both sides.
- A news feed returns malformed XML, 404 or nothing: digest is empty for that feed, run does not raise.
- Upload cap already reached: no upload action is planned.
- Video with no `thumbs` or a thumbnail over 2 MB: reviewer blocks.
- Script that loops the same narration line: reviewer blocks.

---

### Task 1: Slot scheduler

**Files:**
- Create: `scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `SLOTS_DEFAULT: list[dict]` (`{"day": "fri", "time": "18:00"}`), `next_slot(now: datetime, slots: list[dict], taken: list[datetime], min_lead_hours: float = 24, tz: str = "America/New_York") -> datetime` (UTC, tz-aware), `to_rfc3339(dt: datetime) -> str` (`"2026-10-23T22:00:00Z"`), `fmt_local(dt: datetime, tz: str) -> str`.

- [ ] **Step 1: Write failing tests.** `test_next_slot_friday_evening` (now Mon 2026-10-19 12:00Z, min lead 24, default slots → earliest is Thu 2026-10-22 15:00 ET = `2026-10-22T19:00:00Z`), `test_respects_min_lead` (now Thu 2026-10-22 18:00Z skips the Thu slot), `test_skips_taken_slot` (taken has Thu slot → returns Fri `2026-10-23T22:00:00Z`), `test_dst_change` (slot Sun 10:00 ET on 2026-11-01 is `15:00Z`; on 2026-10-25 it is `14:00Z`), `test_to_rfc3339`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_scheduler.py -q`; expect FAIL (module missing).
- [ ] **Step 3:** Implement with `zoneinfo`: scan the next 21 days, build each slot's local datetime, convert to UTC, keep those `>= now + lead` and not within 6 h of any `taken`, return the minimum.
- [ ] **Step 4:** Run the tests; expect all PASS.

### Task 2: Reviewer agent

**Files:**
- Create: `reviewer.py`
- Test: `tests/test_reviewer.py`

**Interfaces:**
- Produces: `Check = dict` with keys `name: str`, `ok: bool`, `severity: "block" | "warn"`, `detail: str`; `rule_checks(meta: dict, probe: dict, existing_titles: list[str], thumb_bytes: int | None) -> list[Check]` (pure: `probe` is `{"duration": float, "width": int, "height": int, "has_audio": bool, "mean_db": float | None, "black_ratio": float}`); `probe_video(path: Path) -> dict`; `llm_review(meta: dict) -> list[Check]`; `review(folder: Path, existing_titles: list[str] | None = None, use_llm: bool = True) -> dict` returning `{"verdict": "pass" | "needs_human" | "fail", "checks": list[Check], "at": iso_utc}` and also writing it to `meta["review"]`.
- Consumes: `scriptgen._chat(prompt) -> dict`.

- [ ] **Step 1: Write failing tests** on `rule_checks` with a good doc fixture (319 s, 1920x1080, chapters starting 0:00, 11 tags, thumb 150 000 bytes) asserting no block failures, then one test per defect: `test_blocks_short_duration`, `test_blocks_wrong_resolution`, `test_blocks_silent_audio` (`mean_db=-60`), `test_blocks_mostly_black` (`black_ratio=0.4`), `test_blocks_duplicate_title` (existing title with similarity ≥ 0.85), `test_blocks_missing_thumbnail`, `test_blocks_oversize_thumbnail` (2_100_000), `test_blocks_looping_script` (more than 10 % duplicate narration lines), `test_warns_on_placeholder_chapter` ("Part 3"), `test_blocks_bad_first_chapter` (first chapter not at 0:00 in description), `test_warns_few_tags`. Also `test_verdict_rules` using a `verdict_from(checks, source)` helper: any failed block → `fail`; news source with no failures → `needs_human`; otherwise `pass`. And `test_llm_unavailable_is_blocking` (monkeypatch `scriptgen._chat` to raise → a failed block check named `llm_review`).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement `rule_checks`, `verdict_from(checks: list[Check], source: str | None) -> str`, `probe_video` (ffprobe for stream info; ffmpeg `volumedetect` for `mean_db`; `blackdetect` for `black_ratio`), `llm_review` (prompt returns JSON `invented_facts_risk`, `policy_risk` 0 to 10 and `misleading_title` bool; block at facts ≥ 7, policy ≥ 6 or misleading; warn at ≥ 4), and `review`. Limits: doc 180 to 900 s, short 20 to 180 s; title 8 to 100 chars (warn above 70); description ≥ 80 chars; tags ≥ 5 (warn) and ≤ 450 chars total; doc narration ≥ 400 words, short ≥ 100.
- [ ] **Step 4:** Run; expect PASS. Then run `review` on the real Pied Piper folder with `use_llm=False` and read the checks.

### Task 3: Upload guard and `uploaded_at`

**Files:**
- Modify: `upload.py`
- Test: `tests/test_upload_guard.py`

**Interfaces:**
- Produces: `uploads_today(out_dir: Path, now: datetime) -> int` (counts `meta["uploaded_at"]` within the UTC day); `upload()` records `meta["uploaded_at"]` and `meta["publish_at"]` and raises `SystemExit` when `uploads_today >= config.MAX_UPLOADS_PER_DAY` or `meta.get("hold")`.

- [ ] **Step 1:** Tests: `test_uploads_today_counts_only_today`, `test_upload_refuses_when_held` (call `upload.upload` on a tmp folder with `hold: true`, expect `SystemExit`).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement the two guards before any network call; set `uploaded_at` after a successful insert.
- [ ] **Step 4:** Run; expect PASS.

### Task 4: Autopilot decision logic and executor

**Files:**
- Create: `autopilot.py`
- Modify: `run.py` (commands `review NAME`, `autopilot tick|status`)
- Test: `tests/test_autopilot.py`

**Interfaces:**
- Consumes: `scheduler.next_slot`, `scheduler.to_rfc3339`, `reviewer.review`, `upload.upload`, `upload.uploads_today`, `run.cmd_doc`, `run.cmd_ideas`.
- Produces: `DEFAULTS: dict` (keys `enabled, auto_approve, uploads_per_day, review_window_hours, upload_lead_hours, min_queue, max_waiting, slots, news_videos`); `load_config() -> dict`, `save_config(cfg: dict) -> None` (file `autopilot.json`); `plan_actions(state: dict, cfg: dict, now: datetime) -> list[dict]` where `state = {"queue_len": int, "connected": bool, "busy": bool, "uploads_today": int, "videos": [{"slug", "source", "approved", "verdict", "hold", "video_id", "publish_at", "fails"}]}` and each action is `{"do": "review" | "schedule" | "upload" | "ideas" | "make", "slug": str | None}`; `tick(now: datetime | None = None) -> dict` (summary `{"actions": [...], "errors": [...]}` also written to `autopilot_state.json`); `status() -> dict`.

- [ ] **Step 1: Write failing tests** for `plan_actions`: `test_disabled_plans_nothing`; `test_unreviewed_video_gets_review`; `test_pass_is_scheduled_not_news`; `test_news_never_scheduled`; `test_upload_only_inside_lead_window` (publish_at 3 h away with lead 2 → no upload; 1 h away → upload); `test_no_upload_when_cap_reached`; `test_no_upload_when_not_connected`; `test_held_video_skipped`; `test_refill_ideas_when_queue_low`; `test_make_when_few_waiting`; `test_no_make_when_busy_or_enough_waiting`; `test_skips_after_three_fails`. Plus `test_tick_lock` (second `tick` while the lock is held returns `{"skipped": "locked"}`) using a temporary lock path.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement `plan_actions` as above. `tick` takes an exclusive `fcntl.flock` on `autopilot.lock`, builds `state` from `output/*/meta.json`, executes actions in order with each wrapped in try/except (increment `meta["autopilot_fails"]`, log to `logs/autopilot.log`), at most one `make` per tick, sets `approved = True` and `approved_by = "reviewer-agent"` on `pass` when `auto_approve`, sets `publish_at` via `next_slot(... taken = other videos' publish_at)`, and calls `upload.upload(folder, "private", to_rfc3339(publish_at))`.
- [ ] **Step 4:** Run; expect PASS.
- [ ] **Step 5:** Add the CLI commands to `run.py` and run `.venv/bin/python run.py autopilot status`.

### Task 5: YouTube watch agent

**Files:**
- Create: `newswatch.py`
- Modify: `scriptgen.py` (`doc_script(topic, facts=None)`), `run.py` (`newswatch`, news topics in `_produce_doc` via `meta["source"]`)
- Test: `tests/test_newswatch.py`

**Interfaces:**
- Produces: `FEEDS: dict[str, str]` (YouTube Official Blog `https://blog.youtube/rss/`, Google Security Blog `https://security.googleblog.com/feeds/posts/default`, Google Safety and Security `https://blog.google/technology/safety-security/rss/`, YouTube Creators channel feed `https://www.youtube.com/feeds/videos.xml?channel_id=UCkRfArvrzheW2E7b6SVT7vQ`); `parse_feed(xml_text: str) -> list[dict]` (keys `title, link, published, summary`, handles RSS and Atom, returns `[]` on malformed XML); `is_relevant(item: dict) -> bool` (keyword filter: security, scam, phishing, hijack, account, passkey, 2-step, impersonation, spam, policy, monetization, copyright, AI-generated, safety, children, verification); `fetch_items(days: int = 10) -> list[dict]`; `summarize(items: list[dict]) -> dict` (`{"items": [{"title","what_changed","why_it_matters","steps","link"}], "video_ideas": [str]}`, built only from the given text); `run(now: datetime | None = None) -> Path` writing `data/newswatch/YYYY-Www.json` and appending proposals to `news_topics.json`.
- `doc_script(topic, facts: str | None = None)`: when `facts` is given the prompts state "use ONLY the facts in SOURCES".

- [ ] **Step 1: Write failing tests:** `test_parse_rss`, `test_parse_atom`, `test_parse_malformed_returns_empty`, `test_is_relevant_filters`, `test_run_survives_empty_feeds` (monkeypatch `fetch_items` → `[]`; file written with empty `items`), `test_summarize_uses_only_given_text` (monkeypatch `scriptgen._chat`; assert the prompt contains the item text and the word ONLY).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement with `urllib.request` (User-Agent set, 20 s timeout, per-feed try/except) and `xml.etree.ElementTree`.
- [ ] **Step 4:** Run; expect PASS. Then run `.venv/bin/python run.py newswatch` for real and open the digest file.

### Task 6: Dashboard Autopilot page

**Files:**
- Modify: `dashboard.py` (endpoints), `dashboard.html` (page, review report panel, schedule display)
- Test: manual check in the browser plus `tests/test_dashboard_api.py` for pure helpers

**Interfaces:**
- Consumes: `autopilot.load_config/save_config/status`, `scheduler.fmt_local`.
- Produces: `GET /api/autopilot` → `{"config", "status", "videos": [{"slug","title","verdict","publish_at","publish_at_local_bd","publish_at_local_us","hold","checks"}], "news": {"week","items","video_ideas"} | null}`; `POST /api/autopilot/config` (validated: `uploads_per_day` 1 to 5, `review_window_hours` 6 to 168); `POST /api/autopilot/hold {slug, hold: bool}`; job names `review`, `autopilot`, `newswatch` added to `ALLOWED_JOBS`; `POST /api/news/queue {topic}` adds a proposal to the topic queue with `source: news`.

- [ ] **Step 1:** Test `validate_autopilot_config(raw: dict) -> dict` rejects out-of-range values and unknown keys.
- [ ] **Step 2:** Run; expect FAIL; implement; expect PASS.
- [ ] **Step 3:** Build the page following the existing design tokens: master switch with plain-language state, settings form, "Needs you" list (`needs_human`, `fail`), "Scheduled" list with Hold/Release buttons and times in Bangladesh and US Eastern, reviewer report (check list with block/warn marks) on the video page, "YouTube watch" digest with a "Make a video about this" button. Empty, loading and error states for each.
- [ ] **Step 4:** Verify in the browser at `http://studio.localhost:8913/#autopilot` (desktop and 673 px wide, both themes, zero console errors).

### Task 7: Timers and docs

**Files:**
- Create: `scripts/install-timers.sh`, `scripts/story-autopilot.service`, `scripts/story-autopilot.timer`, `scripts/story-newswatch.service`, `scripts/story-newswatch.timer`
- Modify: `README.md`

**Interfaces:** timers call `.venv/bin/python run.py autopilot tick` every 30 min and `.venv/bin/python run.py newswatch` Mondays 09:00 local; the install script copies units to `~/.config/systemd/user`, runs `daemon-reload` and `enable --now`; an `--uninstall` flag removes them.

- [ ] **Step 1:** Write the units and script; run `systemd-analyze --user verify` on them.
- [ ] **Step 2:** Document autopilot, reviewer, newswatch and the install command in `README.md`.
- [ ] **Step 3:** Run the full suite `.venv/bin/python -m pytest -q`; expect all PASS.
