# Growth Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.

**Goal:** A daily, hands-off research agent that studies our channel and competitors, proposes or applies growth strategies, and reports everything on a dashboard Growth tab.

**Architecture:** Small focused modules under the repo root: `agentlog` (feed and notifications), `editprofile` (edit settings the renderer reads), `discover` (find competitor channels), `growth` (own-channel snapshot and numbers), `strategy` (store, validate, apply), `agent` (daily orchestrator with the mode switch). A systemd user timer runs `run.py agent`. The dashboard gets a Growth tab backed by `/api/agent*`.

**Tech Stack:** Python 3.14, google-api-python-client (installed), existing `llm.chat` router, ffmpeg, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-19-growth-agent-design.md`

## Global Constraints

- Research reads public metadata only through the official YouTube Data API; no downloading of other creators' videos, scripts or thumbnails.
- Modes are exactly `off`, `handoff` (default), `automatic`. `handoff` applies nothing. `automatic` applies only kinds `edit` and `topic`.
- The agent never writes `autopilot.json`, never uploads, never changes `MAX_UPLOADS_PER_DAY`.
- At most 6 `search.list` calls per run; discovered list capped at 15; one run per UTC day unless `force=True`.
- Every external step (API, model, notify) fails soft: record an `error` event and continue.
- Dashboard text: plain words, no em-dashes. No git repo: "commit" = run `.venv/bin/python -m pytest -q`.

## Review Focus

- YouTube token missing or quota exhausted: `agent.run` returns a result with an error event and does not raise.
- Own channel has zero videos or hidden subscriber count: `growth.analyze` returns zeros, strategies still generate from competitors.
- Model returns malformed or hostile strategies (unknown kind, huge numbers, empty text): dropped by `strategy.validate`.
- Discovery returns our own channel, a hand-picked reference or an already known channel: excluded.
- `notify-send` missing or failing: no exception, feed still written.
- Two runs at once (timer plus dashboard button): the second returns `{"skipped": "locked"}`.
- `automatic` must never apply `title`, `format`, `schedule` or `thumbnail` kinds.

---

### Task 1: Activity feed and notifications (`agentlog.py`)

**Files:** Create `agentlog.py`; Test `tests/test_agentlog.py`

**Interfaces:**
- Produces: `FILE = config.ROOT/"data"/"agent"/"events.jsonl"`; `event(kind: str, title: str, detail: str = "", notify: bool = False, now: dt.datetime | None = None) -> dict` (kinds: `info`, `found`, `strategy`, `applied`, `error`; returns `{at, kind, title, detail, read: False}`); `recent(n: int = 50) -> list[dict]` newest first; `unread() -> int`; `mark_read() -> None`.

- [ ] **Step 1: Failing tests** (monkeypatch `agentlog.FILE` to tmp): `test_event_roundtrip_newest_first`, `test_unread_and_mark_read`, `test_notify_failure_is_silent` (monkeypatch `subprocess.run` to raise `FileNotFoundError`; `event(..., notify=True)` still returns and writes), `test_notify_called_only_when_requested`.
- [ ] **Step 2:** run `pytest tests/test_agentlog.py -q`, expect FAIL. **Step 3:** implement; notification is `subprocess.run(["notify-send", "-a", "Story Studio", title, detail], timeout=5)` inside try/except. **Step 4:** run, expect PASS.

### Task 2: Edit profile used by the renderer (`editprofile.py`, `render.py`, `tts.py`, `run.py`)

**Files:** Create `editprofile.py`; Modify `render.py` (`render(..., loudness: float | None = None)`), `tts.py` (`narrate(lines, work, pause: float = 0.12)`), `run.py` (pass both at the 2 render sites and 2 narrate sites); Test `tests/test_editprofile.py`

**Interfaces:**
- Produces: `FILE = config.ROOT/"edit_profile.json"`; `DEFAULTS = {"target_lufs": -16.0, "sentence_pause_ms": 120}`; `LIMITS = {"target_lufs": (-20.0, -12.0), "sentence_pause_ms": (100, 900)}`; `validate(raw: dict) -> dict` (keeps only known keys, coerces numbers, drops out-of-range or non-numeric values); `load() -> dict` (defaults overlaid by the file); `update(changes: dict) -> dict` (validate, merge, write, return profile).
- Consumes: nothing.

- [ ] **Step 1: Failing tests:** `test_defaults_when_no_file`, `test_validate_drops_unknown_and_out_of_range` (`{"target_lufs": -5, "evil": 1, "sentence_pause_ms": "300"}` → `{"sentence_pause_ms": 300}`), `test_update_persists`, `test_render_adds_loudnorm_filter` (monkeypatch `render._ff` to capture args; with `loudness=-16` the final call contains `loudnorm=I=-16`; without it, no `loudnorm`), `test_narrate_uses_pause` (monkeypatch `_synth_line` and `subprocess.run`; durations include the given pause).
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement. In `render.render`, with music append `,loudnorm=...` to the `amix` chain output label; without music add `-af loudnorm=I={L}:TP=-1.5:LRA=11`. In `tts.narrate` replace the three `0.12` uses by `pause`. In `run.py` read `editprofile.load()` and pass `loudness=p["target_lufs"]`, `pause=p["sentence_pause_ms"]/1000`. **Step 4:** run whole suite, expect all PASS (existing tests unchanged).

### Task 3: Competitor discovery (`discover.py`)

**Files:** Create `discover.py`; Test `tests/test_discover.py`

**Interfaces:**
- Produces: `FILE = config.ROOT/"data"/"agent"/"discovered.json"`; `MAX_FOUND = 15`; `SEEDS` (list of 6 niche search strings); `score(c: dict) -> float` (`views / max(videos, 1)`, 0 if `subscribers < 10000`); `search(yt, seeds: list[str], exclude: set[str]) -> list[dict]` (each `{id, title, subscribers, views, videos, score, found}`; at most `len(seeds[:6])` `search.list` calls with `type="channel"`, `regionCode="US"`, `relevanceLanguage="en"`; excludes ids in `exclude`); `fit_niche(candidates: list[dict], chat) -> list[dict]` (one model call; on failure returns candidates with `"unchecked": True`); `load() -> list[dict]`; `run(yt, own_id: str, refs: list[str], chat=None) -> list[dict]` (merges, keeps top `MAX_FOUND` by score, logs `found` events via `agentlog.event`, returns only the newly added).
- Consumes: `agentlog.event`, `scriptgen._chat`.

- [ ] **Step 1: Failing tests** with a fake `yt` object: `test_score_zero_below_10k_subs`, `test_search_excludes_known_ids`, `test_search_caps_calls_at_six`, `test_run_caps_at_15_keeping_best`, `test_fit_niche_failure_marks_unchecked`, `test_run_never_returns_own_channel_or_refs`.
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement (`channels().list(part="statistics,snippet", id=",".join(ids))` for the numbers). **Step 4:** run, expect PASS.

### Task 4: Own-channel numbers (`growth.py`)

**Files:** Create `growth.py`; Test `tests/test_growth.py`

**Interfaces:**
- Produces: `DIR = config.ROOT/"data"/"agent"/"own"`; `snapshot(yt, now=None) -> dict` (`{date, channel_id, title, subscribers, views, videos, recent: [{id, title, views, seconds, published}]}` from `channels().list(mine=True)` and its uploads playlist, 50 videos; written to `DIR/YYYY-MM-DD.json`); `analyze(snaps: list[dict], study: list[dict]) -> dict` with keys `subs`, `subs_delta_7d`, `views_delta_7d`, `uploads_per_week`, `shorts_median_views`, `long_median_views`, `best` (top 3 recent by views), `competitor_median_views`, `gap_ratio` (our median / competitor median, 0 if unknown). Pure, no network.
- Consumes: `trendwatch.iso_seconds`, `trendwatch.summarize_videos`.

- [ ] **Step 1: Failing tests:** `test_analyze_deltas_over_seven_days`, `test_analyze_empty_channel_is_zeros`, `test_analyze_splits_shorts_and_long` (60 seconds is a Short), `test_gap_ratio_unknown_is_zero`, `test_snapshot_writes_file_with_fake_yt`.
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement. **Step 4:** run, expect PASS.

### Task 5: Strategy store and apply (`strategy.py`)

**Files:** Create `strategy.py`; Test `tests/test_strategy.py`

**Interfaces:**
- Produces: `FILE = config.ROOT/"data"/"agent"/"strategies.json"`; `KINDS = {"topic","title","format","edit","schedule","thumbnail"}`; `AUTO_KINDS = {"edit","topic"}`; `validate(raw: dict) -> dict | None` (needs known `kind`, `text` 8 to 300 chars, `why` and `evidence` list of at most 5 strings; for `edit` a `profile` that survives `editprofile.validate` non-empty; returns normalized `{id, kind, text, why, evidence, profile?, status: "proposed", auto_ok, created}` where `id` is `sha1(kind+text)[:10]`); `load() -> list[dict]`; `add(items: list[dict]) -> list[dict]` (validate, skip ids already present, append, return those added); `set_status(sid: str, status: str) -> dict` (`proposed|applied|dismissed`); `apply(sid: str) -> dict` (`edit` calls `editprofile.update`; `topic` appends `text` to `config.TOPICS_FILE` if not already there; other kinds raise `ValueError("advice only")`; sets `applied` and `applied_at`); `generate(analysis: dict, study: list[dict], chat=None) -> list[dict]` (one model call, JSON `{"strategies": [...]}`, items validated).
- Consumes: `editprofile`, `scriptgen._chat`, `config.TOPICS_FILE`.

- [ ] **Step 1: Failing tests:** `test_validate_rejects_unknown_kind_and_short_text`, `test_validate_edit_needs_valid_profile`, `test_add_dedupes_by_id`, `test_apply_edit_updates_profile`, `test_apply_topic_appends_once`, `test_apply_advice_kind_raises`, `test_generate_drops_malformed` (fake `chat` returns one good and two bad items).
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement. The model prompt includes the niche, the numbers from `analysis`, up to 15 competitor titles with views, the rule "only suggest what the numbers support, original wording, no copying", and the allowed kinds with the `edit` profile keys. **Step 4:** run, expect PASS.

### Task 6: Orchestrator, CLI and timer (`agent.py`, `run.py`, `scripts/`)

**Files:** Create `agent.py`, `scripts/story-agent.service`, `scripts/story-agent.timer`; Modify `run.py` (command `agent`), `scripts/install-timers.sh` (add the two units); Test `tests/test_agent.py`

**Interfaces:**
- Produces: `CONFIG_FILE = config.ROOT/"agent.json"`; `MODES = ("off","handoff","automatic")`; `load_config() -> dict` (`{"mode": "handoff", "study_per_run": 4}`); `save_config(cfg) -> dict` (rejects unknown mode with `ValueError`); `REPORTS = config.ROOT/"data"/"agent"/"reports"`; `run(now=None, yt=None, chat=None, force=False) -> dict` returning `{"skipped": reason}` for `off`, `already ran today`, `locked`, otherwise `{"mode", "new_channels", "studied", "strategies_added", "applied", "errors"}` and writing `REPORTS/YYYY-MM-DD.json`; `latest_report() -> dict | None`.
- Consumes: `discover.run`, `growth.snapshot`, `growth.analyze`, `strategy.generate`, `strategy.add`, `strategy.apply`, `channelwatch.load_refs`, `channelwatch.breakdown`, `agentlog.event`.
- Flow: lock (`fcntl` on `config.ROOT/"agent.lock"`) → snapshot → discover → study (manual refs plus top `study_per_run` discovered, via `channelwatch.breakdown`) → analyze → generate → add → if `automatic`, `apply` each added item whose kind is in `AUTO_KINDS` → events (`notify=True` for new strategies, applied items and errors) → write report. Each step in its own try/except that records an `error` event.

- [ ] **Step 1: Failing tests** (fake `yt` and `chat`, tmp paths): `test_off_does_nothing`, `test_handoff_adds_strategies_applies_none`, `test_automatic_applies_only_edit_and_topic`, `test_second_run_same_day_skipped`, `test_force_runs_again`, `test_api_failure_recorded_not_raised`, `test_lock_held_returns_locked`, `test_save_config_rejects_bad_mode`.
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement; `run.py agent [force]` prints one line summary; service `ExecStart=__ROOT__/.venv/bin/python run.py agent`, timer `OnCalendar=*-*-* 06:30:00`, `Persistent=true`. **Step 4:** run whole suite, expect PASS; `bash -n scripts/install-timers.sh`.

### Task 7: Dashboard Growth tab (`dashboard.py`, `dashboard.html`)

**Files:** Modify `dashboard.py` (GET `/api/agent`; POST `/api/agent/config`, `/api/agent/strategy`, `/api/agent/read`; `"agent"` in `ALLOWED_JOBS`), `dashboard.html` (nav item `["growth","Growth","chart-line-up"]` with unread badge; `growth(m)` view); Test `tests/test_dashboard_agent.py`

**Interfaces:**
- Produces: `agent_view() -> dict` (`config`, `events` (recent 50), `unread`, `strategies`, `report` (latest), `discovered`, `own` (latest snapshot or None), `timer_installed`); POST bodies `{mode}`, `{id, action: "apply"|"dismiss"|"restore"}`, `{}`.
- Consumes: Tasks 1 to 6.
- View, top to bottom: a **mode switch** (Off, Hand-off, Automatic) with one plain sentence under each; **Run now** button (job `agent` with arg `force`); **What I found** (strategy cards: kind chip, plain text, "Why" with evidence, buttons Apply and Dismiss, "advice only" note for non-applicable kinds); **Our channel** numbers; **Competitors** (your 5 plus discovered, with views per video); **Activity** feed with timestamps and unread dots. Opening the tab calls `/api/agent/read`.

- [ ] **Step 1: Failing tests** (use the existing `tests/test_dashboard_api.py` pattern): `test_agent_view_shape`, `test_config_rejects_unknown_mode`, `test_strategy_apply_edit_changes_profile`, `test_strategy_apply_advice_kind_returns_error`, `test_read_marks_events_read`.
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement route code and the HTML view following the existing `autopilot(m)` view style. **Step 4:** run suite, expect PASS; open the dashboard with the browser tools and check the tab at desktop and phone width.

### Task 8: Docs and final check

**Files:** Modify `README.md` (Growth agent section: two modes, what Automatic may change, how to read the feed, how to install the timer); Create `docs/superpowers/ledger-growth-agent.md`.

- [ ] Run `.venv/bin/python -m pytest -q` and `.venv/bin/python run.py agent force` against the real channel with the owner's token; report the feed output and any quota or permission error plainly.
